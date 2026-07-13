"""
TechVest Recruitment Agent — Audit Page
"""
import json
import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from components import inject_css
from components.metrics import render_empty_state
from components.tables import render_audit_log_table, render_interview_slots_table


def main():
    st.set_page_config(page_title="TechVest — Audit", page_icon="📋", layout="wide")
    inject_css()
    st.markdown("""
    <div class="page-header">
        <div class="breadcrumb">TechVest Recruitment Agent › Audit</div>
        <h1>📋 Audit Log</h1>
        <p>Immutable audit trail of every agent action and decision</p>
    </div>""", unsafe_allow_html=True)

    state  = st.session_state.get("agent_state", {})
    run_id = state.get("run_id", "")

    audit_events    = []
    interview_slots = []
    runs            = []
    try:
        from database.sqlite import get_db
        db = get_db()
        if run_id:
            audit_events    = db.get_audit_log(run_id=run_id, limit=200)
            interview_slots = db.get_interview_slots(run_id)
        runs = db.list_runs(limit=10)
    except Exception as e:
        st.warning(f"DB read error: {e}")

    tab_log, tab_runs, tab_slots = st.tabs(["📋 Audit Log", "🏃 Run History", "📅 Interview Slots"])

    with tab_log:
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            search = st.text_input("🔍 Search", placeholder="action, candidate, category…")
        with col2:
            level_filter = st.selectbox("Level", ["ALL", "INFO", "WARNING", "ERROR", "SECURITY"])
        with col3:
            st.markdown("<div style='margin-top:1.75rem;'></div>", unsafe_allow_html=True)
            st.download_button(
                "⬇️ Export Audit JSON",
                data=json.dumps(audit_events, default=str, indent=2),
                file_name="techvest_audit.json",
                mime="application/json",
                use_container_width=True,
                disabled=not audit_events,
            )
        if not audit_events:
            render_empty_state("📋", "No Audit Events Yet", "Run the agent to generate an audit trail.")
        else:
            st.markdown(f'<div style="font-size:0.75rem;color:#64748B;margin-bottom:0.5rem;">'
                        f'{len(audit_events)} entries for run {run_id[:8] if run_id else "—"}</div>',
                        unsafe_allow_html=True)
            render_audit_log_table(audit_events, search=search, level_filter=level_filter)

    with tab_runs:
        if not runs:
            render_empty_state("🏃", "No Run History", "Runs will appear here after the first execution.")
        else:
            import pandas as pd
            rows = [{
                "Run ID":      r.get("run_id","")[:12],
                "Started":     str(r.get("started_at",""))[:16].replace("T"," "),
                "Status":      r.get("status",""),
                "Candidates":  r.get("total_candidates", 0),
                "Interview":   r.get("interview_count", 0),
                "Avg Score":   round(r.get("avg_score", 0), 1),
                "Duration(s)": round(r.get("duration_seconds", 0), 1),
                "Injection":   "⚠️ Yes" if r.get("injection_detected") else "✅ No",
                "Fairness":    r.get("fairness_status","N/A"),
            } for r in runs]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab_slots:
        render_interview_slots_table(interview_slots)


if __name__ == "__main__":
    main()
