"""
TechVest Recruitment Agent — LangGraph Edge Routing
Conditional edge functions that determine the next node based on state.
The LLM's plan_decision drives the primary routing — not hardcoded rules.
"""

from __future__ import annotations

import logging
from typing import Literal

from graph.state import (
    AgentState,
    get_unscored_candidates,
    get_unscheduled_interview_candidates,
    is_complete,
)
from config.settings import get_settings

logger = logging.getLogger(__name__)

# Type alias for node name literals
NodeName = str


# ---------------------------------------------------------------------------
# Primary router — reads LLM plan decision
# ---------------------------------------------------------------------------

def route_from_plan(state: AgentState) -> NodeName:
    """
    Route after plan_node based on what the LLM decided to do next.
    Falls back to deterministic routing if the plan is missing.
    """
    settings = get_settings()

    # Hard stops take priority over LLM decisions
    guardrail = state.get("guardrail_status", {})
    if guardrail.get("loop_detected", False):
        logger.warning("Loop detected — routing to finish")
        return "finish_node"

    if state.get("iteration_count", 0) >= settings.max_iterations:
        logger.warning("Max iterations reached — routing to finish")
        return "finish_node"

    if state.get("total_steps", 0) >= settings.step_limit:
        logger.warning("Step limit reached — routing to finish")
        return "finish_node"

    # Read LLM's decision
    next_action = state.get("next_action", "")

    action_map: dict[str, NodeName] = {
        "parse_resume": "parse_resume_node",
        "score_candidate": "score_candidate_node",
        "run_guardrails": "guardrail_node",
        "check_availability": "availability_node",
        "request_human_approval": "human_approval_node",
        "finalize": "decision_node",
        "finish": "finish_node",
        "schedule_interview": "scheduler_node",
        "audit": "audit_node",
    }

    if next_action in action_map:
        return action_map[next_action]

    # Deterministic fallback routing
    return _deterministic_route(state)


def _deterministic_route(state: AgentState) -> NodeName:
    """Stateful routing when LLM plan is absent or unrecognised."""
    resumes_left = state.get("resumes_to_process", [])
    if resumes_left:
        return "parse_resume_node"

    unscored = get_unscored_candidates(state)
    if unscored:
        return "score_candidate_node"

    if not state.get("final_decisions"):
        return "guardrail_node"

    approval = state.get("human_approval", {})
    if approval.get("required", True) and not approval.get("approved", False):
        return "human_approval_node"

    unscheduled = get_unscheduled_interview_candidates(state)
    if unscheduled:
        return "availability_node"

    scheduled = set(state.get("scheduled_candidates", []))
    avail_results = state.get("availability_results", [])
    unconfirmed = [
        a for a in avail_results
        if a.get("candidate_name") not in scheduled
    ]
    if unconfirmed and approval.get("approved", False):
        return "scheduler_node"

    return "audit_node"


# ---------------------------------------------------------------------------
# Post-parse router
# ---------------------------------------------------------------------------

def route_after_parse(state: AgentState) -> NodeName:
    """
    After parsing a resume:
    - More resumes? → parse next
    - All parsed? → back to plan
    """
    if state.get("resumes_to_process"):
        return "parse_resume_node"
    return "plan_node"


# ---------------------------------------------------------------------------
# Post-score router
# ---------------------------------------------------------------------------

def route_after_score(state: AgentState) -> NodeName:
    """
    After scoring a candidate:
    - More to score? → score next
    - All scored? → back to plan
    """
    unscored = get_unscored_candidates(state)
    if unscored:
        return "score_candidate_node"
    return "plan_node"


# ---------------------------------------------------------------------------
# Post-guardrail router
# ---------------------------------------------------------------------------

def route_after_guardrail(state: AgentState) -> NodeName:
    """
    After guardrail check:
    - Hard stop? → finish
    - Pass? → decision node
    """
    guardrail = state.get("guardrail_status", {})
    if guardrail.get("loop_detected") or not guardrail.get("iteration_limit_ok", True):
        return "finish_node"
    return "decision_node"


# ---------------------------------------------------------------------------
# Post-decision router
# ---------------------------------------------------------------------------

def route_after_decision(state: AgentState) -> NodeName:
    """
    After decisions are made:
    - Human approval required and not yet given? → human_approval_node
    - Otherwise → availability_node
    """
    approval = state.get("human_approval", {})
    if approval.get("required", True) and not approval.get("approved", False):
        return "human_approval_node"
    return "availability_node"


# ---------------------------------------------------------------------------
# Post-human-approval router
# ---------------------------------------------------------------------------

def route_after_human_approval(state: AgentState) -> NodeName:
    """
    After human approval node:
    - Approved? → availability_node
    - Still pending? → stay paused (finish to prevent infinite loop)
    """
    approval = state.get("human_approval", {})
    if approval.get("approved", False):
        return "availability_node"
    # Pause — the graph will be re-invoked after UI action
    return "finish_node"


# ---------------------------------------------------------------------------
# Post-availability router
# ---------------------------------------------------------------------------

def route_after_availability(state: AgentState) -> NodeName:
    """
    After checking availability:
    - Human approved? → scheduler
    - Otherwise → wait (human_approval)
    """
    approval = state.get("human_approval", {})
    if approval.get("approved", False):
        return "scheduler_node"
    return "human_approval_node"


# ---------------------------------------------------------------------------
# Post-scheduler router
# ---------------------------------------------------------------------------

def route_after_scheduler(state: AgentState) -> NodeName:
    """
    After scheduling:
    - More unscheduled? → availability for next candidate
    - Done? → audit
    """
    unscheduled = get_unscheduled_interview_candidates(state)
    if unscheduled:
        return "availability_node"
    return "audit_node"


# ---------------------------------------------------------------------------
# Post-audit router
# ---------------------------------------------------------------------------

def route_after_audit(state: AgentState) -> NodeName:
    """Always proceed to finish after audit."""
    return "finish_node"
