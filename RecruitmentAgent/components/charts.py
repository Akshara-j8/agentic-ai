"""
TechVest Recruitment Agent — Charts Component
Plotly dark-theme chart builders for the enterprise dashboard.
"""

from __future__ import annotations

from typing import Any, Optional

import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from config.settings import UIConstants


# ---------------------------------------------------------------------------
# Theme helpers
# ---------------------------------------------------------------------------

def _dark_layout(title: str = "", height: int = 320) -> dict[str, Any]:
    """Return a Plotly layout dict for the dark enterprise theme."""
    return dict(
        title=dict(text=title, font=dict(color="#94A3B8", size=13, family="Inter")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="Inter"),
        height=height,
        margin=dict(l=16, r=16, t=40 if title else 16, b=16),
        legend=dict(
            bgcolor="rgba(30,41,59,0.7)",
            bordercolor="rgba(255,255,255,0.06)",
            borderwidth=1,
            font=dict(size=11),
        ),
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.04)",
            zerolinecolor="rgba(255,255,255,0.06)",
            showgrid=True,
        ),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.04)",
            zerolinecolor="rgba(255,255,255,0.06)",
            showgrid=True,
        ),
    )


# ---------------------------------------------------------------------------
# Score comparison bar chart
# ---------------------------------------------------------------------------

def render_score_bar_chart(scorecards: list[dict[str, Any]]) -> None:
    """Horizontal bar chart comparing candidate weighted scores."""
    if not scorecards:
        st.info("No scorecards available yet.")
        return

    names = [s.get("candidate_name", "?") for s in scorecards]
    scores = [s.get("overall_weighted_score", 0) for s in scorecards]
    recs = [s.get("recommendation", "Reject") for s in scorecards]

    colors = [
        UIConstants.BADGE_INTERVIEW if r == "Interview"
        else UIConstants.BADGE_HOLD if r == "Hold"
        else UIConstants.BADGE_REJECT
        for r in recs
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=scores,
        y=names,
        orientation="h",
        marker=dict(
            color=colors,
            opacity=0.85,
            line=dict(color="rgba(255,255,255,0.1)", width=1),
        ),
        text=[f"{s:.1f}" for s in scores],
        textposition="outside",
        textfont=dict(color="#94A3B8", size=11),
        hovertemplate="<b>%{y}</b><br>Score: %{x:.1f}<extra></extra>",
    ))

    # Threshold lines
    fig.add_vline(x=72, line_dash="dot", line_color=UIConstants.BADGE_INTERVIEW, opacity=0.5,
                  annotation_text="Interview", annotation_font_color=UIConstants.BADGE_INTERVIEW,
                  annotation_font_size=10)
    fig.add_vline(x=50, line_dash="dot", line_color=UIConstants.BADGE_HOLD, opacity=0.5,
                  annotation_text="Hold", annotation_font_color=UIConstants.BADGE_HOLD,
                  annotation_font_size=10)

    layout = _dark_layout("Candidate Score Comparison", height=max(200, len(names) * 60 + 80))
    layout["xaxis"]["range"] = [0, 105]
    layout["showlegend"] = False
    fig.update_layout(**layout)

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Radar chart (skill profile)
# ---------------------------------------------------------------------------

def render_radar_chart(scorecard: dict[str, Any]) -> None:
    """Radar chart showing criterion scores for a single candidate."""
    from config.rubric import RUBRIC

    criteria = RUBRIC.criteria
    criterion_scores = scorecard.get("criterion_scores", {})

    labels = [c.label for c in criteria]
    values = [
        criterion_scores.get(c.key, {}).get("score", 0)
        if isinstance(criterion_scores.get(c.key), dict)
        else criterion_scores.get(c.key, 0)
        for c in criteria
    ]
    # Close the polygon
    labels_closed = labels + [labels[0]]
    values_closed = values + [values[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=labels_closed,
        fill="toself",
        fillcolor="rgba(99,102,241,0.15)",
        line=dict(color="#6366F1", width=2),
        marker=dict(color="#6366F1", size=6),
        name=scorecard.get("candidate_name", "Candidate"),
        hovertemplate="%{theta}: %{r:.1f}/10<extra></extra>",
    ))

    layout = _dark_layout(f"Skill Radar — {scorecard.get('candidate_name','?')}", height=340)
    layout["polar"] = dict(
        bgcolor="rgba(0,0,0,0)",
        radialaxis=dict(
            range=[0, 10],
            gridcolor="rgba(255,255,255,0.06)",
            tickcolor="rgba(255,255,255,0.3)",
            tickfont=dict(size=9, color="#64748B"),
            dtick=2,
        ),
        angularaxis=dict(
            gridcolor="rgba(255,255,255,0.06)",
            tickfont=dict(size=10, color="#94A3B8"),
        ),
    )
    del layout["xaxis"]
    del layout["yaxis"]
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Score gauge chart
# ---------------------------------------------------------------------------

def render_gauge_chart(score: float, candidate_name: str = "") -> None:
    """Gauge/speedometer chart for a single candidate's score."""
    color = UIConstants.score_color(score)

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        delta={"reference": 72, "valueformat": ".1f",
               "increasing": {"color": UIConstants.SUCCESS},
               "decreasing": {"color": UIConstants.DANGER}},
        number={"font": {"size": 36, "color": color, "family": "Inter"}, "valueformat": ".1f"},
        title={"text": candidate_name or "Score", "font": {"size": 12, "color": "#94A3B8"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#475569",
                     "tickfont": {"size": 10, "color": "#64748B"}},
            "bar": {"color": color, "thickness": 0.25},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 50], "color": "rgba(239,68,68,0.1)"},
                {"range": [50, 72], "color": "rgba(245,158,11,0.1)"},
                {"range": [72, 100], "color": "rgba(16,185,129,0.1)"},
            ],
            "threshold": {
                "line": {"color": color, "width": 4},
                "thickness": 0.75,
                "value": score,
            },
        },
    ))

    layout = _dark_layout("", height=240)
    del layout["xaxis"]
    del layout["yaxis"]
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Recommendation pie chart
# ---------------------------------------------------------------------------

def render_recommendation_pie(scorecards: list[dict[str, Any]]) -> None:
    """Donut chart showing Interview / Hold / Reject distribution."""
    if not scorecards:
        return

    counts: dict[str, int] = {"Interview": 0, "Hold": 0, "Reject": 0}
    for sc in scorecards:
        rec = sc.get("recommendation", "Reject")
        counts[rec] = counts.get(rec, 0) + 1

    labels = list(counts.keys())
    values = list(counts.values())
    colors = [UIConstants.BADGE_INTERVIEW, UIConstants.BADGE_HOLD, UIConstants.BADGE_REJECT]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.6,
        marker=dict(
            colors=colors,
            line=dict(color="#0F172A", width=3),
        ),
        textinfo="percent+value",
        textfont=dict(size=11, color="#F1F5F9"),
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>",
    ))

    fig.add_annotation(
        text=f"<b>{len(scorecards)}</b><br><span style='font-size:10'>Total</span>",
        x=0.5, y=0.5,
        font=dict(size=18, color="#F1F5F9", family="Inter"),
        showarrow=False,
    )

    layout = _dark_layout("Recommendations", height=280)
    del layout["xaxis"]
    del layout["yaxis"]
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Timeline bar chart (execution timeline)
# ---------------------------------------------------------------------------

def render_execution_timeline(trajectory: list[dict[str, Any]]) -> None:
    """Gantt-style timeline of agent trajectory events."""
    if not trajectory:
        st.info("No trajectory events yet.")
        return

    event_types = [e.get("event_type", "action") for e in trajectory]
    titles = [e.get("title", "")[:40] for e in trajectory]
    timestamps = [e.get("timestamp", "")[:19] for e in trajectory]
    durations = [e.get("duration_ms", 0) or 0 for e in trajectory]

    type_colors = {
        "thought": UIConstants.PRIMARY,
        "action": UIConstants.ACCENT,
        "observation": UIConstants.SUCCESS,
        "decision": UIConstants.SECONDARY,
        "guardrail": UIConstants.WARNING,
        "human_approval": UIConstants.INFO,
        "scheduler": UIConstants.SUCCESS,
        "error": UIConstants.DANGER,
    }

    colors = [type_colors.get(t, "#94A3B8") for t in event_types]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=list(range(len(trajectory))),
        y=[max(d, 50) for d in durations],
        marker=dict(color=colors, opacity=0.8,
                    line=dict(color="rgba(255,255,255,0.1)", width=1)),
        text=titles,
        textposition="outside",
        textfont=dict(size=9, color="#64748B"),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Duration: %{y:.0f}ms<br>"
            "<extra></extra>"
        ),
    ))

    layout = _dark_layout("Agent Execution Timeline", height=300)
    layout["yaxis"]["title"] = "Duration (ms)"
    layout["xaxis"]["title"] = "Event #"
    layout["showlegend"] = False
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Rubric weight chart
# ---------------------------------------------------------------------------

def render_rubric_weights() -> None:
    """Horizontal bar chart showing rubric criterion weights."""
    from config.rubric import RUBRIC

    labels = [c.label for c in RUBRIC.criteria]
    weights = [c.weight * 100 for c in RUBRIC.criteria]

    fig = go.Figure(go.Bar(
        x=weights,
        y=labels,
        orientation="h",
        marker=dict(
            color=UIConstants.CHART_PALETTE[:len(labels)],
            opacity=0.8,
        ),
        text=[f"{w:.0f}%" for w in weights],
        textposition="outside",
        textfont=dict(color="#94A3B8", size=10),
    ))

    layout = _dark_layout("Rubric Criterion Weights", height=280)
    layout["showlegend"] = False
    layout["xaxis"]["title"] = "Weight %"
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
