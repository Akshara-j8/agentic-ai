"""
TechVest Recruitment Agent — Settings Page
"""
import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from components import inject_css
from components.metrics import render_status_banner


def main():
    st.set_page_config(page_title="TechVest — Settings", page_icon="⚙️", layout="wide")
    inject_css()
    st.markdown("""
    <div class="page-header">
        <div class="breadcrumb">TechVest Recruitment Agent › Settings</div>
        <h1>⚙️ Settings</h1>
        <p>Configure the agent, LLM, guardrails, and application preferences</p>
    </div>""", unsafe_allow_html=True)

    from config.settings import get_settings
    settings = get_settings()

    tab_llm, tab_agent, tab_guard, tab_app = st.tabs(
        ["🤖 LLM", "🕸️ Agent", "🛡️ Guardrails", "🖥️ Application"]
    )

    with tab_llm:
        st.markdown("### LLM Configuration")
        col1, col2 = st.columns(2)
        with col1:
            models = ["openai/gpt-4o-mini","openai/gpt-4o","openai/gpt-3.5-turbo",
                      "anthropic/claude-3-haiku","anthropic/claude-3-sonnet",
                      "google/gemini-flash-1.5","mistralai/mistral-7b-instruct"]
            cur = st.session_state.get("selected_model", settings.default_model)
            sel = st.selectbox("Default Model", models, index=models.index(cur) if cur in models else 0)
            st.session_state["selected_model"] = sel

            temp = st.slider("Temperature", 0.0, 1.0,
                             st.session_state.get("temperature", settings.default_temperature), 0.05)
            st.session_state["temperature"] = temp

            mtok = st.select_slider("Max Tokens", [512,1024,2048,4096,8192],
                                    value=st.session_state.get("max_tokens", settings.default_max_tokens))
            st.session_state["max_tokens"] = mtok

        with col2:
            st.markdown("**API Key Status**")
            if settings.is_configured:
                render_status_banner("success", f"✅ OpenRouter API key configured (sk-…{settings.openrouter_api_key[-6:]})")
            else:
                render_status_banner("error", "❌ OPENROUTER_API_KEY not set. Add it to your .env file.")
            st.markdown("**OpenRouter Base URL**")
            st.code(settings.openrouter_base_url)
            st.markdown("**Fallback Model**")
            st.code(settings.fallback_model)

    with tab_agent:
        st.markdown("### Agent Configuration")
        col1, col2 = st.columns(2)
        with col1:
            rec_lim = st.number_input("Recursion Limit", 5, 100, settings.recursion_limit)
            max_it  = st.number_input("Max Iterations", 1, 50, settings.max_iterations)
            step_lim = st.number_input("Step Limit", 10, 200, settings.step_limit)
        with col2:
            human_req = st.toggle("Require Human Approval", value=settings.human_approval_required)
            verbose   = st.toggle("Verbose Logging", value=settings.verbose_logging)
            auto_save = st.toggle("Auto Save to DB", value=settings.auto_save)

        if st.button("💾 Save Agent Settings", type="primary"):
            st.session_state["recursion_limit"]        = rec_lim
            st.session_state["max_iterations"]         = max_it
            st.session_state["step_limit"]             = step_lim
            st.session_state["human_approval_required"] = human_req
            st.session_state["verbose_logging"]        = verbose
            st.session_state["auto_save"]              = auto_save
            render_status_banner("success", "Settings saved to session.")

    with tab_guard:
        st.markdown("### Guardrail Thresholds")
        col1, col2 = st.columns(2)
        with col1:
            min_sc = st.slider("Min Score Threshold (Interview)", 0.0, 100.0, settings.min_score_threshold, 1.0)
            inj_sens = st.selectbox("Injection Sensitivity", ["low","medium","high"],
                                    index=["low","medium","high"].index(settings.injection_sensitivity))
        with col2:
            strict = st.toggle("Fairness Strict Mode", value=settings.fairness_strict_mode)
            guard_en = st.toggle("Enable All Guardrails", value=settings.enable_guardrails)

        st.markdown("### Rubric Thresholds")
        from config.rubric import THRESHOLDS
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Interview Threshold", f"{THRESHOLDS.interview}")
        with c2:
            st.metric("Hold Threshold", f"{THRESHOLDS.hold}")

        if st.button("💾 Save Guardrail Settings", type="primary"):
            st.session_state["min_score_threshold"] = min_sc
            render_status_banner("success", "Guardrail settings saved.")

    with tab_app:
        st.markdown("### Application")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Version**")
            st.code(settings.app_version)
            st.markdown("**Database Path**")
            st.code(settings.database_path)
            st.markdown("**Audit Log Path**")
            st.code(settings.audit_log_path)
        with col2:
            st.markdown("**Project Root**")
            from config.settings import PROJECT_ROOT
            st.code(str(PROJECT_ROOT))
            if st.button("🗑️ Clear Session State", type="secondary"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.success("Session cleared.")
                st.rerun()

        st.markdown("### Environment Variables Template")
        st.code("""OPENROUTER_API_KEY=sk-or-v1-...
DEFAULT_MODEL=openai/gpt-4o-mini
DEFAULT_TEMPERATURE=0.1
DEFAULT_MAX_TOKENS=4096
RECURSION_LIMIT=25
MAX_ITERATIONS=10
HUMAN_APPROVAL_REQUIRED=true
ENABLE_GUARDRAILS=true""", language="bash")


if __name__ == "__main__":
    main()
