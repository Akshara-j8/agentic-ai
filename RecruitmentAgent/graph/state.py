"""
TechVest Recruitment Agent — LangGraph State
Defines the complete state TypedDict that flows through every graph node.
All fields are Optional to support partial updates at each node.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Optional

from langgraph.graph import MessagesState
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Helper: reducer for appending to lists without overwriting
# ---------------------------------------------------------------------------

def append_list(existing: list, new_items: list) -> list:
    """LangGraph reducer: append new items to existing list."""
    if not new_items:
        return existing or []
    return (existing or []) + (new_items if isinstance(new_items, list) else [new_items])


# ---------------------------------------------------------------------------
# Sub-state types (typed dicts for structured fields)
# ---------------------------------------------------------------------------

class ResumeInput(TypedDict, total=False):
    filename: str
    content: str          # Raw text extracted from PDF
    uploaded_at: str


class GuardrailStatus(TypedDict, total=False):
    injection_checked: bool
    fairness_checked: bool
    step_limit_ok: bool
    iteration_limit_ok: bool
    loop_detected: bool
    overall_pass: bool
    last_checked_at: str
    violations: list[str]


class HumanApprovalStatus(TypedDict, total=False):
    required: bool
    pending: bool
    approved: bool
    approver: str
    approved_at: str
    notes: str
    candidates_pending: list[str]


# ---------------------------------------------------------------------------
# Main agent state
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    """
    Complete LangGraph state for the TechVest Recruitment Agent.

    Every field is Optional (total=False) to allow partial updates.
    The graph passes this state through all nodes and edges.
    """

    # ------------------------------------------------------------------
    # Run metadata
    # ------------------------------------------------------------------
    run_id: str
    session_id: str
    started_at: str
    current_node: str
    iteration_count: int
    total_steps: int
    status: str                          # "running" | "paused" | "completed" | "error"
    error_message: Optional[str]

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------
    job_description: str                 # Full JD text
    rubric: dict[str, Any]               # Serialised rubric (from config)
    resume_inputs: list[ResumeInput]     # Uploaded resume files

    # ------------------------------------------------------------------
    # Processing pipeline
    # ------------------------------------------------------------------
    resumes_to_process: list[str]        # Filenames not yet parsed
    resumes_processed: list[str]         # Filenames already parsed

    # ------------------------------------------------------------------
    # Parsed profiles
    # ------------------------------------------------------------------
    parsed_profiles: list[dict[str, Any]]     # ParsedProfile dicts
    current_candidate: Optional[str]          # Name being processed now

    # ------------------------------------------------------------------
    # Scorecards
    # ------------------------------------------------------------------
    scorecards: list[dict[str, Any]]          # Scorecard dicts
    scored_candidates: list[str]              # Names already scored

    # ------------------------------------------------------------------
    # Availability & scheduling
    # ------------------------------------------------------------------
    availability_results: list[dict[str, Any]]  # AvailabilityResult dicts
    scheduled_candidates: list[str]

    # ------------------------------------------------------------------
    # Final decisions / ranking
    # ------------------------------------------------------------------
    final_decisions: list[dict[str, Any]]    # CandidateDecision dicts
    ranked_shortlist: list[dict[str, Any]]   # Ordered shortlist for UI
    top_candidate: Optional[str]

    # ------------------------------------------------------------------
    # Trajectory & audit
    # ------------------------------------------------------------------
    trajectory: list[dict[str, Any]]         # TrajectoryEvent dicts (reducer: append)
    audit_events: list[dict[str, Any]]       # Lightweight audit event list

    # ------------------------------------------------------------------
    # Guardrails
    # ------------------------------------------------------------------
    guardrail_status: GuardrailStatus
    injection_results: list[dict[str, Any]]  # InjectionResult dicts per candidate
    fairness_result: Optional[dict[str, Any]]  # FairnessResult dict

    # ------------------------------------------------------------------
    # Human approval
    # ------------------------------------------------------------------
    human_approval: HumanApprovalStatus

    # ------------------------------------------------------------------
    # Plan / LLM reasoning
    # ------------------------------------------------------------------
    plan_decision: Optional[dict[str, Any]]   # PlanDecision dict
    next_action: Optional[str]                # What the planner decided to do next

    # ------------------------------------------------------------------
    # LLM usage stats
    # ------------------------------------------------------------------
    total_tool_calls: int
    total_llm_calls: int
    total_tokens_used: int
    execution_start_ms: float
    execution_end_ms: Optional[float]


# ---------------------------------------------------------------------------
# State factory
# ---------------------------------------------------------------------------

def create_initial_state(
    run_id: str,
    job_description: str,
    resume_inputs: list[ResumeInput],
    rubric_dict: Optional[dict[str, Any]] = None,
    session_id: Optional[str] = None,
) -> AgentState:
    """
    Create a fresh AgentState for a new agent run.

    Args:
        run_id:          Unique run identifier
        job_description: Full job description text
        resume_inputs:   List of {filename, content} dicts
        rubric_dict:     Serialised rubric (defaults to RUBRIC.to_dict())
        session_id:      Optional Streamlit session ID

    Returns:
        Fully initialised AgentState
    """
    import time
    from config.rubric import RUBRIC

    filenames = [r["filename"] for r in resume_inputs if r.get("filename")]

    return AgentState(
        # Metadata
        run_id=run_id,
        session_id=session_id or run_id,
        started_at=datetime.utcnow().isoformat(),
        current_node="",
        iteration_count=0,
        total_steps=0,
        status="running",
        error_message=None,

        # Inputs
        job_description=job_description,
        rubric=rubric_dict or RUBRIC.to_dict(),
        resume_inputs=resume_inputs,

        # Pipeline tracking
        resumes_to_process=list(filenames),
        resumes_processed=[],

        # Empty accumulators
        parsed_profiles=[],
        current_candidate=None,
        scorecards=[],
        scored_candidates=[],
        availability_results=[],
        scheduled_candidates=[],
        final_decisions=[],
        ranked_shortlist=[],
        top_candidate=None,
        trajectory=[],
        audit_events=[],

        # Guardrails
        guardrail_status=GuardrailStatus(
            injection_checked=False,
            fairness_checked=False,
            step_limit_ok=True,
            iteration_limit_ok=True,
            loop_detected=False,
            overall_pass=True,
            violations=[],
        ),
        injection_results=[],
        fairness_result=None,

        # Human approval
        human_approval=HumanApprovalStatus(
            required=True,
            pending=False,
            approved=False,
            approver="",
            notes="",
            candidates_pending=[],
        ),

        # Plan
        plan_decision=None,
        next_action=None,

        # Stats
        total_tool_calls=0,
        total_llm_calls=0,
        total_tokens_used=0,
        execution_start_ms=time.time() * 1000,
        execution_end_ms=None,
    )


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def add_trajectory_event(state: AgentState, event: dict[str, Any]) -> AgentState:
    """Return updated state with new trajectory event appended."""
    trajectory = list(state.get("trajectory", []))
    trajectory.append(event)
    return {**state, "trajectory": trajectory}  # type: ignore[return-value]


def increment_step(state: AgentState) -> AgentState:
    """Increment both iteration_count and total_steps."""
    return {
        **state,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "total_steps": state.get("total_steps", 0) + 1,
    }  # type: ignore[return-value]


def get_unscored_candidates(state: AgentState) -> list[str]:
    """Return names of candidates who have been parsed but not yet scored."""
    parsed_names = {p.get("name", "") for p in state.get("parsed_profiles", [])}
    scored_names = set(state.get("scored_candidates", []))
    return sorted(parsed_names - scored_names)


def get_unscheduled_interview_candidates(state: AgentState) -> list[str]:
    """Return names of Interview-recommended candidates not yet scheduled."""
    interview_names = {
        d.get("candidate_name", "")
        for d in state.get("final_decisions", [])
        if d.get("final_recommendation") == "Interview"
    }
    scheduled = set(state.get("scheduled_candidates", []))
    return sorted(interview_names - scheduled)


def is_complete(state: AgentState) -> bool:
    """
    Determine if the agent has finished all required work.
    Complete when: all resumes parsed + scored + decisions made + approved.
    """
    resumes_left = state.get("resumes_to_process", [])
    unscored = get_unscored_candidates(state)
    has_decisions = bool(state.get("final_decisions"))
    approval_done = (
        not state.get("human_approval", {}).get("required", True)
        or state.get("human_approval", {}).get("approved", False)
    )
    return (
        len(resumes_left) == 0
        and len(unscored) == 0
        and has_decisions
        and approval_done
    )


def state_summary(state: AgentState) -> dict[str, Any]:
    """Return a compact summary of the current state for logging."""
    return {
        "run_id": state.get("run_id", ""),
        "status": state.get("status", "unknown"),
        "iteration": state.get("iteration_count", 0),
        "steps": state.get("total_steps", 0),
        "resumes_pending": len(state.get("resumes_to_process", [])),
        "parsed": len(state.get("parsed_profiles", [])),
        "scored": len(state.get("scored_candidates", [])),
        "decisions": len(state.get("final_decisions", [])),
        "trajectory_events": len(state.get("trajectory", [])),
        "guardrail_pass": state.get("guardrail_status", {}).get("overall_pass", True),
        "current_node": state.get("current_node", ""),
        "next_action": state.get("next_action", ""),
    }
