"""
app.py — Main Streamlit application entry point.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import json
import streamlit as st

# ── Page config must be first Streamlit call ──────────────────────────────────
st.set_page_config(
    page_title="Prompt Pipeline",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Local imports (after page config) ────────────────────────────────────────
import config as cfg
from assets.styles     import CUSTOM_CSS
from assets.components import (
    render_header, render_metrics, render_timeline,
    render_stage_card, render_final_output,
    render_history_item, render_info, render_divider,
)
from app_sidebar   import render_sidebar
from app_downloads import render_download_buttons
from pipeline      import PipelineEngine
from utils.validators  import is_valid_api_key, is_meaningful_input
from utils.formatters  import format_json, format_duration

# ── Inject CSS ────────────────────────────────────────────────────────────────
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Session-state initialisation
# ─────────────────────────────────────────────────────────────────────────────

def _init_session_state() -> None:
    defaults = {
        "history":         [],      # list[dict] — serialised PipelineResult dicts
        "last_result":     None,    # most recent PipelineResult object
        "running":         False,   # pipeline currently executing?
        "input_text":      "",      # current text-area content
        "stage_progress":  0,       # 0-4
        "progress_msg":    "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_session_state()


# ─────────────────────────────────────────────────────────────────────────────
# Progress callback (called from pipeline thread-safe via Streamlit widget)
# ─────────────────────────────────────────────────────────────────────────────

def _on_progress(stage: int, message: str) -> None:
    st.session_state["stage_progress"] = stage
    st.session_state["progress_msg"]   = message


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

settings = render_sidebar()

api_key    = settings["api_key"]
model_slug = settings["model_slug"]
task_name  = settings["task_name"]
task_id    = settings["task_id"]
sample_inp = settings["sample_input"]


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────

render_header()

task_cfg = cfg.PIPELINE_TASKS[task_name]

st.markdown(
    f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;">
      <span style="font-size:2rem;">{task_cfg['icon']}</span>
      <div>
        <div style="font-size:1.3rem;font-weight:700;color:#e6edf3;">{task_name}</div>
        <div style="font-size:0.85rem;color:#8b949e;">{task_cfg['description']}</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Input area
# ─────────────────────────────────────────────────────────────────────────────

# If a sample was selected in the sidebar, load it into the text area
if sample_inp and sample_inp != st.session_state.get("_last_sample"):
    st.session_state["input_text"]   = sample_inp
    st.session_state["_last_sample"] = sample_inp

input_col, _ = st.columns([3, 1])
with input_col:
    raw_input = st.text_area(
        label="📥 Raw Input",
        value=st.session_state["input_text"],
        height=180,
        placeholder=task_cfg["placeholder"],
        key="input_text_area",
        help="Enter raw text for the pipeline. Use the sidebar to load a sample.",
    )
    # Sync back to session state
    st.session_state["input_text"] = raw_input


# ── Validation feedback ────────────────────────────────────────────────────────
input_ok  = is_meaningful_input(raw_input)
api_ok    = is_valid_api_key(api_key)

hint_col1, hint_col2 = st.columns(2)
with hint_col1:
    if not api_ok:
        st.error("❌ API key required — add it in the sidebar or .env file.", icon="🔑")
    else:
        st.success("✓ API key ready", icon="✅")

with hint_col2:
    word_count = len(raw_input.split()) if raw_input else 0
    if not input_ok:
        st.warning(f"Input needs at least 5 words (current: {word_count})", icon="✏️")
    else:
        st.success(f"✓ {word_count} words", icon="📝")


render_divider()


# ─────────────────────────────────────────────────────────────────────────────
# Run button + Pipeline execution
# ─────────────────────────────────────────────────────────────────────────────

run_disabled = not (input_ok and api_ok) or st.session_state["running"]

run_col, clear_col, *_ = st.columns([2, 1, 4])

with run_col:
    run_clicked = st.button(
        "🚀 Run Pipeline",
        disabled=run_disabled,
        use_container_width=True,
        type="primary",
    )

with clear_col:
    if st.button("🗑 Clear", use_container_width=True):
        st.session_state["input_text"] = ""
        st.session_state["last_result"] = None
        st.session_state["_last_sample"] = None
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Execute pipeline
# ─────────────────────────────────────────────────────────────────────────────

if run_clicked and input_ok and api_ok:
    st.session_state["running"]        = True
    st.session_state["last_result"]    = None
    st.session_state["stage_progress"] = 0
    st.session_state["progress_msg"]   = "Initialising..."

    # Progress bar + spinner
    progress_bar  = st.progress(0, text="Starting pipeline…")
    status_text   = st.empty()

    with st.spinner("Running pipeline… this may take 20–60 seconds"):
        try:
            engine = PipelineEngine(
                api_key          = api_key,
                model            = model_slug,
                progress_callback= _on_progress,
            )
            result = engine.run(task_id=task_id, raw_input=raw_input)

            # Update progress bar through stages
            for stage_idx in range(1, 5):
                pct = (stage_idx / 4) * 100
                progress_bar.progress(
                    int(pct),
                    text=f"Stage {stage_idx}/4 complete",
                )

            progress_bar.progress(100, text="✅ Done!")
            status_text.empty()

            st.session_state["last_result"] = result
            st.session_state["running"]     = False

            # Append to history (keep last 20)
            history_entry = result.to_dict()
            st.session_state["history"].insert(0, history_entry)
            st.session_state["history"] = st.session_state["history"][:20]

        except Exception as exc:
            progress_bar.empty()
            st.session_state["running"] = False
            st.error(f"❌ Pipeline error: {exc}", icon="💥")
            cfg.logger.exception("Unhandled pipeline error: %s", exc)

    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Results display
# ─────────────────────────────────────────────────────────────────────────────

result = st.session_state.get("last_result")

if result is not None:
    render_divider()

    # ── Summary metrics ─────────────────────────────────────────────────────
    if result.success:
        st.success(
            f"✅ Pipeline completed in {format_duration(result.total_latency_ms)} "
            f"using {result.total_tokens:,} tokens",
            icon="🎉",
        )
    else:
        st.error(f"❌ Pipeline failed: {result.error}", icon="💥")

    render_metrics(
        total_ms    = result.total_latency_ms,
        total_tokens= result.total_tokens,
        stage_count = len(result.stages),
        model       = result.model,
    )

    # ── Execution timeline ───────────────────────────────────────────────────
    render_timeline(result.stages)

    render_divider()

    # ── Stage-by-stage panels ────────────────────────────────────────────────
    st.markdown("### 🔬 Stage-by-Stage Breakdown")
    for idx, stage_exec in enumerate(result.stages):
        render_stage_card(stage_exec, stage_index=idx)

    render_divider()

    # ── Final output ─────────────────────────────────────────────────────────
    if result.final_output:
        render_final_output(result.final_output, result.task_name)

    render_divider()

    # ── Download buttons ─────────────────────────────────────────────────────
    render_download_buttons(result)

elif not st.session_state["running"]:
    # Empty state
    render_divider()
    render_info(
        "Select a task and enter your input above, then click <strong>Run Pipeline</strong> to begin. "
        "Use the sidebar to load a sample input."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Execution History (bottom section)
# ─────────────────────────────────────────────────────────────────────────────

render_divider()

history = st.session_state.get("history", [])

with st.expander(f"🕓 Execution History ({len(history)} runs)", expanded=False):
    if not history:
        st.markdown(
            '<div style="color:#8b949e;font-size:0.88rem;">No runs yet.</div>',
            unsafe_allow_html=True,
        )
    else:
        # Header row
        hcol1, hcol2 = st.columns([4, 1])
        with hcol1:
            st.markdown("**Past Runs**")
        with hcol2:
            if st.button("🗑 Clear History", key="clear_history_btn"):
                st.session_state["history"] = []
                st.rerun()

        for i, item in enumerate(history):
            render_history_item(item, i)

            # Expandable JSON for each history entry
            with st.expander(f"View details — Run #{i+1}", expanded=False):
                st.code(
                    json.dumps(item.get("final_output", {}), indent=2),
                    language="json",
                )


# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────

render_divider()
st.markdown(
    """
    <div style="text-align:center;color:#484f58;font-size:0.75rem;padding:12px 0;">
      ⚡ Prompt Pipeline · Built with Streamlit + OpenRouter API ·
      Multi-stage LLM orchestration with Pydantic validation
    </div>
    """,
    unsafe_allow_html=True,
)
