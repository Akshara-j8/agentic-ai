"""
runner.py

Executes a user-written prompt on a sample input by calling the OpenRouter
API (or any OpenAI-compatible endpoint).  Returns the raw model output as a
string, which the examiner will later analyse.
"""

import json
import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration  (overridable via environment variables)
# ---------------------------------------------------------------------------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
)
MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")  # cheap & fast
TIMEOUT_SECONDS = int(os.getenv("OPENROUTER_TIMEOUT", "60"))
MAX_RETRIES = 2


def run_prompt(user_prompt: str, sample_input: str) -> dict[str, Any]:
    """Send *user_prompt* + *sample_input* to the model and return the result.

    The user's prompt and the sample input are combined by the caller (app.py),
    so this function simply sends the full message to the LLM.

    Returns a dict with keys:
        "ok"          — bool, whether the call succeeded
        "output"      — str, the model's response text (empty on failure)
        "error"       — str, error detail if ``ok`` is ``False``
        "model"       — str, the model identifier used
    """
    if not OPENROUTER_API_KEY:
        return {
            "ok": False,
            "output": "",
            "error": "OPENROUTER_API_KEY is not set in .env",
            "model": MODEL,
        }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": user_prompt,
            }
        ],
        "temperature": 0.3,  # low temperature for more deterministic grading
        "max_tokens": 2048,
    }

    last_error = ""
    for attempt in range(1, MAX_RETRIES + 2):  # attempt = 1, 2, 3
        try:
            resp = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return {
                "ok": True,
                "output": content.strip(),
                "error": "",
                "model": MODEL,
            }

        except requests.exceptions.Timeout:
            last_error = f"Request timed out after {TIMEOUT_SECONDS}s"
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            body = ""
            try:
                body = e.response.text[:300] if e.response is not None else ""
            except Exception:
                pass
            last_error = f"HTTP {status}: {body}"
            # Non-retryable client errors
            if 400 <= status < 500:
                break
        except requests.exceptions.RequestException as e:
            last_error = f"Request failed: {e}"
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            last_error = f"Unexpected API response format: {e}"

        # If we get here and still have retries left, continue
        if attempt <= MAX_RETRIES:
            import time

            time.sleep(1.0)

    return {
        "ok": False,
        "output": "",
        "error": last_error,
        "model": MODEL,
    }