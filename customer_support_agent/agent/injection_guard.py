"""
Prompt-injection guard.

All ticket body text is treated as untrusted data.  The guard scans for
instruction-override patterns before the message reaches any LLM or
policy-decision node.  If a pattern fires:

  - The *original* message is replaced with a sanitised placeholder that
    cannot hijack the downstream prompt.
  - An audit event with event="flagged_injection_attempt" is written to
    logs/audit.jsonl.
  - A flag is set on the state so every downstream node knows the message
    was sanitised.

The agent continues to process the sanitised message normally, applying
standard intent-classification and policy checks.
"""

import re
from typing import TypedDict

from logs.audit import write_audit_event


# ---------------------------------------------------------------------------
# Detection patterns
# Each pattern targets a known injection idiom:
#   - instruction overrides  ("ignore previous instructions / policy / rules")
#   - persona hijacking       ("you are now …", "act as …", "pretend …")
#   - direct action commands  ("issue a full refund now", "approve the credit")
#   - jailbreak framing       ("DAN mode", "developer mode", "system prompt")
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"\b(ignore|disregard|forget|bypass|override|skip)\s+"
        r"(previous\s+)?(instructions?|policy|policies|rules?|guidelines?|constraints?|system)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(you are now|act as|pretend (you are|to be)|roleplay as|simulate|"
        r"from now on|your new (role|persona|instructions?))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(issue|give|apply|approve|grant|process|execute|perform)\s+"
        r"(a\s+)?(full\s+)?refund\s*(now|immediately|right away|at once|asap)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(DAN mode|developer mode|god mode|jailbreak|do anything now|"
        r"unrestricted mode|admin override)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(reveal|print|show|output|display)\s+(your\s+)?"
        r"(system prompt|instructions?|context|configuration)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"<(/?)(system|user|assistant|prompt|instruction)\s*/?>",
        re.IGNORECASE,
    ),
]

_SAFE_PLACEHOLDER = "[REDACTED — injection attempt detected]"


def _find_injection(text: str) -> str | None:
    """Return the first matching pattern label, or None if clean."""
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


class InjectionResult(TypedDict):
    sanitised_message: str
    injection_detected: bool
    injection_snippet: str | None


def screen_message(raw_message: str) -> InjectionResult:
    """
    Screen *raw_message* for prompt-injection content.

    Returns an InjectionResult.  If an injection is detected the
    sanitised_message contains a safe placeholder; the original is
    **never** forwarded to downstream nodes or the LLM.

    A flagged_injection_attempt audit event is written automatically.
    """
    snippet = _find_injection(raw_message)
    if snippet is None:
        return InjectionResult(
            sanitised_message=raw_message,
            injection_detected=False,
            injection_snippet=None,
        )

    write_audit_event(
        {
            "event": "flagged_injection_attempt",
            "raw_snippet": snippet,
            "original_length": len(raw_message),
            "note": "Ticket body contained instruction-override pattern; message sanitised.",
        }
    )

    return InjectionResult(
        sanitised_message=_SAFE_PLACEHOLDER,
        injection_detected=True,
        injection_snippet=snippet,
    )
