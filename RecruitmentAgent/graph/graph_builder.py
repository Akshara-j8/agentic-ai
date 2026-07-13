"""
TechVest Recruitment Agent — LangGraph Graph Builder
Compiles the complete StateGraph with nodes, conditional edges, and checkpointing.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from config.settings import get_settings
from graph.edges import (
    route_after_audit,
    route_after_availability,
    route_after_decision,
    route_after_guardrail,
    route_after_human_approval,
    route_after_parse,
    route_after_scheduler,
    route_after_score,
    route_from_plan,
)
from graph.nodes import (
    audit_node,
    availability_node,
    decision_node,
    finish_node,
    guardrail_node,
    human_approval_node,
    parse_resume_node,
    plan_node,
    scheduler_node,
    score_candidate_node,
)
from graph.state import AgentState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(*, use_checkpointer: bool = True) -> Any:
    """
    Construct and compile the TechVest Recruitment Agent graph.

    Graph topology:
        START → plan_node
        plan_node → [conditional: parse/score/guardrail/decision/approval/avail/scheduler/audit/finish]
        parse_resume_node → [conditional: parse next OR back to plan]
        score_candidate_node → [conditional: score next OR back to plan]
        guardrail_node → [conditional: decision OR finish (hard stop)]
        decision_node → [conditional: human_approval OR availability]
        human_approval_node → [conditional: availability OR finish (paused)]
        availability_node → [conditional: scheduler OR human_approval]
        scheduler_node → [conditional: availability (next) OR audit]
        audit_node → finish_node
        finish_node → END

    Args:
        use_checkpointer: Enable in-memory checkpointing for state persistence

    Returns:
        Compiled LangGraph CompiledStateGraph
    """
    settings = get_settings()

    # ------------------------------------------------------------------
    # Create StateGraph
    # ------------------------------------------------------------------
    graph = StateGraph(AgentState)

    # ------------------------------------------------------------------
    # Register nodes
    # ------------------------------------------------------------------
    graph.add_node("plan_node", plan_node)
    graph.add_node("parse_resume_node", parse_resume_node)
    graph.add_node("score_candidate_node", score_candidate_node)
    graph.add_node("guardrail_node", guardrail_node)
    graph.add_node("decision_node", decision_node)
    graph.add_node("human_approval_node", human_approval_node)
    graph.add_node("availability_node", availability_node)
    graph.add_node("scheduler_node", scheduler_node)
    graph.add_node("audit_node", audit_node)
    graph.add_node("finish_node", finish_node)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    graph.add_edge(START, "plan_node")

    # ------------------------------------------------------------------
    # Conditional edges from plan_node (LLM-driven routing)
    # ------------------------------------------------------------------
    graph.add_conditional_edges(
        "plan_node",
        route_from_plan,
        {
            "parse_resume_node": "parse_resume_node",
            "score_candidate_node": "score_candidate_node",
            "guardrail_node": "guardrail_node",
            "decision_node": "decision_node",
            "human_approval_node": "human_approval_node",
            "availability_node": "availability_node",
            "scheduler_node": "scheduler_node",
            "audit_node": "audit_node",
            "finish_node": "finish_node",
        },
    )

    # ------------------------------------------------------------------
    # Conditional edges from each work node
    # ------------------------------------------------------------------
    graph.add_conditional_edges(
        "parse_resume_node",
        route_after_parse,
        {
            "parse_resume_node": "parse_resume_node",
            "plan_node": "plan_node",
        },
    )

    graph.add_conditional_edges(
        "score_candidate_node",
        route_after_score,
        {
            "score_candidate_node": "score_candidate_node",
            "plan_node": "plan_node",
        },
    )

    graph.add_conditional_edges(
        "guardrail_node",
        route_after_guardrail,
        {
            "decision_node": "decision_node",
            "finish_node": "finish_node",
        },
    )

    graph.add_conditional_edges(
        "decision_node",
        route_after_decision,
        {
            "human_approval_node": "human_approval_node",
            "availability_node": "availability_node",
        },
    )

    graph.add_conditional_edges(
        "human_approval_node",
        route_after_human_approval,
        {
            "availability_node": "availability_node",
            "finish_node": "finish_node",
        },
    )

    graph.add_conditional_edges(
        "availability_node",
        route_after_availability,
        {
            "scheduler_node": "scheduler_node",
            "human_approval_node": "human_approval_node",
        },
    )

    graph.add_conditional_edges(
        "scheduler_node",
        route_after_scheduler,
        {
            "availability_node": "availability_node",
            "audit_node": "audit_node",
        },
    )

    graph.add_conditional_edges(
        "audit_node",
        route_after_audit,
        {
            "finish_node": "finish_node",
        },
    )

    # Terminal edge
    graph.add_edge("finish_node", END)

    # ------------------------------------------------------------------
    # Compile with optional checkpointer
    # ------------------------------------------------------------------
    compile_kwargs: dict[str, Any] = {
        "interrupt_before": ["human_approval_node"],
    }

    if use_checkpointer:
        compile_kwargs["checkpointer"] = MemorySaver()

    compiled = graph.compile(**compile_kwargs)

    logger.info(
        f"Graph compiled | nodes={len(graph.nodes)} | "
        f"recursion_limit={settings.recursion_limit} | "
        f"checkpointer={'memory' if use_checkpointer else 'none'}"
    )

    return compiled


# ---------------------------------------------------------------------------
# Run helper
# ---------------------------------------------------------------------------

def run_agent(
    initial_state: AgentState,
    *,
    thread_id: str | None = None,
    stream_events: bool = False,
) -> AgentState:
    """
    Execute the compiled agent graph on an initial state.

    Args:
        initial_state:  Fully initialised AgentState
        thread_id:      Checkpointer thread ID (default: run_id)
        stream_events:  If True, yield events (for Streamlit display)

    Returns:
        Final AgentState after graph execution
    """
    settings = get_settings()
    compiled_graph = build_graph(use_checkpointer=True)

    config: dict[str, Any] = {
        "recursion_limit": settings.recursion_limit,
        "configurable": {
            "thread_id": thread_id or initial_state.get("run_id", "default"),
        },
    }

    try:
        if stream_events:
            events = []
            for event in compiled_graph.stream(initial_state, config=config):
                events.append(event)
            # Return the last state snapshot
            final_state = compiled_graph.get_state(config).values
            return final_state
        else:
            result = compiled_graph.invoke(initial_state, config=config)
            return result
    except Exception as exc:
        logger.error(f"Graph execution failed: {exc}")
        raise


def resume_agent_after_approval(
    run_id: str,
    approved: bool,
    approver: str = "recruiter",
    notes: str = "",
) -> AgentState:
    """
    Resume the graph after human approval has been granted/denied.

    Args:
        run_id:   Thread ID / run ID
        approved: Whether the recruiter approved scheduling
        approver: Name of the approver
        notes:    Optional approval notes

    Returns:
        Updated AgentState
    """
    settings = get_settings()
    compiled_graph = build_graph(use_checkpointer=True)

    config: dict[str, Any] = {
        "recursion_limit": settings.recursion_limit,
        "configurable": {"thread_id": run_id},
    }

    # Update the human_approval field in the checkpointed state
    current_state = compiled_graph.get_state(config)
    if not current_state:
        raise ValueError(f"No checkpointed state found for run_id={run_id}")

    approval_update = {
        "human_approval": {
            "required": True,
            "pending": False,
            "approved": approved,
            "approver": approver,
            "approved_at": __import__("datetime").datetime.utcnow().isoformat(),
            "notes": notes,
            "candidates_pending": [],
        },
        "status": "running" if approved else "rejected",
    }

    # Inject update and resume
    compiled_graph.update_state(config, approval_update)
    result = compiled_graph.invoke(None, config=config)
    return result
