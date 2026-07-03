"""
assets/styles.py — Custom CSS injected into the Streamlit app.
Dark professional theme with card layouts, syntax highlighting hints,
timeline bars, and responsive stage panels.
"""

CUSTOM_CSS = """
<style>
/* ── Google Font ──────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Root variables ──────────────────────────────────────────────────── */
:root {
    --bg-main:      #0e1117;
    --bg-card:      #161b22;
    --bg-card2:     #1c2333;
    --border:       #30363d;
    --accent:       #58a6ff;
    --accent2:      #3fb950;
    --accent3:      #f78166;
    --accent4:      #e3b341;
    --text-primary: #e6edf3;
    --text-muted:   #8b949e;
    --font-mono:    'JetBrains Mono', 'Courier New', monospace;
    --font-ui:      'Inter', sans-serif;
    --radius:       8px;
    --radius-lg:    12px;
}

/* ── Global resets ────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: var(--font-ui) !important;
    color: var(--text-primary) !important;
}

/* ── Sidebar ──────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--bg-card) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stTextInput label,
[data-testid="stSidebar"] p {
    color: var(--text-primary) !important;
}

/* ── Main header ──────────────────────────────────────────────────────── */
.app-header {
    background: linear-gradient(135deg, #1a1f2e 0%, #0d1117 100%);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 24px 32px;
    margin-bottom: 24px;
    text-align: center;
}
.app-header h1 {
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 6px 0;
}
.app-header p {
    color: var(--text-muted) !important;
    font-size: 0.95rem;
    margin: 0;
}

/* ── Stage cards ──────────────────────────────────────────────────────── */
.stage-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 20px 24px;
    margin-bottom: 16px;
    position: relative;
}
.stage-card.success { border-left: 4px solid var(--accent2); }
.stage-card.error   { border-left: 4px solid var(--accent3); }
.stage-card.running { border-left: 4px solid var(--accent4); animation: pulse 1.5s infinite; }

@keyframes pulse {
    0%, 100% { border-left-color: var(--accent4); }
    50%       { border-left-color: #b88a20; }
}

/* ── Stage header row ─────────────────────────────────────────────────── */
.stage-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
}
.stage-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--text-primary);
}
.stage-meta {
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: wrap;
}

/* ── Badges / chips ───────────────────────────────────────────────────── */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 500;
    font-family: var(--font-mono);
}
.badge-blue   { background: rgba(88,166,255,0.15); color: var(--accent); border: 1px solid rgba(88,166,255,0.3); }
.badge-green  { background: rgba(63,185,80,0.15);  color: var(--accent2); border: 1px solid rgba(63,185,80,0.3); }
.badge-red    { background: rgba(247,129,102,0.15);color: var(--accent3); border: 1px solid rgba(247,129,102,0.3); }
.badge-yellow { background: rgba(227,179,65,0.15); color: var(--accent4); border: 1px solid rgba(227,179,65,0.3); }
.badge-gray   { background: rgba(139,148,158,0.15);color: var(--text-muted); border: 1px solid rgba(139,148,158,0.3); }

/* ── JSON viewer ─────────────────────────────────────────────────────── */
.json-viewer {
    background: #0d1117;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
    font-family: var(--font-mono);
    font-size: 0.8rem;
    line-height: 1.6;
    overflow-x: auto;
    max-height: 400px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
    color: #a5d6ff;
}

/* ── Timeline bar ────────────────────────────────────────────────────── */
.timeline-container {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 20px 24px;
    margin-bottom: 20px;
}
.timeline-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
}
.timeline-label {
    width: 200px;
    font-size: 0.82rem;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.timeline-bar-bg {
    flex: 1;
    background: var(--bg-card2);
    border-radius: 4px;
    height: 12px;
    overflow: hidden;
}
.timeline-bar-fill {
    height: 100%;
    border-radius: 4px;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    transition: width 0.4s ease;
}
.timeline-value {
    width: 70px;
    font-size: 0.78rem;
    color: var(--text-muted);
    text-align: right;
    font-family: var(--font-mono);
}

/* ── Metric cards ────────────────────────────────────────────────────── */
.metric-row {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 20px;
}
.metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px 20px;
    flex: 1;
    min-width: 120px;
    text-align: center;
}
.metric-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--accent);
    font-family: var(--font-mono);
}
.metric-label {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-top: 4px;
}

/* ── Final output box ────────────────────────────────────────────────── */
.final-output-box {
    background: linear-gradient(135deg, #0d2137 0%, #0a1628 100%);
    border: 1px solid rgba(88,166,255,0.4);
    border-radius: var(--radius-lg);
    padding: 24px 28px;
    margin-top: 8px;
}
.final-output-box h3 {
    color: var(--accent) !important;
    font-size: 1.1rem;
    margin: 0 0 16px 0;
}

/* ── Error box ────────────────────────────────────────────────────────── */
.error-box {
    background: rgba(247,129,102,0.08);
    border: 1px solid rgba(247,129,102,0.4);
    border-radius: var(--radius);
    padding: 16px 20px;
    color: var(--accent3) !important;
    font-size: 0.9rem;
}

/* ── Info box ─────────────────────────────────────────────────────────── */
.info-box {
    background: rgba(88,166,255,0.07);
    border: 1px solid rgba(88,166,255,0.25);
    border-radius: var(--radius);
    padding: 12px 16px;
    font-size: 0.88rem;
    color: var(--text-muted) !important;
}

/* ── History item ────────────────────────────────────────────────────── */
.history-item {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 12px 16px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: border-color 0.2s;
}
.history-item:hover { border-color: var(--accent); }
.history-item .hi-title { font-weight: 600; font-size: 0.9rem; }
.history-item .hi-meta  { font-size: 0.78rem; color: var(--text-muted); margin-top: 3px; }

/* ── Prompt text box ─────────────────────────────────────────────────── */
.prompt-box {
    background: #0d1117;
    border: 1px dashed var(--border);
    border-radius: var(--radius);
    padding: 14px 16px;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    line-height: 1.65;
    color: #cdd9e5;
    max-height: 300px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
}

/* ── Streamlit overrides ─────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #1f6feb, #388bfd) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: var(--radius) !important;
    font-weight: 600 !important;
    transition: opacity 0.2s !important;
}
.stButton > button:hover { opacity: 0.88 !important; }

/* Secondary button style via class workaround */
.btn-secondary > button {
    background: var(--bg-card2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
}

div[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
}
div[data-testid="stExpander"] summary {
    color: var(--text-primary) !important;
    font-weight: 500;
}

.stTextArea > label, .stSelectbox > label {
    color: var(--text-primary) !important;
    font-weight: 500;
}

.stProgress > div > div {
    background: linear-gradient(90deg, var(--accent), var(--accent2)) !important;
}

/* ── Divider ──────────────────────────────────────────────────────────── */
hr.section-divider {
    border: none;
    border-top: 1px solid var(--border);
    margin: 24px 0;
}
</style>
"""
