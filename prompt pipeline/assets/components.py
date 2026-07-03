"""
assets/components.py — Reusable HTML/Streamlit component helpers.

All functions return raw HTML strings or call st.* directly.
Keeps app.py clean by isolating rendering logic here.
"""

from __future__ import annotations
import json
import streamlit as st
from utils.formatters import format_json, format_duration


# ─── Page header ──────────────────────────────────────────────────────────────

def render_header() -> None:
    st.markdown(
        """
        <div class="app-header">
          <h1>⚡ Prompt Pipeline</h1>
          <p>Multi-stage LLM pipeline with structured JSON passing, self-critic, and full transparency</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── Metric row ───────────────────────────────────────────────────────────────

def render_metrics(
    total_ms: float,
    total_tokens: int,
    stage_count: int,
    model: str,
) -> None:
    model_short = model.split("/")[-1] if "/" in model else model
    st.markdown(
        f"""
        <div class="metric-row">
          <div class="metric-card">
            <div class="metric-value">{format_duration(total_ms)}</div>
            <div class="metric-label">Total Time</div>
          </div>
          <div class="metric-card">
            <div class="metric-value">{total_tokens:,}</div>
            <div class="metric-label">Total Tokens</div>
          </div>
          <div class="metric-card">
            <div class="metric-value">{stage_count}</div>
            <div class="metric-label">Stages Run</div>
          </div>
          <div class="metric-card">
            <div class="metric-value" style="font-size:0.9rem;">{model_short}</div>
            <div class="metric-label">Model</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── Execution timeline bar chart ─────────────────────────────────────────────

def render_timeline(stages: list) -> None:
    """Render a proportional bar chart of per-stage latencies."""
    if not stages:
        return

    max_ms = max((s.latency_ms for s in stages), default=1) or 1

    rows_html = ""
    for s in stages:
        pct = min(100, (s.latency_ms / max_ms) * 100)
        color = "#3fb950" if s.success else "#f78166"
        rows_html += f"""
        <div class="timeline-row">
          <div class="timeline-label">{s.stage_name}</div>
          <div class="timeline-bar-bg">
            <div class="timeline-bar-fill" style="width:{pct:.1f}%;background:{color};"></div>
          </div>
          <div class="timeline-value">{format_duration(s.latency_ms)}</div>
        </div>
        """

    st.markdown(
        f"""
        <div class="timeline-container">
          <div style="font-weight:600;margin-bottom:14px;color:#e6edf3;">⏱ Execution Timeline</div>
          {rows_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── Stage card ───────────────────────────────────────────────────────────────

def render_stage_card(stage_exec, stage_index: int) -> None:
    """Render a full expandable stage card."""
    s = stage_exec
    status_class = "success" if s.success else "error"
    status_badge = (
        '<span class="badge badge-green">✓ Success</span>'
        if s.success
        else '<span class="badge badge-red">✗ Failed</span>'
    )
    retry_badge = (
        f'<span class="badge badge-yellow">↺ {s.retries} retr{"y" if s.retries == 1 else "ies"}</span>'
        if s.retries > 0
        else ""
    )
    token_badge = (
        f'<span class="badge badge-gray">🔤 {s.total_tokens} tok</span>'
        if s.total_tokens > 0
        else ""
    )
    time_badge = f'<span class="badge badge-blue">⏱ {format_duration(s.latency_ms)}</span>'

    st.markdown(
        f"""
        <div class="stage-card {status_class}">
          <div class="stage-header">
            <div class="stage-title">{s.stage_name}</div>
            <div class="stage-meta">
              {status_badge} {time_badge} {token_badge} {retry_badge}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Error message
    if not s.success and s.error:
        st.markdown(
            f'<div class="error-box">❌ {s.error}</div>',
            unsafe_allow_html=True,
        )
        return

    # Validation warning
    if s.validation_error:
        st.warning(f"⚠️ Schema validation: {s.validation_error}", icon="⚠️")

    # Expandable sections
    with st.expander("📤 JSON Output", expanded=(stage_index == 0)):
        json_str = format_json(s.parsed_json)
        st.code(json_str, language="json")

    with st.expander("💬 Prompts (System + User)", expanded=False):
        st.markdown("**System Prompt:**")
        st.markdown(
            f'<div class="prompt-box">{_escape(s.system_prompt)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown("**User Prompt:**")
        st.markdown(
            f'<div class="prompt-box">{_escape(s.user_prompt)}</div>',
            unsafe_allow_html=True,
        )

    with st.expander("📄 Raw LLM Response", expanded=False):
        st.markdown(
            f'<div class="prompt-box">{_escape(s.raw_response)}</div>',
            unsafe_allow_html=True,
        )


# ─── Final output box ─────────────────────────────────────────────────────────

def render_final_output(final_output: dict, task_name: str) -> None:
    st.markdown(
        f"""
        <div class="final-output-box">
          <h3>🎯 Final Pipeline Output — {task_name}</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.code(format_json(final_output), language="json")


# ─── History item ─────────────────────────────────────────────────────────────

def render_history_item(item: dict, index: int) -> None:
    task   = item.get("task_name", "Unknown")
    ts     = item.get("timestamp", "")
    ms     = item.get("total_latency_ms", 0)
    tokens = item.get("total_tokens", 0)
    ok     = item.get("success", False)
    icon   = "✅" if ok else "❌"

    st.markdown(
        f"""
        <div class="history-item">
          <div class="hi-title">{icon} #{index+1} — {task}</div>
          <div class="hi-meta">{ts} &nbsp;|&nbsp; {format_duration(ms)} &nbsp;|&nbsp; {tokens:,} tokens</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── Info / empty state ───────────────────────────────────────────────────────

def render_info(message: str) -> None:
    st.markdown(
        f'<div class="info-box">ℹ️ {message}</div>',
        unsafe_allow_html=True,
    )


# ─── Section divider ──────────────────────────────────────────────────────────

def render_divider() -> None:
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)


# ─── Utility ──────────────────────────────────────────────────────────────────

def _escape(text: str) -> str:
    """HTML-escape text for display inside a div."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
