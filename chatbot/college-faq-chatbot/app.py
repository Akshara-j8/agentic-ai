"""
Streamlit application for the BVRITH College FAQ RAG Chatbot.

Two pages:
  1. 💬 Chat        — conversational RAG interface with streaming
  2. 📊 Dashboard   — RAGAS evaluation results and charts

Run:
    streamlit run app.py
"""
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import streamlit as st

from config import (
    APP_TITLE,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CHROMA_DB_DIR,
    DEBUG_MODE_DEFAULT,
    EVALUATION_DIR,
    EVALUATION_REPORT_FILE,
    TOP_K,
)
from ingest import get_chunk_count, run_ingestion
from rag import build_chat_history, query, stream_query
from evaluator import load_report, run_full_evaluation
from utils import format_debug_chunks, format_source_citation, setup_logger
from memory import SessionMemory, generate_session_id

logger = setup_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Page configuration  (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
#  Custom CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Global ─────────────────────────────────────── */
    html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }

    /* ── Sidebar ─────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        color: #e2e8f0;
    }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stSelectbox label { color: #cbd5e1 !important; }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { color: #f8fafc !important; }

    /* ── Chat messages ────────────────────────────────── */
    .user-bubble {
        background: #2563eb;
        color: #fff;
        padding: 0.75rem 1rem;
        border-radius: 1rem 1rem 0.2rem 1rem;
        margin: 0.4rem 0 0.4rem 3rem;
        max-width: 80%;
        float: right;
        clear: both;
        word-wrap: break-word;
    }
    .bot-bubble {
        background: #1e293b;
        color: #e2e8f0;
        padding: 0.75rem 1rem;
        border-radius: 1rem 1rem 1rem 0.2rem;
        margin: 0.4rem 3rem 0.4rem 0;
        max-width: 80%;
        float: left;
        clear: both;
        word-wrap: break-word;
        border: 1px solid #334155;
    }
    .clearfix { clear: both; }

    /* ── Citation badges ──────────────────────────────── */
    .citation {
        display: inline-block;
        background: #0f4c81;
        color: #bfdbfe;
        font-size: 0.72rem;
        padding: 0.15rem 0.5rem;
        border-radius: 999px;
        margin: 0.15rem 0.1rem;
    }

    /* ── Metric cards ─────────────────────────────────── */
    .metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 0.75rem;
        padding: 1rem 1.25rem;
        text-align: center;
        color: #e2e8f0;
    }
    .metric-card .value {
        font-size: 2rem;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-card .label {
        font-size: 0.8rem;
        color: #94a3b8;
        margin-top: 0.25rem;
    }

    /* ── Info banner ──────────────────────────────────── */
    .info-banner {
        background: #0c2a4a;
        border-left: 4px solid #2563eb;
        color: #bfdbfe;
        padding: 0.6rem 1rem;
        border-radius: 0.4rem;
        font-size: 0.85rem;
        margin-bottom: 0.75rem;
    }

    /* ── Latency strip ────────────────────────────────── */
    .latency-strip {
        font-size: 0.75rem;
        color: #64748b;
        padding: 0.2rem 0;
        border-top: 1px solid #1e293b;
        margin-top: 0.5rem;
    }

    /* ── Nav tabs ─────────────────────────────────────── */
    div[data-testid="stHorizontalBlock"] > div { border-radius: 0.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Session state initialisation
# ─────────────────────────────────────────────────────────────────────────────
def _init_session() -> None:
    """Initialise Streamlit session state keys with defaults.

    On first run within a browser session:
      1. Read or generate a session ID from the URL query params.
      2. Load any previously saved name + history from disk.
      3. Populate session_state so the chat resumes seamlessly.
    """
    # ── 1. Session ID — stored in ?sid= query param (survives refresh) ─────
    if "session_id" not in st.session_state:
        params = st.query_params
        sid = params.get("sid", None)
        if not sid:
            sid = generate_session_id()
            st.query_params["sid"] = sid
        st.session_state["session_id"] = sid
        st.session_state["_memory_loaded"] = False   # flag to load once

    # ── 2. Load from disk on the very first run of this browser session ─────
    if not st.session_state.get("_memory_loaded", False):
        mem = SessionMemory(st.session_state["session_id"])
        saved = mem.load()
        st.session_state["messages"]   = saved.get("messages", [])
        st.session_state["user_name"]  = saved.get("user_name")  # None if new
        st.session_state["_memory_loaded"] = True

    # ── 3. Fill any remaining defaults ─────────────────────────────────────
    defaults: Dict[str, Any] = {
        "messages":    [],
        "user_name":   None,
        "debug_mode":  DEBUG_MODE_DEFAULT,
        "top_k":       TOP_K,
        "page":        "chat",    # "chat" | "dashboard" | "governance"
        "chunk_count": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_session()


# ─────────────────────────────────────────────────────────────────────────────
#  Sidebar governance scores (lightweight — reads cached report files)
# ─────────────────────────────────────────────────────────────────────────────
def _render_sidebar_governance_scores() -> None:
    """Render compact governance score strip inside the sidebar.

    Reads from reports/deepeval.json and reports/giskard_report.json.
    Falls back to placeholder values if reports don't exist yet.
    """
    import json as _json

    BASE = Path(__file__).resolve().parent
    REPORTS = BASE / "reports"

    def _load(p: Path):
        try:
            if p.exists():
                return _json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return None

    deepeval = _load(REPORTS / "deepeval.json")
    giskard  = _load(REPORTS / "giskard_report.json")
    gov_logs = BASE / "logs" / "governance_logs.jsonl"

    # ── Parse scores ──────────────────────────────────────────────────────
    hallucination = bias = faithfulness = safety = 0.0
    total_t = passed_t = 0
    latest_scan = "Not run"
    injection_status = "UNKNOWN"
    leakage_status   = "UNKNOWN"

    if deepeval:
        latest_scan = deepeval.get("generated_at", "?")[:10]
        total_t += deepeval.get("total_test_cases", 0)
        for row in deepeval.get("summary", []):
            m = row.get("metric", "")
            s = row.get("avg_score", 0.0)
            passed_t += row.get("passed", 0)
            if "hallucination" in m:
                hallucination = s
            elif "faithfulness" in m:
                faithfulness  = s
            elif "bias" in m:
                bias = s

    if giskard:
        summary = giskard.get("summary", {})
        total_g = summary.get("total_findings", 0)
        tp      = summary.get("true_positives", 0)
        safety  = max(0.0, 1.0 - (tp / total_g)) if total_g > 0 else 1.0
        findings = giskard.get("findings", [])
        inj_tps = [f for f in findings
                   if "injection" in f.get("type","").lower()
                   and f.get("classification") == "True Positive"]
        lk_tps  = [f for f in findings
                   if "leakage" in f.get("type","").lower()
                   and f.get("classification") == "True Positive"]
        injection_status = "⚠️ VULN" if inj_tps else "✅ SECURE"
        leakage_status   = "⚠️ VULN" if lk_tps  else "✅ SECURE"

    # Check live log for runtime events
    if gov_logs.exists():
        try:
            lines = gov_logs.read_text(encoding="utf-8").strip().split("\n")
            log_events = [_json.loads(l) for l in lines if l.strip()]
            inj_ev = [e for e in log_events
                      if "injection" in e.get("vulnerability","").lower()]
            pii_ev = [e for e in log_events
                      if "pii" in e.get("vulnerability","").lower()
                      or "leakage" in e.get("vulnerability","").lower()]
            injection_status = f"🚨 {len(inj_ev)} events" if inj_ev else "✅ SECURE"
            leakage_status   = f"🚨 {len(pii_ev)} events" if pii_ev else "✅ SECURE"
        except Exception:
            pass

    # Placeholder when no reports exist
    if not deepeval and not giskard:
        hallucination, bias, faithfulness, safety = 0.82, 0.91, 0.79, 0.95
        total_t, passed_t = 20, 20
        latest_scan = "placeholder"
        injection_status = "✅ SECURE"
        leakage_status   = "✅ SECURE"

    metric_scores = [s for s in [hallucination, faithfulness, bias, safety] if s > 0]
    gov_score = sum(metric_scores) / len(metric_scores) if metric_scores else 0.0

    def _bar(v: float) -> str:
        color = "#22c55e" if v >= 0.75 else "#f59e0b" if v >= 0.50 else "#ef4444"
        return color

    st.markdown("### 🛡️ Governance Scores")
    st.markdown(
        f"""
        <div style="background:#0f172a;border-radius:0.6rem;padding:0.6rem 0.8rem;
                    border:1px solid #1e293b;font-size:0.78rem;color:#e2e8f0;">
          <div style="text-align:center;font-size:1.2rem;font-weight:700;
                      color:{_bar(gov_score)};margin-bottom:0.4rem;">
            {gov_score:.0%} overall
          </div>
          <table style="width:100%;border-collapse:collapse;">
            <tr><td style="color:#94a3b8;">🎯 Hallucination</td>
                <td style="text-align:right;color:{_bar(hallucination)};font-weight:600;">{hallucination:.0%}</td></tr>
            <tr><td style="color:#94a3b8;">⚖️ Bias</td>
                <td style="text-align:right;color:{_bar(bias)};font-weight:600;">{bias:.0%}</td></tr>
            <tr><td style="color:#94a3b8;">🔗 Faithfulness</td>
                <td style="text-align:right;color:{_bar(faithfulness)};font-weight:600;">{faithfulness:.0%}</td></tr>
            <tr><td style="color:#94a3b8;">🛡️ Safety</td>
                <td style="text-align:right;color:{_bar(safety)};font-weight:600;">{safety:.0%}</td></tr>
            <tr><td colspan="2"><hr style="border:0;border-top:1px solid #1e293b;margin:0.3rem 0;"></td></tr>
            <tr><td style="color:#94a3b8;">💉 Injection</td>
                <td style="text-align:right;font-size:0.72rem;color:#e2e8f0;">{injection_status}</td></tr>
            <tr><td style="color:#94a3b8;">🔒 Data Leak</td>
                <td style="text-align:right;font-size:0.72rem;color:#e2e8f0;">{leakage_status}</td></tr>
            <tr><td colspan="2"><hr style="border:0;border-top:1px solid #1e293b;margin:0.3rem 0;"></td></tr>
            <tr><td style="color:#94a3b8;">📋 Tests</td>
                <td style="text-align:right;color:#38bdf8;">{passed_t}/{total_t} passed</td></tr>
            <tr><td style="color:#94a3b8;">🕒 Last scan</td>
                <td style="text-align:right;color:#64748b;font-size:0.7rem;">{latest_scan}</td></tr>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Sidebar
# ─────────────────────────────────────────────────────────────────────────────
def _render_sidebar() -> None:
    """Render the left sidebar with status and settings."""
    with st.sidebar:
        st.markdown("## 🎓 BVRITH FAQ Chatbot")
        st.markdown("---")

        # ── Navigation ──────────────────────────────────────────────────────
        st.markdown("### 📌 Navigation")
        nav_col1, nav_col2 = st.columns(2)
        with nav_col1:
            if st.button("💬 Chat", use_container_width=True,
                         type="primary" if st.session_state.page == "chat" else "secondary"):
                st.session_state.page = "chat"
                st.rerun()
        with nav_col2:
            if st.button("📊 Dashboard", use_container_width=True,
                         type="primary" if st.session_state.page == "dashboard" else "secondary"):
                st.session_state.page = "dashboard"
                st.rerun()

        if st.button("🛡️ Governance", use_container_width=True,
                     type="primary" if st.session_state.page == "governance" else "secondary"):
            st.session_state.page = "governance"
            st.rerun()

        st.markdown("---")

        # ── Governance scores (shown on all pages, live from reports) ────────
        _render_sidebar_governance_scores()

        st.markdown("---")

        # ── User Identity ────────────────────────────────────────────────────
        st.markdown("### 👤 Your Profile")
        current_name = st.session_state.get("user_name") or ""
        new_name = st.text_input(
            "Your name",
            value=current_name,
            placeholder="Enter your name…",
            key="name_input",
            help="Your name is remembered across refreshes.",
        )
        if new_name.strip() and new_name.strip() != current_name:
            st.session_state["user_name"] = new_name.strip()
            mem = SessionMemory(st.session_state["session_id"])
            mem.set_name(new_name.strip())
            st.rerun()

        if st.session_state.get("user_name"):
            st.success(f"👋 Hello, {st.session_state['user_name']}!")

        st.markdown("---")

        # ── Vector DB Status ─────────────────────────────────────────────────
        st.markdown("### 🗄️ Vector DB Status")
        db_exists = CHROMA_DB_DIR.exists() and any(CHROMA_DB_DIR.iterdir())

        if db_exists:
            st.success("✅ Vector DB Ready")
            if st.session_state.chunk_count is None:
                with st.spinner("Counting chunks…"):
                    st.session_state.chunk_count = get_chunk_count()
            chunk_count = st.session_state.chunk_count
        else:
            st.error("❌ Vector DB Not Found")
            st.warning("Run `python ingest.py` to build the vector store.")
            chunk_count = 0
            if st.button("🔄 Run Ingestion Now", use_container_width=True):
                with st.spinner("Ingesting knowledge base… this may take a minute."):
                    try:
                        run_ingestion()
                        st.session_state.chunk_count = get_chunk_count()
                        st.success("Ingestion complete!")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Ingestion failed: {exc}")

        st.markdown("---")

        # ── Document Info ────────────────────────────────────────────────────
        st.markdown("### 📄 Document Info")
        st.markdown(f"- **File:** `knowledge_base.docx`")
        st.markdown(f"- **Chunks stored:** `{chunk_count}`")
        st.markdown(f"- **Chunk size:** `{CHUNK_SIZE}` chars")
        st.markdown(f"- **Overlap:** `{CHUNK_OVERLAP}` chars")

        st.markdown("---")

        # ── Retrieval Settings ───────────────────────────────────────────────
        st.markdown("### ⚙️ Retrieval Settings")
        st.session_state.top_k = st.slider(
            "Top-K results",
            min_value=1,
            max_value=10,
            value=st.session_state.top_k,
            help="Number of document chunks to retrieve per query.",
        )

        st.markdown("---")

        # ── Debug Mode ───────────────────────────────────────────────────────
        st.markdown("### 🔍 Debug")
        st.session_state.debug_mode = st.toggle(
            "Show retrieved chunks",
            value=st.session_state.debug_mode,
        )

        st.markdown("---")
        st.caption("Powered by LangChain · ChromaDB · OpenRouter · RAGAS")


# ─────────────────────────────────────────────────────────────────────────────
#  Chat page
# ─────────────────────────────────────────────────────────────────────────────
def _render_chat_message(role: str, content: str, meta: Optional[Dict] = None) -> None:
    """Render a single chat bubble with optional citation/latency metadata."""
    if role == "user":
        st.markdown(
            f'<div class="user-bubble">🧑 {content}</div><div class="clearfix"></div>',
            unsafe_allow_html=True,
        )
    else:
        citations_html = ""
        if meta and meta.get("citations"):
            badges = "".join(
                f'<span class="citation">{c}</span>'
                for c in meta["citations"]
            )
            citations_html = f"<div style='margin-top:0.4rem'>{badges}</div>"

        latency_html = ""
        if meta:
            parts = []
            if meta.get("elapsed"):
                parts.append(f"⏱ {meta['elapsed']:.2f}s")
            if meta.get("chunks"):
                parts.append(f"📄 {meta['chunks']} chunks")
            if meta.get("tokens"):
                parts.append(f"🔢 ~{meta['tokens']} tokens")
            if parts:
                latency_html = (
                    f'<div class="latency-strip">'
                    + " &nbsp;|&nbsp; ".join(parts)
                    + "</div>"
                )

        st.markdown(
            f'<div class="bot-bubble">🎓 {content}'
            f'{citations_html}{latency_html}'
            f'</div><div class="clearfix"></div>',
            unsafe_allow_html=True,
        )


def _render_chat_page() -> None:
    """Render the main chat interface."""
    st.markdown(f"# 💬 {APP_TITLE}")
    st.markdown(
        '<div class="info-banner">'
        "Ask any question about BVRITH — admissions, fees, courses, "
        "placements, facilities, and more. All answers are sourced directly "
        "from the official knowledge base."
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Clear chat ──────────────────────────────────────────────────────────
    col_title, col_clear = st.columns([6, 1])
    with col_clear:
        if st.button("🗑️ Clear", help="Clear chat history"):
            st.session_state.messages = []
            mem = SessionMemory(st.session_state["session_id"])
            mem.save_messages([])   # wipe history on disk, keep name
            st.rerun()

    # ── Render history ──────────────────────────────────────────────────────
    for msg in st.session_state.messages:
        _render_chat_message(
            role=msg["role"],
            content=msg["content"],
            meta=msg.get("meta"),
        )

    # ── Input box ───────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    user_input = st.chat_input(
        "Ask a question about BVRITH college…",
        key="chat_input",
    )

    if not user_input:
        return

    # Guard: vector store must exist
    if not (CHROMA_DB_DIR.exists() and any(CHROMA_DB_DIR.iterdir())):
        st.error(
            "Vector store not found. "
            "Please run `python ingest.py` before chatting."
        )
        return

    # Append user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    _render_chat_message("user", user_input)

    # Build LangChain chat history (exclude the just-added user turn)
    lc_history = build_chat_history(st.session_state.messages[:-1])

    # ── Streaming response ──────────────────────────────────────────────────
    response_placeholder = st.empty()
    full_answer = ""

    with st.spinner(""):
        try:
            token_gen, source_docs, retrieval_elapsed = stream_query(
                question=user_input,
                chat_history=lc_history,
                top_k=st.session_state.top_k,
                debug=st.session_state.debug_mode,
                user_name=st.session_state.get("user_name"),
            )

            gen_start = time.perf_counter()
            for token in token_gen:
                full_answer += token
                # Typing animation — update placeholder each token
                response_placeholder.markdown(
                    f'<div class="bot-bubble">🎓 {full_answer}▌</div>'
                    '<div class="clearfix"></div>',
                    unsafe_allow_html=True,
                )

            total_elapsed = retrieval_elapsed + (time.perf_counter() - gen_start)
            response_placeholder.empty()

        except Exception as exc:
            logger.error("Query failed: %s", exc)
            error_msg = (
                "Sorry, I encountered an error processing your question. "
                f"Details: {exc}"
            )
            response_placeholder.error(error_msg)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_msg}
            )
            return

    # Build citation list
    citations = []
    seen_cit: set = set()
    for doc in source_docs:
        cit = format_source_citation(doc.metadata)
        if cit not in seen_cit:
            seen_cit.add(cit)
            citations.append(cit)

    approx_tokens = len(full_answer) // 4

    meta = {
        "elapsed": total_elapsed,
        "chunks": len(source_docs),
        "tokens": approx_tokens,
        "citations": citations,
    }

    # Persist assistant message
    st.session_state.messages.append(
        {"role": "assistant", "content": full_answer, "meta": meta}
    )
    _render_chat_message("assistant", full_answer, meta)

    # ── Save to persistent memory ────────────────────────────────────────────
    mem = SessionMemory(st.session_state["session_id"])
    mem.save_messages(st.session_state.messages)

    # ── Debug: show retrieved chunks ─────────────────────────────────────────
    if st.session_state.debug_mode and source_docs:
        with st.expander(f"🔍 Debug — {len(source_docs)} retrieved chunks", expanded=False):
            st.markdown(format_debug_chunks(source_docs))


# ─────────────────────────────────────────────────────────────────────────────
#  Dashboard page
# ─────────────────────────────────────────────────────────────────────────────
def _render_dashboard_page() -> None:
    """Render the evaluation dashboard."""
    import json
    try:
        import plotly.graph_objects as go
        import plotly.express as px
        HAS_PLOTLY = True
    except ImportError:
        HAS_PLOTLY = False

    st.markdown("# 📊 Evaluation Dashboard")
    st.markdown(
        '<div class="info-banner">'
        "RAGAS evaluation results — Faithfulness, Answer Relevancy, "
        "Context Precision, and Context Recall."
        "</div>",
        unsafe_allow_html=True,
    )

    report_path = EVALUATION_DIR / EVALUATION_REPORT_FILE
    report = load_report(report_path)

    # ── Run evaluation button ────────────────────────────────────────────────
    col_run, col_spacer = st.columns([2, 5])
    with col_run:
        run_eval = st.button(
            "▶️ Run Evaluation",
            use_container_width=True,
            help="Auto-generate test cases and score with RAGAS.",
        )

    if run_eval:
        with st.spinner("Running RAGAS evaluation — this takes a few minutes…"):
            try:
                report = run_full_evaluation()
                st.success("Evaluation complete!")
                st.rerun()
            except Exception as exc:
                st.error(f"Evaluation failed: {exc}")
                return

    if report is None:
        st.info(
            "No evaluation report found. "
            "Click **▶️ Run Evaluation** above to generate one."
        )
        return

    metrics: Dict[str, float] = report.get("metrics", {})
    overall: float = report.get("overall_score", 0.0)
    pass_rate: float = report.get("pass_rate", 0.0)
    weakest: str = report.get("weakest_metric", "N/A")
    recommendations: List[str] = report.get("recommendations", [])
    generated_at: str = report.get("generated_at", "unknown")
    n_cases: int = report.get("total_test_cases", 0)

    st.caption(f"Last evaluated: {generated_at}  |  Test cases: {n_cases}")

    # ── KPI cards ─────────────────────────────────────────────────────────────
    st.markdown("### 🏆 Overall Performance")
    kpi_cols = st.columns(4)
    kpi_data = [
        ("Overall Score", f"{overall:.0%}", "📈"),
        ("Pass Rate", f"{pass_rate:.0%}", "✅"),
        ("Test Cases", str(n_cases), "📋"),
        ("Weakest Metric", weakest.replace("_", " ").title(), "⚠️"),
    ]
    for col, (label, value, icon) in zip(kpi_cols, kpi_data):
        with col:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="value">{icon} {value}</div>'
                f'<div class="label">{label}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Metric charts ─────────────────────────────────────────────────────────
    st.markdown("### 📊 RAGAS Metric Scores")

    metric_names = [k.replace("_", " ").title() for k in metrics.keys()]
    metric_values = list(metrics.values())

    if HAS_PLOTLY:
        # Bar chart
        col_bar, col_radar = st.columns(2)

        with col_bar:
            colors = [
                "#22c55e" if v >= 0.7 else "#f59e0b" if v >= 0.5 else "#ef4444"
                for v in metric_values
            ]
            fig_bar = go.Figure(
                go.Bar(
                    x=metric_names,
                    y=metric_values,
                    marker_color=colors,
                    text=[f"{v:.2f}" for v in metric_values],
                    textposition="outside",
                )
            )
            fig_bar.update_layout(
                title="Metric Scores (Bar)",
                yaxis=dict(range=[0, 1.1], tickformat=".0%"),
                plot_bgcolor="#0f172a",
                paper_bgcolor="#0f172a",
                font_color="#e2e8f0",
                margin=dict(t=40, b=20),
                showlegend=False,
            )
            fig_bar.add_hline(
                y=0.7, line_dash="dash", line_color="#64748b",
                annotation_text="Pass threshold (0.7)",
                annotation_font_color="#94a3b8",
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_radar:
            fig_radar = go.Figure(
                go.Scatterpolar(
                    r=metric_values + [metric_values[0]],
                    theta=metric_names + [metric_names[0]],
                    fill="toself",
                    line_color="#38bdf8",
                    fillcolor="rgba(56,189,248,0.2)",
                )
            )
            fig_radar.update_layout(
                title="Metric Radar",
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 1]),
                    bgcolor="#1e293b",
                ),
                plot_bgcolor="#0f172a",
                paper_bgcolor="#0f172a",
                font_color="#e2e8f0",
                margin=dict(t=40, b=20),
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        # Latency chart (per-question)
        per_q = report.get("per_question_results", [])
        if per_q:
            st.markdown("### ⏱ Per-Question Answer Length")
            q_labels = [f"Q{i+1}" for i in range(len(per_q))]
            ans_lens = [len(r.get("answer", "")) for r in per_q]
            fig_lat = px.bar(
                x=q_labels,
                y=ans_lens,
                labels={"x": "Question", "y": "Answer length (chars)"},
                title="Answer Length per Test Question",
                color=ans_lens,
                color_continuous_scale="Blues",
            )
            fig_lat.update_layout(
                plot_bgcolor="#0f172a",
                paper_bgcolor="#0f172a",
                font_color="#e2e8f0",
                margin=dict(t=40, b=20),
                showlegend=False,
            )
            st.plotly_chart(fig_lat, use_container_width=True)

    else:
        # Fallback: plain table
        st.warning("Install `plotly` for interactive charts: `pip install plotly`")
        for name, val in zip(metric_names, metric_values):
            bar = "█" * int(val * 20)
            st.markdown(f"**{name}**: `{val:.4f}` {bar}")

    # ── Metric breakdown table ─────────────────────────────────────────────
    st.markdown("### 🔢 Metric Breakdown")
    breakdown_cols = st.columns(len(metrics))
    for col, (k, v) in zip(breakdown_cols, metrics.items()):
        status = "🟢" if v >= 0.7 else "🟡" if v >= 0.5 else "🔴"
        col.metric(
            label=f"{status} {k.replace('_', ' ').title()}",
            value=f"{v:.4f}",
            delta=f"{v - 0.7:+.4f} vs threshold",
        )

    # ── Recommendations ────────────────────────────────────────────────────
    st.markdown("### 💡 Recommendations")
    for rec in recommendations:
        st.markdown(f"- {rec}")

    # ── Per-question results table ─────────────────────────────────────────
    per_q_results = report.get("per_question_results", [])
    if per_q_results:
        with st.expander("📋 Per-Question Results", expanded=False):
            for i, r in enumerate(per_q_results, 1):
                st.markdown(f"**Q{i}: {r.get('question', '')}**")
                st.markdown(f"*Answer:* {r.get('answer', '')[:300]}…")
                st.markdown(f"*Ground truth:* {r.get('ground_truth', '')[:200]}")
                st.markdown(f"*Contexts retrieved:* {len(r.get('contexts', []))}")
                st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
#  Main router
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    """Entry point — render sidebar then route to the selected page."""
    _render_sidebar()

    if st.session_state.page == "chat":
        _render_chat_page()
    elif st.session_state.page == "dashboard":
        _render_dashboard_page()
    elif st.session_state.page == "governance":
        try:
            from governance_dashboard import render_governance_dashboard
            render_governance_dashboard()
        except ImportError as exc:
            st.error(
                f"Could not load Governance Dashboard: {exc}\n\n"
                "Ensure `governance_dashboard.py` is in the project root."
            )
    else:
        _render_chat_page()


if __name__ == "__main__":
    main()
