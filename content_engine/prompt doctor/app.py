"""
app.py

Streamlit front-end for Prompt Doctor.

Workflow
--------
1. User selects a domain (summarization, translation, code_gen, data_extraction).
2. User sees the current level's task description and a sample input.
3. User writes a prompt in a text area.
4. On "Submit", runner.py executes the prompt on the sample input.
5. examiner.py evaluates the prompt itself (not just the output).
6. Results are displayed: per-principle pass/fail with weaknesses and questions.
7. If every principle passes, the next level is unlocked.
"""

import logging
import os
from typing import Any

import streamlit as st

from examiner import examine
from levels import DOMAINS, LEVELS, get_level
from runner import run_prompt

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Prompt Doctor",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
_DEFAULT_STATE: dict[str, Any] = {
    "domain_id": DOMAINS[0]["id"],
    "level_id": 1,
    "max_unlocked_level": 1,
    "submitted": False,
    "exam_result": None,
    "runner_result": None,
    "current_sample": None,
    "error": None,
}

for key, val in _DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ---------------------------------------------------------------------------
# Helper: get the current domain dict
# ---------------------------------------------------------------------------
def _current_domain() -> dict | None:
    for d in DOMAINS:
        if d["id"] == st.session_state.domain_id:
            return d
    return None


# ---------------------------------------------------------------------------
# Sidebar — domain & level selection
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image(
        "https://img.icons8.com/fluency/96/doctor-male.png",
        width=64,
    )
    st.title("Prompt Doctor")
    st.caption("Learn prompt engineering, one level at a time.")

    st.divider()

    # --- Domain selector ---
    domain_options = {d["label"]: d["id"] for d in DOMAINS}
    selected_label = st.selectbox(
        "Choose a domain",
        options=list(domain_options.keys()),
        index=0,
        key="domain_selector",
    )
    # Reset level when domain changes
    if st.session_state.domain_id != domain_options[selected_label]:
        st.session_state.domain_id = domain_options[selected_label]
        st.session_state.level_id = 1
        st.session_state.max_unlocked_level = 1
        st.session_state.submitted = False
        st.session_state.exam_result = None
        st.session_state.runner_result = None
        st.session_state.current_sample = None
        st.session_state.error = None

    st.divider()

    # --- Level progress ---
    st.subheader("Progress")
    for lvl in LEVELS:
        lvl_id = lvl["id"]
        unlocked = lvl_id <= st.session_state.max_unlocked_level
        completed = lvl_id < st.session_state.max_unlocked_level
        current = lvl_id == st.session_state.level_id

        if completed:
            icon = "✅"
        elif current:
            icon = "▶️"
        elif unlocked:
            icon = "🔓"
        else:
            icon = "🔒"

        st.markdown(f"{icon} **Level {lvl_id}:** {lvl['title']}")

    st.divider()
    st.caption("Built with Streamlit + OpenRouter")


# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
domain = _current_domain()
if domain is None:
    st.error("Selected domain not found.  Please choose another.")
    st.stop()

level = get_level(st.session_state.level_id)
if level is None:
    st.error(f"Level {st.session_state.level_id} not found.")
    st.stop()

# --- Header ---
st.header(f"🩺 Level {level['id']}: {level['title']}")
st.markdown(level["description"])

# --- Principles for this level ---
principles = level["principles"]
st.markdown("**Principles being evaluated:**")
cols = st.columns(len(principles))
for col, pname in zip(cols, principles):
    col.markdown(f"- `{pname}`")

st.divider()

# --- Sample input ---
samples = domain["sample_inputs"]
# Cycle through samples based on level_id so the user gets variety
sample_idx = (level["id"] - 1) % len(samples)
sample_input = samples[sample_idx]

if st.session_state.current_sample is None:
    st.session_state.current_sample = sample_input

with st.expander("📄 Sample input", expanded=True):
    st.text(st.session_state.current_sample)

# --- Prompt input ---
st.subheader("✍️ Your prompt")
user_prompt = st.text_area(
    "Write your prompt below.  The sample input will be appended automatically.",
    height=200,
    placeholder=(
        "Example: You are an expert summarizer. Summarize the following text "
        "in 2–3 sentences, capturing the key points.\n\n---\n\n{input}"
    ),
    key="prompt_input",
)

# --- Submit ---
col1, col2 = st.columns([1, 5])
with col1:
    submitted = st.button(
        "🚀 Submit",
        type="primary",
        use_container_width=True,
        disabled=not user_prompt.strip(),
    )

if submitted:
    st.session_state.submitted = True
    st.session_state.exam_result = None
    st.session_state.runner_result = None
    st.session_state.error = None

    # 1. Combine prompt with sample input and run through the model
    full_prompt = user_prompt.strip() + "\n\n" + st.session_state.current_sample
    with st.spinner("Running your prompt through the model..."):
        runner_result = run_prompt(full_prompt, st.session_state.current_sample)
        st.session_state.runner_result = runner_result

    if not runner_result["ok"]:
        st.session_state.error = runner_result["error"]
    else:
        # 2. Examine the prompt
        with st.spinner("The examiner is grading your prompt..."):
            exam_result = examine(
                user_prompt=user_prompt,
                sample_input=st.session_state.current_sample,
                model_output=runner_result["output"],
                level_id=level["id"],
            )
            st.session_state.exam_result = exam_result

    # Force a rerun so the results section below renders
    st.rerun()

# ---------------------------------------------------------------------------
# Results section (renders after submission)
# ---------------------------------------------------------------------------
if st.session_state.submitted:
    st.divider()
    st.subheader("📊 Results")

    # --- Error display ---
    if st.session_state.error:
        st.error(f"**Execution error:** {st.session_state.error}")
        st.info(
            "Make sure your `.env` file contains a valid `OPENROUTER_API_KEY`."
        )
        st.stop()

    # --- Runner output ---
    runner_res = st.session_state.runner_result
    if runner_res and runner_res.get("output"):
        with st.expander("🤖 Model output", expanded=False):
            st.text(runner_res["output"])
            st.caption(f"Model: {runner_res.get('model', 'unknown')}")

    # --- Examiner results ---
    exam_res = st.session_state.exam_result
    if exam_res is None:
        st.warning("Examiner result not available yet.")
        st.stop()

    verdict = exam_res.get("verdict", "revise")
    ran_ok = exam_res.get("ran_ok", False)

    if verdict == "pass":
        st.success("🎉 **Verdict: PASS** — All principles satisfied!")
    else:
        st.warning("📝 **Verdict: REVISE** — Some principles need work.")

    if not ran_ok:
        st.caption(
            "⚠️ The examiner encountered an issue.  Results below may be "
            "incomplete."
        )

    # --- Per-principle breakdown ---
    st.divider()
    st.subheader("🔍 Principle-by-principle evaluation")

    principles_data = exam_res.get("principles", [])
    for p in principles_data:
        pname = p.get("name", "?")
        passed = p.get("pass", False)
        weakness = p.get("weakness", "")
        question = p.get("question", "")

        if passed:
            st.success(f"✅ **{pname}** — Pass")
        else:
            st.error(f"❌ **{pname}** — Fail")

            if weakness:
                st.markdown(f"**Weakness:** _{weakness}_")
            if question:
                st.markdown(f"**💡 Guiding question:** {question}")

        st.divider()

    # --- Level-up logic ---
    if verdict == "pass":
        current_level = st.session_state.level_id
        if current_level < 5:
            next_level = current_level + 1
            if next_level > st.session_state.max_unlocked_level:
                st.session_state.max_unlocked_level = next_level

            st.balloons()
            st.success(
                f"🌟 **Level {current_level} complete!** "
                f"Level {next_level} is now unlocked."
            )

            if st.button(
                f"➡️ Proceed to Level {next_level}",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.level_id = next_level
                st.session_state.submitted = False
                st.session_state.exam_result = None
                st.session_state.runner_result = None
                st.session_state.current_sample = None
                st.session_state.error = None
                st.rerun()
        else:
            st.balloons()
            st.success(
                "🏆 **Congratulations!** You've completed all 5 levels of "
                "Prompt Doctor!"
            )
    else:
        if st.button("🔄 Try again", use_container_width=True):
            st.session_state.submitted = False
            st.session_state.exam_result = None
            st.session_state.runner_result = None
            st.session_state.error = None
            st.rerun()