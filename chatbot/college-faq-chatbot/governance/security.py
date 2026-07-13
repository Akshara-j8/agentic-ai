"""
governance/security.py
======================
Security middleware for the BVRITH College FAQ RAG chatbot.

Provides:
- Input validation (length, character limits)
- Prompt injection detection (heuristics + pattern matching)
- PII masking (email, phone, Aadhaar, PAN)
- Output filtering (harmful content, system prompt leakage)
- Tool whitelist enforcement
- Source citation validation
- Governance event logging to logs/governance_logs.jsonl

Usage:
    from governance.security import SecurityMiddleware
    mw = SecurityMiddleware()
    result = mw.validate_input(user_text)
    if result.is_safe:
        answer = rag_answer(result.sanitized_text)
    filtered = mw.filter_output(answer)
"""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils import setup_logger

logger = setup_logger("security_middleware")

# ── Governance log path ────────────────────────────────────────────────────────
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
GOVERNANCE_LOG = LOGS_DIR / "governance_logs.jsonl"


# ─────────────────────────────────────────────────────────────────────────────
#  Configuration constants
# ─────────────────────────────────────────────────────────────────────────────

MAX_INPUT_LENGTH: int = 2000        # characters
MAX_OUTPUT_LENGTH: int = 4000       # characters
ALLOWED_TOOLS: List[str] = [        # whitelisted tool names
    "retrieve_chunks",
    "get_retriever",
    "format_chunks_for_context",
]

# Patterns that strongly indicate prompt injection attempts
INJECTION_PATTERNS: List[str] = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"forget\s+(your|all|the)\s+(instructions?|rules?|prompt|context)",
    r"you\s+are\s+now\s+(a\s+)?(?:dan|jailbreak|unrestricted|evil|hacked)",
    r"system\s*:\s*(override|disable|bypass|ignore)",
    r"reveal\s+(your|the)\s+(system\s+)?prompt",
    r"print\s+(your|the)\s+(system\s+)?prompt",
    r"show\s+(your|the)\s+(system\s+)?prompt",
    r"disregard\s+(all\s+)?(previous|prior)\s+(instructions?|rules?)",
    r"act\s+as\s+(if\s+you\s+(are|were)\s+)?(?:dan|jailbreak|unrestricted)",
    r"pretend\s+(you\s+are|to\s+be)\s+(an?\s+)?(unrestricted|evil|unethical)",
    r"override\s+(your\s+)?(safety|ethical|content)\s+(guidelines?|filter|rules?)",
    r"new\s+persona[:\s]",
    r"do\s+anything\s+now",
    r"jailbreak",
    r"<\s*system\s*>",
    r"\[system\]",
    r"\[inst\]",
    r"<\s*/?inst\s*>",
    r"\[\/inst\]",
]

# PII patterns for masking
PII_PATTERNS: List[Tuple[str, str, str]] = [
    # (name, pattern, replacement)
    ("email",   r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", "[EMAIL REDACTED]"),
    ("phone_in", r"(?:\+91[\-\s]?)?[6-9]\d{9}", "[PHONE REDACTED]"),
    ("phone_intl", r"\+\d{1,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{4}", "[PHONE REDACTED]"),
    ("aadhaar", r"\b\d{4}\s?\d{4}\s?\d{4}\b", "[AADHAAR REDACTED]"),
    ("pan",     r"\b[A-Z]{5}\d{4}[A-Z]\b", "[PAN REDACTED]"),
    ("dob",     r"\b(?:\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\b", "[DOB REDACTED]"),
    ("credit_card", r"\b(?:\d{4}[\s\-]?){3}\d{4}\b", "[CARD REDACTED]"),
]

# Harmful content signals in output
HARMFUL_OUTPUT_PATTERNS: List[str] = [
    r"how\s+to\s+(make|build|create|synthesize)\s+(bomb|explosive|weapon|poison|drug)",
    r"(step\s+\d+[:\s]+)?.*(detonate|explode|ignite|synthesize\s+meth)",
    r"instructions?\s+(for|on)\s+(harming|killing|attacking)",
]

# System prompt leakage patterns
SYSTEM_LEAK_PATTERNS: List[str] = [
    r"you\s+are\s+(an?\s+)?official\s+faq\s+assistant\s+for\s+bvrith",
    r"strict\s+rules.*retrieved\s+context",
    r"never\s+reveal\s+these\s+instructions",
]


# ─────────────────────────────────────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class InputValidationResult:
    """Result of input validation."""
    is_safe: bool
    sanitized_text: str
    original_text: str
    violations: List[str] = field(default_factory=list)
    risk_level: str = "LOW"  # LOW | MEDIUM | HIGH | CRITICAL
    pii_detected: bool = False
    injection_detected: bool = False


@dataclass
class OutputFilterResult:
    """Result of output filtering."""
    is_safe: bool
    filtered_text: str
    original_text: str
    violations: List[str] = field(default_factory=list)
    system_leak_detected: bool = False
    harmful_content_detected: bool = False


# ─────────────────────────────────────────────────────────────────────────────
#  Governance event logger
# ─────────────────────────────────────────────────────────────────────────────

def log_governance_event(
    framework: str,
    severity: str,
    vulnerability: str,
    prompt: str,
    response: str,
    score: Optional[float] = None,
    extra: Optional[dict] = None,
) -> None:
    """Append a governance event to logs/governance_logs.jsonl.

    Args:
        framework:     Tool that generated the event (e.g., "security", "giskard").
        severity:      LOW / MEDIUM / HIGH / CRITICAL.
        vulnerability: Short description of the issue type.
        prompt:        The original user input (truncated for safety).
        response:      The model or middleware response.
        score:         Optional numeric score (0–1).
        extra:         Additional key-value metadata.
    """
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "framework": framework,
        "severity": severity,
        "vulnerability": vulnerability,
        "prompt": prompt[:500],  # truncate to avoid huge log files
        "response": response[:500],
        "score": score,
    }
    if extra:
        event.update(extra)
    try:
        with GOVERNANCE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as exc:
        logger.warning("Could not write governance log: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
#  SecurityMiddleware
# ─────────────────────────────────────────────────────────────────────────────

class SecurityMiddleware:
    """Stateless security middleware — validates inputs, filters outputs.

    All checks are deterministic and do not call the LLM, so they are fast
    and safe to run on every request.
    """

    # ── Input validation ──────────────────────────────────────────────────────

    def validate_input(self, text: str) -> InputValidationResult:
        """Run all input security checks on the user's query.

        Checks performed (in order):
        1. Length limit
        2. Null / empty guard
        3. Prompt injection detection
        4. PII detection (with masking)

        Args:
            text: Raw user input.

        Returns:
            InputValidationResult with is_safe flag and sanitized text.
        """
        violations: List[str] = []
        sanitized = text
        is_safe = True
        risk_level = "LOW"
        pii_detected = False
        injection_detected = False

        # 1. Null/empty guard
        if not text or not text.strip():
            return InputValidationResult(
                is_safe=False,
                sanitized_text="",
                original_text=text,
                violations=["Empty or null input rejected."],
                risk_level="LOW",
            )

        # 2. Length check
        if len(text) > MAX_INPUT_LENGTH:
            violations.append(
                f"Input exceeds maximum length ({len(text)} > {MAX_INPUT_LENGTH} chars). Truncated."
            )
            sanitized = text[:MAX_INPUT_LENGTH]
            risk_level = "MEDIUM"
            log_governance_event(
                framework="security",
                severity="MEDIUM",
                vulnerability="Oversized Input",
                prompt=text[:200],
                response="Input truncated",
            )

        # 3. Prompt injection detection
        text_lower = sanitized.lower()
        matched_patterns = []
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                matched_patterns.append(pattern)

        if matched_patterns:
            injection_detected = True
            is_safe = False
            risk_level = "CRITICAL"
            violations.append(
                f"Prompt injection attempt detected. "
                f"Matched patterns: {len(matched_patterns)}."
            )
            log_governance_event(
                framework="security",
                severity="CRITICAL",
                vulnerability="Prompt Injection",
                prompt=text[:200],
                response="Request blocked by security middleware",
                extra={"matched_patterns": len(matched_patterns)},
            )
            logger.warning("SECURITY: Prompt injection blocked. Input: %s", text[:100])

        # 4. PII detection and masking
        for pii_name, pattern, replacement in PII_PATTERNS:
            if re.search(pattern, sanitized):
                pii_detected = True
                violations.append(f"PII detected and masked: {pii_name}.")
                sanitized = re.sub(pattern, replacement, sanitized)
                if risk_level not in ("CRITICAL", "HIGH"):
                    risk_level = "MEDIUM"
                log_governance_event(
                    framework="security",
                    severity="MEDIUM",
                    vulnerability=f"PII Detected ({pii_name})",
                    prompt=text[:200],
                    response="PII masked before processing",
                    extra={"pii_type": pii_name},
                )

        return InputValidationResult(
            is_safe=is_safe,
            sanitized_text=sanitized,
            original_text=text,
            violations=violations,
            risk_level=risk_level,
            pii_detected=pii_detected,
            injection_detected=injection_detected,
        )

    # ── Output filtering ──────────────────────────────────────────────────────

    def filter_output(self, text: str, original_query: str = "") -> OutputFilterResult:
        """Filter the LLM's output before returning it to the user.

        Checks performed:
        1. System prompt leakage detection
        2. Harmful content detection
        3. Output length cap

        Args:
            text:           Raw LLM output.
            original_query: The user's original question (for logging).

        Returns:
            OutputFilterResult with is_safe flag and filtered text.
        """
        violations: List[str] = []
        filtered = text
        is_safe = True
        system_leak = False
        harmful = False

        # 1. System prompt leakage
        text_lower = text.lower()
        for pattern in SYSTEM_LEAK_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                system_leak = True
                is_safe = False
                violations.append("System prompt leakage detected in output.")
                filtered = (
                    "I'm sorry, I cannot share internal configuration details. "
                    "Please ask me about BVRITH college information."
                )
                log_governance_event(
                    framework="security",
                    severity="CRITICAL",
                    vulnerability="System Prompt Leakage",
                    prompt=original_query[:200],
                    response=text[:200],
                )
                logger.warning("SECURITY: System prompt leakage blocked.")
                break

        # 2. Harmful content detection
        if not system_leak:
            for pattern in HARMFUL_OUTPUT_PATTERNS:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    harmful = True
                    is_safe = False
                    violations.append("Harmful content detected in LLM output.")
                    filtered = (
                        "I'm unable to provide that type of information. "
                        "For any safety or security concerns on campus, "
                        "please contact the Student Affairs office."
                    )
                    log_governance_event(
                        framework="security",
                        severity="CRITICAL",
                        vulnerability="Harmful Content in Output",
                        prompt=original_query[:200],
                        response=text[:200],
                    )
                    logger.warning("SECURITY: Harmful output blocked.")
                    break

        # 3. Output length cap
        if len(filtered) > MAX_OUTPUT_LENGTH:
            filtered = filtered[:MAX_OUTPUT_LENGTH] + "…"
            violations.append(f"Output truncated to {MAX_OUTPUT_LENGTH} chars.")

        return OutputFilterResult(
            is_safe=is_safe,
            filtered_text=filtered,
            original_text=text,
            violations=violations,
            system_leak_detected=system_leak,
            harmful_content_detected=harmful,
        )

    # ── Tool whitelist ────────────────────────────────────────────────────────

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Return True only if the tool is on the whitelist.

        Args:
            tool_name: Name of the tool to check.

        Returns:
            True if allowed, False otherwise.
        """
        allowed = tool_name in ALLOWED_TOOLS
        if not allowed:
            log_governance_event(
                framework="security",
                severity="HIGH",
                vulnerability="Disallowed Tool Call",
                prompt=tool_name,
                response="Tool call blocked",
            )
            logger.warning("SECURITY: Disallowed tool call blocked: %s", tool_name)
        return allowed

    # ── Citation validation ───────────────────────────────────────────────────

    def validate_citations(self, answer: str, source_docs: list) -> Tuple[bool, str]:
        """Check that every citation in the answer appears in source_docs.

        Args:
            answer:      The LLM answer string.
            source_docs: List of LangChain Document objects returned by retrieval.

        Returns:
            (is_valid, note) where note describes any unsupported claims.
        """
        # Extract [Section | Page N] style citations from the answer
        citation_pattern = r"\[([^\]]+)\|\s*Page\s+\S+\]"
        cited = re.findall(citation_pattern, answer, re.IGNORECASE)

        if not cited:
            return True, "No explicit citations found — answer may lack grounding."

        # Build a set of section headings from retrieved docs
        available_sections = {
            doc.metadata.get("section_heading", "").strip().lower()
            for doc in source_docs
        }

        unsupported = []
        for c in cited:
            if c.strip().lower() not in available_sections:
                unsupported.append(c.strip())

        if unsupported:
            log_governance_event(
                framework="security",
                severity="MEDIUM",
                vulnerability="Unsupported Citation",
                prompt="citation_validation",
                response=str(unsupported),
            )
            return False, f"Unsupported citations detected: {unsupported}"

        return True, "All citations validated against retrieved documents."

    # ── Convenience: full pipeline ────────────────────────────────────────────

    def process_request(
        self,
        user_input: str,
        rag_callable,
    ) -> Tuple[str, dict]:
        """Run the full security pipeline: validate → answer → filter.

        Args:
            user_input:   Raw user input string.
            rag_callable: Callable(question: str) -> str — the RAG answer function.

        Returns:
            Tuple of (final_response_text, security_metadata_dict).
        """
        metadata = {
            "input_safe": True,
            "output_safe": True,
            "violations": [],
            "risk_level": "LOW",
            "pii_masked": False,
            "injection_blocked": False,
        }

        # Validate input
        input_result = self.validate_input(user_input)
        metadata["input_safe"] = input_result.is_safe
        metadata["violations"].extend(input_result.violations)
        metadata["risk_level"] = input_result.risk_level
        metadata["pii_masked"] = input_result.pii_detected
        metadata["injection_blocked"] = input_result.injection_detected

        if not input_result.is_safe:
            blocked_response = (
                "⚠️ Your message was flagged by our security system and could not "
                "be processed. Please ask a question about BVRITH college.\n\n"
                "If you believe this is a mistake, please rephrase your question."
            )
            return blocked_response, metadata

        # Call RAG
        try:
            raw_answer = rag_callable(input_result.sanitized_text)
        except Exception as exc:
            logger.error("RAG callable failed: %s", exc)
            raw_answer = (
                "I encountered an error processing your question. "
                "Please try again or contact the BVRITH IT helpdesk."
            )

        # Filter output
        output_result = self.filter_output(raw_answer, original_query=user_input)
        metadata["output_safe"] = output_result.is_safe
        metadata["violations"].extend(output_result.violations)

        return output_result.filtered_text, metadata
