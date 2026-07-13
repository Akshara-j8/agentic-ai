"""
TechVest Recruitment Agent — Tables Component
Ranked shortlist, audit log, guardrail event, and slot tables.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from config.settings import UIConstants


def render_ranked_shortlist_table(decisions: list[dict[str, Any]]) -> None:
    """Render ranked candidate shortlist as a styled DataFrame."""
    if not decisions:
        st.info("No decisions yet.")
        return

    rows = []
    for d in sorted(decisions, key=lambda x: x.get("weighted_score", 0), reverse=True):
        rec = d.get("final_recommendation", "Reject")
        rows.append({
            "Rank":           d.get("rank", 0),
            "Candidate":      d.get("candidate_name", "?"),
            "Score":          round(d.get("weighted_score", 0), 1),
            "Recommendation": rec,
            "Confidence":     f"{d.get('confidence', 0)*100:.0f}%",
            "Priority":       "⭐" if d.get("priority_flag") else "",
            "Reasoning":      d.get("reasoning", "")[:80],
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Rank":           st.column_config.NumberColumn("🏆 Rank", width="small"),
            "Candidate":      st.column_config.TextColumn("👤 Candidate", width="medium"),
            "Score":          st.column_config.ProgressColumn("📊 Score", min_value=0, max_value=100, width="medium"),
            "Recommendation": st.column_config.TextColumn("🎯 Rec.", width="small"),
            "Confidence":     st.column_config.TextColumn("🎲 Conf.", width="small"),
            "Priority":       st.column_config.TextColumn("⭐", width="small"),
            "Reasoning":      st.column_config.TextColumn("💬 Reasoning", width="large"),
        },
    )


def render_audit_log_table(
    audit_events: list[dict[str, Any]],
    search: str = "",
    level_filter: str = "ALL",
    limit: int = 100,
) -> None:
    """Render audit log as a searchable, filterable table."""
    if not audit_events:
        st.info("No audit events recorded.")
        return

    events = list(audit_events)

    # Filter by level
    if level_filter != "ALL":
        events = [e for e in events if e.get("level", "INFO") == level_filter]

    # Search filter
    if search:
        q = search.lower()
        events = [
            e for e in events
            if q in str(e.get("action", "")).lower()
            or q in str(e.get("target", "")).lower()
            or q in str(e.get("details", "")).lower()
        ]

    events = events[:limit]

    rows = []
    for e in events:
        details = e.get("details", "")
        if isinstance(details, dict):
            details = json.dumps(details, default=str)[:80]
        rows.append({
            "Time":     str(e.get("timestamp", ""))[:19].replace("T", " "),
            "Level":    e.get("level", "INFO"),
            "Category": e.get("category", "system"),
            "Actor":    e.get("actor", "agent"),
            "Action":   e.get("action", "")[:50],
            "Target":   str(e.get("target", "") or "")[:30],
            "Details":  str(details)[:80],
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Time":     st.column_config.TextColumn("🕐 Time",     width="medium"),
            "Level":    st.column_config.TextColumn("📊 Level",    width="small"),
            "Category": st.column_config.TextColumn("📂 Category", width="small"),
            "Actor":    st.column_config.TextColumn("👤 Actor",    width="small"),
            "Action":   st.column_config.TextColumn("⚡ Action",   width="medium"),
            "Target":   st.column_config.TextColumn("🎯 Target",   width="small"),
            "Details":  st.column_config.TextColumn("📝 Details",  width="large"),
        },
    )


def render_guardrail_events_table(guardrail_events: list[dict[str, Any]]) -> None:
    """Render guardrail events table with colour-coded status."""
    if not guardrail_events:
        st.info("No guardrail events recorded.")
        return

    rows = []
    for e in guardrail_events:
        rows.append({
            "Time":      str(e.get("timestamp", ""))[:19].replace("T", " "),
            "Type":      e.get("guardrail_type", ""),
            "Status":    e.get("status", "PASS"),
            "Candidate": e.get("candidate_name", "") or "—",
            "Severity":  e.get("severity", "none"),
            "Action":    e.get("action_taken", "") or "—",
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Time":      st.column_config.TextColumn("🕐 Time",      width="medium"),
            "Type":      st.column_config.TextColumn("🛡️ Type",      width="medium"),
            "Status":    st.column_config.TextColumn("✅ Status",    width="small"),
            "Candidate": st.column_config.TextColumn("👤 Candidate", width="medium"),
            "Severity":  st.column_config.TextColumn("⚠️ Severity", width="small"),
            "Action":    st.column_config.TextColumn("🔧 Action",    width="medium"),
        },
    )


def render_interview_slots_table(slots: list[dict[str, Any]]) -> None:
    """Render confirmed / proposed interview slots."""
    if not slots:
        st.info("No interview slots scheduled yet.")
        return

    rows = []
    for s in slots:
        rows.append({
            "Candidate":   s.get("candidate_name", "?"),
            "Date":        s.get("slot_date", s.get("date", "")),
            "Time":        s.get("slot_time", s.get("time", "")),
            "Timezone":    s.get("timezone", "Asia/Kolkata"),
            "Interviewer": s.get("interviewer", ""),
            "Duration":    f"{s.get('duration_minutes', 60)} min",
            "Format":      s.get("format", "Video"),
            "Type":        s.get("interview_type", "Technical"),
            "Confirmed":   "✅" if s.get("confirmed") else "⏳",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_scorecard_comparison_table(scorecards: list[dict[str, Any]]) -> None:
    """Render side-by-side criterion score comparison table."""
    if not scorecards:
        st.info("No scorecards to compare.")
        return

    from config.rubric import RUBRIC

    rows = []
    for criterion in RUBRIC.criteria:
        row: dict[str, Any] = {
            "Criterion": criterion.label,
            "Weight":    f"{criterion.weight*100:.0f}%",
        }
        for sc in scorecards:
            name = sc.get("candidate_name", "?")
            cs = sc.get("criterion_scores", {}).get(criterion.key, {})
            score = cs.get("score", 0) if isinstance(cs, dict) else 0
            row[name] = round(float(score), 1)
        rows.append(row)

    # Overall row
    overall_row: dict[str, Any] = {"Criterion": "OVERALL", "Weight": "100%"}
    for sc in scorecards:
        overall_row[sc.get("candidate_name", "?")] = round(sc.get("overall_weighted_score", 0), 1)
    rows.append(overall_row)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
