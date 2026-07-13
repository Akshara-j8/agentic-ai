"""
TechVest Recruitment Agent — Candidates Page
Full candidate cards with scores, skill breakdown, and action buttons.
"""

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from components import inject_css
from components.cards import render_candidate_card
from components.charts import render_radar_chart, render_gauge_chart
from components.metrics import render_empty_state, render_status_banner
from components.tables import render_scorecard_comparison_table


def main():
    st.set_page_config(page_title="TechVest — Candidates", page_icon="👥", layout="wide")
    inject_css()

    st.markdown("""
    <div class="page-header">
        <div class="breadcrumb">TechVest Recruitment Agent › Candidates</div>
        <h1>👥 Candidates</h1>
        <p>Detailed analysis for each evaluated candidate</p>
    </div>
    """, unsafe_allow_html=True)

    state      = st.session_state.get("agent_state", {})
    scorecards = state.get("scorecards", [])
    profiles   = state.get("parsed_profiles", [])
    run_id     = state.get("run_id", "")

    if not scorecards:
        render_empty_state("👥", "No Candidates Evaluated", "Run the agent first to evaluate candidates.")
        return

    # ── Filters & search ─────────────────────────────────────────────
    col_s, col_f, col_sort = st.columns([3, 2, 2])
    with col_s:
        search = st.text_input("🔍 Search candidates", placeholder="Name, skill, recommendation…")
    with col_f:
        rec_filter = st.selectbox("Filter by Recommendation", ["All", "Interview", "Hold", "Reject"])
    with col_sort:
        sort_by = st.selectbox("Sort by", ["Score (High→Low)", "Score (Low→High)", "Name (A→Z)"])

    # Apply filters
    filtered = list(scorecards)
    if search:
        q = search.lower()
        filtered = [s for s in filtered if q in s.get("candidate_name","").lower()
                    or any(q in sk.lower() for sk in _get_profile_skills(s.get("candidate_name",""), profiles))]
    if rec_filter != "All":
        filtered = [s for s in filtered if s.get("recommendation") == rec_filter]

    if sort_by == "Score (High→Low)":
        filtered.sort(key=lambda x: x.get("overall_weighted_score", 0), reverse=True)
    elif sort_by == "Score (Low→High)":
        filtered.sort(key=lambda x: x.get("overall_weighted_score", 0))
    else:
        filtered.sort(key=lambda x: x.get("candidate_name", ""))

    st.markdown(f'<div style="font-size:0.78rem;color:#64748B;margin:0.5rem 0;">{len(filtered)} candidate(s)</div>',
                unsafe_allow_html=True)

    # ── Tabs: Cards | Comparison ──────────────────────────────────────
    tab_cards, tab_compare, tab_charts = st.tabs(["📇 Candidate Cards", "📊 Comparison Table", "📈 Score Charts"])

    with tab_cards:
        for sc in filtered:
            profile = _find_profile(sc.get("candidate_name",""), profiles)
            action  = render_candidate_card(sc, profile, show_actions=True, run_id=run_id)
            if action == "approve":
                st.success(f"✅ {sc.get('candidate_name')} marked for Interview")
            elif action == "reject":
                st.warning(f"❌ {sc.get('candidate_name')} rejected")
            elif action == "schedule":
                _handle_schedule(sc.get("candidate_name",""), run_id)
            st.markdown("<hr style='border-color:rgba(255,255,255,0.04);margin:0.5rem 0;'>",
                        unsafe_allow_html=True)

    with tab_compare:
        render_scorecard_comparison_table(filtered)

    with tab_charts:
        if len(filtered) == 1:
            sc = filtered[0]
            c1, c2 = st.columns(2)
            with c1:
                render_gauge_chart(sc.get("overall_weighted_score", 0), sc.get("candidate_name",""))
            with c2:
                render_radar_chart(sc)
        else:
            for sc in filtered:
                st.markdown(f"**{sc.get('candidate_name','')}**")
                c1, c2 = st.columns(2)
                with c1:
                    render_gauge_chart(sc.get("overall_weighted_score", 0), sc.get("candidate_name",""))
                with c2:
                    render_radar_chart(sc)
                st.markdown("---")


def _find_profile(name: str, profiles: list) -> dict:
    return next((p for p in profiles if p.get("name") == name), {})


def _get_profile_skills(name: str, profiles: list) -> list:
    p = _find_profile(name, profiles)
    return p.get("skills", []) + p.get("programming_languages", [])


def _handle_schedule(candidate_name: str, run_id: str) -> None:
    state = st.session_state.get("agent_state", {})
    avail = next(
        (a for a in state.get("availability_results", []) if a.get("candidate_name") == candidate_name),
        None,
    )
    if avail and avail.get("proposed_slots"):
        slot = avail["proposed_slots"][0]
        st.info(f"📅 Proposed slot: {slot.get('date')} {slot.get('time')} ({slot.get('interviewer')})")
    else:
        st.info(f"📅 No slots proposed yet for {candidate_name}. Run availability check first.")


if __name__ == "__main__":
    main()
