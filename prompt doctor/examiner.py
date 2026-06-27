"""
examiner.py

The AI examiner that evaluates a student's prompt against the principles
required for the current level.

Key design decisions:
------------------------
1. **Examiner prompt is a meta-prompt** — it instructs the LLM to act as a
   strict prompt-engineering teacher.  The student's prompt is embedded
   inside this meta-prompt so the LLM judges the prompt *itself*, not the
   output it produces.

2. **Per-level principle filtering** — only the principles relevant to the
   current level are included in the examiner prompt.  This prevents the
   examiner from penalising a student for something they haven't learned yet.

3. **Structured JSON output** — the examiner is forced to return valid JSON
   matching the schema.  If parsing fails, we fall back to a safe default
   that fails all principles gracefully.

4. **No rewriting** — the meta-prompt explicitly forbids the examiner from
   improving or rewriting the student's prompt.  It must only quote weaknesses
   and ask guiding questions.

5. **One question per failed principle** — the examiner must ask exactly one
   guiding question for every principle that did not pass.
"""

import json
import logging
import re
from typing import Any

from levels import get_criteria, get_principles_for_level

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default fallback (used when the examiner call itself fails)
# ---------------------------------------------------------------------------
_FALLBACK_RESULT: dict[str, Any] = {
    "level": 0,
    "principles": [],
    "ran_ok": False,
    "verdict": "revise",
}


def _build_examiner_system_prompt(level_id: int) -> str:
    """Build the meta-prompt that tells the LLM how to examine prompts.

    Only the principles for *level_id* are included so the examiner never
    judges criteria the student hasn't been taught yet.
    """
    principles = get_principles_for_level(level_id)

    criteria_section = "\n\n".join(
        f"### {p}\n{get_criteria(p)}" for p in principles
    )

    return f"""You are a fair prompt-engineering examiner. Your job is to evaluate a student's prompt against a specific set of principles.

## Principles to evaluate (Level {level_id})

{criteria_section}

## Rules

1. Judge ONLY the principles listed above. Ignore everything else.
2. NEVER rewrite or improve the student's prompt. You are an examiner, not a tutor.
3. If a principle **passes**, set `"pass": true`, `"weakness": ""`, and `"question": ""`.
4. If a principle **fails**, quote the exact weak phrase or say what is missing, and ask exactly one short guiding question.
5. Return ONLY valid JSON inside a ```json code block with no other text.

## Output schema

```json
{{
  "level": {level_id},
  "principles": [
    {{
      "name": "{principles[0]}",
      "pass": true,
      "weakness": "",
      "question": ""
    }}
  ],
  "ran_ok": true,
  "verdict": "pass"
}}
```

Use the EXACT principle names above as the `"name"` field. For example, if the principle is `"clear_instruction"`, use `"clear_instruction"` — not `"clear instruction"`.

The `verdict` must be `"pass"` only when **every** principle has `"pass": true`. Otherwise use `"revise"`.
"""


def _build_examiner_user_message(
    user_prompt: str, sample_input: str, model_output: str
) -> str:
    """Build the user message that contains the student's work for the examiner."""
    return f"""Here is the student's submission.  Evaluate it against the principles
you were given above.

## Student's prompt

```
{user_prompt}
```

## Sample input the prompt was run on

```
{sample_input}
```

## Model output produced by the prompt

```
{model_output}
```

Now produce your evaluation as JSON following the schema exactly."""


def _parse_examiner_response(
    raw: str, level_id: int, expected_principles: list[str]
) -> dict[str, Any]:
    """Parse the examiner's JSON response with multiple fallback strategies.

    Strategy order:
    1. Try direct ``json.loads``.
    2. Try extracting a JSON block from markdown fences.
    3. Try extracting a JSON object from the first ``{{`` to the last ``}}``.
    4. If all fail, build a safe fallback that fails all principles.
    """
    # --- Strategy 1: direct parse ---
    raw_stripped = raw.strip()
    try:
        data = json.loads(raw_stripped)
        return _validate_and_fill(data, level_id, expected_principles)
    except json.JSONDecodeError:
        pass

    # --- Strategy 2: extract from ```json ... ``` fences ---
    match = re.search(
        r"```(?:json)?\s*\n?(.*?)\n?```", raw_stripped, re.DOTALL
    )
    if match:
        try:
            data = json.loads(match.group(1).strip())
            return _validate_and_fill(data, level_id, expected_principles)
        except json.JSONDecodeError:
            pass

    # --- Strategy 3: find first { and last } ---
    start = raw_stripped.find("{")
    end = raw_stripped.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(raw_stripped[start : end + 1])
            return _validate_and_fill(data, level_id, expected_principles)
        except json.JSONDecodeError:
            pass

    # --- All strategies exhausted → build safe fallback ---
    logger.warning(
        "Could not parse examiner response.  Raw text (first 500 chars): %s",
        raw_stripped[:500],
    )
    return _build_failed_result(level_id, expected_principles)


def _validate_and_fill(
    data: dict, level_id: int, expected_principles: list[str]
) -> dict[str, Any]:
    """Validate the parsed JSON and fill in any missing fields.

    This ensures the returned dict always matches the expected schema even
    if the LLM omits some fields.
    """
    principles_raw = data.get("principles", [])

    # Build a lookup from the parsed data, normalising names
    # (LLMs sometimes return "clear instruction" instead of "clear_instruction")
    def _normalise(n: str) -> str:
        return n.lower().replace(" ", "_").replace("-", "_")

    parsed_by_name: dict[str, dict] = {}
    normalised_to_original: dict[str, str] = {}
    for p in principles_raw:
        raw_name = p.get("name", "").strip()
        if raw_name:
            key = _normalise(raw_name)
            parsed_by_name[key] = p
            normalised_to_original[key] = raw_name

    # Rebuild the principles list in the expected order
    principles_out: list[dict[str, Any]] = []
    for name in expected_principles:
        key = _normalise(name)
        if key in parsed_by_name:
            p = parsed_by_name[key]
            principles_out.append(
                {
                    "name": name,
                    "pass": bool(p.get("pass", False)),
                    "weakness": str(p.get("weakness", "")),
                    "question": str(p.get("question", "")),
                }
            )
        else:
            # Principle was expected but missing from the response → fail it
            principles_out.append(
                {
                    "name": name,
                    "pass": False,
                    "weakness": "Not evaluated by examiner.",
                    "question": "Can you add this principle to your prompt?",
                }
            )

    all_pass = all(p["pass"] for p in principles_out)

    return {
        "level": level_id,
        "principles": principles_out,
        "ran_ok": True,
        "verdict": "pass" if all_pass else "revise",
    }


def _build_failed_result(
    level_id: int, expected_principles: list[str]
) -> dict[str, Any]:
    """Build a result where all principles fail (used when parsing fails)."""
    principles_out = [
        {
            "name": name,
            "pass": False,
            "weakness": "Examiner could not parse the evaluation response.",
            "question": "Please review the principles and try again.",
        }
        for name in expected_principles
    ]
    return {
        "level": level_id,
        "principles": principles_out,
        "ran_ok": False,
        "verdict": "revise",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def examine(
    user_prompt: str,
    sample_input: str,
    model_output: str,
    level_id: int,
    *,
    llm_call: callable = None,
) -> dict[str, Any]:
    """Evaluate *user_prompt* against the principles for *level_id*.

    Parameters
    ----------
    user_prompt : str
        The prompt the student wrote.
    sample_input : str
        The sample input the prompt was run on.
    model_output : str
        The output produced by running the prompt.
    level_id : int
        The current level (1–5).
    llm_call : callable, optional
        A function ``fn(system_prompt, user_message) -> str`` that calls the
        LLM and returns the raw response text.  Defaults to
        ``_default_llm_call`` which uses OpenRouter.

    Returns
    -------
    dict
        A dict matching the schema described in the module docstring.
    """
    expected_principles = get_principles_for_level(level_id)
    if not expected_principles:
        return _build_failed_result(level_id, expected_principles)

    system_prompt = _build_examiner_system_prompt(level_id)
    user_message = _build_examiner_user_message(
        user_prompt, sample_input, model_output
    )

    if llm_call is None:
        llm_call = _default_llm_call

    try:
        raw_response = llm_call(system_prompt, user_message)
    except Exception as exc:
        logger.exception("Examiner LLM call failed: %s", exc)
        return _build_failed_result(level_id, expected_principles)

    return _parse_examiner_response(
        raw_response, level_id, expected_principles
    )


# ---------------------------------------------------------------------------
# Default LLM call (OpenRouter via runner)
# ---------------------------------------------------------------------------


def _default_llm_call(system_prompt: str, user_message: str) -> str:
    """Call the OpenRouter API with the examiner meta-prompt.

    We use the same ``runner.run_prompt`` infrastructure but with a system
    message instead of a user-only message.
    """
    import os

    import requests
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    base_url = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    timeout = int(os.getenv("OPENROUTER_TIMEOUT", "60"))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.2,  # even lower temperature for consistent grading
        "max_tokens": 2048,
    }

    resp = requests.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )