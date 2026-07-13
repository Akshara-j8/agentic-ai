"""
TechVest Recruitment Agent — Candidate Scorer Tool
Scores a parsed candidate profile against the weighted rubric.
Applies injection penalty if candidate resume contained adversarial content.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from langchain_core.tools import tool

from config.prompts import SCORE_CANDIDATE_PROMPT, SYSTEM_SCORER
from config.rubric import RUBRIC, THRESHOLDS
from llm.client import get_llm_client
from llm.models import Scorecard, CriterionScore, Recommendation

logger = logging.getLogger(__name__)

# Penalty applied to overall score when injection is detected (points, 0–100 scale)
INJECTION_SCORE_PENALTY: float = 15.0


# ---------------------------------------------------------------------------
# Core tool
# ---------------------------------------------------------------------------

@tool
def score_candidate(
    candidate_profile_json: str,
    job_description: str = "",
    run_id: str = "",
) -> str:
    """
    Score a parsed candidate profile against the TechVest rubric.

    Applies:
    - Anonymisation (strips name, email, institution for fairness)
    - LLM-based rubric scoring
    - Weighted score computation
    - Injection penalty if candidate attempted adversarial input
    - Recommendation generation (Interview / Hold / Reject)

    Args:
        candidate_profile_json: JSON string of ParsedProfile
        job_description:        Full JD text for context
        run_id:                 Run ID for audit

    Returns:
        JSON string of Scorecard
    """
    start_ms = time.time() * 1000
    client = get_llm_client()

    # ------------------------------------------------------------------
    # Parse input
    # ------------------------------------------------------------------
    try:
        profile = json.loads(candidate_profile_json) if isinstance(candidate_profile_json, str) \
            else candidate_profile_json
    except json.JSONDecodeError as exc:
        logger.error(f"Invalid profile JSON: {exc}")
        return json.dumps({"error": str(exc), "candidate_name": "Unknown"})

    candidate_name = profile.get("name", "Unknown")
    injection_detected = profile.get("injection_detected", False)

    # ------------------------------------------------------------------
    # Anonymise profile before sending to LLM (fairness gate)
    # ------------------------------------------------------------------
    anon_profile = _anonymise_profile(profile)

    # ------------------------------------------------------------------
    # Call LLM scorer
    # ------------------------------------------------------------------
    try:
        raw_result = client.structured_invoke(
            prompt_template=SCORE_CANDIDATE_PROMPT,
            variables={
                "candidate_profile": json.dumps(anon_profile, indent=2),
                "rubric_json": RUBRIC.to_json_string(),
                "job_description": job_description[:3000],
            },
            system_prompt=SYSTEM_SCORER,
        )
    except Exception as exc:
        logger.error(f"Scoring LLM call failed for {candidate_name}: {exc}")
        raw_result = _fallback_score(candidate_name)

    # ------------------------------------------------------------------
    # Validate and compute weighted score
    # ------------------------------------------------------------------
    criterion_scores_raw = raw_result.get("criterion_scores", {})
    criterion_scores: dict[str, CriterionScore] = {}
    raw_scores: dict[str, float] = {}

    for criterion in RUBRIC.criteria:
        key = criterion.key
        raw = criterion_scores_raw.get(key, {})
        if isinstance(raw, dict):
            cs = CriterionScore(
                score=raw.get("score", 0),
                evidence=raw.get("evidence", ""),
                notes=raw.get("notes", ""),
            )
        else:
            cs = CriterionScore(score=float(raw) if raw else 0)
        criterion_scores[key] = cs
        raw_scores[key] = cs.score

    # Recompute weighted score from our rubric (don't trust LLM arithmetic)
    weighted_score = RUBRIC.compute_weighted_score(raw_scores)

    # ------------------------------------------------------------------
    # Apply injection penalty
    # ------------------------------------------------------------------
    injection_penalty_applied = False
    if injection_detected:
        original_score = weighted_score
        weighted_score = max(0.0, weighted_score - INJECTION_SCORE_PENALTY)
        injection_penalty_applied = True
        logger.warning(
            f"[INJECTION PENALTY] {candidate_name}: "
            f"{original_score:.1f} → {weighted_score:.1f} "
            f"(−{INJECTION_SCORE_PENALTY} pts)"
        )

    # ------------------------------------------------------------------
    # Generate recommendation
    # ------------------------------------------------------------------
    recommendation = RUBRIC.get_recommendation(weighted_score)

    # ------------------------------------------------------------------
    # Build Scorecard
    # ------------------------------------------------------------------
    try:
        scorecard = Scorecard(
            candidate_name=candidate_name,
            criterion_scores=criterion_scores,
            overall_weighted_score=weighted_score,
            recommendation=Recommendation(recommendation),
            confidence=float(raw_result.get("confidence", 0.7)),
            strengths=raw_result.get("strengths", [])[:5],
            gaps=raw_result.get("gaps", [])[:5],
            reasoning=raw_result.get("reasoning", ""),
            injection_penalty_applied=injection_penalty_applied,
            fairness_reviewed=False,
        )
        result_dict = scorecard.model_dump(mode="json")
    except Exception as exc:
        logger.warning(f"Scorecard validation failed: {exc}")
        result_dict = {
            "candidate_name": candidate_name,
            "overall_weighted_score": weighted_score,
            "recommendation": recommendation,
            "criterion_scores": {k: v.model_dump() for k, v in criterion_scores.items()},
            "injection_penalty_applied": injection_penalty_applied,
        }

    duration_ms = time.time() * 1000 - start_ms
    result_dict["_tool_duration_ms"] = round(duration_ms, 2)

    logger.info(
        f"[score_candidate] {candidate_name} → "
        f"score={weighted_score:.1f} | "
        f"recommendation={recommendation} | "
        f"injection_penalty={injection_penalty_applied} | "
        f"{duration_ms:.0f}ms"
    )

    # Audit log
    try:
        from database.audit import get_audit_logger
        audit = get_audit_logger(run_id=run_id)
        audit.log_decision(
            candidate_name=candidate_name,
            recommendation=recommendation,
            score=weighted_score,
            reasoning=result_dict.get("reasoning", "")[:200],
            run_id=run_id,
        )
    except Exception:
        pass

    return json.dumps(result_dict, default=str)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _anonymise_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """
    Create a fairness-safe copy of the profile.
    Removes: name, email, phone, location, institution names.
    """
    anon = dict(profile)
    anon["name"] = "CANDIDATE"
    anon["email"] = None
    anon["phone"] = None
    anon["location"] = None

    # Anonymise education institutions
    education = anon.get("education", [])
    if isinstance(education, list):
        anon_edu = []
        for edu in education:
            if isinstance(edu, dict):
                edu_copy = dict(edu)
                edu_copy["institution"] = "UNIVERSITY"
                anon_edu.append(edu_copy)
            else:
                anon_edu.append(edu)
        anon["education"] = anon_edu

    # Remove injection flags from scoring context
    anon.pop("injection_detected", None)
    anon.pop("injection_severity", None)
    anon.pop("raw_text_snippet", None)

    return anon


def _fallback_score(candidate_name: str) -> dict[str, Any]:
    """Generate a minimal fallback scorecard when LLM fails."""
    return {
        "criterion_scores": {k: {"score": 0, "evidence": "LLM call failed", "notes": ""} for k in RUBRIC.criterion_keys()},
        "overall_weighted_score": 0.0,
        "recommendation": "Reject",
        "confidence": 0.1,
        "strengths": [],
        "gaps": ["Scoring failed — please retry"],
        "reasoning": "Automated scoring failed due to an LLM error. Manual review required.",
    }
