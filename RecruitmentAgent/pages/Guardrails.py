"""
TechVest Recruitment Agent — Guardrails Page
"""
import json
import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from components import inject_css
from components.metrics import render_empty_state, render_status_banner
from components.tables import render_guardrail_events_table
from config.settings import UIConstants


def main():
    st.set_page_config(page_title="TechVest — Guardrails", page_icon="🛡️", layout="wide")
    inject_css()
    st.markdown("""
    <div class="page-header">
        <div class="breadcrumb">TechVest Recruitment Agent › Guardrails</div>
        <h1>🛡️ Guardrails</h1>
        <p>Security, fairness, and safety controls for autonomous recruitment</p>
    </div>""", unsafe_allow_html=True)

    state    = st.session_state.get("agent_state", {})
    gs       = state.get("guardrail_status", {})
    profiles = state.get("parsed_profiles", [])
    fair     = state.get("fairness_result", {})
    run_id   = state.get("run_id", "")

    guardrail_events = []
    try:
        from database.sqlite import get_db
        if run_id:
            guardrail_events = get_db().get_guardrail_events(run_id)
    except Exception:
        pass

    overall    = gs.get("overall_pass", True)
    violations = gs.get("violations", [])
    if overall:
        render_status_banner("success", "✅ All guardrails PASSED — no safety violations detected.")
    else:
        render_status_banner("error", f"❌ Guardrail FAILURE: {' | '.join(violations) or 'Unknown'}")

    st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
    st.markdown("### 🔒 Guardrail Status")

    gcols = st.columns(5)
    checks = [
        ("🛡️", "Injection Check",  gs.get("injection_checked", False),   "Prompt injection scanned"),
        ("⚖️", "Fairness Audit",   gs.get("fairness_checked", False),    "Bias validated"),
        ("📊", "Step Limit",       gs.get("step_limit_ok", True),        "Within step budget"),
        ("🔄", "Iteration Limit",  gs.get("iteration_limit_ok", True),   "Within iteration budget"),
        ("🔍", "Loop Detection",   not gs.get("loop_detected", False),   "No loops detected"),
    ]
    for col, (icon, label, passed, desc) in zip(gcols, checks):
        color  = UIConstants.SUCCESS if passed else UIConstants.DANGER
        status = "PASS" if passed else "FAIL"
        with col:
            st.markdown(f"""
            <div style="background:rgba(30,41,59,0.7);border:1px solid {color}30;border-radius:12px;
                 padding:1rem;text-align:center;border-top:3px solid {color};">
                <div style="font-size:1.5rem;">{icon}</div>
                <div style="font-size:0.78rem;font-weight:700;color:#E2E8F0;margin:0.3rem 0;">{label}</div>
                <div style="background:{color}20;color:{color};font-size:0.7rem;font-weight:700;
                     padding:2px 10px;border-radius:99px;border:1px solid {color}40;">{status}</div>
                <div style="font-size:0.65rem;color:#64748B;margin-top:0.3rem;">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
    tab_inj, tab_fair, tab_events = st.tabs(["💉 Injection Attacks", "⚖️ Fairness Audit", "📋 All Events"])

    with tab_inj:
        injected = [p for p in profiles if p.get("injection_detected")]
        if not injected:
            st.markdown("""<div style="text-align:center;padding:2rem;color:#10B981;">
                <div style="font-size:2rem;">✅</div>
                <div style="font-size:0.9rem;font-weight:600;margin-top:0.5rem;">No prompt injection attacks detected</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class="alert-banner alert-danger"><span>🚨</span>
                <span><strong>{len(injected)} injection attack(s) detected and quarantined.</strong>
                Score penalties of −15 pts applied.</span></div>""", unsafe_allow_html=True)
            for p in injected:
                severity  = p.get("injection_severity", "medium")
                sev_color = {"low":"#F59E0B","medium":"#EF4444","high":"#DC2626","critical":"#991B1B"}.get(severity,"#EF4444")
                st.markdown(f"""
                <div class="injection-warning" style="margin-top:1rem;">
                    <div class="warning-title">⚠️ {p.get('name','?')} — Severity:
                        <span style="color:{sev_color};text-transform:uppercase;">{severity}</span></div>
                    <div style="font-size:0.75rem;color:#94A3B8;margin-top:0.4rem;">
                        File: <code>{p.get('resume_filename','?')}</code> · Score penalty −15 pts applied.<br>
                        Attack quarantined — scoring continued on sanitised content.
                    </div>
                </div>""", unsafe_allow_html=True)

    with tab_fair:
        if not fair:
            render_empty_state("⚖️", "Fairness Audit Not Run Yet", "Run the agent to see fairness results.")
        else:
            overall_f = fair.get("overall_fairness", "PASS")
            bias_sc   = fair.get("bias_score", 0)
            f_color   = UIConstants.SUCCESS if overall_f == "PASS" else UIConstants.DANGER
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:1.5rem;padding:1rem;
                 background:rgba(30,41,59,0.7);border-radius:12px;border:1px solid {f_color}30;margin-bottom:1rem;">
                <div style="font-size:2rem;">{'✅' if overall_f=='PASS' else '❌'}</div>
                <div>
                    <div style="font-size:1rem;font-weight:700;color:{f_color};">Fairness: {overall_f}</div>
                    <div style="font-size:0.78rem;color:#94A3B8;">Bias score: {bias_sc:.3f} (0=none, 1=high bias)</div>
                    <div style="font-size:0.75rem;color:#64748B;margin-top:0.25rem;">{fair.get('audit_notes','')[:150]}</div>
                </div>
            </div>""", unsafe_allow_html=True)
            for chk in fair.get("checks", []):
                s = chk.get("status", "PASS")
                c = {"PASS":UIConstants.SUCCESS,"FAIL":UIConstants.DANGER,"WARNING":UIConstants.WARNING}.get(s,"#94A3B8")
                st.markdown(f"""
                <div style="padding:0.6rem 1rem;background:rgba(30,41,59,0.5);border-left:3px solid {c};
                     border-radius:0 8px 8px 0;margin-bottom:6px;">
                    <div style="display:flex;justify-content:space-between;">
                        <span style="font-size:0.8rem;font-weight:600;color:#E2E8F0;">
                            {chk.get('check_name','').replace('_',' ').title()}</span>
                        <span style="background:{c}20;color:{c};font-size:0.65rem;font-weight:700;
                              padding:1px 8px;border-radius:99px;">{s}</span>
                    </div>
                    <div style="font-size:0.72rem;color:#94A3B8;margin-top:2px;">
                        {chk.get('finding') or 'No issues found'}</div>
                </div>""", unsafe_allow_html=True)

    with tab_events:
        render_guardrail_events_table(guardrail_events)


if __name__ == "__main__":
    main()
