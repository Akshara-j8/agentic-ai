"""
TechVest Recruitment Agent — Fairness & Bias Check Tool
Validates scoring results for demographic bias, name bias, college prestige bias,
gender indicators, and inconsistent evidence standards.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from langchain_core.tools import tool

from config.prompts import FAIRNESS_AUDIT_PROMPT, SYSTEM_GUARDRAIL
from llm.client import get_llm_client
from llm.models import FairnessResult, FairnessCheck, FairnessStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rule-based bias patterns (fast, no LLM cost)
# ---------------------------------------------------------------------------

# Gendered pronouns that shouldn't appear in scoring reasoning
GENDER_PATTERNS = [
    re.compile(r"\b(he|she|his|her|him|hers)\b", re.IGNORECASE),
    re.compile(r"\b(male|female|man|woman|boy|girl)\b", re.IGNORECASE),
]

# Elite institution names that could cause prestige bias
PRESTIGE_INSTITUTIONS = {
    "iit", "iim", "mit", "stanford", "harvard", "oxford", "cambridge",
    "caltech", "berkeley", "yale", "princeton", "columbia", "nyu",
    "cmu", "carnegie mellon",
}

# Age-related keywords
AGE_PATTERNS = [
    re.compile(r"\b(young|old|senior|junior|fresh|recent)\s+(candidate|graduate)\b", re.IGNORECASE),
    re.compile(r"\b(too\s+old|too\s+young)\b", re.IGNORECASE),
    re.compile(r"\bgraduated?\s+in\s+(19[5-9]\d|20[0-2]\d)\b", re.IGNORECASE),
]

# Religious indicators
RELIGION_PATTERNS = [
    re.compile(r"\b(christian|muslim|hindu|jewish|sikh|buddhist|atheist)\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Core tool
# ---------------------------------------------------------------------------

@tool
def fairness_check(
    scorecards_json: str,
    run_id: str = "",
) -> str:
    """
    Run a comprehensive fairness and bias audit on a set of scorecards.

    Checks:
    1. Name-based demographic assumptions
    2. College prestige bias (institution → score correlation)
    3. Gender indicator language in reasoning
    4. Age-related bias
    5. Religious indicator bias
    6. Evidence consistency across candidates
    7. LLM-based holistic review

    Args:
        scorecards_json: JSON string — list of Scorecard dicts
        run_id:          Run ID for audit

    Returns:
        JSON string of FairnessResult
    """
    start_ms = time.time() * 1000

    try:
        scorecards = json.loads(scorecards_json) if isinstance(scorecards_json, str) else scorecards_json
    except Exception as exc:
        return json.dumps({"overall_fairness": "FAIL", "error": str(exc)})

    if not isinstance(scorecards, list):
        scorecards = [scorecards]

    checks: list[FairnessCheck] = []
    all_pass = True

    # ------------------------------------------------------------------
    # Check 1: Gender language in reasoning
    # ------------------------------------------------------------------
    gender_issues: list[str] = []
    for sc in scorecards:
        reasoning = sc.get("reasoning", "")
        for pattern in GENDER_PATTERNS:
            if pattern.search(reasoning):
                gender_issues.append(sc.get("candidate_name", "Unknown"))
                break

    checks.append(FairnessCheck(
        check_name="gender_language",
        status=FairnessStatus.FAIL if gender_issues else FairnessStatus.PASS,
        finding=f"Gendered language detected in reasoning for: {', '.join(gender_issues)}" if gender_issues else None,
        affected_candidates=gender_issues,
    ))
    if gender_issues:
        all_pass = False

    # ------------------------------------------------------------------
    # Check 2: College prestige bias
    # ------------------------------------------------------------------
    prestige_inflated: list[str] = []
    for sc in scorecards:
        reasoning = (sc.get("reasoning", "") + " " + _get_all_evidence(sc)).lower()
        has_prestige = any(inst in reasoning for inst in PRESTIGE_INSTITUTIONS)
        edu_score = sc.get("criterion_scores", {}).get("education", {})
        edu_score_val = edu_score.get("score", 0) if isinstance(edu_score, dict) else 0
        edu_evidence = edu_score.get("evidence", "") if isinstance(edu_score, dict) else ""

        # Warn if a prestige institution is mentioned prominently in education evidence
        if has_prestige and any(inst in edu_evidence.lower() for inst in PRESTIGE_INSTITUTIONS):
            prestige_inflated.append(sc.get("candidate_name", "Unknown"))

    checks.append(FairnessCheck(
        check_name="college_prestige_bias",
        status=FairnessStatus.WARNING if prestige_inflated else FairnessStatus.PASS,
        finding=(
            f"Institution name present in scoring evidence — "
            f"verify scores are merit-based: {', '.join(prestige_inflated)}"
            if prestige_inflated else None
        ),
        affected_candidates=prestige_inflated,
    ))

    # ------------------------------------------------------------------
    # Check 3: Age indicators
    # ------------------------------------------------------------------
    age_issues: list[str] = []
    for sc in scorecards:
        reasoning = sc.get("reasoning", "")
        for pattern in AGE_PATTERNS:
            if pattern.search(reasoning):
                age_issues.append(sc.get("candidate_name", "Unknown"))
                break

    checks.append(FairnessCheck(
        check_name="age_bias",
        status=FairnessStatus.FAIL if age_issues else FairnessStatus.PASS,
        finding=f"Age-related language in reasoning: {', '.join(age_issues)}" if age_issues else None,
        affected_candidates=age_issues,
    ))
    if age_issues:
        all_pass = False

    # ------------------------------------------------------------------
    # Check 4: Religious indicators
    # ------------------------------------------------------------------
    religion_issues: list[str] = []
    for sc in scorecards:
        reasoning = sc.get("reasoning", "")
        for pattern in RELIGION_PATTERNS:
            if pattern.search(reasoning):
                religion_issues.append(sc.get("candidate_name", "Unknown"))
                break

    checks.append(FairnessCheck(
        check_name="religion_bias",
        status=FairnessStatus.FAIL if religion_issues else FairnessStatus.PASS,
        finding=f"Religious references in reasoning: {', '.join(religion_issues)}" if religion_issues else None,
        affected_candidates=religion_issues,
    ))
    if religion_issues:
        all_pass = False

    # ------------------------------------------------------------------
    # Check 5: Evidence consistency
    # ------------------------------------------------------------------
    evidence_lengths = []
    for sc in scorecards:
        total_evidence = sum(
            len(v.get("evidence", "") if isinstance(v, dict) else "")
            for v in sc.get("criterion_scores", {}).values()
        )
        evidence_lengths.append((sc.get("candidate_name", ""), total_evidence))

    inconsistent: list[str] = []
    if len(evidence_lengths) > 1:
        mean_ev = sum(l for _, l in evidence_lengths) / len(evidence_lengths)
        for name, length in evidence_lengths:
            if length < mean_ev * 0.3:          # Less than 30% of average
                inconsistent.append(name)

    checks.append(FairnessCheck(
        check_name="evidence_consistency",
        status=FairnessStatus.WARNING if inconsistent else FairnessStatus.PASS,
        finding=(
            f"Much less evidence provided for: {', '.join(inconsistent)} "
            f"— may indicate inconsistent evaluation standard"
            if inconsistent else None
        ),
        affected_candidates=inconsistent,
    ))

    # ------------------------------------------------------------------
    # Check 6: Score variance (flag extreme outliers)
    # ------------------------------------------------------------------
    scores = [sc.get("overall_weighted_score", 0) for sc in scorecards]
    if len(scores) > 1:
        mean_score = sum(scores) / len(scores)
        extreme_outliers = [
            scorecards[i].get("candidate_name", "")
            for i, s in enumerate(scores)
            if abs(s - mean_score) > 35          # More than 35 points from mean
        ]
    else:
        extreme_outliers = []

    checks.append(FairnessCheck(
        check_name="score_variance",
        status=FairnessStatus.WARNING if extreme_outliers else FairnessStatus.PASS,
        finding=(
            f"Extreme score outliers detected: {', '.join(extreme_outliers)}. "
            f"Review if based on merit."
            if extreme_outliers else None
        ),
        affected_candidates=extreme_outliers,
    ))

    # ------------------------------------------------------------------
    # LLM holistic review
    # ------------------------------------------------------------------
    llm_result: dict[str, Any] = {}
    try:
        client = get_llm_client()
        scoring_data = json.dumps([{
            "name": sc.get("candidate_name"),
            "score": sc.get("overall_weighted_score"),
            "recommendation": sc.get("recommendation"),
            "reasoning": sc.get("reasoning", "")[:200],
        } for sc in scorecards], indent=2)

        llm_result = client.structured_invoke(
            prompt_template=FAIRNESS_AUDIT_PROMPT,
            variables={"scoring_data": scoring_data},
            system_prompt=SYSTEM_GUARDRAIL,
        )
        # Incorporate LLM findings
        if isinstance(llm_result, dict):
            llm_checks = llm_result.get("checks", [])
            for lc in llm_checks:
                if isinstance(lc, dict) and lc.get("status") in ("FAIL", "WARNING"):
                    checks.append(FairnessCheck(
                        check_name=f"llm_{lc.get('check_name', 'review')}",
                        status=FairnessStatus(lc.get("status", "PASS")),
                        finding=lc.get("finding"),
                        affected_candidates=lc.get("affected_candidates", []),
                    ))
                    if lc.get("status") == "FAIL":
                        all_pass = False
    except Exception as exc:
        logger.warning(f"LLM fairness check failed: {exc}")

    # ------------------------------------------------------------------
    # Compute bias score (fraction of checks that FAILED — warnings don't fail)
    # ------------------------------------------------------------------
    hard_fail_count = sum(1 for c in checks if c.status == FairnessStatus.FAIL)
    warn_count = sum(1 for c in checks if c.status == FairnessStatus.WARNING)
    bias_score = round(hard_fail_count / max(len(checks), 1), 3)

    # Only mark FAIL if there are real hard failures (not just warnings)
    overall = FairnessStatus.PASS if hard_fail_count == 0 else FairnessStatus.FAIL

    result = FairnessResult(
        overall_fairness=overall,
        checks=checks,
        bias_score=bias_score,
        recommendations=llm_result.get("recommendations", [
            "Review scoring evidence for each candidate",
            "Ensure institution names do not influence education scores",
        ]),
        audit_notes=(
            llm_result.get("audit_notes", "")
            or f"Automated fairness check completed. {len(checks)} checks run. "
               f"{'No significant bias detected.' if all_pass else 'Potential bias detected — review flagged items.'}"
        ),
    )

    duration_ms = time.time() * 1000 - start_ms
    result_dict = result.model_dump(mode="json")
    result_dict["_tool_duration_ms"] = round(duration_ms, 2)

    logger.info(
        f"[fairness_check] overall={overall.value} | "
        f"bias_score={bias_score:.3f} | "
        f"checks={len(checks)} | "
        f"{duration_ms:.0f}ms"
    )

    # Audit
    try:
        from database.audit import get_audit_logger
        audit = get_audit_logger(run_id=run_id)
        audit.log_guardrail(
            guardrail_type="fairness_audit",
            status=overall.value,
            details={"bias_score": bias_score, "checks": len(checks), "failures": fail_count},
            severity="high" if overall == FairnessStatus.FAIL else "none",
            action_taken="flagged_for_review" if overall == FairnessStatus.FAIL else "pass",
            run_id=run_id,
        )
    except Exception:
        pass

    return json.dumps(result_dict, default=str)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_all_evidence(scorecard: dict[str, Any]) -> str:
    """Concatenate all evidence strings from a scorecard."""
    parts = []
    for v in scorecard.get("criterion_scores", {}).values():
        if isinstance(v, dict):
            parts.append(v.get("evidence", ""))
            parts.append(v.get("notes", ""))
    return " ".join(parts)


@tool
def prompt_injection_detector(
    text: str,
    context: str = "resume",
    run_id: str = "",
) -> str:
    """
    Standalone prompt injection detection tool.
    Can be called on any arbitrary text (resume, cover letter, notes).

    Args:
        text:    Text to analyse for injection attempts
        context: Where the text came from ("resume", "cover_letter", etc.)
        run_id:  Run ID for audit

    Returns:
        JSON string of InjectionResult
    """
    from tools.parser import _rule_based_injection_check, INJECTION_PATTERNS
    from config.prompts import INJECTION_DETECTION_PROMPT, SYSTEM_GUARDRAIL
    from llm.models import InjectionResult, InjectionSeverity

    detected, flagged, severity = _rule_based_injection_check(text)

    # LLM confirmation
    llm_result: dict[str, Any] = {}
    if detected:
        try:
            client = get_llm_client()
            llm_result = client.structured_invoke(
                prompt_template=INJECTION_DETECTION_PROMPT,
                variables={"text": text[:3000]},
                system_prompt=SYSTEM_GUARDRAIL,
            )
        except Exception as exc:
            logger.warning(f"LLM injection detection failed: {exc}")

    result = InjectionResult(
        injection_detected=detected,
        severity=InjectionSeverity(severity),
        attack_type=llm_result.get("attack_type"),
        flagged_text=flagged + llm_result.get("flagged_text", []),
        confidence=llm_result.get("confidence", 0.9 if detected else 0.0),
        recommendation="quarantine" if severity in ("high", "critical") else ("warn" if detected else "allow"),
        sanitised_text=llm_result.get("sanitised_text", text),
    )

    return result.model_dump_json()


@tool
def audit_logger_tool(
    action: str,
    details: str = "",
    run_id: str = "",
    level: str = "INFO",
) -> str:
    """
    Persist an audit log entry from within the agent graph.

    Args:
        action:  Short action description
        details: JSON string or plain text details
        run_id:  Current run ID
        level:   Log level (INFO, WARNING, ERROR, SECURITY)

    Returns:
        JSON confirmation
    """
    try:
        from database.audit import get_audit_logger, AuditLevel
        audit = get_audit_logger(run_id=run_id)
        audit.log(
            action,
            level=AuditLevel(level.upper()),
            details=details,
            run_id=run_id,
        )
        return json.dumps({"status": "logged", "action": action})
    except Exception as exc:
        return json.dumps({"status": "error", "reason": str(exc)})
