import streamlit as st
from main import ask, MODELS, short_name

st.set_page_config(
    page_title="Multi-Model Comparison Tool",
    page_icon="🧠",
    layout="wide",
)

# ---------------------------------------------------------------- styling
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    /* hide default chrome */
    #MainMenu, footer, header {visibility: hidden;}

    html, body, [class*="css"] {font-family: 'Plus Jakarta Sans', sans-serif;}

    .stApp {
        background:
            radial-gradient(1100px 500px at 8% -8%, #FFE0F0 0%, rgba(255,224,240,0) 55%),
            radial-gradient(1000px 520px at 100% 0%, #DDE7FF 0%, rgba(221,231,255,0) 55%),
            radial-gradient(900px 600px at 50% 120%, #E3FFF7 0%, rgba(227,255,247,0) 60%),
            #FBFAFF;
    }

    .block-container {padding-top: 2.2rem; max-width: 1200px;}

    @keyframes shimmer {
        0%   {background-position: 0% 50%;}
        50%  {background-position: 100% 50%;}
        100% {background-position: 0% 50%;}
    }
    @keyframes rise {
        from {opacity: 0; transform: translateY(14px);}
        to   {opacity: 1; transform: translateY(0);}
    }

    /* gradient hero */
    .hero {
        background: linear-gradient(115deg, #EC4899 0%, #8B5CF6 38%, #6366F1 68%, #06B6D4 100%);
        background-size: 220% 220%;
        animation: shimmer 9s ease infinite;
        border-radius: 24px;
        padding: 38px 44px;
        color: #fff;
        box-shadow: 0 18px 44px rgba(139, 92, 246, 0.34);
        margin-bottom: 28px;
        position: relative;
        overflow: hidden;
    }
    .hero::after {
        content: "";
        position: absolute;
        top: -40%; right: -10%;
        width: 320px; height: 320px;
        background: radial-gradient(circle, rgba(255,255,255,.28) 0%, rgba(255,255,255,0) 70%);
    }
    .hero h1 {
        font-size: 2.3rem;
        font-weight: 800;
        margin: 0 0 8px 0;
        letter-spacing: -0.6px;
        color: #fff;
    }
    .hero p {
        font-size: 1.05rem;
        margin: 0;
        opacity: 0.95;
        font-weight: 500;
    }

    /* result card */
    .card {
        position: relative;
        background: rgba(255,255,255,0.72);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255,255,255,0.9);
        border-radius: 20px;
        padding: 24px 24px 22px;
        box-shadow: 0 10px 30px rgba(80, 60, 140, 0.10);
        height: 100%;
        overflow: hidden;
        animation: rise .45s ease both;
        transition: transform .18s ease, box-shadow .18s ease;
    }
    .card::before {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 6px;
        background: var(--accent, #8B5CF6);
        background-image: var(--accent-grad);
    }
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 22px 44px rgba(80, 60, 140, 0.18);
    }
    .card-head {
        display: flex;
        align-items: center;
        gap: 13px;
        margin-bottom: 16px;
    }
    .avatar {
        width: 46px; height: 46px;
        border-radius: 13px;
        display: grid; place-items: center;
        font-weight: 800; font-size: 1.15rem;
        color: #fff;
        flex-shrink: 0;
        box-shadow: 0 6px 16px rgba(0,0,0,0.18);
    }
    .card-title {font-weight: 800; font-size: 1.08rem; color: #221B3A; line-height: 1.15;}
    .card-sub   {font-size: .78rem; color: #9A92B5; margin-top: 3px; font-weight: 600;}

    .badge {
        display: inline-block;
        font-size: .67rem;
        font-weight: 800;
        padding: 3px 10px;
        border-radius: 999px;
        margin-left: 6px;
        vertical-align: middle;
    }
    .badge-fast  {background: linear-gradient(135deg,#D1FAE5,#A7F3D0); color: #0F9D58;}
    .badge-cheap {background: linear-gradient(135deg,#FEF3C7,#FDE68A); color: #B45309;}
    .badge-err   {background: linear-gradient(135deg,#FFE4E6,#FECDD3); color: #E11D48;}

    .answer {
        background: linear-gradient(180deg,#FAF9FF 0%,#F5F2FF 100%);
        border-radius: 14px;
        padding: 15px 17px;
        font-size: .95rem;
        line-height: 1.6;
        color: #322B47;
        border: 1px solid #EEE9FF;
        min-height: 100px;
    }
    .err-box {
        background: linear-gradient(180deg,#FFF1F2 0%,#FFE4E6 100%);
        border: 1px solid #FECDD3;
        border-radius: 14px;
        padding: 15px 17px;
        color: #BE123C;
        font-size: .9rem;
        min-height: 100px;
    }

    /* stat row */
    .stats {display: flex; gap: 10px; margin-top: 18px;}
    .stat {
        flex: 1;
        border-radius: 14px;
        padding: 12px 10px;
        text-align: center;
        border: 1px solid transparent;
    }
    .stat-lat  {background: linear-gradient(180deg,#EFF6FF,#DBEAFE); border-color:#BFDBFE;}
    .stat-tok  {background: linear-gradient(180deg,#F5F3FF,#EDE9FE); border-color:#DDD6FE;}
    .stat-cost {background: linear-gradient(180deg,#ECFDF5,#D1FAE5); border-color:#A7F3D0;}
    .stat .label {font-size: .66rem; text-transform: uppercase; letter-spacing: .6px; font-weight: 800;}
    .stat-lat  .label {color: #2563EB;}
    .stat-tok  .label {color: #7C3AED;}
    .stat-cost .label {color: #059669;}
    .stat .value {font-size: 1.22rem; font-weight: 800; color: #221B3A; margin-top: 3px;}
    .stat .unit  {font-size: .72rem; color: #9A92B5; font-weight: 700;}

    .stButton > button {
        border-radius: 14px;
        font-weight: 800;
        padding: 0.6rem 1.6rem;
        border: none;
        color: #fff;
        background: linear-gradient(120deg,#EC4899,#8B5CF6 60%,#6366F1);
        background-size: 180% 180%;
        box-shadow: 0 10px 24px rgba(139, 92, 246, 0.40);
        transition: transform .15s ease, box-shadow .15s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 14px 30px rgba(139, 92, 246, 0.50);
        background-position: 100% 50%;
    }
    .stButton > button:disabled {
        background: #D8D2EC;
        box-shadow: none;
        color: #fff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- helpers
# Deterministic accent gradient per model so avatars/cards stay consistent.
_PALETTE = [
    ("#EC4899", "#F472B6"),  # pink
    ("#8B5CF6", "#A78BFA"),  # violet
    ("#06B6D4", "#22D3EE"),  # cyan
    ("#F59E0B", "#FBBF24"),  # amber
    ("#10B981", "#34D399"),  # emerald
    ("#6366F1", "#818CF8"),  # indigo
]

def accent_for(model: str) -> tuple:
    return _PALETTE[sum(ord(c) for c in model) % len(_PALETTE)]

def provider_of(model: str) -> str:
    return model.split("/")[0]

# ---------------------------------------------------------------- hero
st.markdown(
    """
    <div class="hero">
        <h1>🧠 Multi-Model Comparison Tool</h1>
        <p>Ask one question, compare answers, latency and cost across multiple LLMs side by side.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- inputs
with st.container():
    question = st.text_area(
        "Your question",
        placeholder="e.g. A farmer has 17 sheep. All but 9 die. How many are left?",
        height=120,
    )

    selected_models = st.multiselect(
        "Models to compare",
        options=MODELS,
        default=MODELS,
        format_func=short_name,
    )

running = st.session_state.get("running", False)
run = st.button(
    "🚀  Compare models",
    type="primary",
    disabled=running or not question.strip() or not selected_models,
)

if not question.strip() and not run:
    st.info("💡 Type a question above and pick the models you want to compare.")

# ---------------------------------------------------------------- run
def _esc(text: str) -> str:
    """Escape HTML so model output can't break the card or trigger markdown."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )

def render_card(model, result, fastest, cheapest):
    c1, c2 = accent_for(model)
    grad = f"linear-gradient(135deg,{c1},{c2})"
    initial = short_name(model)[0].upper()

    if "error" in result:
        body = f'<div class="err-box">⚠️ {_esc(result["error"])}</div>'
        badges = '<span class="badge badge-err">failed</span>'
        stats = ""
    else:
        badges = ""
        if model == fastest:
            badges += '<span class="badge badge-fast">⚡ fastest</span>'
        if model == cheapest:
            badges += '<span class="badge badge-cheap">💰 cheapest</span>'
        body = f'<div class="answer">{_esc(result["answer"])}</div>'
        stats = (
            '<div class="stats">'
            '<div class="stat stat-lat"><div class="label">Latency</div>'
            f'<div class="value">{result["latency"]:.2f}<span class="unit"> s</span></div></div>'
            '<div class="stat stat-tok"><div class="label">Tokens</div>'
            f'<div class="value">{result["in_tok"]}<span class="unit"> / {result["out_tok"]}</span></div></div>'
            '<div class="stat stat-cost"><div class="label">Cost</div>'
            f'<div class="value"><span class="unit">$ </span>{result["cost"]:.5f}</div></div>'
            '</div>'
        )

    html = (
        f'<div class="card" style="--accent:{c1}; --accent-grad:{grad};">'
        '<div class="card-head">'
        f'<div class="avatar" style="background:{grad};">{initial}</div>'
        f'<div><div class="card-title">{short_name(model)} {badges}</div>'
        f'<div class="card-sub">{provider_of(model)}</div></div>'
        '</div>'
        f'{body}{stats}'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

if run:
    st.session_state["running"] = True
    results = {}
    progress = st.progress(0.0, text="Starting…")
    for i, model in enumerate(selected_models):
        progress.progress(i / len(selected_models), text=f"Querying {short_name(model)}…")
        try:
            results[model] = ask(question, model)
        except Exception as e:
            results[model] = {"error": str(e)}
    progress.progress(1.0, text="Done")
    progress.empty()
    st.session_state["running"] = False

    # determine winners (only among successful runs)
    ok = {m: r for m, r in results.items() if "error" not in r}
    fastest = min(ok, key=lambda m: ok[m]["latency"]) if ok else None
    cheapest = min(ok, key=lambda m: ok[m]["cost"]) if ok else None

    st.markdown(
        '<h3 style="background:linear-gradient(120deg,#EC4899,#8B5CF6,#6366F1);'
        '-webkit-background-clip:text;background-clip:text;color:transparent;'
        'font-weight:800;margin:6px 0 14px;">✨ Results</h3>',
        unsafe_allow_html=True,
    )
    cols = st.columns(len(results))
    for col, (model, result) in zip(cols, results.items()):
        with col:
            render_card(model, result, fastest, cheapest)

    st.caption(
        "Costs are illustrative estimates based on published per-token prices and may not reflect actual billing."
    )
