"""
TechVest Recruitment Agent — KPI Metrics Component
Enterprise-grade KPI cards for the dashboard header.
"""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st

from config.settings import UIConstants


def render_kpi_row(
    candidates: int,
    interview_ready: int,
    avg_score: float,
    rejected: int,
    tool_calls: int,
    exec_time: float,
    guardrail_pass_rate: float,
) -> None:
    """
    Render a row of 7 KPI metric cards at the top of the dashboard.
    """
    kpis = [
        {
            "icon": "👥",
            "value": str(candidates),
            "label": "Candidates",
            "delta": None,
            "color": UIConstants.PRIMARY,
        },
        {
            "icon": "✅",
            "value": str(interview_ready),
            "label": "Interview Ready",
            "delta": None,
            "color": UIConstants.SUCCESS,
        },
        {
            "icon": "📊",
            "value": f"{avg_score:.1f}",
            "label": "Avg Score",
            "delta": None,
            "color": UIConstants.ACCENT,
        },
        {
            "icon": "❌",
            "value": str(rejected),
            "label": "Rejected",
            "delta": None,
            "color": UIConstants.DANGER,
        },
        {
            "icon": "⚡",
            "value": str(tool_calls),
            "label": "Tool Calls",
            "delta": None,
            "color": UIConstants.SECONDARY,
        },
        {
            "icon": "⏱️",
            "value": f"{exec_time:.1f}s",
            "label": "Exec Time",
            "delta": None,
            "color": UIConstants.INFO,
        },
        {
            "icon": "🛡️",
            "value": f"{guardrail_pass_rate:.0f}%",
            "label": "Guardrail Pass",
            "delta": None,
            "color": UIConstants.SUCCESS if guardrail_pass_rate >= 80 else UIConstants.WARNING,
        },
    ]

    cols = st.columns(len(kpis))
    for col, kpi in zip(cols, kpis):
        with col:
            _render_kpi_card(
                icon=kpi["icon"],
                value=kpi["value"],
                label=kpi["label"],
                color=kpi["color"],
            )


def _render_kpi_card(icon: str, value: str, label: str, color: str) -> None:
    """Render a single glassmorphism KPI card."""
    st.markdown(f"""
    <div class="kpi-card">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.5rem;">
            <span class="kpi-icon">{icon}</span>
        </div>
        <div class="kpi-value" style="background:linear-gradient(135deg, {color}, {color}aa);
             -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
            {value}
        </div>
        <div class="kpi-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def render_status_banner(state: str, message: str) -> None:
    """Render a status banner (success / warning / error / info)."""
    banner_class = {
        "success": "alert-success",
        "warning": "alert-warning",
        "error": "alert-danger",
        "info": "alert-info",
    }.get(state, "alert-info")

    icon = {
        "success": "✅",
        "warning": "⚠️",
        "error": "❌",
        "info": "ℹ️",
    }.get(state, "ℹ️")

    st.markdown(
        f'<div class="alert-banner {banner_class}">'
        f'<span>{icon}</span>'
        f'<span>{message}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_run_summary_card(summary: dict[str, Any]) -> None:
    """Render a run summary panel."""
    status = summary.get("status", "unknown")
    status_color = {
        "completed": UIConstants.SUCCESS,
        "running": UIConstants.ACCENT,
        "paused": UIConstants.WARNING,
        "error": UIConstants.DANGER,
    }.get(status, "#94A3B8")

    st.markdown(f"""
    <div class="glass-panel animate-fade-in">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
            <div>
                <div style="font-size:0.72rem; color:#64748B; text-transform:uppercase; letter-spacing:0.06em;">
                    Run ID
                </div>
                <div style="font-size:0.85rem; font-weight:600; color:#94A3B8; font-family:monospace;">
                    {summary.get('run_id','N/A')[:16]}…
                </div>
            </div>
            <div style="background:{status_color}20; color:{status_color};
                 padding:0.3rem 0.8rem; border-radius:99px; font-size:0.75rem; font-weight:700;
                 border:1px solid {status_color}40;">
                {status.upper()}
            </div>
        </div>
        <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:0.75rem;">
            <div style="text-align:center; padding:0.5rem; background:rgba(0,0,0,0.2); border-radius:8px;">
                <div style="font-size:1.2rem; font-weight:800; color:{UIConstants.SUCCESS};">
                    {summary.get('interview_count',0)}
                </div>
                <div style="font-size:0.65rem; color:#64748B;">Interview</div>
            </div>
            <div style="text-align:center; padding:0.5rem; background:rgba(0,0,0,0.2); border-radius:8px;">
                <div style="font-size:1.2rem; font-weight:800; color:{UIConstants.WARNING};">
                    {summary.get('hold_count',0)}
                </div>
                <div style="font-size:0.65rem; color:#64748B;">Hold</div>
            </div>
            <div style="text-align:center; padding:0.5rem; background:rgba(0,0,0,0.2); border-radius:8px;">
                <div style="font-size:1.2rem; font-weight:800; color:{UIConstants.DANGER};">
                    {summary.get('reject_count',0)}
                </div>
                <div style="font-size:0.65rem; color:#64748B;">Reject</div>
            </div>
        </div>
        <div style="margin-top:0.75rem; font-size:0.72rem; color:#64748B; display:flex; gap:1rem; flex-wrap:wrap;">
            <span>⏱️ {summary.get('duration_seconds',0):.1f}s</span>
            <span>⚡ {summary.get('total_tool_calls',0)} tool calls</span>
            <span>🤖 {summary.get('total_llm_calls',0)} LLM calls</span>
            <span>🏆 Top: {summary.get('top_candidate','N/A')}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_agent_thinking_spinner(message: str = "Agent is thinking...") -> None:
    """Show an animated thinking indicator."""
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:0.75rem; padding:1rem;
         background:rgba(99,102,241,0.08); border:1px solid rgba(99,102,241,0.2);
         border-radius:12px; margin:0.5rem 0;">
        <div class="spinner"></div>
        <div>
            <div style="font-size:0.85rem; font-weight:600; color:#A5B4FC;">{message}</div>
            <div style="font-size:0.72rem; color:#64748B;">Processing with LangGraph…</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_empty_state(
    icon: str = "🎯",
    title: str = "No Data Yet",
    description: str = "Run the agent to see results here.",
) -> None:
    """Render a placeholder empty-state panel."""
    st.markdown(f"""
    <div style="text-align:center; padding:4rem 2rem; color:#475569;">
        <div style="font-size:3.5rem; margin-bottom:0.75rem;">{icon}</div>
        <div style="font-size:1rem; font-weight:700; color:#64748B; margin-bottom:0.5rem;">{title}</div>
        <div style="font-size:0.82rem; color:#475569; max-width:300px; margin:0 auto;">{description}</div>
    </div>
    """, unsafe_allow_html=True)
