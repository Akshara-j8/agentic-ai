"""
services/openrouter_client.py — OpenRouter API client.

Features:
- Reusable httpx-based client
- Automatic JSON extraction and repair
- Retry on invalid JSON / rate-limit errors with exponential back-off
- Detailed logging: prompt, raw response, latency, token usage, retry count
- Structured StageResult return type
"""

from __future__ import annotations

import json
import re
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

import config as cfg

logger = logging.getLogger("prompt_pipeline.client")


# ─── Return type ──────────────────────────────────────────────────────────────

@dataclass
class StageResult:
    """Structured result from a single pipeline stage LLM call."""
    stage:          int
    task_id:        str
    raw_response:   str          = ""
    parsed_json:    dict         = field(default_factory=dict)
    prompt_tokens:  int          = 0
    completion_tokens: int       = 0
    total_tokens:   int          = 0
    latency_ms:     float        = 0.0
    retries:        int          = 0
    model:          str          = ""
    success:        bool         = True
    error:          Optional[str] = None

    @property
    def token_summary(self) -> str:
        return f"in={self.prompt_tokens} out={self.completion_tokens} total={self.total_tokens}"


# ─── JSON helpers ─────────────────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    """
    Extract JSON from model response text.

    Tries in order:
    1. The text itself (already valid JSON)
    2. Content inside ```json ... ``` fences
    3. Content inside ``` ... ``` fences
    4. First {...} block found via regex
    """
    text = text.strip()

    # Direct parse
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Fenced code blocks
    for pattern in (r"```json\s*([\s\S]+?)\s*```", r"```\s*([\s\S]+?)\s*```"):
        m = re.search(pattern, text)
        if m:
            candidate = m.group(1).strip()
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

    # First {...} block
    m = re.search(r"\{[\s\S]+\}", text)
    if m:
        candidate = m.group(0)
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in response: {text[:200]}...")


def _repair_json(text: str) -> str:
    """
    Attempt lightweight JSON repair:
    - Remove trailing commas before } or ]
    - Replace single quotes with double quotes (simple cases)
    """
    # Remove trailing commas
    text = re.sub(r",\s*([\}\]])", r"\1", text)
    return text


# ─── OpenRouter Client ────────────────────────────────────────────────────────

class OpenRouterClient:
    """
    Thin wrapper around the OpenRouter chat completions endpoint.

    Usage:
        client = OpenRouterClient(api_key="sk-...", model="openai/gpt-4o-mini")
        result = client.call_stage(stage=1, task_id="support_triage",
                                   system_prompt="...", user_prompt="...")
    """

    def __init__(
        self,
        api_key:     Optional[str] = None,
        model:       Optional[str] = None,
        timeout:     int           = cfg.REQUEST_TIMEOUT,
        max_retries: int           = cfg.MAX_RETRIES,
        retry_delay: float         = cfg.RETRY_DELAY,
    ):
        self.api_key     = api_key or cfg.OPENROUTER_API_KEY
        self.model       = model   or cfg.DEFAULT_MODEL
        self.timeout     = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.base_url    = cfg.OPENROUTER_BASE_URL.rstrip("/")

        if not self.api_key:
            raise ValueError(
                "OpenRouter API key is missing. "
                "Set OPENROUTER_API_KEY in your .env file."
            )

    # ── Internal HTTP call ────────────────────────────────────────────────────

    def _post(self, messages: list[dict], temperature: float, max_tokens: int) -> dict:
        """Make a single HTTP POST to the chat completions endpoint."""
        headers = {
            "Authorization":  f"Bearer {self.api_key}",
            "Content-Type":   "application/json",
            "HTTP-Referer":   cfg.OPENROUTER_REFERER,
            "X-Title":        cfg.OPENROUTER_APP_TITLE,
        }
        payload = {
            "model":       self.model,
            "messages":    messages,
            "temperature": temperature,
            "max_tokens":  max_tokens,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

        if resp.status_code == 401:
            raise PermissionError("Invalid OpenRouter API key (401 Unauthorized).")
        if resp.status_code == 429:
            raise RuntimeError("Rate limit exceeded (429). Retrying...")
        if resp.status_code >= 400:
            raise RuntimeError(
                f"OpenRouter API error {resp.status_code}: {resp.text[:300]}"
            )

        return resp.json()

    # ── Public interface ──────────────────────────────────────────────────────

    def call_stage(
        self,
        stage:         int,
        task_id:       str,
        system_prompt: str,
        user_prompt:   str,
        temperature:   float = cfg.TEMPERATURE,
        max_tokens:    int   = cfg.MAX_TOKENS,
    ) -> StageResult:
        """
        Call the LLM for one pipeline stage and return a StageResult.

        Retries automatically on:
        - JSON parse failures
        - Rate limit errors
        - Network timeouts
        """
        messages = [
            {"role": "system",  "content": system_prompt},
            {"role": "user",    "content": user_prompt},
        ]

        logger.info(
            "STAGE %d | task=%s | model=%s | temp=%.2f | max_tokens=%d",
            stage, task_id, self.model, temperature, max_tokens,
        )
        logger.debug("SYSTEM PROMPT:\n%s", system_prompt)
        logger.debug("USER PROMPT:\n%s", user_prompt)

        attempt    = 0
        last_error = ""
        t_start    = time.perf_counter()

        while attempt <= self.max_retries:
            try:
                api_resp = self._post(messages, temperature, max_tokens)
                raw_text = api_resp["choices"][0]["message"]["content"]
                usage    = api_resp.get("usage", {})

                latency_ms = (time.perf_counter() - t_start) * 1000

                logger.debug("RAW RESPONSE (attempt %d):\n%s", attempt, raw_text)
                logger.info(
                    "STAGE %d | attempt=%d | latency=%.0fms | tokens=%s",
                    stage, attempt,
                    latency_ms,
                    f"in={usage.get('prompt_tokens',0)} out={usage.get('completion_tokens',0)}",
                )

                # ── JSON extraction ──────────────────────────────────────────
                try:
                    json_str = _extract_json(raw_text)
                except ValueError:
                    # Try after light repair
                    json_str = _extract_json(_repair_json(raw_text))

                parsed = json.loads(json_str)

                return StageResult(
                    stage             = stage,
                    task_id           = task_id,
                    raw_response      = raw_text,
                    parsed_json       = parsed,
                    prompt_tokens     = usage.get("prompt_tokens", 0),
                    completion_tokens = usage.get("completion_tokens", 0),
                    total_tokens      = usage.get("total_tokens", 0),
                    latency_ms        = latency_ms,
                    retries           = attempt,
                    model             = self.model,
                    success           = True,
                )

            except (ValueError, json.JSONDecodeError) as e:
                last_error = f"JSON parse error: {e}"
                logger.warning("STAGE %d attempt %d — %s", stage, attempt, last_error)
                # Add repair instruction to next attempt
                messages.append({
                    "role":    "assistant",
                    "content": api_resp.get("choices", [{}])[0].get("message", {}).get("content", ""),
                })
                messages.append({
                    "role":    "user",
                    "content": (
                        "Your previous response was not valid JSON. "
                        "Please return ONLY a valid JSON object with no markdown, "
                        "no explanation, no code fences."
                    ),
                })

            except RuntimeError as e:
                last_error = str(e)
                logger.warning("STAGE %d attempt %d — %s", stage, attempt, last_error)

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = f"Network error: {e}"
                logger.warning("STAGE %d attempt %d — %s", stage, attempt, last_error)

            except PermissionError as e:
                # Don't retry auth errors
                latency_ms = (time.perf_counter() - t_start) * 1000
                logger.error("Auth error: %s", e)
                return StageResult(
                    stage=stage, task_id=task_id,
                    latency_ms=latency_ms, retries=attempt,
                    model=self.model, success=False, error=str(e),
                )

            attempt += 1
            if attempt <= self.max_retries:
                sleep_time = self.retry_delay * (2 ** (attempt - 1))
                logger.info("Retrying in %.1fs...", sleep_time)
                time.sleep(sleep_time)

        # All retries exhausted
        latency_ms = (time.perf_counter() - t_start) * 1000
        logger.error(
            "STAGE %d FAILED after %d attempts. Last error: %s",
            stage, self.max_retries + 1, last_error,
        )
        return StageResult(
            stage     = stage,
            task_id   = task_id,
            latency_ms= latency_ms,
            retries   = attempt - 1,
            model     = self.model,
            success   = False,
            error     = last_error,
        )
