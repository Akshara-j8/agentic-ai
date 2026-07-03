"""
app_downloads.py — Download button helpers for JSON and TXT exports.
"""

from __future__ import annotations
import json
import datetime
import streamlit as st
from utils.formatters import format_json


def render_download_buttons(result) -> None:
    """Render JSON and TXT download buttons for a completed PipelineResult."""
    st.markdown("#### 💾 Download Results")
    col1, col2 = st.columns(2)

    # ── JSON export ────────────────────────────────────────────────────────
    json_data = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    filename_base = (
        f"pipeline_{result.task_id}_{result.timestamp.replace(':', '-')}"
    )

    with col1:
        st.download_button(
            label="⬇️ Download JSON",
            data=json_data,
            file_name=f"{filename_base}.json",
            mime="application/json",
            use_container_width=True,
        )

    # ── TXT export ─────────────────────────────────────────────────────────
    txt_lines: list[str] = [
        "=" * 60,
        f"PROMPT PIPELINE RESULT",
        "=" * 60,
        f"Task     : {result.task_name}",
        f"Model    : {result.model}",
        f"Timestamp: {result.timestamp}",
        f"Duration : {result.total_latency_ms:.0f} ms",
        f"Tokens   : {result.total_tokens:,}",
        f"Success  : {result.success}",
        "",
        "─" * 60,
        "RAW INPUT",
        "─" * 60,
        result.raw_input,
        "",
    ]

    for s in result.stages:
        txt_lines += [
            "─" * 60,
            s.stage_name.upper(),
            f"  Latency : {s.latency_ms:.0f} ms",
            f"  Tokens  : {s.total_tokens}",
            f"  Retries : {s.retries}",
            f"  Success : {s.success}",
            "",
            "  OUTPUT JSON:",
            format_json(s.parsed_json),
            "",
        ]

    txt_lines += [
        "=" * 60,
        "FINAL OUTPUT",
        "=" * 60,
        format_json(result.final_output),
    ]

    txt_data = "\n".join(txt_lines)

    with col2:
        st.download_button(
            label="⬇️ Download TXT",
            data=txt_data,
            file_name=f"{filename_base}.txt",
            mime="text/plain",
            use_container_width=True,
        )
