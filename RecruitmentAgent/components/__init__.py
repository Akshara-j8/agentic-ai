"""TechVest Recruitment Agent — Components package."""

from components.sidebar import render_dynamic_sidebar
# Legacy aliases kept for any remaining imports
try:
    from components.sidebar import render_sidebar  # type: ignore[attr-defined]
except ImportError:
    render_sidebar = render_dynamic_sidebar  # type: ignore[assignment]

def inject_css() -> None:
    """Legacy stub — CSS now injected inside app.py."""
    pass
from components.cards import render_candidate_card, render_shortlist_row
from components.charts import (
    render_score_bar_chart,
    render_radar_chart,
    render_gauge_chart,
    render_recommendation_pie,
    render_execution_timeline,
    render_rubric_weights,
)
from components.metrics import (
    render_kpi_row,
    render_status_banner,
    render_run_summary_card,
    render_agent_thinking_spinner,
    render_empty_state,
)
from components.timeline import (
    render_trajectory_timeline,
    render_event_type_legend,
    render_trajectory_stats,
)
from components.tables import (
    render_ranked_shortlist_table,
    render_audit_log_table,
    render_guardrail_events_table,
    render_interview_slots_table,
    render_scorecard_comparison_table,
)

__all__ = [
    "render_dynamic_sidebar", "render_sidebar", "inject_css",
    "render_candidate_card", "render_shortlist_row",
    "render_score_bar_chart", "render_radar_chart", "render_gauge_chart",
    "render_recommendation_pie", "render_execution_timeline", "render_rubric_weights",
    "render_kpi_row", "render_status_banner", "render_run_summary_card",
    "render_agent_thinking_spinner", "render_empty_state",
    "render_trajectory_timeline", "render_event_type_legend", "render_trajectory_stats",
    "render_ranked_shortlist_table", "render_audit_log_table",
    "render_guardrail_events_table", "render_interview_slots_table",
    "render_scorecard_comparison_table",
]
