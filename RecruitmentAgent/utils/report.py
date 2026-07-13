"""TechVest PDF report generator.

This module generates a per-candidate enterprise report PDF.
It is used by Streamlit download buttons.

Requirements:
- reportlab
- Works without external assets.
"""

from __future__ import annotations

import io
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _safe_str(x: Any, default: str = "") -> str:
    if x is None:
        return default
    return str(x)


def _make_styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "title",
            parent=styles["Title"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#111827"),
        ),
        "h": ParagraphStyle(
            "h",
            parent=styles["Heading2"],
            fontSize=12,
            leading=14,
            textColor=colors.HexColor("#111827"),
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=styles["BodyText"],
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#111827"),
        ),
        "small": ParagraphStyle(
            "small",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=10,
            textColor=colors.HexColor("#374151"),
        ),
    }


def generate_candidate_report_pdf(
    *,
    candidate_name: str,
    profile: dict[str, Any],
    scorecard: dict[str, Any],
    run_id: str = "",
) -> bytes:
    """Generate a PDF report for a single candidate.

    Args:
        candidate_name: Candidate display name
        profile: Parsed profile dict
        scorecard: Scorecard dict
        run_id: Optional run id

    Returns:
        PDF bytes
    """

    buf = io.BytesIO()
    styles = _make_styles()

    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=30,
    )

    overall = float(scorecard.get("overall_weighted_score", 0.0) or 0.0)
    recommendation = _safe_str(scorecard.get("recommendation", "Reject"))
    confidence = float(scorecard.get("confidence", 0.0) or 0.0)

    inj = bool(profile.get("injection_detected", False))
    inj_sev = _safe_str(profile.get("injection_severity", "medium"))

    # Header
    story: list[Any] = []
    story.append(Paragraph("TechVest Recruitment Agent — Candidate Report", styles["title"]))
    story.append(Spacer(1, 10))

    meta_lines = [
        f"<b>Candidate:</b> {_safe_str(candidate_name)}",
        f"<b>Overall Weighted Score:</b> {overall:.1f} / 100",
        f"<b>Recommendation:</b> {recommendation}",
        f"<b>Confidence:</b> {confidence * 100:.0f}%",
    ]
    if inj:
        meta_lines.append(f"<b>Prompt Injection:</b> YES (severity: {inj_sev})")
    else:
        meta_lines.append("<b>Prompt Injection:</b> No")

    story.append(Paragraph("<br/>".join(meta_lines), styles["body"]))
    if run_id:
        story.append(Paragraph(f"<b>Run ID:</b> {run_id}", styles["small"]))

    # Profile summary
    story.append(Spacer(1, 8))
    story.append(Paragraph("Profile", styles["h"]))

    years_exp = profile.get("years_experience", 0)
    summary = _safe_str(profile.get("summary", ""))

    skills = list(profile.get("skills", []) or []) + list(profile.get("programming_languages", []) or [])
    skills = list(dict.fromkeys(skills))

    edu = profile.get("education", []) or []

    exp_lines = [
        f"<b>Years of experience:</b> {_safe_str(years_exp)}",
        f"<b>Summary:</b> {_safe_str(summary)[:800]}",
    ]
    story.append(Paragraph("<br/>".join(exp_lines), styles["body"]))

    if skills:
        story.append(Paragraph("<b>Key Skills:</b>", styles["small"]))
        story.append(Paragraph(", ".join([_safe_str(s) for s in skills[:20]]), styles["small"]))

    # Education table (top 3)
    if edu:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Education (top entries)", styles["small"]))

        rows = [["Degree", "Institution", "Year"]]
        for e in edu[:3]:
            if not isinstance(e, dict):
                continue
            rows.append([
                _safe_str(e.get("degree", "")),
                _safe_str(e.get("institution", "")),
                _safe_str(e.get("year", "")),
            ])

        table = Table(rows, colWidths=[180, 170, 45])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ])
        )
        story.append(table)

    # Rubric breakdown
    story.append(Spacer(1, 8))
    story.append(Paragraph("Rubric Breakdown", styles["h"]))

    criterion_scores = scorecard.get("criterion_scores", {}) or {}
    rows = [["Criterion", "Score (0-10)", "Evidence"]]
    for key, item in criterion_scores.items():
        if isinstance(item, dict):
            score = item.get("score", 0)
            evidence = item.get("evidence", "")
        else:
            score = 0
            evidence = ""
        rows.append([
            _safe_str(key),
            _safe_str(score),
            _safe_str(evidence)[:140],
        ])

    rubric_table = Table(rows, colWidths=[110, 70, 230])
    rubric_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
            ("FONTSIZE", (0, 0), (-1, -1), 8.0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(rubric_table)

    # Strengths / Gaps / Reasoning
    story.append(Spacer(1, 10))
    story.append(Paragraph("Decision Evidence", styles["h"]))

    strengths = scorecard.get("strengths", []) or []
    gaps = scorecard.get("gaps", []) or []
    reasoning = _safe_str(scorecard.get("reasoning", ""))

    story.append(Paragraph("<b>Strengths:</b>", styles["small"]))
    story.append(Paragraph("<br/>".join([f"• {_safe_str(s)}" for s in strengths[:8]]) or "—", styles["small"]))

    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Skill Gaps:</b>", styles["small"]))
    story.append(Paragraph("<br/>".join([f"• {_safe_str(g)}" for g in gaps[:8]]) or "—", styles["small"]))

    story.append(Spacer(1, 4))
    if reasoning:
        story.append(Paragraph("<b>Agent Reasoning:</b>", styles["small"]))
        story.append(Paragraph(reasoning[:1200], styles["body"]))

    doc.build(story)
    return buf.getvalue()

