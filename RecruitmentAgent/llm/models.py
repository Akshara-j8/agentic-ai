"""
TechVest Recruitment Agent — Pydantic Output Models
All structured LLM outputs are validated through these models.
Ensures type safety and consistent data shapes throughout the pipeline.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Recommendation(str, Enum):
    INTERVIEW = "Interview"
    HOLD = "Hold"
    REJECT = "Reject"


class InjectionSeverity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FairnessStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class InterviewFormat(str, Enum):
    VIDEO = "Video"
    ONSITE = "On-site"
    PHONE = "Phone"


class InterviewType(str, Enum):
    TECHNICAL = "Technical"
    HR = "HR"
    PANEL = "Panel"


# ---------------------------------------------------------------------------
# Resume parsing models
# ---------------------------------------------------------------------------

class EducationEntry(BaseModel):
    degree: str
    institution: str
    year: Optional[int] = None
    gpa: Optional[float] = None


class ExperienceEntry(BaseModel):
    title: str
    company: str
    duration_months: int = 0
    responsibilities: list[str] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    name: str
    description: str
    technologies: list[str] = Field(default_factory=list)


class ParsedProfile(BaseModel):
    """
    Structured candidate profile extracted from resume text.
    Demographic identifiers are retained here but stripped before scoring.
    """

    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    years_experience: int = 0
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    programming_languages: list[str] = Field(default_factory=list)
    ml_frameworks: list[str] = Field(default_factory=list)
    tools_and_platforms: list[str] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    publications: list[str] = Field(default_factory=list)
    raw_text_snippet: str = ""

    # Internal tracking
    resume_filename: str = ""
    injection_detected: bool = False
    injection_severity: InjectionSeverity = InjectionSeverity.NONE
    parse_timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("years_experience", mode="before")
    @classmethod
    def clamp_years(cls, v: Any) -> int:
        try:
            return max(0, min(int(v), 50))
        except (TypeError, ValueError):
            return 0

    @property
    def all_skills(self) -> list[str]:
        """Combined deduplicated skill list."""
        combined = set(self.skills + self.programming_languages + self.ml_frameworks + self.tools_and_platforms)
        return sorted(combined)

    def anonymised_dict(self) -> dict[str, Any]:
        """
        Return profile with PII stripped for fairness-safe scoring.
        Removes: name, email, phone, institution names from education.
        """
        data = self.model_dump()
        data["name"] = "CANDIDATE_ANONYMISED"
        data["email"] = None
        data["phone"] = None
        data["location"] = None
        # Anonymise institution names
        for edu in data.get("education", []):
            edu["institution"] = "INSTITUTION_ANONYMISED"
        return data


# ---------------------------------------------------------------------------
# Scoring models
# ---------------------------------------------------------------------------

class CriterionScore(BaseModel):
    score: float = Field(ge=0, le=10)
    evidence: str = ""
    notes: str = ""

    @field_validator("score", mode="before")
    @classmethod
    def clamp_score(cls, v: Any) -> float:
        try:
            return max(0.0, min(float(v), 10.0))
        except (TypeError, ValueError):
            return 0.0


class Scorecard(BaseModel):
    """Complete scoring result for one candidate."""

    candidate_name: str
    criterion_scores: dict[str, CriterionScore] = Field(default_factory=dict)
    overall_weighted_score: float = Field(ge=0.0, le=100.0, default=0.0)
    recommendation: Recommendation = Recommendation.REJECT
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    reasoning: str = ""
    score_timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Guardrail flags
    injection_penalty_applied: bool = False
    fairness_reviewed: bool = False

    @field_validator("overall_weighted_score", mode="before")
    @classmethod
    def clamp_overall(cls, v: Any) -> float:
        try:
            return max(0.0, min(float(v), 100.0))
        except (TypeError, ValueError):
            return 0.0

    @property
    def score_band(self) -> str:
        if self.overall_weighted_score >= 75:
            return "Exceptional"
        elif self.overall_weighted_score >= 60:
            return "Strong"
        elif self.overall_weighted_score >= 50:
            return "Good"
        elif self.overall_weighted_score >= 35:
            return "Below Average"
        return "Poor"

    def to_display_dict(self) -> dict[str, Any]:
        return {
            "name": self.candidate_name,
            "score": round(self.overall_weighted_score, 1),
            "recommendation": self.recommendation.value,
            "confidence": round(self.confidence * 100, 1),
            "band": self.score_band,
            "strengths": self.strengths,
            "gaps": self.gaps,
            "reasoning": self.reasoning,
        }


# ---------------------------------------------------------------------------
# Interview scheduling models
# ---------------------------------------------------------------------------

class InterviewSlot(BaseModel):
    date: str                            # YYYY-MM-DD
    time: str                            # HH:MM
    timezone: str = "Asia/Kolkata"
    interviewer: str = ""
    duration_minutes: int = 60
    format: InterviewFormat = InterviewFormat.VIDEO


class AvailabilityResult(BaseModel):
    """Interview scheduling result for one candidate."""

    candidate_name: str
    interview_type: InterviewType = InterviewType.TECHNICAL
    proposed_slots: list[InterviewSlot] = Field(default_factory=list)
    preferred_slot: int = 0
    notes: str = ""
    scheduled: bool = False
    confirmed_slot: Optional[InterviewSlot] = None

    @property
    def best_slot(self) -> Optional[InterviewSlot]:
        if not self.proposed_slots:
            return None
        idx = min(self.preferred_slot, len(self.proposed_slots) - 1)
        return self.proposed_slots[idx]


# ---------------------------------------------------------------------------
# Guardrail models
# ---------------------------------------------------------------------------

class InjectionResult(BaseModel):
    injection_detected: bool = False
    severity: InjectionSeverity = InjectionSeverity.NONE
    attack_type: Optional[str] = None
    flagged_text: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    recommendation: str = "allow"
    sanitised_text: str = ""


class FairnessCheck(BaseModel):
    check_name: str
    status: FairnessStatus = FairnessStatus.PASS
    finding: Optional[str] = None
    affected_candidates: list[str] = Field(default_factory=list)


class FairnessResult(BaseModel):
    overall_fairness: FairnessStatus = FairnessStatus.PASS
    checks: list[FairnessCheck] = Field(default_factory=list)
    bias_score: float = Field(ge=0.0, le=1.0, default=0.0)
    recommendations: list[str] = Field(default_factory=list)
    audit_notes: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Decision models
# ---------------------------------------------------------------------------

class CandidateDecision(BaseModel):
    candidate_name: str
    final_recommendation: Recommendation = Recommendation.REJECT
    rank: int = 0
    weighted_score: float = 0.0
    confidence: float = 0.5
    reasoning: str = ""
    priority_flag: bool = False


class DecisionResult(BaseModel):
    decisions: list[CandidateDecision] = Field(default_factory=list)
    summary: str = ""
    top_candidate: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def ranked_decisions(self) -> list[CandidateDecision]:
        return sorted(self.decisions, key=lambda d: d.weighted_score, reverse=True)


# ---------------------------------------------------------------------------
# Trajectory / audit event models
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    DECISION = "decision"
    GUARDRAIL = "guardrail"
    HUMAN = "human_approval"
    SCHEDULER = "scheduler"
    ERROR = "error"


class TrajectoryEvent(BaseModel):
    """Single event in the agent's reasoning trajectory."""

    event_id: str = ""
    event_type: EventType
    node: str = ""
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: Optional[float] = None
    success: bool = True

    @property
    def icon(self) -> str:
        icons = {
            EventType.THOUGHT: "🧠",
            EventType.ACTION: "⚡",
            EventType.OBSERVATION: "👁️",
            EventType.DECISION: "🎯",
            EventType.GUARDRAIL: "🛡️",
            EventType.HUMAN: "👤",
            EventType.SCHEDULER: "📅",
            EventType.ERROR: "❌",
        }
        return icons.get(self.event_type, "•")

    @property
    def color(self) -> str:
        colors = {
            EventType.THOUGHT: "#6366F1",
            EventType.ACTION: "#06B6D4",
            EventType.OBSERVATION: "#10B981",
            EventType.DECISION: "#8B5CF6",
            EventType.GUARDRAIL: "#F59E0B",
            EventType.HUMAN: "#3B82F6",
            EventType.SCHEDULER: "#10B981",
            EventType.ERROR: "#EF4444",
        }
        return colors.get(self.event_type, "#94A3B8")


# ---------------------------------------------------------------------------
# Plan node output model
# ---------------------------------------------------------------------------

class PlanDecision(BaseModel):
    next_action: str
    target_candidate: Optional[str] = None
    reasoning: str = ""
    estimated_steps_remaining: int = 5


# ---------------------------------------------------------------------------
# Agent run summary
# ---------------------------------------------------------------------------

class RunSummary(BaseModel):
    """Summary of a complete agent run."""

    run_id: str = ""
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    total_candidates: int = 0
    interview_count: int = 0
    hold_count: int = 0
    reject_count: int = 0
    avg_score: float = 0.0
    top_candidate: str = ""
    guardrail_passes: int = 0
    guardrail_failures: int = 0
    total_tool_calls: int = 0
    total_llm_calls: int = 0
    injection_detected: bool = False
    fairness_status: str = "PASS"
    total_duration_seconds: float = 0.0
    status: str = "completed"

    @property
    def duration_str(self) -> str:
        secs = int(self.total_duration_seconds)
        return f"{secs // 60}m {secs % 60}s" if secs >= 60 else f"{secs}s"
