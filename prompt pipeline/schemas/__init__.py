"""
schemas/__init__.py — Pydantic schemas for all 6 pipeline tasks.

Each task has 4 stage schemas (S1–S4) representing the structured JSON
that flows between pipeline stages. All schemas inherit from BaseStageOutput
which carries common metadata fields.
"""

from __future__ import annotations
from typing import Any, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ─── Shared helpers ───────────────────────────────────────────────────────────

def _coerce_str(v: Any) -> Any:
    """
    Coerce a value to str when the LLM accidentally returns a list.

    - list  → join with newline
    - other → return unchanged (Pydantic handles normal validation)
    """
    if isinstance(v, list):
        return "\n".join(str(item) for item in v)
    return v


# ─── Shared base ──────────────────────────────────────────────────────────────

class BaseStageOutput(BaseModel):
    """Common fields attached to every stage output."""
    stage: int = Field(..., description="Stage number that produced this output")
    task_id: str = Field(..., description="Pipeline task identifier")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Model confidence 0–1")
    notes: Optional[str] = Field(None, description="Optional model notes or caveats")

    class Config:
        extra = "allow"   # Pass-through unknown fields between stages


# ══════════════════════════════════════════════════════════════════════════════
#  1. SUPPORT TICKET TRIAGE
# ══════════════════════════════════════════════════════════════════════════════

class SupportTicketS1(BaseStageOutput):
    """Stage 1 — Extraction: parse raw ticket into structured fields."""
    customer_name: Optional[str] = None
    subject: str
    raw_issue: str
    product_mentioned: Optional[str] = None
    account_type: Optional[str] = None
    urgency_signals: list[str] = Field(default_factory=list)
    sentiment: str = Field(..., description="positive|neutral|frustrated|angry")
    key_facts: list[str] = Field(default_factory=list)


class SupportTicketS2(BaseStageOutput):
    """Stage 2 — Reasoning: categorise and prioritise."""
    category: str = Field(..., description="billing|technical|account|shipping|general")
    sub_category: Optional[str] = None
    priority: str = Field(..., description="P1-critical|P2-high|P3-medium|P4-low")
    priority_rationale: str
    estimated_resolution_hours: int
    required_team: str
    sla_breach_risk: bool
    reasoning_chain: list[str] = Field(default_factory=list)

    @field_validator("priority_rationale", mode="before")
    @classmethod
    def coerce_prose_to_str(cls, v: Any) -> Any:
        return _coerce_str(v)


class SupportTicketS3(BaseStageOutput):
    """Stage 3 — Final output: draft reply and routing."""
    ticket_id: str
    summary_one_liner: str
    priority: str
    category: str
    assigned_team: str
    suggested_reply: str
    internal_notes: str
    escalate: bool
    tags: list[str] = Field(default_factory=list)

    @field_validator("internal_notes", "suggested_reply", "summary_one_liner", mode="before")
    @classmethod
    def coerce_prose_to_str(cls, v: Any) -> Any:
        return _coerce_str(v)


class SupportTicketS4(BaseStageOutput):
    """Stage 4 — Self-critic: quality check and optional regeneration."""
    quality_score: float = Field(..., ge=0.0, le=10.0)
    issues_found: list[str] = Field(default_factory=list)
    regenerate: bool
    final_output: SupportTicketS3
    improvement_notes: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
#  2. ESSAY GRADER
# ══════════════════════════════════════════════════════════════════════════════

class EssayGraderS1(BaseStageOutput):
    """Stage 1 — Extraction: parse essay structure."""
    title: Optional[str] = None
    word_count: int
    paragraph_count: int
    thesis_statement: Optional[str] = None
    main_arguments: list[str] = Field(default_factory=list)
    evidence_present: bool
    conclusion_present: bool
    writing_level: str = Field(..., description="elementary|middle|high-school|college|graduate")


class EssayGraderS2(BaseStageOutput):
    """Stage 2 — Reasoning: detailed rubric evaluation."""
    content_score: float = Field(..., ge=0, le=25)
    organisation_score: float = Field(..., ge=0, le=25)
    style_score: float = Field(..., ge=0, le=25)
    mechanics_score: float = Field(..., ge=0, le=25)
    total_score: float = Field(..., ge=0, le=100)
    letter_grade: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    reasoning_chain: list[str] = Field(default_factory=list)


class EssayGraderS3(BaseStageOutput):
    """Stage 3 — Final output: student-facing feedback report."""
    overall_grade: str
    total_score: float
    executive_summary: str
    detailed_feedback: dict[str, str]
    top_three_improvements: list[str] = Field(default_factory=list)
    exemplary_sentences: list[str] = Field(default_factory=list)
    recommended_resources: list[str] = Field(default_factory=list)

    @field_validator("executive_summary", mode="before")
    @classmethod
    def coerce_prose_to_str(cls, v: Any) -> Any:
        return _coerce_str(v)


class EssayGraderS4(BaseStageOutput):
    """Stage 4 — Self-critic."""
    quality_score: float = Field(..., ge=0.0, le=10.0)
    issues_found: list[str] = Field(default_factory=list)
    regenerate: bool
    final_output: EssayGraderS3
    improvement_notes: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
#  3. BUG REPORT TRIAGE
# ══════════════════════════════════════════════════════════════════════════════

class BugReportS1(BaseStageOutput):
    """Stage 1 — Extraction: parse raw bug report."""
    title: str
    reporter: Optional[str] = None
    environment: Optional[str] = None
    steps_to_reproduce: list[str] = Field(default_factory=list)
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    error_messages: list[str] = Field(default_factory=list)
    affected_component: Optional[str] = None
    version: Optional[str] = None


class BugReportS2(BaseStageOutput):
    """Stage 2 — Reasoning: severity, type, and ownership."""
    severity: str = Field(..., description="critical|major|minor|trivial")
    bug_type: str = Field(..., description="crash|regression|performance|ui|security|logic|data")
    reproducibility: str = Field(..., description="always|sometimes|rarely|cannot-reproduce")
    affected_users_estimate: str
    owning_team: str
    blocking: bool
    root_cause_hypothesis: str
    reasoning_chain: list[str] = Field(default_factory=list)

    @field_validator("root_cause_hypothesis", "affected_users_estimate", mode="before")
    @classmethod
    def coerce_prose_to_str(cls, v: Any) -> Any:
        return _coerce_str(v)


class BugReportS3(BaseStageOutput):
    """Stage 3 — Final output: structured triage ticket."""
    bug_id: str
    title: str
    severity: str
    priority: str
    assigned_team: str
    short_description: str
    reproduction_steps: list[str] = Field(default_factory=list)
    suggested_fix: Optional[str] = None
    workaround: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    estimated_fix_hours: Optional[int] = None

    @field_validator("short_description", "suggested_fix", "workaround", mode="before")
    @classmethod
    def coerce_prose_to_str(cls, v: Any) -> Any:
        return _coerce_str(v)


class BugReportS4(BaseStageOutput):
    """Stage 4 — Self-critic."""
    quality_score: float = Field(..., ge=0.0, le=10.0)
    issues_found: list[str] = Field(default_factory=list)
    regenerate: bool
    final_output: BugReportS3
    improvement_notes: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
#  4. MEETING NOTES TO ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

class MeetingNotesS1(BaseStageOutput):
    """Stage 1 — Extraction: parse raw meeting notes."""
    meeting_title: Optional[str] = None
    date: Optional[str] = None
    attendees: list[str] = Field(default_factory=list)
    duration_minutes: Optional[int] = None
    topics_discussed: list[str] = Field(default_factory=list)
    decisions_made: list[str] = Field(default_factory=list)
    raw_action_mentions: list[str] = Field(default_factory=list)
    blockers_mentioned: list[str] = Field(default_factory=list)


class ActionItem(BaseModel):
    owner: str
    task: str
    due_date: Optional[str] = None
    priority: str = Field(..., description="high|medium|low")


class MeetingNotesS2(BaseStageOutput):
    """Stage 2 — Reasoning: structured action items and priorities."""
    action_items: list[ActionItem] = Field(default_factory=list)
    key_decisions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    risks_identified: list[str] = Field(default_factory=list)
    follow_up_meetings_needed: bool
    reasoning_chain: list[str] = Field(default_factory=list)


class MeetingNotesS3(BaseStageOutput):
    """Stage 3 — Final output: shareable meeting summary."""
    subject_line: str
    executive_summary: str
    action_items: list[ActionItem] = Field(default_factory=list)
    key_decisions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    next_meeting_suggestion: Optional[str] = None
    email_body: str

    @field_validator("executive_summary", "email_body", "subject_line", mode="before")
    @classmethod
    def coerce_prose_to_str(cls, v: Any) -> Any:
        return _coerce_str(v)


class MeetingNotesS4(BaseStageOutput):
    """Stage 4 — Self-critic."""
    quality_score: float = Field(..., ge=0.0, le=10.0)
    issues_found: list[str] = Field(default_factory=list)
    regenerate: bool
    final_output: MeetingNotesS3
    improvement_notes: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
#  5. RECIPE ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class RecipeAdapterS1(BaseStageOutput):
    """Stage 1 — Extraction: parse original recipe and requirements."""
    recipe_name: str
    original_servings: Optional[int] = None
    target_servings: Optional[int] = None
    original_ingredients: list[str] = Field(default_factory=list)
    preparation_steps: list[str] = Field(default_factory=list)
    dietary_restrictions: list[str] = Field(default_factory=list)
    cuisine_type: Optional[str] = None
    cooking_time_minutes: Optional[int] = None


class RecipeAdapterS2(BaseStageOutput):
    """Stage 2 — Reasoning: identify conflicts and substitutions."""
    conflicting_ingredients: list[str] = Field(default_factory=list)
    substitutions: dict[str, str] = Field(default_factory=dict)
    scaling_adjustments: dict[str, str] = Field(default_factory=dict)
    technique_modifications: list[str] = Field(default_factory=list)
    nutritional_impact: str
    feasibility: str = Field(..., description="easy|moderate|difficult|not-feasible")
    reasoning_chain: list[str] = Field(default_factory=list)

    @field_validator("nutritional_impact", mode="before")
    @classmethod
    def coerce_prose_to_str(cls, v: Any) -> Any:
        return _coerce_str(v)


class RecipeAdapterS3(BaseStageOutput):
    """Stage 3 — Final output: adapted recipe."""
    adapted_recipe_name: str
    servings: int
    prep_time_minutes: int
    cook_time_minutes: int
    dietary_labels: list[str] = Field(default_factory=list)
    ingredients: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)
    chef_tips: list[str] = Field(default_factory=list)
    substitution_notes: list[str] = Field(default_factory=list)
    nutrition_per_serving: Optional[dict[str, str]] = None


class RecipeAdapterS4(BaseStageOutput):
    """Stage 4 — Self-critic."""
    quality_score: float = Field(..., ge=0.0, le=10.0)
    issues_found: list[str] = Field(default_factory=list)
    regenerate: bool
    final_output: RecipeAdapterS3
    improvement_notes: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
#  6. TRIP PLANNER
# ══════════════════════════════════════════════════════════════════════════════

class TripPlannerS1(BaseStageOutput):
    """Stage 1 — Extraction: parse trip request."""
    destination: str
    origin: Optional[str] = None
    travel_dates: Optional[str] = None
    duration_days: Optional[int] = None
    num_travelers: Optional[int] = None
    budget_usd: Optional[float] = None
    budget_level: str = Field(..., description="budget|mid-range|luxury")
    interests: list[str] = Field(default_factory=list)
    dietary_preferences: list[str] = Field(default_factory=list)
    mobility_requirements: Optional[str] = None
    must_see: list[str] = Field(default_factory=list)


class ItineraryDay(BaseModel):
    day: int
    date: Optional[str] = None
    theme: str
    morning: str
    afternoon: str
    evening: str
    meals: list[str] = Field(default_factory=list)
    estimated_cost_usd: Optional[float] = None


class TripPlannerS2(BaseStageOutput):
    """Stage 2 — Reasoning: plan logistics and prioritise attractions."""
    recommended_neighbourhoods: list[str] = Field(default_factory=list)
    transportation_options: list[str] = Field(default_factory=list)
    top_attractions: list[str] = Field(default_factory=list)
    must_book_in_advance: list[str] = Field(default_factory=list)
    budget_breakdown: dict[str, float] = Field(default_factory=dict)
    best_time_to_visit: str
    local_tips: list[str] = Field(default_factory=list)
    reasoning_chain: list[str] = Field(default_factory=list)

    @field_validator("best_time_to_visit", mode="before")
    @classmethod
    def coerce_prose_to_str(cls, v: Any) -> Any:
        return _coerce_str(v)


class TripPlannerS3(BaseStageOutput):
    """Stage 3 — Final output: full itinerary."""
    trip_title: str
    destination: str
    duration_days: int
    total_estimated_cost_usd: Optional[float] = None
    overview: str
    itinerary: list[ItineraryDay] = Field(default_factory=list)
    packing_essentials: list[str] = Field(default_factory=list)
    practical_info: dict[str, str] = Field(default_factory=dict)
    emergency_contacts: list[str] = Field(default_factory=list)

    @field_validator("overview", "trip_title", mode="before")
    @classmethod
    def coerce_prose_to_str(cls, v: Any) -> Any:
        return _coerce_str(v)


class TripPlannerS4(BaseStageOutput):
    """Stage 4 — Self-critic."""
    quality_score: float = Field(..., ge=0.0, le=10.0)
    issues_found: list[str] = Field(default_factory=list)
    regenerate: bool
    final_output: TripPlannerS3
    improvement_notes: Optional[str] = None


# ─── Registry: map task_id → list of stage schema classes ─────────────────────
TASK_SCHEMAS: dict[str, list[type[BaseStageOutput]]] = {
    "support_triage": [SupportTicketS1, SupportTicketS2, SupportTicketS3, SupportTicketS4],
    "essay_grader":   [EssayGraderS1,   EssayGraderS2,   EssayGraderS3,   EssayGraderS4],
    "bug_triage":     [BugReportS1,     BugReportS2,     BugReportS3,     BugReportS4],
    "meeting_notes":  [MeetingNotesS1,  MeetingNotesS2,  MeetingNotesS3,  MeetingNotesS4],
    "recipe_adapter": [RecipeAdapterS1, RecipeAdapterS2, RecipeAdapterS3, RecipeAdapterS4],
    "trip_planner":   [TripPlannerS1,   TripPlannerS2,   TripPlannerS3,   TripPlannerS4],
}
