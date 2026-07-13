"""
TechVest Recruitment Agent — LLM Client
Wraps OpenRouter API via LangChain ChatOpenAI with:
- Retry logic (tenacity)
- Fallback model support
- Token usage tracking
- Structured output parsing
- Streaming support
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Generator, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

class LLMClient:
    """
    Enterprise LLM client backed by OpenRouter API.

    Features:
    - Primary + fallback model support
    - Automatic retry with exponential backoff
    - Token usage tracking
    - JSON-structured response parsing
    - Streaming support for trajectory display
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        self._settings = get_settings()
        self.model = model or self._settings.default_model
        self.temperature = temperature if temperature is not None else self._settings.default_temperature
        self.max_tokens = max_tokens or self._settings.default_max_tokens

        # Token / call statistics
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_calls: int = 0
        self._total_errors: int = 0
        self._start_time: float = time.time()

        # Build LLM instances
        self._primary_llm = self._build_llm(self.model)
        self._fallback_llm = self._build_llm(self._settings.fallback_model)

    # ------------------------------------------------------------------
    # Builder
    # ------------------------------------------------------------------

    def _build_llm(self, model: str) -> ChatOpenAI:
        """Construct a ChatOpenAI instance pointed at OpenRouter."""
        if not self._settings.openrouter_api_key:
            logger.warning("OPENROUTER_API_KEY not set — LLM calls will fail.")

        return ChatOpenAI(
            model=model,
            openai_api_key=self._settings.openrouter_api_key,
            openai_api_base=self._settings.openrouter_base_url,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            default_headers=self._settings.openrouter_headers,
            request_timeout=60,
            max_retries=0,  # We handle retries ourselves via tenacity
        )

    # ------------------------------------------------------------------
    # Core invoke (with retry + fallback)
    # ------------------------------------------------------------------

    def invoke(
        self,
        messages: "list[BaseMessage] | str",
        *,
        parse_json: bool = False,
        system_prompt: Optional[str] = None,
    ) -> "dict[str, Any] | str":
        """
        Invoke the LLM with a list of messages or a plain string prompt.

        Args:
            messages:      LangChain BaseMessage list OR a plain string prompt
            parse_json:    If True, parse response as JSON
            system_prompt: Optional system message to prepend

        Returns:
            Parsed JSON dict or raw string depending on parse_json flag.
        """
        # Accept plain string prompts for convenience
        if isinstance(messages, str):
            return self.chat(messages, system_prompt=system_prompt, parse_json=parse_json)

        full_messages: list[BaseMessage] = []
        if system_prompt:
            full_messages.append(SystemMessage(content=system_prompt))
        full_messages.extend(messages)

        start = time.time()
        try:
            response = self._invoke_with_retry(full_messages)
        except Exception as exc:
            logger.error(f"Primary model failed, trying fallback: {exc}")
            try:
                response = self._invoke_fallback(full_messages)
            except Exception as fallback_exc:
                self._total_errors += 1
                logger.error(f"Fallback also failed: {fallback_exc}")
                raise RuntimeError(
                    f"Both primary ({self.model}) and fallback models failed. "
                    f"Last error: {fallback_exc}"
                ) from fallback_exc

        elapsed = time.time() - start
        self._total_calls += 1

        # Track token usage if available
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            self._total_prompt_tokens += response.usage_metadata.get("input_tokens", 0)
            self._total_completion_tokens += response.usage_metadata.get("output_tokens", 0)

        content = response.content if isinstance(response, AIMessage) else str(response)

        if parse_json:
            return self._parse_json_safe(content)

        return content

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception)),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _invoke_with_retry(self, messages: list[BaseMessage]) -> AIMessage:
        """Invoke primary LLM with tenacity retry logic."""
        return self._primary_llm.invoke(messages)

    def _invoke_fallback(self, messages: list[BaseMessage]) -> AIMessage:
        """Invoke fallback LLM (no retry — single attempt)."""
        return self._fallback_llm.invoke(messages)

    # ------------------------------------------------------------------
    # Convenience wrappers
    # ------------------------------------------------------------------

    def chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        *,
        parse_json: bool = False,
    ) -> dict[str, Any] | str:
        """Simple single-turn chat wrapper."""
        messages = [HumanMessage(content=user_message)]
        return self.invoke(messages, parse_json=parse_json, system_prompt=system_prompt)

    def structured_invoke(
        self,
        prompt_template: str,
        variables: dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Format a prompt template, invoke LLM, and return parsed JSON.

        Args:
            prompt_template: String template with {variable} placeholders
            variables:       Dict of template variables
            system_prompt:   Optional system message

        Returns:
            Parsed JSON dict (falls back to {'raw': content} on parse failure)
        """
        formatted = prompt_template.format(**variables)
        return self.chat(formatted, system_prompt=system_prompt, parse_json=True)

    def stream(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """
        Stream LLM response token by token.

        Yields:
            Individual string chunks as they arrive.
        """
        messages: list[BaseMessage] = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=user_message))

        try:
            for chunk in self._primary_llm.stream(messages):
                if hasattr(chunk, "content"):
                    yield chunk.content
        except Exception as exc:
            logger.error(f"Streaming failed: {exc}")
            # Fall back to non-streaming
            result = self.chat(user_message, system_prompt=system_prompt)
            yield str(result)

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    def update_model(self, model: str) -> None:
        """Hot-swap the primary LLM model."""
        self.model = model
        self._primary_llm = self._build_llm(model)
        logger.info(f"LLM model updated to: {model}")

    def update_temperature(self, temperature: float) -> None:
        """Update sampling temperature and rebuild LLM."""
        self.temperature = temperature
        self._primary_llm = self._build_llm(self.model)
        self._fallback_llm = self._build_llm(self._settings.fallback_model)

    def update_max_tokens(self, max_tokens: int) -> None:
        """Update max tokens and rebuild LLM."""
        self.max_tokens = max_tokens
        self._primary_llm = self._build_llm(self.model)
        self._fallback_llm = self._build_llm(self._settings.fallback_model)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    @property
    def usage_stats(self) -> dict[str, Any]:
        """Return token usage and call statistics."""
        elapsed = time.time() - self._start_time
        return {
            "total_calls": self._total_calls,
            "total_errors": self._total_errors,
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
            "elapsed_seconds": round(elapsed, 2),
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def reset_stats(self) -> None:
        """Reset usage statistics."""
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_calls = 0
        self._total_errors = 0
        self._start_time = time.time()

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json_safe(content: str) -> dict[str, Any]:
        """
        Robustly parse JSON from LLM output.
        Handles markdown code fences and stray text.
        """
        # Strip markdown code fences
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last fence lines
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        # Find first { and last }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            text = text[start:end]

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning(f"JSON parse failed, returning raw: {exc}")
            return {"raw": content, "parse_error": str(exc)}

    def __repr__(self) -> str:
        return (
            f"LLMClient(model={self.model!r}, "
            f"temperature={self.temperature}, "
            f"max_tokens={self.max_tokens})"
        )


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_client_instance: Optional[LLMClient] = None


def get_llm_client(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    *,
    force_new: bool = False,
) -> LLMClient:
    """
    Return a singleton LLMClient, creating one if necessary.

    Args:
        model:       Override model identifier
        temperature: Override sampling temperature
        max_tokens:  Override max tokens
        force_new:   Force creation of a new instance

    Returns:
        LLMClient instance
    """
    global _client_instance

    if force_new or _client_instance is None:
        _client_instance = LLMClient(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif model or temperature is not None or max_tokens:
        # Update settings on existing instance
        if model:
            _client_instance.update_model(model)
        if temperature is not None:
            _client_instance.update_temperature(temperature)
        if max_tokens:
            _client_instance.update_max_tokens(max_tokens)

    return _client_instance
