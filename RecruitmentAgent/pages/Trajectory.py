"""
TechVest Recruitment Agent — Trajectory Page
"""
import json
import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from components import inject_css
from components.timeline import render_trajectory_timeline, render_event_type_legend, render_trajectory_stats
from components.charts import render_execution_timeline
from components.metrics import render_empty_state


def main():
    st.set_page_config(page_title="TechVest — Trajectory", page_icon="🧠", layout="wide")
    inject_css()
    st.markdown("""
    <div class="page-header">
        <div class="breadcrumb">TechVest Recruitment Agent › Trajectory</div>
        <h1>🧠 Agent Trajectory</h1>
        <p>Complete thought → action → observation → decision reasoning chain</p>
    </div>""", unsafe_allow_html=True)

    state      = st.session_state.get("agent_state", {})
    trajectory = state.get("trajectory", [])

    if not trajectory:
        render_empty_state("🧠", "No Trajectory Yet", "Run the agent to see the full reasoning chain.")
        return

    st.markdown("### 📊 Event Statistics")
    render_trajectory_stats(trajectory)
    st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([3, 2, 2])
    with col1:
        event_types = ["all","thought","action","observation","decision",
                       "guardrail","human_approval","scheduler","error"]
        filter_type = st.selectbox("Filter by event type", event_types,
                                   format_func=lambda x: x.replace("_"," ").title() if x != "all" else "All Events")
    with col2:
        show_meta = st.checkbox("Show metadata", value=False)
    with col3:
        st.markdown("<div style='margin-top:1.75rem;'></div>", unsafe_allow_html=True)
        st.download_button("⬇️ Export", data=json.dumps(trajectory, default=str, indent=2),
                           file_name="trajectory.json", mime="application/json", use_container_width=True)

    st.markdown("### 🔑 Legend")
    render_event_type_legend()

    with st.expander("📈 Execution Timeline Chart", expanded=False):
        render_execution_timeline(trajectory)

    st.markdown("### 🕐 Full Timeline")
    render_trajectory_timeline(trajectory, filter_type=filter_type, show_metadata=show_meta)

    with st.expander("🔍 Raw JSON (last 20 events)", expanded=False):
        st.json(trajectory[-20:] if len(trajectory) > 20 else trajectory)


if __name__ == "__main__":
    main()
