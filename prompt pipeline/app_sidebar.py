"""
app_sidebar.py — Streamlit sidebar rendering.

Returns a dict of user-selected settings consumed by app.py.
Kept separate to keep app.py focused on orchestration.
"""

from __future__ import annotations
import streamlit as st
import config as cfg
from utils.sample_inputs import SAMPLES
from utils.validators import is_valid_api_key


def render_sidebar() -> dict:
    """
    Render the full sidebar and return a settings dict:
    {
        "api_key":      str,
        "model_slug":   str,
        "task_name":    str,
        "task_id":      str,
        "sample_input": str | None,
    }
    """
    with st.sidebar:
        # ── Branding ──────────────────────────────────────────────────────
        st.markdown(
            """
            <div style="text-align:center;padding:12px 0 20px 0;">
              <div style="font-size:2rem;">⚡</div>
              <div style="font-weight:700;font-size:1.1rem;color:#e6edf3;">Prompt Pipeline</div>
              <div style="font-size:0.75rem;color:#8b949e;margin-top:4px;">
                OpenRouter · Multi-Stage LLM
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()

        # ── API Key ────────────────────────────────────────────────────────
        st.markdown("### 🔑 API Configuration")
        env_key = cfg.OPENROUTER_API_KEY
        if env_key:
            masked = env_key[:8] + "..." + env_key[-4:]
            st.markdown(
                f'<div style="font-size:0.8rem;color:#3fb950;">✓ Key loaded from .env ({masked})</div>',
                unsafe_allow_html=True,
            )
            api_key = env_key
        else:
            api_key = st.text_input(
                "OpenRouter API Key",
                type="password",
                placeholder="sk-or-...",
                help="Get your free key at openrouter.ai",
            )
            if api_key and not is_valid_api_key(api_key):
                st.warning("Key looks too short — double-check it.", icon="⚠️")
            elif not api_key:
                st.markdown(
                    '<div style="font-size:0.78rem;color:#f78166;">⚠ No key provided</div>',
                    unsafe_allow_html=True,
                )

        st.divider()

        # ── Model selection ────────────────────────────────────────────────
        st.markdown("### 🤖 Model")
        model_display_names = list(cfg.AVAILABLE_MODELS.keys())
        # Default to GPT-4o Mini
        default_idx = 0
        current_slug = cfg.DEFAULT_MODEL
        for i, (name, slug) in enumerate(cfg.AVAILABLE_MODELS.items()):
            if slug == current_slug:
                default_idx = i
                break

        selected_model_name = st.selectbox(
            "Select Model",
            options=model_display_names,
            index=default_idx,
            label_visibility="collapsed",
        )
        model_slug = cfg.AVAILABLE_MODELS[selected_model_name]
        st.markdown(
            f'<div style="font-size:0.75rem;color:#8b949e;margin-top:-8px;">{model_slug}</div>',
            unsafe_allow_html=True,
        )

        st.divider()

        # ── Task selection ─────────────────────────────────────────────────
        st.markdown("### 📋 Pipeline Task")
        task_names  = list(cfg.PIPELINE_TASKS.keys())
        task_icons  = [v["icon"] for v in cfg.PIPELINE_TASKS.values()]
        task_labels = [f"{icon}  {name}" for icon, name in zip(task_icons, task_names)]

        selected_label = st.selectbox(
            "Select Task",
            options=task_labels,
            label_visibility="collapsed",
        )
        # Recover plain task name from label
        selected_task_name = selected_label.split("  ", 1)[-1].strip()
        task_cfg = cfg.PIPELINE_TASKS[selected_task_name]
        task_id  = task_cfg["id"]

        st.markdown(
            f'<div style="font-size:0.8rem;color:#8b949e;margin-top:-8px;">'
            f'{task_cfg["description"]}</div>',
            unsafe_allow_html=True,
        )

        st.divider()

        # ── Sample inputs ──────────────────────────────────────────────────
        st.markdown("### 📂 Load Sample Input")
        task_samples = SAMPLES.get(task_id, [])
        sample_labels = ["— choose a sample —"] + [s["label"] for s in task_samples]

        chosen_sample = st.selectbox(
            "Sample",
            options=sample_labels,
            label_visibility="collapsed",
        )
        sample_input: str | None = None
        if chosen_sample != "— choose a sample —":
            for s in task_samples:
                if s["label"] == chosen_sample:
                    sample_input = s["input"]
                    break

        st.divider()

        # ── Pipeline info ──────────────────────────────────────────────────
        st.markdown("### ℹ️ Pipeline Stages")
        st.markdown(
            """
            <div style="font-size:0.82rem;line-height:1.9;color:#8b949e;">
              🔍 <b style="color:#e6edf3;">Stage 1</b> — Extraction<br>
              🧠 <b style="color:#e6edf3;">Stage 2</b> — Reasoning<br>
              ✍️ <b style="color:#e6edf3;">Stage 3</b> — Generation<br>
              🔎 <b style="color:#e6edf3;">Stage 4</b> — Self-Critic<br>
              <span style="font-size:0.75rem;">Each stage receives only the
              structured JSON output from the previous stage.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()
        st.markdown(
            '<div style="font-size:0.7rem;color:#484f58;text-align:center;">'
            'Powered by OpenRouter API<br>No RAG · No Agents · Pure LLM Pipelines'
            '</div>',
            unsafe_allow_html=True,
        )

    return {
        "api_key":      api_key,
        "model_slug":   model_slug,
        "task_name":    selected_task_name,
        "task_id":      task_id,
        "sample_input": sample_input,
    }
