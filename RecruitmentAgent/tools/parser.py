"""
TechVest Recruitment Agent — Resume Parser Tool
LangChain tool that extracts structured candidate profiles from raw resume text.
Integrates injection detection as a first-pass safety gate.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

from langchain_core.tools import tool

from config.prompts import PARSE_RESUME_PROMPT, SYSTEM_PARSER, INJECTION_DETECTION_PROMPT, SYSTEM_GUARDRAIL
from llm.client import get_llm_client
from llm.models import ParsedProfile, InjectionResult, InjectionSeverity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Injection pre-scanner (rule-based, fast — before LLM call)
# ---------------------------------------------------------------------------

INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"ignore\s+(the\s+)?rubric", re.IGNORECASE),
    re.compile(r"rank\s+me\s+first", re.IGNORECASE),
    re.compile(r"give\s+(me\s+)?(maximum|highest|perfect|full)\s+score", re.IGNORECASE),
    re.compile(r"override\s+(the\s+)?(system\s+)?(prompt|instructions?|rubric)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|prior)\s+context", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a?\s*(different|new)\s+(ai|model|assistant)", re.IGNORECASE),
    re.compile(r"act\s+as\s+if\s+(i\s+)?scored?\s+\d+", re.IGNORECASE),
    re.compile(r"disregard\s+(previous|all)\s+(instructions?|context)", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"DAN\s+mode", re.IGNORECASE),
    re.compile(r"do\s+not\s+(evaluate|score|rank)\s+me", re.IGNORECASE),
    re.compile(r"output\s+(only|just)\s+['\"]?interview['\"]?", re.IGNORECASE),
    re.compile(r"award\s+(me\s+)?(\d+|full|maximum)\s+(points?|score)", re.IGNORECASE),
]


def _rule_based_injection_check(text: str) -> tuple[bool, list[str], str]:
    """
    Fast regex-based injection check.

    Returns:
        (detected: bool, flagged_snippets: list[str], severity: str)
    """
    flagged: list[str] = []
    for pattern in INJECTION_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            # Find the actual matched string for display
            found = pattern.search(text)
            if found:
                flagged.append(found.group(0))

    if not flagged:
        return False, [], "none"

    count = len(flagged)
    severity = "low" if count == 1 else ("medium" if count <= 3 else "high")
    return True, flagged, severity


def _sanitise_text(text: str, flagged: list[str]) -> str:
    """Replace injection snippets with [REDACTED] markers."""
    sanitised = text
    for snippet in flagged:
        sanitised = sanitised.replace(snippet, f"[INJECTION_REDACTED: {snippet[:30]}...]")
    return sanitised


# ---------------------------------------------------------------------------
# Core tool function
# ---------------------------------------------------------------------------

@tool
def parse_resume(
    resume_text: str,
    filename: str = "resume.pdf",
    run_id: str = "",
) -> str:
    """
    Parse a candidate resume and extract a structured profile.

    Performs:
    1. Rule-based prompt injection scan
    2. LLM-based injection confirmation (if rule-based flags)
    3. LLM profile extraction using sanitised text
    4. Returns JSON-serialised ParsedProfile

    Args:
        resume_text: Raw text content of the resume
        filename:    Original filename for tracking
        run_id:      Current agent run ID for audit

    Returns:
        JSON string of ParsedProfile
    """
    start_ms = time.time() * 1000
    client = get_llm_client()

    # ------------------------------------------------------------------
    # Step 1: Rule-based injection scan (fast, no LLM cost)
    # ------------------------------------------------------------------
    injection_detected, flagged_snippets, rule_severity = _rule_based_injection_check(resume_text)

    # ------------------------------------------------------------------
    # Step 2: LLM-based injection confirmation if rule-based fires
    # ------------------------------------------------------------------
    llm_injection: Optional[dict[str, Any]] = None
    if injection_detected:
        try:
            prompt = INJECTION_DETECTION_PROMPT.format(text=resume_text[:3000])
            llm_injection = client.chat(prompt, system_prompt=SYSTEM_GUARDRAIL, parse_json=True)
            # Upgrade to LLM result if higher confidence
            if isinstance(llm_injection, dict):
                llm_detected = llm_injection.get("injection_detected", False)
                llm_severity = llm_injection.get("severity", rule_severity)
                # Use more severe of the two
                severity_rank = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
                if severity_rank.get(llm_severity, 0) >= severity_rank.get(rule_severity, 0):
                    rule_severity = llm_severity
                injection_detected = injection_detected or llm_detected
                if llm_injection.get("flagged_text"):
                    flagged_snippets.extend(llm_injection["flagged_text"])
                    flagged_snippets = list(set(flagged_snippets))
        except Exception as exc:
            logger.warning(f"LLM injection check failed, using rule-based only: {exc}")

    # Sanitise text if injection detected
    text_to_parse = _sanitise_text(resume_text, flagged_snippets) if injection_detected else resume_text

    # Log injection event
    if injection_detected:
        logger.warning(
            f"[INJECTION] Detected in {filename} | severity={rule_severity} | "
            f"snippets={flagged_snippets[:3]}"
        )
        try:
            from database.audit import get_audit_logger
            audit = get_audit_logger(run_id=run_id)
            audit.log_injection_attack(
                candidate_name=filename,
                severity=rule_severity,
                flagged_text=flagged_snippets,
                run_id=run_id,
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Step 3: LLM resume parsing on (sanitised) text
    # ------------------------------------------------------------------
    try:
        raw_result = client.structured_invoke(
            prompt_template=PARSE_RESUME_PROMPT,
            variables={"resume_text": text_to_parse[:8000]},
            system_prompt=SYSTEM_PARSER,
        )
    except Exception as exc:
        logger.error(f"Resume parsing LLM call failed: {exc}")
        # Return minimal profile on failure
        raw_result = {
            "name": _extract_name_fallback(resume_text),
            "parse_error": str(exc),
        }

    # ------------------------------------------------------------------
    # Step 4: Build and validate ParsedProfile
    # ------------------------------------------------------------------
    if "parse_error" not in raw_result:
        # Validate through Pydantic
        try:
            profile = ParsedProfile(**{
                **raw_result,
                "resume_filename": filename,
                "injection_detected": injection_detected,
                "injection_severity": InjectionSeverity(rule_severity),
                "raw_text_snippet": resume_text[:200],
            })
            result_dict = profile.model_dump(mode="json")
        except Exception as exc:
            logger.warning(f"Profile validation failed, using raw dict: {exc}")
            result_dict = {**raw_result, "resume_filename": filename,
                           "injection_detected": injection_detected,
                           "injection_severity": rule_severity}
    else:
        result_dict = {**raw_result, "resume_filename": filename,
                       "injection_detected": injection_detected,
                       "injection_severity": rule_severity}

    duration_ms = time.time() * 1000 - start_ms
    result_dict["_tool_duration_ms"] = round(duration_ms, 2)

    logger.info(
        f"[parse_resume] {filename} → "
        f"name={result_dict.get('name')} | "
        f"injection={injection_detected} | "
        f"{duration_ms:.0f}ms"
    )

    return json.dumps(result_dict, default=str)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_name_fallback(text: str) -> str:
    """Very simple name extraction from first non-empty line."""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and len(stripped.split()) >= 2 and len(stripped) < 60:
            return stripped
    return "Unknown Candidate"


def extract_text_from_pdf_bytes(pdf_bytes: bytes, filename: str = "resume.pdf") -> str:
    """
    Extract plain text from PDF bytes.
    Tries PyMuPDF first, falls back to pypdf.
    """
    text = ""

    # Try PyMuPDF (fitz) — better layout handling
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        parts = []
        for page in doc:
            parts.append(page.get_text())
        doc.close()
        text = "\n".join(parts).strip()
        if text:
            return text
    except ImportError:
        logger.debug("PyMuPDF not available, trying pypdf")
    except Exception as exc:
        logger.warning(f"PyMuPDF extraction failed for {filename}: {exc}")

    # Fallback: pypdf
    try:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(parts).strip()
    except ImportError:
        logger.warning("pypdf not available — returning empty string")
    except Exception as exc:
        logger.warning(f"pypdf extraction failed for {filename}: {exc}")

    return text or f"[PDF extraction failed for {filename}]"
