"""
TechVest Recruitment Agent — Interview Scheduler Tool
Confirms interview slots and creates calendar entries after human approval.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from llm.models import AvailabilityResult, InterviewSlot

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core tool
# ---------------------------------------------------------------------------

@tool
def propose_interview(
    availability_json: str,
    slot_index: int = 0,
    human_approved: bool = True,
    run_id: str = "",
) -> str:
    """
    Confirm an interview slot for a candidate and persist the booking.

    Must be called ONLY after human approval has been granted.
    Saves the confirmed slot to the database.

    Args:
        availability_json: JSON string of AvailabilityResult
        slot_index:        Index of preferred slot (0 = first)
        human_approved:    Must be True to proceed
        run_id:            Run ID for audit

    Returns:
        JSON string with confirmation details
    """
    start_ms = time.time() * 1000

    # Safety gate — refuse without human approval
    if not human_approved:
        return json.dumps({
            "status": "blocked",
            "reason": "Human approval required before scheduling interviews.",
            "action": "Request human approval first.",
        })

    # Parse availability
    try:
        if isinstance(availability_json, str):
            data = json.loads(availability_json)
        else:
            data = availability_json
    except Exception as exc:
        return json.dumps({"status": "error", "reason": f"Invalid JSON: {exc}"})

    candidate_name = data.get("candidate_name", "Unknown")
    proposed_slots = data.get("proposed_slots", [])

    if not proposed_slots:
        return json.dumps({
            "status": "no_slots",
            "candidate_name": candidate_name,
            "reason": "No proposed slots available.",
        })

    # Select the preferred slot
    idx = min(slot_index, len(proposed_slots) - 1)
    selected_slot = proposed_slots[idx]

    # ------------------------------------------------------------------
    # Persist to database
    # ------------------------------------------------------------------
    try:
        from database.sqlite import get_db
        db = get_db()
        slot_data = {
            "candidate_name": candidate_name,
            "date": selected_slot.get("date", ""),
            "time": selected_slot.get("time", ""),
            "timezone": selected_slot.get("timezone", "Asia/Kolkata"),
            "interviewer": selected_slot.get("interviewer", ""),
            "duration_minutes": selected_slot.get("duration_minutes", 60),
            "format": selected_slot.get("format", "Video"),
            "interview_type": data.get("interview_type", "Technical"),
            "confirmed": True,
        }
        db.save_interview_slot(run_id or "unknown", slot_data)
    except Exception as exc:
        logger.warning(f"DB slot save failed: {exc}")

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------
    try:
        from database.audit import get_audit_logger
        audit = get_audit_logger(run_id=run_id)
        audit.info(
            "interview_scheduled",
            category=audit._get_db().__class__.__name__,  # type: ignore
            target=candidate_name,
            details={
                "date": selected_slot.get("date"),
                "time": selected_slot.get("time"),
                "interviewer": selected_slot.get("interviewer"),
                "format": selected_slot.get("format"),
            },
            run_id=run_id,
        )
    except Exception:
        pass

    duration_ms = time.time() * 1000 - start_ms

    confirmation = {
        "status": "confirmed",
        "candidate_name": candidate_name,
        "confirmed_slot": selected_slot,
        "interview_type": data.get("interview_type", "Technical"),
        "confirmation_id": f"TV-{run_id[:8].upper()}-{candidate_name[:4].upper()}",
        "confirmation_timestamp": datetime.utcnow().isoformat(),
        "notes": data.get("notes", ""),
        "_tool_duration_ms": round(duration_ms, 2),
    }

    logger.info(
        f"[propose_interview] {candidate_name} → "
        f"confirmed slot {idx} | "
        f"{selected_slot.get('date')} {selected_slot.get('time')} | "
        f"{duration_ms:.0f}ms"
    )

    return json.dumps(confirmation, default=str)


# ---------------------------------------------------------------------------
# Confirmation helper (used by UI)
# ---------------------------------------------------------------------------

def confirm_slot_for_candidate(
    candidate_name: str,
    slot: dict[str, Any],
    run_id: str,
    interviewer_override: str = "",
) -> dict[str, Any]:
    """
    Direct (non-tool) slot confirmation — used by the Streamlit UI
    when the recruiter manually selects a slot.
    """
    try:
        from database.sqlite import get_db
        db = get_db()
        slot_data = {
            "candidate_name": candidate_name,
            **slot,
            "confirmed": True,
            "interviewer": interviewer_override or slot.get("interviewer", ""),
        }
        slot_id = db.save_interview_slot(run_id, slot_data)
        return {"status": "confirmed", "slot_id": slot_id, "candidate": candidate_name}
    except Exception as exc:
        logger.error(f"Slot confirmation failed: {exc}")
        return {"status": "error", "reason": str(exc)}
