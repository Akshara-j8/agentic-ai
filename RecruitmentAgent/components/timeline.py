"""
TechVest Recruitment Agent — Timeline Component
Beautiful event-by-event trajectory visualisation.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from config.settings import UIConstants

EVENT_META = {
    "thought":        {"icon": "🧠", "color": UIConstants.PRIMARY,   "label": "Thought"},
    "action":         {"icon": "⚡", "color": UIConstants.ACCENT,    "label": "Action"},
    "observation":    {"icon": "👁️", "color": UIConstants.SUCCESS,   "label": "Observation"},
    "decision":       {"icon": "🎯", "color": UIConstants.SECONDARY, "label": "Decision"},
    "guardrail":      {"icon": "🛡️", "color": UIConstants.WARNING,   "label": "Guardrail"},
    "human_approval": {"icon": "👤", "color": UIConstants.INFO,      "label": "Human Approval"},
    "scheduler":      {"icon": "📅", "color": UIConstants.SUCCESS,   "label": "Scheduler"},
    "error":          {"icon": "❌", "color": UIConstants.DANGER,    "label": "Error"},
}


def render_trajectory_timeline(
    trajectory: list[dict[str, Any]],
    filter_type: str = "all",
    show_metadata: bool = False,
) -> None:
    if not trajectory:
        st.markdown("""
        <div style="text-align:center;padding:3rem;color:#475569;">
            <div style="font-size:2.5rem;">📭</div>
            <div style="margin-top:0.5rem;font-size:0.88rem;">
                No trajectory events yet.<br>Run the agent to see the reasoning timeline.
            </div>
        </div>""", unsafe_allow_html=True)
        return

    events = trajectory if filter_type == "all" else [
        e for e in trajectory if e.get("event_type") == filter_type
    ]
    if not events:
        st.info(f"No '{filter_type}' events in this run.")
        return

    st.markdown(
        f'<div style="font-size:0.75rem;color:#64748B;margin-bottom:1rem;">'
        f'Showing {len(events)} of {len(trajectory)} events</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="timeline-container">', unsafe_allow_html=True)
    for i, event in enumerate(events):
        _render_single_event(event, i, show_metadata)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_single_event(event: dict[str, Any], index: int, show_metadata: bool) -> None:
    etype   = event.get("event_type", "action")
    meta    = EVENT_META.get(etype, EVENT_META["action"])
    color   = meta["color"]
    icon    = meta["icon"]
    label   = meta["label"]
    title   = event.get("title", "")
    content = event.get("content", "")
    ts      = event.get("timestamp", "")[:19].replace("T", " ")
    dur_ms  = event.get("duration_ms")
    success = event.get("success", True)
    node    = event.get("node", "")
    metadata = event.get("metadata", {})

    dur_str = f"{dur_ms:.0f}ms" if dur_ms else ""

    dot = (
        f"position:absolute;left:-1.65rem;top:1.1rem;"
        f"width:12px;height:12px;border-radius:50%;"
        f"background:{color};border:2px solid #0F172A;"
    )

    st.markdown(f"""
    <div class="timeline-event animate-fade-in" style="animation-delay:{index*0.04}s;">
        <div style="{dot}"></div>
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:0.5rem;">
            <div style="flex:1;">
                <div style="display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap;margin-bottom:0.3rem;">
                    <span style="font-size:1rem;">{icon}</span>
                    <span style="font-size:0.8rem;font-weight:700;color:#E2E8F0;">{title}</span>
                    <span style="background:{color}20;color:{color};font-size:0.65rem;font-weight:700;
                          padding:1px 7px;border-radius:99px;border:1px solid {color}40;
                          text-transform:uppercase;">{label}</span>
                    {'<span style="color:#EF4444;font-size:0.72rem;">⚠️ Failed</span>' if not success else ''}
                </div>
                <div style="color:#94A3B8;font-size:0.78rem;line-height:1.5;">{content}</div>
            </div>
            <div style="text-align:right;flex-shrink:0;">
                <div style="font-size:0.65rem;color:#475569;">{ts}</div>
                {f'<div style="font-size:0.65rem;color:#64748B;">{dur_str}</div>' if dur_str else ''}
                {f'<div style="font-size:0.62rem;color:#334155;font-family:monospace;">{node}</div>' if node else ''}
            </div>
        </div>
        {_meta_snippet(metadata) if show_metadata and metadata else ''}
    </div>""", unsafe_allow_html=True)


def _meta_snippet(metadata: dict) -> str:
    import json
    snippet = json.dumps(metadata, default=str)[:200]
    return (
        f'<div style="margin-top:0.5rem;font-family:monospace;font-size:0.68rem;'
        f'color:#475569;background:rgba(0,0,0,0.3);padding:0.4rem 0.6rem;'
        f'border-radius:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
        f'{snippet}</div>'
    )


def render_event_type_legend() -> None:
    st.markdown('<div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-bottom:1rem;">', unsafe_allow_html=True)
    for etype, meta in EVENT_META.items():
        c, ico, lbl = meta["color"], meta["icon"], meta["label"]
        st.markdown(
            f'<span style="background:{c}15;color:{c};font-size:0.72rem;font-weight:600;'
            f'padding:3px 10px;border-radius:99px;border:1px solid {c}30;">{ico} {lbl}</span>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def render_trajectory_stats(trajectory: list[dict]) -> None:
    if not trajectory:
        return
    counts: dict[str, int] = {}
    total_ms = 0.0
    for e in trajectory:
        counts[e.get("event_type", "action")] = counts.get(e.get("event_type", "action"), 0) + 1
        total_ms += e.get("duration_ms") or 0

    cols = st.columns(len(EVENT_META) + 1)
    for i, (etype, meta) in enumerate(EVENT_META.items()):
        with cols[i]:
            c = meta["color"]
            st.markdown(
                f'<div style="text-align:center;padding:0.4rem;">'
                f'<div style="font-size:1rem;">{meta["icon"]}</div>'
                f'<div style="font-size:0.9rem;font-weight:700;color:{c};">{counts.get(etype,0)}</div>'
                f'<div style="font-size:0.6rem;color:#64748B;">{meta["label"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    with cols[-1]:
        st.markdown(
            f'<div style="text-align:center;padding:0.4rem;">'
            f'<div style="font-size:1rem;">⏱️</div>'
            f'<div style="font-size:0.9rem;font-weight:700;color:#94A3B8;">{total_ms/1000:.1f}s</div>'
            f'<div style="font-size:0.6rem;color:#64748B;">Total</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
