"""
TechVest Recruitment Agent — Dashboard Page
Main overview: KPI cards, charts, shortlist, run summary.
"""

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from components import inject_css
from components.metrics import render_kpi_row, render_status_banner, render_run_summary_card, render_empty_state
from components.charts import render_score_bar_chart, render_recommendation_pie, render_execution_timeline, render_rubric_weights
from components.cards import render_shortlist_row
from components.tables import render_ranked_shortlist_table


def main():
    st.set_page_config(
        page_title="TechVest — Dashboard",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

    # ── Page header ──────────────────────────────────────────────────
    st.markdown("""
    <div class="page-header">
        <div class="breadcrumb">TechVest Recruitment Agent</div>
        <h1>📊 Dashboard</h1>
        <p>Real-time overview of the autonomous recruitment pipeline</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Pull state ────────────────────────────────────────────────────
    state       = st.session_state.get("agent_state", {})
    scorecards  = state.get("scorecards", [])
    decisions   = state.get("final_decisions", [])
    trajectory  = state.get("trajectory", [])
    run_summary = st.session_state.get("last_run_summary", {})
    status      = state.get("status", "idle")

    # Status banner
    if status == "running":
        render_status_banner("info", "Agent is running — results update automatically.")
    elif status == "paused":
        render_status_banner("warning", "⏸️ Agent paused — awaiting human approval before scheduling.")
    elif status == "completed":
        render_status_banner("success", f"✅ Run complete — {len(scorecards)} candidates processed.")
    elif status == "error":
        render_status_banner("error", f"❌ Error: {state.get('error_message','Unknown error')}")

    # ── KPI row ───────────────────────────────────────────────────────
    total    = len(scorecards)
    inter    = sum(1 for s in scorecards if s.get("recommendation") == "Interview")
    hold     = sum(1 for s in scorecards if s.get("recommendation") == "Hold")
    rej      = sum(1 for s in scorecards if s.get("recommendation") == "Reject")
    avg_sc   = sum(s.get("overall_weighted_score", 0) for s in scorecards) / max(total, 1)
    tool_c   = state.get("total_tool_calls", 0)
    start_ms = state.get("execution_start_ms", 0)
    end_ms   = state.get("execution_end_ms") or (__import__("time").time() * 1000 if status == "running" else start_ms)
    exec_t   = (end_ms - start_ms) / 1000 if start_ms else 0

    gs       = state.get("guardrail_status", {})
    g_checks = [gs.get("injection_checked", False), gs.get("fairness_checked", False),
                gs.get("step_limit_ok", True), gs.get("iteration_limit_ok", True),
                not gs.get("loop_detected", False)]
    g_rate   = (sum(g_checks) / len(g_checks) * 100) if g_checks else 100

    st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
    render_kpi_row(total, inter, avg_sc, rej, tool_c, exec_t, g_rate)

    st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)

    if not scorecards:
        render_empty_state("🚀", "No Results Yet", "Upload a JD and resumes, then click ▶ Run Agent in the sidebar.")
        return

    # ── Charts row ────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="chart-card"><div class="chart-title">Score Comparison</div>', unsafe_allow_html=True)
        render_score_bar_chart(scorecards)
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="chart-card"><div class="chart-title">Recommendation Split</div>', unsafe_allow_html=True)
        render_recommendation_pie(scorecards)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    with col3:
        st.markdown('<div class="chart-card"><div class="chart-title">Execution Timeline</div>', unsafe_allow_html=True)
        render_execution_timeline(trajectory)
        st.markdown("</div>", unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="chart-card"><div class="chart-title">Rubric Weights</div>', unsafe_allow_html=True)
        render_rubric_weights()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Ranked shortlist ──────────────────────────────────────────────
    st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
    st.markdown("### 🏆 Ranked Shortlist")
    render_ranked_shortlist_table(decisions)

    # ── Run summary ───────────────────────────────────────────────────
    if run_summary:
        st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("### 📋 Run Summary")
        render_run_summary_card(run_summary)

    # ── Export buttons ────────────────────────────────────────────────
    if decisions:
        st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("### ⬇️ Export Results")
        import json, pandas as pd
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button("📄 Export JSON", data=json.dumps(decisions, default=str, indent=2),
                               file_name="techvest_shortlist.json", mime="application/json", use_container_width=True)
        with c2:
            df = pd.DataFrame([{
                "Candidate": d.get("candidate_name"), "Score": d.get("weighted_score"),
                "Recommendation": d.get("final_recommendation"), "Rank": d.get("rank"),
            } for d in decisions])
            st.download_button("📊 Export CSV", data=df.to_csv(index=False),
                               file_name="techvest_shortlist.csv", mime="text/csv", use_container_width=True)
        with c3:
            audit = st.session_state.get("agent_state", {}).get("trajectory", [])
            st.download_button("📋 Export Trajectory", data=json.dumps(audit, default=str, indent=2),
                               file_name="techvest_trajectory.json", mime="application/json", use_container_width=True)


if __name__ == "__main__":
    main()
