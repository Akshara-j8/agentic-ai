"""
TechVest Recruitment Agent — Candidate Card Components
Enterprise-grade candidate cards with scores, badges, skills, and action buttons.
"""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st

from config.settings import UIConstants


# ---------------------------------------------------------------------------
# Avatar colour palette (deterministic by name)
# ---------------------------------------------------------------------------
AVATAR_COLORS = [
    ("rgba(99,102,241,0.2)", "#6366F1"),
    ("rgba(139,92,246,0.2)", "#8B5CF6"),
    ("rgba(6,182,212,0.2)", "#06B6D4"),
    ("rgba(16,185,129,0.2)", "#10B981"),
    ("rgba(245,158,11,0.2)", "#F59E0B"),
    ("rgba(239,68,68,0.2)", "#EF4444"),
]


def _avatar_colors(name: str) -> tuple[str, str]:
    idx = sum(ord(c) for c in name) % len(AVATAR_COLORS)
    return AVATAR_COLORS[idx]


def _initials(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if name else "?"


def _badge_html(recommendation: str) -> str:
    cls = {
        "Interview": "badge-interview",
        "Hold": "badge-hold",
        "Reject": "badge-reject",
    }.get(recommendation, "badge-hold")
    icon = {"Interview": "✅", "Hold": "⏸️", "Reject": "❌"}.get(recommendation, "•")
    return f'<span class="badge {cls}">{icon} {recommendation}</span>'


def _score_bar(score: float) -> str:
    color = UIConstants.score_color(score)
    return f"""
    <div class="score-bar-container" style="margin:4px 0;">
        <div class="score-bar-fill" style="width:{score}%; background:linear-gradient(90deg,{color}aa,{color});"></div>
    </div>"""


def _skill_chips(skills: list[str], max_show: int = 8) -> str:
    shown = skills[:max_show]
    rest = len(skills) - max_show
    html = "".join(f'<span class="skill-chip">{s}</span>' for s in shown)
    if rest > 0:
        html += f'<span class="skill-chip" style="opacity:0.5;">+{rest} more</span>'
    return html


# ---------------------------------------------------------------------------
# Main candidate card
# ---------------------------------------------------------------------------

def render_candidate_card(
    scorecard: dict[str, Any],
    profile: dict[str, Any],
    show_actions: bool = True,
    run_id: str = "",
) -> Optional[str]:
    """
    Render a full enterprise candidate card.

    Returns:
        "approve" | "reject" | "schedule" | None depending on button clicked
    """
    name = scorecard.get("candidate_name", profile.get("name", "Unknown"))
    score = scorecard.get("overall_weighted_score", 0.0)
    rec = scorecard.get("recommendation", "Reject")
    confidence = scorecard.get("confidence", 0.5)
    strengths = scorecard.get("strengths", [])
    gaps = scorecard.get("gaps", [])
    reasoning = scorecard.get("reasoning", "")
    injection = profile.get("injection_detected", False)
    years_exp = profile.get("years_experience", 0)
    skills = profile.get("skills", []) + profile.get("programming_languages", [])
    education = profile.get("education", [])
    projects = profile.get("projects", [])
    criterion_scores = scorecard.get("criterion_scores", {})

    bg, fg = _avatar_colors(name)
    score_color = UIConstants.score_color(score)

    # Injection warning strip
    injection_html = ""
    if injection:
        severity = profile.get("injection_severity", "medium")
        injection_html = f"""
        <div class="injection-warning" style="margin-bottom:0.75rem;">
            <div class="warning-title">⚠️ Prompt Injection Detected (severity: {severity.upper()})</div>
            <div style="font-size:0.72rem; color:#94A3B8; margin-top:0.25rem;">
                Score penalty of −15 points applied. Attack quarantined.
            </div>
        </div>"""

    # Education summary
    edu_summary = ""
    for edu in education[:1]:
        edu_summary = f"{edu.get('degree','')}, {edu.get('institution','')}"
        if edu.get("year"):
            edu_summary += f" ({edu['year']})"

    card_html = f"""
    <div class="candidate-card animate-fade-in">
        {injection_html}
        <div style="display:flex; align-items:flex-start; gap:1rem; margin-bottom:1rem;">
            <div class="avatar" style="background:{bg}; color:{fg}; width:56px; height:56px;
                 border-radius:50%; display:flex; align-items:center; justify-content:center;
                 font-size:1.3rem; font-weight:800; flex-shrink:0; border:2px solid {fg}40;">
                {_initials(name)}
            </div>
            <div style="flex:1; min-width:0;">
                <div style="display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap;">
                    <div class="candidate-name">{name}</div>
                    {_badge_html(rec)}
                    {'<span class="badge badge-injection">⚠️ INJECTION</span>' if injection else ''}
                </div>
                <div class="candidate-meta" style="margin-top:0.2rem;">
                    {years_exp} year{"s" if years_exp != 1 else ""} experience
                    {f" · {edu_summary}" if edu_summary else ""}
                </div>
            </div>
            <div style="text-align:right; flex-shrink:0;">
                <div style="font-size:1.8rem; font-weight:800; color:{score_color}; line-height:1;">
                    {score:.0f}
                </div>
                <div style="font-size:0.65rem; color:#64748B; text-transform:uppercase; letter-spacing:0.06em;">
                    / 100
                </div>
                <div style="font-size:0.7rem; color:#64748B; margin-top:2px;">
                    {confidence*100:.0f}% conf.
                </div>
            </div>
        </div>
        {_score_bar(score)}
        <div style="margin-top:0.75rem;">
            {_skill_chips(list(dict.fromkeys(skills)), max_show=10)}
        </div>
    </div>"""

    st.markdown(card_html, unsafe_allow_html=True)

    # --- Expandable detail section ---
    with st.expander(f"🔍 View Full Analysis — {name}", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Strengths**")
            for s in strengths:
                st.markdown(f"✅ {s}")
            if education:
                st.markdown("**Education**")
                for edu in education:
                    st.markdown(f"🎓 {edu.get('degree','?')} — {edu.get('institution','?')} {edu.get('year','')}")

        with col2:
            st.markdown("**Skill Gaps**")
            for g in gaps:
                st.markdown(f"⚠️ {g}")
            if projects:
                st.markdown("**Projects**")
                for proj in projects[:3]:
                    st.markdown(f"🔧 **{proj.get('name','')}** — {proj.get('description','')[:80]}")

        if reasoning:
            st.markdown("**Agent Reasoning**")
            st.info(reasoning)

        # Criterion breakdown
        if criterion_scores:
            st.markdown("**Rubric Breakdown**")
            from config.rubric import RUBRIC
            for criterion in RUBRIC.criteria:
                key = criterion.key
                cs = criterion_scores.get(key, {})
                cs_score = cs.get("score", 0) if isinstance(cs, dict) else 0
                cs_evidence = cs.get("evidence", "") if isinstance(cs, dict) else ""
                bar_pct = cs_score * 10
                bar_color = UIConstants.score_color(bar_pct)
                st.markdown(
                    f'<div style="margin-bottom:6px;">'
                    f'<div style="display:flex; justify-content:space-between; font-size:0.75rem; margin-bottom:2px;">'
                    f'<span style="color:#94A3B8;">{criterion.label}</span>'
                    f'<span style="color:{bar_color}; font-weight:700;">{cs_score}/10</span>'
                    f'</div>'
                    f'<div class="score-bar-container">'
                    f'<div class="score-bar-fill" style="width:{bar_pct}%; background:{bar_color};"></div>'
                    f'</div>'
                    f'<div style="font-size:0.68rem; color:#64748B; margin-top:2px;">{cs_evidence[:80]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # --- Action buttons ---
    action = None
    if show_actions:
        btn_cols = st.columns(4)
        safe_name = name.replace(" ", "_").lower()
        with btn_cols[0]:
            if st.button("✅ Approve", key=f"approve_{safe_name}_{run_id}", use_container_width=True):
                action = "approve"
        with btn_cols[1]:
            if st.button("❌ Reject", key=f"reject_{safe_name}_{run_id}", use_container_width=True):
                action = "reject"
        with btn_cols[2]:
            if st.button("📅 Schedule", key=f"schedule_{safe_name}_{run_id}", use_container_width=True):
                action = "schedule"
        with btn_cols[3]:
            _render_download_button(scorecard, profile, safe_name)

    return action


def _render_download_button(scorecard: dict, profile: dict, safe_name: str) -> None:
    """Render download buttons for the candidate report (PDF + JSON)."""
    import json

    # JSON report
    report = {"profile": profile, "scorecard": scorecard}
    json_bytes = json.dumps(report, default=str, indent=2).encode("utf-8")

    # PDF report
    try:
        from utils.report import generate_candidate_report_pdf

        pdf_bytes = generate_candidate_report_pdf(
            candidate_name=scorecard.get("candidate_name", profile.get("name", safe_name)),
            profile=profile,
            scorecard=scorecard,
            run_id="",
        )
    except Exception:
        pdf_bytes = None

    st.download_button(
        "⬇️ Report (PDF)",
        data=pdf_bytes if pdf_bytes is not None else json_bytes,
        file_name=(
            f"techvest_{safe_name}_report.pdf" if pdf_bytes is not None else f"techvest_{safe_name}_report.json"
        ),
        mime=(
            "application/pdf" if pdf_bytes is not None else "application/json"
        ),
        key=f"dl_pdf_{safe_name}",
        use_container_width=True,
    )

    # Secondary JSON download (always available)
    st.download_button(
        "⬇️ Report (JSON)",
        data=json_bytes,
        file_name=f"techvest_{safe_name}_report.json",
        mime="application/json",
        key=f"dl_json_{safe_name}",
        use_container_width=True,
    )



# ---------------------------------------------------------------------------
# Compact shortlist row (for tables)
# ---------------------------------------------------------------------------

def render_shortlist_row(decision: dict[str, Any], rank: int) -> None:
    """Render a compact ranked shortlist row."""
    name = decision.get("candidate_name", "?")
    score = decision.get("weighted_score", 0)
    rec = decision.get("final_recommendation", "Reject")
    confidence = decision.get("confidence", 0.5)
    priority = decision.get("priority_flag", False)

    bg, fg = _avatar_colors(name)
    score_color = UIConstants.score_color(score)
    rec_color = {"Interview": "#10B981", "Hold": "#F59E0B", "Reject": "#EF4444"}.get(rec, "#94A3B8")

    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:1rem; padding:0.75rem;
         background:rgba(30,41,59,0.5); border-radius:12px; margin-bottom:6px;
         border:1px solid rgba(255,255,255,0.05);">
        <div style="font-size:1rem; font-weight:800; color:#475569; width:24px; text-align:center;">
            {'🥇' if rank == 1 else '🥈' if rank == 2 else '🥉' if rank == 3 else f'#{rank}'}
        </div>
        <div style="width:36px; height:36px; border-radius:50%; background:{bg};
             display:flex; align-items:center; justify-content:center;
             font-size:0.8rem; font-weight:700; color:{fg}; flex-shrink:0;">
            {_initials(name)}
        </div>
        <div style="flex:1;">
            <div style="font-size:0.88rem; font-weight:600; color:#F1F5F9;">
                {name} {'⭐' if priority else ''}
            </div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:1rem; font-weight:800; color:{score_color};">{score:.1f}</div>
            <div style="font-size:0.65rem; color:{rec_color}; font-weight:600;">{rec}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
