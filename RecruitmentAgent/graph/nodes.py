"""
TechVest Recruitment Agent — LangGraph Nodes
Each node is a pure function: AgentState → AgentState (partial update dict).
Nodes are autonomous — the LLM decides what to do next via the plan node.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any

from graph.state import (
    AgentState,
    add_trajectory_event,
    get_unscored_candidates,
    get_unscheduled_interview_candidates,
    increment_step,
    state_summary,
)
from llm.models import EventType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trajectory event builder helper
# ---------------------------------------------------------------------------

def _event(
    event_type: EventType,
    title: str,
    content: str,
    node: str = "",
    metadata: dict | None = None,
    success: bool = True,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type.value,
        "node": node,
        "title": title,
        "content": content,
        "metadata": metadata or {},
        "timestamp": datetime.utcnow().isoformat(),
        "duration_ms": duration_ms,
        "success": success,
    }


# ---------------------------------------------------------------------------
# NODE 1 — Plan Node
# ---------------------------------------------------------------------------

def plan_node(state: AgentState) -> dict[str, Any]:
    """
    Deterministic planning node.
    Inspects current state and decides the next action without LLM calls.
    The LLM is reserved for actual work (parsing, scoring, decisions).
    """
    node_name = "plan_node"
    start = time.time()

    parsed_count = len(state.get("parsed_profiles", []))
    resume_count = len(state.get("resume_inputs", []))
    scored_count = len(state.get("scored_candidates", []))
    iteration = state.get("iteration_count", 0)

    # Always use deterministic fallback — no LLM cost for routing
    result = _fallback_plan(state)

    next_action = result.get("next_action", "finalize")
    target = result.get("target_candidate")
    reasoning = result.get("reasoning", "")

    duration_ms = (time.time() - start) * 1000

    trajectory = list(state.get("trajectory", []))
    trajectory.append(_event(
        EventType.THOUGHT, "🧠 Planning Next Action",
        f"{reasoning}\n→ Next: **{next_action}**" + (f" for {target}" if target else ""),
        node=node_name, duration_ms=duration_ms,
    ))

    updates: dict[str, Any] = {
        "current_node": node_name,
        "next_action": next_action,
        "current_candidate": target,
        "plan_decision": result,
        "trajectory": trajectory,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "total_steps": state.get("total_steps", 0) + 1,
    }
    return updates


def _fallback_plan(state: AgentState) -> dict[str, Any]:
    """Rule-based fallback plan when LLM is unavailable."""
    resumes_left = state.get("resumes_to_process", [])
    unscored = get_unscored_candidates(state)
    has_decisions = bool(state.get("final_decisions", []))
    approved = state.get("human_approval", {}).get("approved", False)
    unscheduled = get_unscheduled_interview_candidates(state)

    if resumes_left:
        return {"next_action": "parse_resume", "target_candidate": resumes_left[0], "reasoning": "Resumes pending"}
    if unscored:
        return {"next_action": "score_candidate", "target_candidate": unscored[0], "reasoning": "Candidates unscored"}
    if not has_decisions:
        return {"next_action": "run_guardrails", "reasoning": "Ready for guardrail + decision pass"}
    if not approved:
        return {"next_action": "request_human_approval", "reasoning": "Awaiting human approval"}
    if unscheduled:
        return {"next_action": "check_availability", "target_candidate": unscheduled[0], "reasoning": "Schedule interviews"}
    return {"next_action": "finalize", "reasoning": "All work complete"}


# ---------------------------------------------------------------------------
# NODE 2 — Parse Resume Node
# ---------------------------------------------------------------------------

def parse_resume_node(state: AgentState) -> dict[str, Any]:
    """
    Parse the next unprocessed resume.
    Calls the parse_resume tool and updates state.
    """
    from tools.parser import parse_resume

    node_name = "parse_resume_node"
    start = time.time()

    resumes_to_process = list(state.get("resumes_to_process", []))
    if not resumes_to_process:
        return {"current_node": node_name}

    # Pick the first unprocessed resume
    target_filename = resumes_to_process[0]
    resume_inputs = state.get("resume_inputs", [])
    resume_data = next(
        (r for r in resume_inputs if r.get("filename") == target_filename), None
    )

    if not resume_data:
        logger.warning(f"Resume data not found for {target_filename}")
        resumes_to_process.pop(0)
        return {
            "current_node": node_name,
            "resumes_to_process": resumes_to_process,
            "resumes_processed": state.get("resumes_processed", []) + [target_filename],
        }

    resume_text = resume_data.get("content", "")
    run_id = state.get("run_id", "")

    trajectory = list(state.get("trajectory", []))
    trajectory.append(_event(
        EventType.ACTION, f"⚡ Parsing Resume: {target_filename}",
        f"Extracting structured profile from {target_filename} ({len(resume_text)} chars)",
        node=node_name,
    ))

    try:
        raw_result = parse_resume.invoke({
            "resume_text": resume_text,
            "filename": target_filename,
            "run_id": run_id,
        })
        profile = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
        success = True
        error_msg = None
    except Exception as exc:
        logger.error(f"parse_resume_node failed for {target_filename}: {exc}")
        profile = {"name": target_filename, "parse_error": str(exc), "resume_filename": target_filename}
        success = False
        error_msg = str(exc)

    duration_ms = (time.time() - start) * 1000
    candidate_name = profile.get("name", target_filename)
    injection = profile.get("injection_detected", False)

    obs_content = (
        f"Parsed: **{candidate_name}** | "
        f"Skills: {len(profile.get('skills', []))} | "
        f"Experience: {profile.get('years_experience', 0)}y | "
        f"{'⚠️ INJECTION DETECTED' if injection else '✅ Clean'}"
    )
    trajectory.append(_event(
        EventType.OBSERVATION, f"👁️ Profile Extracted: {candidate_name}",
        obs_content, node=node_name,
        metadata={"candidate": candidate_name, "injection": injection},
        success=success, duration_ms=duration_ms,
    ))

    # Persist profile
    try:
        from database.sqlite import get_db
        get_db().save_profile(run_id, profile)
    except Exception as exc:
        logger.warning(f"DB profile save failed: {exc}")

    # Update state
    parsed_profiles = list(state.get("parsed_profiles", [])) + [profile]
    resumes_to_process.pop(0)
    resumes_processed = list(state.get("resumes_processed", [])) + [target_filename]

    return {
        "current_node": node_name,
        "parsed_profiles": parsed_profiles,
        "resumes_to_process": resumes_to_process,
        "resumes_processed": resumes_processed,
        "current_candidate": candidate_name,
        "trajectory": trajectory,
        "total_steps": state.get("total_steps", 0) + 1,
        "total_tool_calls": state.get("total_tool_calls", 0) + 1,
    }


# ---------------------------------------------------------------------------
# NODE 3 — Score Candidate Node
# ---------------------------------------------------------------------------

def score_candidate_node(state: AgentState) -> dict[str, Any]:
    """
    Score the next unscored candidate against the rubric.
    """
    from tools.scorer import score_candidate

    node_name = "score_candidate_node"
    start = time.time()

    unscored = get_unscored_candidates(state)
    if not unscored:
        return {"current_node": node_name}

    target_name = state.get("current_candidate") or unscored[0]
    if target_name not in unscored:
        target_name = unscored[0]

    # Find the profile
    profile = next(
        (p for p in state.get("parsed_profiles", []) if p.get("name") == target_name),
        None,
    )
    if not profile:
        return {"current_node": node_name}

    run_id = state.get("run_id", "")
    jd = state.get("job_description", "")

    trajectory = list(state.get("trajectory", []))
    trajectory.append(_event(
        EventType.ACTION, f"⚡ Scoring: {target_name}",
        f"Evaluating {target_name} against 7-criterion weighted rubric",
        node=node_name,
    ))

    try:
        raw_result = score_candidate.invoke({
            "candidate_profile_json": json.dumps(profile),
            "job_description": jd,
            "run_id": run_id,
        })
        scorecard = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
        success = True
    except Exception as exc:
        logger.error(f"score_candidate_node failed for {target_name}: {exc}")
        scorecard = {
            "candidate_name": target_name,
            "overall_weighted_score": 0.0,
            "recommendation": "Reject",
            "error": str(exc),
        }
        success = False

    duration_ms = (time.time() - start) * 1000
    score = scorecard.get("overall_weighted_score", 0)
    rec = scorecard.get("recommendation", "Reject")
    penalty = scorecard.get("injection_penalty_applied", False)

    obs_content = (
        f"Score: **{score:.1f}/100** | "
        f"Recommendation: **{rec}** | "
        f"Confidence: {scorecard.get('confidence', 0)*100:.0f}% | "
        f"{'⚠️ Injection penalty applied' if penalty else '✅ No penalty'}"
    )
    trajectory.append(_event(
        EventType.OBSERVATION, f"👁️ Score Result: {target_name}",
        obs_content, node=node_name,
        metadata={"score": score, "recommendation": rec, "penalty": penalty},
        success=success, duration_ms=duration_ms,
    ))

    # Persist scorecard
    try:
        from database.sqlite import get_db
        get_db().save_scorecard(run_id, scorecard)
    except Exception as exc:
        logger.warning(f"DB scorecard save failed: {exc}")

    scored_candidates = list(state.get("scored_candidates", [])) + [target_name]
    scorecards = list(state.get("scorecards", [])) + [scorecard]

    return {
        "current_node": node_name,
        "scorecards": scorecards,
        "scored_candidates": scored_candidates,
        "trajectory": trajectory,
        "total_steps": state.get("total_steps", 0) + 1,
        "total_tool_calls": state.get("total_tool_calls", 0) + 1,
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
    }



# ---------------------------------------------------------------------------
# NODE 4 — Guardrail Node
# ---------------------------------------------------------------------------

def guardrail_node(state: AgentState) -> dict[str, Any]:
    """
    Run all guardrails: fairness check + injection summary + step/iteration limits.
    """
    from tools.fairness import fairness_check
    from config.settings import get_settings

    node_name = "guardrail_node"
    start = time.time()
    settings = get_settings()
    run_id = state.get("run_id", "")
    violations: list[str] = []

    trajectory = list(state.get("trajectory", []))
    trajectory.append(_event(
        EventType.GUARDRAIL, "🛡️ Running Guardrail Checks",
        "Executing: fairness audit, injection summary, step limit, iteration limit",
        node=node_name,
    ))

    # ------------------------------------------------------------------
    # Guardrail 1: Step limit
    # ------------------------------------------------------------------
    total_steps = state.get("total_steps", 0)
    step_ok = total_steps < settings.step_limit
    if not step_ok:
        violations.append(f"Step limit exceeded ({total_steps}/{settings.step_limit})")

    # ------------------------------------------------------------------
    # Guardrail 2: Iteration limit
    # ------------------------------------------------------------------
    iteration = state.get("iteration_count", 0)
    iter_ok = iteration < settings.max_iterations
    if not iter_ok:
        violations.append(f"Iteration limit exceeded ({iteration}/{settings.max_iterations})")

    # ------------------------------------------------------------------
    # Guardrail 3: Loop detection (same node repeated > 5 times)
    # ------------------------------------------------------------------
    trajectory_events = state.get("trajectory", [])
    recent_nodes = [e.get("node", "") for e in trajectory_events[-10:]]
    loop_detected = len(recent_nodes) >= 6 and len(set(recent_nodes[-6:])) == 1
    if loop_detected:
        violations.append("Loop detected — same node repeated 6+ times")

    # ------------------------------------------------------------------
    # Guardrail 4: Fairness check on scorecards
    # ------------------------------------------------------------------
    fairness_result = state.get("fairness_result")
    scorecards = state.get("scorecards", [])
    if scorecards and not fairness_result:
        try:
            raw = fairness_check.invoke({
                "scorecards_json": json.dumps(scorecards),
                "run_id": run_id,
            })
            fairness_result = json.loads(raw) if isinstance(raw, str) else raw
            if fairness_result.get("overall_fairness") == "FAIL":
                violations.append("Fairness audit FAILED — bias detected")
        except Exception as exc:
            logger.warning(f"Fairness check failed: {exc}")
            fairness_result = {"overall_fairness": "WARNING", "error": str(exc)}

    # ------------------------------------------------------------------
    # Guardrail 5: Injection summary
    # ------------------------------------------------------------------
    injection_count = sum(
        1 for p in state.get("parsed_profiles", [])
        if p.get("injection_detected", False)
    )
    if injection_count > 0:
        trajectory.append(_event(
            EventType.GUARDRAIL, f"⚠️ {injection_count} Injection Attack(s) Detected",
            f"{injection_count} resume(s) contained prompt injection attempts. "
            f"Score penalties have been applied. Attacks quarantined.",
            node=node_name,
            metadata={"injection_count": injection_count},
        ))

    duration_ms = (time.time() - start) * 1000
    overall_pass = len(violations) == 0 and not loop_detected

    guardrail_status = {
        "injection_checked": True,
        "fairness_checked": bool(fairness_result),
        "step_limit_ok": step_ok,
        "iteration_limit_ok": iter_ok,
        "loop_detected": loop_detected,
        "overall_pass": overall_pass,
        "last_checked_at": datetime.utcnow().isoformat(),
        "violations": violations,
    }

    result_content = (
        f"**{'✅ PASS' if overall_pass else '❌ FAIL'}** | "
        f"Step: {'✅' if step_ok else '❌'} | "
        f"Iteration: {'✅' if iter_ok else '❌'} | "
        f"Fairness: {fairness_result.get('overall_fairness', 'N/A') if fairness_result else 'N/A'} | "
        f"Loop: {'⚠️' if loop_detected else '✅'}"
    )
    trajectory.append(_event(
        EventType.GUARDRAIL, "🛡️ Guardrail Result",
        result_content, node=node_name,
        metadata=guardrail_status, success=overall_pass,
        duration_ms=duration_ms,
    ))

    return {
        "current_node": node_name,
        "guardrail_status": guardrail_status,
        "fairness_result": fairness_result,
        "trajectory": trajectory,
        "total_steps": state.get("total_steps", 0) + 1,
    }


# ---------------------------------------------------------------------------
# NODE 5 — Decision Node
# ---------------------------------------------------------------------------

def decision_node(state: AgentState) -> dict[str, Any]:
    """
    Make final hiring decisions across all scored candidates.
    Trusts the scorer's rubric-based recommendations — no LLM override.
    Uses LLM only for ranking summary text.
    """
    from config.rubric import THRESHOLDS, RUBRIC

    node_name = "decision_node"
    start = time.time()
    run_id = state.get("run_id", "")
    scorecards = state.get("scorecards", [])

    if not scorecards:
        return {"current_node": node_name}

    trajectory = list(state.get("trajectory", []))
    trajectory.append(_event(
        EventType.DECISION, "🎯 Making Final Decisions",
        f"Reviewing {len(scorecards)} scorecards for final hiring recommendations",
        node=node_name,
    ))

    # Build decisions from scorecard data — trust the rubric scores, not LLM re-evaluation
    sorted_sc = sorted(scorecards, key=lambda s: s.get("overall_weighted_score", 0), reverse=True)
    decisions = []
    for rank, sc in enumerate(sorted_sc, 1):
        score = sc.get("overall_weighted_score", 0)
        # Always recompute recommendation from current thresholds
        recommendation = RUBRIC.get_recommendation(score)
        decisions.append({
            "candidate_name": sc.get("candidate_name", ""),
            "final_recommendation": recommendation,
            "rank": rank,
            "weighted_score": round(score, 1),
            "confidence": sc.get("confidence", 0.7),
            "reasoning": sc.get("reasoning", ""),
            "priority_flag": rank == 1,
        })

    top_candidate = decisions[0]["candidate_name"] if decisions else ""

    # Persist to DB
    try:
        from database.sqlite import get_db
        db = get_db()
        for d in decisions:
            db.save_decision(run_id, d)
    except Exception as exc:
        logger.warning(f"DB decision save failed: {exc}")

    duration_ms = (time.time() - start) * 1000
    summary_lines = [
        f"**{d['candidate_name']}**: {d['final_recommendation']} (score: {d['weighted_score']:.1f})"
        for d in decisions
    ]
    trajectory.append(_event(
        EventType.DECISION, f"🎯 Decisions Complete — Top: {top_candidate}",
        "\n".join(summary_lines), node=node_name,
        metadata={"decisions": len(decisions), "top": top_candidate},
        duration_ms=duration_ms,
    ))

    return {
        "current_node": node_name,
        "final_decisions": decisions,
        "ranked_shortlist": decisions,
        "top_candidate": top_candidate,
        "trajectory": trajectory,
        "total_steps": state.get("total_steps", 0) + 1,
    }


def _fallback_decisions(scorecards: list[dict]) -> tuple[list[dict], str]:
    """Score-based decisions when LLM is unavailable."""
    sorted_sc = sorted(scorecards, key=lambda s: s.get("overall_weighted_score", 0), reverse=True)
    decisions = []
    for i, sc in enumerate(sorted_sc, 1):
        decisions.append({
            "candidate_name": sc.get("candidate_name", ""),
            "final_recommendation": sc.get("recommendation", "Reject"),
            "rank": i,
            "weighted_score": sc.get("overall_weighted_score", 0),
            "confidence": sc.get("confidence", 0.5),
            "reasoning": sc.get("reasoning", "Score-based ranking"),
            "priority_flag": i == 1,
        })
    top = sorted_sc[0].get("candidate_name", "") if sorted_sc else ""
    return decisions, top


# ---------------------------------------------------------------------------
# NODE 6 — Human Approval Node
# ---------------------------------------------------------------------------

def human_approval_node(state: AgentState) -> dict[str, Any]:
    """
    Pause point for human review before scheduling.
    In Streamlit, this node sets pending=True and waits for UI interaction.
    """
    node_name = "human_approval_node"
    approval = state.get("human_approval", {})

    # If already approved, pass through
    if approval.get("approved", False):
        return {
            "current_node": node_name,
            "human_approval": {**approval, "pending": False},
        }

    # Mark as pending — the graph will pause here via interrupt
    interview_candidates = [
        d.get("candidate_name", "")
        for d in state.get("final_decisions", [])
        if d.get("final_recommendation") == "Interview"
    ]

    trajectory = list(state.get("trajectory", []))
    trajectory.append(_event(
        EventType.HUMAN, "👤 Awaiting Human Approval",
        f"Recruitment manager approval required before scheduling interviews.\n"
        f"Candidates pending approval: {', '.join(interview_candidates)}",
        node=node_name,
        metadata={"candidates": interview_candidates},
    ))

    updated_approval = {
        **approval,
        "required": True,
        "pending": True,
        "approved": False,
        "candidates_pending": interview_candidates,
    }

    return {
        "current_node": node_name,
        "human_approval": updated_approval,
        "status": "paused",
        "trajectory": trajectory,
    }


# ---------------------------------------------------------------------------
# NODE 7 — Availability Node
# ---------------------------------------------------------------------------

def availability_node(state: AgentState) -> dict[str, Any]:
    """
    Check availability for Interview-recommended candidates.
    """
    from tools.availability import check_availability

    node_name = "availability_node"
    start = time.time()
    run_id = state.get("run_id", "")

    unscheduled = get_unscheduled_interview_candidates(state)
    target_name = state.get("current_candidate") or (unscheduled[0] if unscheduled else None)

    if not target_name:
        return {"current_node": node_name}

    # Find decision for this candidate
    decision = next(
        (d for d in state.get("final_decisions", []) if d.get("candidate_name") == target_name),
        {},
    )
    recommendation = decision.get("final_recommendation", "Interview")

    trajectory = list(state.get("trajectory", []))
    trajectory.append(_event(
        EventType.SCHEDULER, f"📅 Checking Availability: {target_name}",
        f"Fetching interview slots for {target_name} ({recommendation})",
        node=node_name,
    ))

    try:
        raw = check_availability.invoke({
            "candidate_name": target_name,
            "recommendation": recommendation,
            "run_id": run_id,
        })
        avail = json.loads(raw) if isinstance(raw, str) else raw
        success = True
    except Exception as exc:
        logger.error(f"availability_node failed for {target_name}: {exc}")
        avail = {"candidate_name": target_name, "proposed_slots": [], "error": str(exc)}
        success = False

    duration_ms = (time.time() - start) * 1000
    slot_count = len(avail.get("proposed_slots", []))

    trajectory.append(_event(
        EventType.SCHEDULER, f"📅 Slots Proposed: {target_name}",
        f"{slot_count} interview slots proposed for {target_name}",
        node=node_name,
        metadata={"slots": slot_count}, success=success,
        duration_ms=duration_ms,
    ))

    availability_results = list(state.get("availability_results", [])) + [avail]

    return {
        "current_node": node_name,
        "availability_results": availability_results,
        "trajectory": trajectory,
        "total_steps": state.get("total_steps", 0) + 1,
        "total_tool_calls": state.get("total_tool_calls", 0) + 1,
    }


# ---------------------------------------------------------------------------
# NODE 8 — Scheduler Node
# ---------------------------------------------------------------------------

def scheduler_node(state: AgentState) -> dict[str, Any]:
    """
    Confirm interview slots for approved candidates.
    """
    from tools.scheduler import propose_interview

    node_name = "scheduler_node"
    start = time.time()
    run_id = state.get("run_id", "")
    approval = state.get("human_approval", {})
    human_approved = approval.get("approved", False)

    availability_results = state.get("availability_results", [])
    scheduled = list(state.get("scheduled_candidates", []))

    trajectory = list(state.get("trajectory", []))

    new_scheduled: list[str] = []
    for avail in availability_results:
        cname = avail.get("candidate_name", "")
        if cname in scheduled:
            continue

        try:
            raw = propose_interview.invoke({
                "availability_json": json.dumps(avail),
                "slot_index": avail.get("preferred_slot", 0),
                "human_approved": human_approved,
                "run_id": run_id,
            })
            result = json.loads(raw) if isinstance(raw, str) else raw
            status = result.get("status", "unknown")
        except Exception as exc:
            logger.error(f"scheduler_node failed for {cname}: {exc}")
            status = "error"

        if status == "confirmed":
            new_scheduled.append(cname)
            trajectory.append(_event(
                EventType.SCHEDULER, f"✅ Interview Confirmed: {cname}",
                f"Interview scheduled for {cname}",
                node=node_name,
            ))
        elif status == "blocked":
            trajectory.append(_event(
                EventType.HUMAN, f"⏸️ Blocked: {cname}",
                "Human approval required before confirming interview.",
                node=node_name, success=False,
            ))

    duration_ms = (time.time() - start) * 1000

    return {
        "current_node": node_name,
        "scheduled_candidates": scheduled + new_scheduled,
        "trajectory": trajectory,
        "total_steps": state.get("total_steps", 0) + 1,
        "total_tool_calls": state.get("total_tool_calls", 0) + 1,
    }


# ---------------------------------------------------------------------------
# NODE 9 — Audit Node
# ---------------------------------------------------------------------------

def audit_node(state: AgentState) -> dict[str, Any]:
    """
    Persist the complete run audit trail to the database.
    """
    from database.audit import get_audit_logger
    from database.sqlite import get_db

    node_name = "audit_node"
    run_id = state.get("run_id", "")

    try:
        audit = get_audit_logger(run_id=run_id)
        summary = state_summary(state)
        audit.info(
            "run_audit_snapshot",
            details=summary,
            run_id=run_id,
        )

        # Persist all trajectory events
        db = get_db()
        for event in state.get("trajectory", []):
            try:
                db.save_trajectory_event(run_id, event)
            except Exception:
                pass
    except Exception as exc:
        logger.error(f"audit_node failed: {exc}")

    trajectory = list(state.get("trajectory", []))
    trajectory.append(_event(
        EventType.ACTION, "📋 Audit Trail Persisted",
        f"Run {run_id[:8]} audit saved — {len(state.get('trajectory', []))} events",
        node=node_name,
    ))

    return {
        "current_node": node_name,
        "trajectory": trajectory,
    }


# ---------------------------------------------------------------------------
# NODE 10 — Finish Node
# ---------------------------------------------------------------------------

def finish_node(state: AgentState) -> dict[str, Any]:
    """
    Finalise the agent run — compute summary stats and mark complete.
    """
    from database.sqlite import get_db

    node_name = "finish_node"
    run_id = state.get("run_id", "")
    start_ms = state.get("execution_start_ms", 0)
    end_ms = time.time() * 1000
    duration_sec = (end_ms - start_ms) / 1000

    scorecards = state.get("scorecards", [])
    decisions = state.get("final_decisions", [])

    interview_count = sum(1 for d in decisions if d.get("final_recommendation") == "Interview")
    hold_count = sum(1 for d in decisions if d.get("final_recommendation") == "Hold")
    reject_count = sum(1 for d in decisions if d.get("final_recommendation") == "Reject")
    avg_score = (
        sum(s.get("overall_weighted_score", 0) for s in scorecards) / len(scorecards)
        if scorecards else 0.0
    )
    injection_detected = any(
        p.get("injection_detected", False) for p in state.get("parsed_profiles", [])
    )

    summary = {
        "status": "completed",
        "completed_at": datetime.utcnow().isoformat(),
        "total_candidates": len(scorecards),
        "interview_count": interview_count,
        "hold_count": hold_count,
        "reject_count": reject_count,
        "avg_score": round(avg_score, 2),
        "top_candidate": state.get("top_candidate", ""),
        "total_tool_calls": state.get("total_tool_calls", 0),
        "total_llm_calls": state.get("total_llm_calls", 0),
        "injection_detected": int(injection_detected),
        "fairness_status": state.get("fairness_result", {}).get("overall_fairness", "N/A"),
        "duration_seconds": round(duration_sec, 2),
    }

    try:
        get_db().complete_run(run_id, summary)
    except Exception as exc:
        logger.warning(f"finish_node DB update failed: {exc}")

    trajectory = list(state.get("trajectory", []))
    trajectory.append(_event(
        EventType.DECISION, "🏁 Agent Run Complete",
        f"✅ All {len(scorecards)} candidates processed in {duration_sec:.1f}s\n"
        f"Interview: {interview_count} | Hold: {hold_count} | Reject: {reject_count}\n"
        f"Top candidate: {state.get('top_candidate', 'N/A')} | "
        f"Avg score: {avg_score:.1f}",
        node=node_name,
        metadata=summary,
    ))

    return {
        "current_node": node_name,
        "status": "completed",
        "execution_end_ms": end_ms,
        "trajectory": trajectory,
    }
