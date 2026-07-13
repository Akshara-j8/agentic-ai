"""
TechVest Recruitment Agent — Dynamic Sidebar
Shows live run status, job info, resume count, current node, guardrails.
No upload controls here — those live in the wizard steps.
"""
from __future__ import annotations

import streamlit as st


def render_dynamic_sidebar() -> None:
    with st.sidebar:
        # Branding
        st.markdown("""
        <div style="text-align:center;padding:1rem 0 0.5rem;">
            <div style="font-size:2rem;">🎯</div>
            <div style="font-size:1rem;font-weight:800;color:#F1F5F9;">TechVest</div>
            <div style="font-size:0.72rem;color:#64748B;">Recruitment Agent v2.0</div>
        </div>""", unsafe_allow_html=True)
        st.divider()

        # ── Current Step ──────────────────────────────────────────────
        step = st.session_state.get("current_step", 1)
        step_labels = {
            1: ("🏠", "Landing"),
            2: ("📄", "Job Description"),
            3: ("📎", "Upload Resumes"),
            4: ("▶️", "Run Agent"),
            5: ("⚡", "Executing"),
            6: ("📊", "Results"),
        }
        icon, label = step_labels.get(step, ("•", "Unknown"))
        st.markdown(
            f'<div style="background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.3);'
            f'border-radius:8px;padding:0.5rem 0.75rem;font-size:0.8rem;">'
            f'<div style="color:#64748B;font-size:0.65rem;text-transform:uppercase;">Current Step</div>'
            f'<div style="color:#F1F5F9;font-weight:700;">{icon} {label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='margin-top:0.75rem;'></div>", unsafe_allow_html=True)

        # ── Job Description status ────────────────────────────────────
        st.markdown('<div style="font-size:0.7rem;color:#64748B;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.4rem;">Job Description</div>', unsafe_allow_html=True)
        jd_text = st.session_state.get("jd_text", "")
        jd_source = st.session_state.get("jd_source", "")
        if jd_text:
            src_icon = "✨" if jd_source == "ai_generated" else "📤"
            src_label = "AI Generated" if jd_source == "ai_generated" else "Uploaded"
            st.markdown(
                f'<div style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.25);'
                f'border-radius:6px;padding:0.4rem 0.65rem;font-size:0.75rem;color:#10B981;">'
                f'✅ Ready ({src_icon} {src_label})<br>'
                f'<span style="color:#64748B;font-size:0.68rem;">{len(jd_text)} characters</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);'
                'border-radius:6px;padding:0.4rem 0.65rem;font-size:0.75rem;color:#EF4444;">'
                '❌ Not set — complete Step 2</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='margin-top:0.75rem;'></div>", unsafe_allow_html=True)

        # ── Resumes ───────────────────────────────────────────────────
        st.markdown('<div style="font-size:0.7rem;color:#64748B;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.4rem;">Candidate Resumes</div>', unsafe_allow_html=True)
        resume_inputs = st.session_state.get("resume_inputs", [])
        if resume_inputs:
            st.markdown(
                f'<div style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.25);'
                f'border-radius:6px;padding:0.4rem 0.65rem;font-size:0.75rem;color:#10B981;">'
                f'✅ {len(resume_inputs)} resume(s) loaded</div>',
                unsafe_allow_html=True,
            )
            for r in resume_inputs[:5]:
                st.markdown(
                    f'<div style="font-size:0.68rem;color:#64748B;padding:2px 0.3rem;">📎 {r["filename"]}</div>',
                    unsafe_allow_html=True,
                )
            if len(resume_inputs) > 5:
                st.markdown(
                    f'<div style="font-size:0.68rem;color:#475569;padding:2px 0.3rem;">+{len(resume_inputs)-5} more…</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);'
                'border-radius:6px;padding:0.4rem 0.65rem;font-size:0.75rem;color:#EF4444;">'
                '❌ No resumes — complete Step 3</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='margin-top:0.75rem;'></div>", unsafe_allow_html=True)

        # ── Agent state ───────────────────────────────────────────────
        agent_state = st.session_state.get("agent_state", {})
        if agent_state:
            st.markdown('<div style="font-size:0.7rem;color:#64748B;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.4rem;">Agent Status</div>', unsafe_allow_html=True)
            status = agent_state.get("status", "idle")
            current_node = agent_state.get("current_node", "—")
            iteration = agent_state.get("iteration_count", 0)
            tool_calls = agent_state.get("total_tool_calls", 0)
            llm_calls = agent_state.get("total_llm_calls", 0)
            parsed = len(agent_state.get("parsed_profiles", []))
            scored = len(agent_state.get("scored_candidates", []))
            total_resumes = len(agent_state.get("resume_inputs", []))

            status_color = {
                "running": "#06B6D4",
                "completed": "#10B981",
                "paused": "#F59E0B",
                "error": "#EF4444",
            }.get(status, "#64748B")

            st.markdown(f"""
            <div style="background:rgba(30,41,59,0.6);border:1px solid rgba(255,255,255,0.07);
                 border-radius:8px;padding:0.65rem 0.75rem;font-size:0.73rem;line-height:1.9;">
                <div style="display:flex;justify-content:space-between;">
                    <span style="color:#94A3B8;">Status</span>
                    <span style="color:{status_color};font-weight:700;">{status.upper()}</span>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span style="color:#94A3B8;">Node</span>
                    <span style="color:#818CF8;">{current_node.replace('_',' ').title()}</span>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span style="color:#94A3B8;">Progress</span>
                    <span style="color:#F1F5F9;">{parsed}/{total_resumes} parsed · {scored} scored</span>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span style="color:#94A3B8;">Iterations</span>
                    <span style="color:#F1F5F9;">{iteration}</span>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span style="color:#94A3B8;">Tool Calls</span>
                    <span style="color:#F1F5F9;">{tool_calls}</span>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span style="color:#94A3B8;">LLM Calls</span>
                    <span style="color:#F1F5F9;">{llm_calls}</span>
                </div>
            </div>""", unsafe_allow_html=True)

            st.markdown("<div style='margin-top:0.75rem;'></div>", unsafe_allow_html=True)

        # ── Guardrail status ──────────────────────────────────────────
        st.markdown('<div style="font-size:0.7rem;color:#64748B;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.4rem;">Guardrails</div>', unsafe_allow_html=True)
        gs = st.session_state.get("guardrail_status", {})
        checks = [
            ("🛡️ Injection",  gs.get("injection_checked", False)),
            ("⚖️ Fairness",   gs.get("fairness_checked", False)),
            ("📊 Step Limit", gs.get("step_limit_ok", True)),
            ("🔄 Iterations", gs.get("iteration_limit_ok", True)),
            ("🔍 No Loops",   not gs.get("loop_detected", False)),
        ]
        for label, passed in checks:
            color = "#10B981" if passed else "#EF4444"
            dot = "●" if passed else "○"
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;font-size:0.72rem;padding:2px 0;">'
                f'<span style="color:#94A3B8;">{label}</span>'
                f'<span style="color:{color};font-weight:700;">{dot}</span></div>',
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Last run summary ──────────────────────────────────────────
        last = st.session_state.get("last_run_summary")
        if last:
            st.markdown('<div style="font-size:0.7rem;color:#64748B;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.4rem;">Last Run</div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div style="font-size:0.72rem;color:#94A3B8;line-height:1.8;">
                <div>👥 {last.get('total_candidates', 0)} candidates</div>
                <div>✅ {last.get('interview_count', 0)} interview · ⏸️ {last.get('hold_count', 0)} hold · ❌ {last.get('reject_count', 0)} reject</div>
                <div>⏱️ {last.get('duration_seconds', 0):.1f}s · ⚡ {last.get('total_tool_calls', 0)} calls</div>
                <div>🏆 {last.get('top_candidate', '—')}</div>
            </div>""", unsafe_allow_html=True)
            st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)

        # ── API status ────────────────────────────────────────────────
        from config.settings import get_settings
        settings = get_settings()
        if settings.is_configured:
            st.markdown('<div style="font-size:0.72rem;color:#10B981;font-weight:600;">● API Connected</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-size:0.72rem;color:#EF4444;font-weight:600;">● API Key Missing</div>', unsafe_allow_html=True)
            st.caption("Set OPENROUTER_API_KEY in .env")

        # ── Reset button ──────────────────────────────────────────────
        st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
        if st.button("↺  Reset Everything", use_container_width=True, key="sidebar_reset"):
            for k in ["agent_state", "run_id", "last_run_summary", "guardrail_status",
                      "guardrail_overall", "agent_running", "approval_pending",
                      "jd_text", "jd_source", "resume_inputs", "current_step",
                      "agent_run_complete"]:
                st.session_state.pop(k, None)
            st.rerun()
