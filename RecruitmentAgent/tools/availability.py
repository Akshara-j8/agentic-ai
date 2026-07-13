"""
TechVest Recruitment Agent — Availability Check Tool
Checks interviewer availability and proposes interview slots.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any

from langchain_core.tools import tool

from config.prompts import AVAILABILITY_PROMPT
from llm.client import get_llm_client
from llm.models import AvailabilityResult, InterviewSlot, InterviewFormat, InterviewType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Static availability constraints
# ---------------------------------------------------------------------------

AVAILABILITY_WINDOWS = {
    "Technical Panel": {
        "days": [0, 1, 2, 3, 4],          # Mon–Fri
        "slots": ["10:00", "11:00", "14:00", "15:00", "16:00"],
        "duration": 60,
        "format": "Video",
    },
    "HR Screening": {
        "days": [0, 1, 2, 3, 4],
        "slots": ["09:00", "10:00", "10:30"],
        "duration": 45,
        "format": "Video",
    },
    "Final Panel": {
        "days": [1, 3],                    # Tue, Thu only
        "slots": ["14:00", "15:30"],
        "duration": 90,
        "format": "Video",
    },
}

BLOCKED_DATES: set[str] = set()         # Could be populated from a real calendar


# ---------------------------------------------------------------------------
# Core tool
# ---------------------------------------------------------------------------

@tool
def check_availability(
    candidate_name: str,
    recommendation: str = "Interview",
    run_id: str = "",
) -> str:
    """
    Check interviewer availability and propose 3 interview slots for a candidate.

    Determines the interview type based on recommendation:
    - Interview → Technical Panel + HR Screening
    - Hold → HR Screening only (initial screen)

    Args:
        candidate_name: Candidate's full name
        recommendation: "Interview" | "Hold"
        run_id:         Run ID for audit

    Returns:
        JSON string of AvailabilityResult
    """
    start_ms = time.time() * 1000

    # Only schedule Interview or Hold-for-review candidates
    if recommendation not in ("Interview", "Hold"):
        result = AvailabilityResult(
            candidate_name=candidate_name,
            interview_type=InterviewType.HR,
            proposed_slots=[],
            notes=f"No scheduling required — candidate is {recommendation}",
        )
        return result.model_dump_json()

    # ------------------------------------------------------------------
    # Determine interview type
    # ------------------------------------------------------------------
    interview_type = InterviewType.TECHNICAL if recommendation == "Interview" else InterviewType.HR
    panel_key = "Technical Panel" if recommendation == "Interview" else "HR Screening"

    # ------------------------------------------------------------------
    # Generate 3 slots from static availability
    # ------------------------------------------------------------------
    proposed_slots = _generate_slots(panel_key, n=3)

    # ------------------------------------------------------------------
    # Enrich with LLM (adds context-aware notes)
    # ------------------------------------------------------------------
    try:
        client = get_llm_client()
        current_date = datetime.utcnow().strftime("%Y-%m-%d")
        raw = client.structured_invoke(
            prompt_template=AVAILABILITY_PROMPT,
            variables={
                "candidate_name": candidate_name,
                "recommendation": recommendation,
                "current_date": current_date,
            },
        )
        # Use LLM-proposed slots if valid
        if isinstance(raw, dict) and raw.get("proposed_slots"):
            llm_slots = raw["proposed_slots"][:3]
            proposed_slots = [
                InterviewSlot(
                    date=s.get("date", proposed_slots[i].date if i < len(proposed_slots) else ""),
                    time=s.get("time", proposed_slots[i].time if i < len(proposed_slots) else ""),
                    timezone=s.get("timezone", "Asia/Kolkata"),
                    interviewer=s.get("interviewer", panel_key),
                    duration_minutes=s.get("duration_minutes", 60),
                    format=InterviewFormat(s.get("format", "Video")),
                )
                for i, s in enumerate(llm_slots)
            ]
    except Exception as exc:
        logger.warning(f"LLM availability enrichment failed: {exc} — using static slots")

    # ------------------------------------------------------------------
    # Build result
    # ------------------------------------------------------------------
    result = AvailabilityResult(
        candidate_name=candidate_name,
        interview_type=interview_type,
        proposed_slots=proposed_slots,
        preferred_slot=0,
        notes=(
            f"3 slots proposed for {candidate_name} ({recommendation}). "
            f"Panel: {panel_key}. Please confirm preferred slot."
        ),
    )

    duration_ms = time.time() * 1000 - start_ms
    result_dict = result.model_dump(mode="json")
    result_dict["_tool_duration_ms"] = round(duration_ms, 2)

    logger.info(
        f"[check_availability] {candidate_name} → "
        f"{len(proposed_slots)} slots proposed | {duration_ms:.0f}ms"
    )

    return json.dumps(result_dict, default=str)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_slots(panel_key: str, n: int = 3) -> list[InterviewSlot]:
    """Generate n interview slots starting from the next business day."""
    window = AVAILABILITY_WINDOWS.get(panel_key, AVAILABILITY_WINDOWS["Technical Panel"])
    slots: list[InterviewSlot] = []
    current_date = datetime.utcnow()

    # Start from next business day
    candidate_date = current_date + timedelta(days=1)
    days_checked = 0

    while len(slots) < n and days_checked < 30:
        # Skip weekends
        if candidate_date.weekday() not in window["days"]:
            candidate_date += timedelta(days=1)
            days_checked += 1
            continue

        date_str = candidate_date.strftime("%Y-%m-%d")
        if date_str in BLOCKED_DATES:
            candidate_date += timedelta(days=1)
            days_checked += 1
            continue

        # Pick time slots for this date
        for time_str in window["slots"]:
            if len(slots) >= n:
                break
            slots.append(InterviewSlot(
                date=date_str,
                time=time_str,
                timezone="Asia/Kolkata",
                interviewer=panel_key,
                duration_minutes=window["duration"],
                format=InterviewFormat(window["format"]),
            ))

        candidate_date += timedelta(days=1)
        days_checked += 1

    return slots[:n]
