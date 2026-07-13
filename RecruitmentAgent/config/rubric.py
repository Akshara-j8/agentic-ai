"""
TechVest Recruitment Agent — Weighted Scoring Rubric
Defines all evaluation criteria, weights, and scoring bands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Rubric criterion dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RubricCriterion:
    """A single evaluation criterion in the rubric."""

    key: str
    label: str
    weight: float                       # 0.0–1.0, all weights must sum to 1.0
    description: str
    scoring_guide: dict[str, str]       # band_label -> description
    max_score: int = 10

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "weight": self.weight,
            "description": self.description,
            "scoring_guide": self.scoring_guide,
            "max_score": self.max_score,
        }


# ---------------------------------------------------------------------------
# Rubric definition
# ---------------------------------------------------------------------------

RUBRIC_CRITERIA: list[RubricCriterion] = [
    RubricCriterion(
        key="python_proficiency",
        label="Python Proficiency",
        weight=0.20,
        description=(
            "Depth and breadth of Python expertise: core language features, "
            "OOP, async/await, type hints, testing, packaging, performance optimisation."
        ),
        scoring_guide={
            "9–10": "Expert — advanced Python internals, significant open-source contributions, production systems at scale",
            "7–8":  "Proficient — type-annotated code, async patterns, well-tested production projects",
            "5–6":  "Competent — solid Python, basic OOP, simple scripts / notebooks, limited testing",
            "3–4":  "Beginner — Python mentioned but limited evidence; mostly script-level work",
            "0–2":  "Minimal / No Python evidence in resume",
        },
    ),
    RubricCriterion(
        key="machine_learning",
        label="Machine Learning",
        weight=0.25,
        description=(
            "ML algorithm knowledge, model training/evaluation, deep learning, "
            "frameworks (TensorFlow, PyTorch, scikit-learn), deployment (MLflow, ONNX), "
            "data pipeline design, experimentation rigour."
        ),
        scoring_guide={
            "9–10": "Expert — novel ML research, production model deployment, MLOps expertise",
            "7–8":  "Proficient — multiple deployed ML models, solid evaluation practices, framework proficiency",
            "5–6":  "Competent — completed ML projects/courses, familiar with core algorithms",
            "3–4":  "Beginner — basic ML knowledge; coursework or tutorial projects only",
            "0–2":  "Minimal / No ML evidence",
        },
    ),
    RubricCriterion(
        key="projects",
        label="Projects & Impact",
        weight=0.20,
        description=(
            "Quality, scale, and real-world impact of technical projects: "
            "problem complexity, technologies used, measurable outcomes, "
            "open-source contributions, production usage."
        ),
        scoring_guide={
            "9–10": "Exceptional — large-scale production systems, measurable business/research impact",
            "7–8":  "Strong — multiple solid projects with real users or clear measurable outcomes",
            "5–6":  "Good — decent projects with some complexity; limited measurable impact",
            "3–4":  "Basic — tutorial projects, simple CRUD apps, limited technical challenge",
            "0–2":  "No notable projects mentioned",
        },
    ),
    RubricCriterion(
        key="communication",
        label="Communication",
        weight=0.10,
        description=(
            "Written communication quality inferred from resume: "
            "clarity, structure, use of metrics, conciseness, "
            "absence of vague buzzwords, professional tone."
        ),
        scoring_guide={
            "9–10": "Excellent — quantified achievements, crisp writing, zero fluff",
            "7–8":  "Good — mostly clear with some metrics; minor wordiness",
            "5–6":  "Average — readable but heavy on buzzwords; limited quantification",
            "3–4":  "Below average — vague, unstructured, hard to parse skills/impact",
            "0–2":  "Poor — unclear, disorganised, or nearly incomprehensible",
        },
    ),
    RubricCriterion(
        key="problem_solving",
        label="Problem Solving",
        weight=0.10,
        description=(
            "Evidence of analytical and systems-thinking ability: "
            "complex technical challenges solved, algorithm design, "
            "architecture decisions, debugging at scale."
        ),
        scoring_guide={
            "9–10": "Exceptional — solved novel hard problems, architectural thinking, competitive programming",
            "7–8":  "Strong — evidence of thoughtful design and non-trivial technical decisions",
            "5–6":  "Moderate — standard engineering problems; limited design evidence",
            "3–4":  "Basic — minimal evidence of complex problem solving",
            "0–2":  "No evidence",
        },
    ),
    RubricCriterion(
        key="tools_and_infrastructure",
        label="Tools & Infrastructure",
        weight=0.10,
        description=(
            "DevOps / MLOps / Cloud tooling: Docker, Kubernetes, CI/CD, "
            "AWS/GCP/Azure, Git, databases (SQL + NoSQL), monitoring, "
            "data engineering (Spark, Airflow, Kafka)."
        ),
        scoring_guide={
            "9–10": "Expert — multi-cloud architect, Kubernetes at scale, mature CI/CD, observability",
            "7–8":  "Proficient — Docker, CI/CD, cloud services, databases used in production",
            "5–6":  "Competent — basic containerisation, Git, one cloud provider, SQL",
            "3–4":  "Beginner — Git and basic tools only; no cloud/infra evidence",
            "0–2":  "Minimal / No tooling evidence",
        },
    ),
    RubricCriterion(
        key="education",
        label="Education & Credentials",
        weight=0.05,
        description=(
            "Formal education and certifications — weighted lightly to avoid prestige bias. "
            "Considers degree level and field relevance, professional certifications, "
            "and continuous learning evidence. Institution name is IGNORED."
        ),
        scoring_guide={
            "9–10": "Relevant advanced degree (MS/PhD CS/AI/Stats) + strong certifications",
            "7–8":  "Relevant Bachelor's degree + notable certifications or self-learning",
            "5–6":  "Relevant Bachelor's degree or equivalent industry experience",
            "3–4":  "Non-CS degree with some relevant coursework or bootcamp",
            "0–2":  "No formal education in a relevant field and no certifications",
        },
    ),
]


# ---------------------------------------------------------------------------
# Recommendation thresholds
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecommendationThresholds:
    """Score thresholds for hiring recommendations."""
    interview: float = 55.0    # >= 55 → Interview
    hold: float = 38.0         # >= 38 → Hold
    # < hold → Reject


THRESHOLDS = RecommendationThresholds()


# ---------------------------------------------------------------------------
# Rubric registry
# ---------------------------------------------------------------------------

class Rubric:
    """
    Master rubric object.
    Provides weighted scoring computation and serialisation.
    """

    def __init__(self, criteria: list[RubricCriterion] = RUBRIC_CRITERIA) -> None:
        self.criteria = criteria
        self._validate_weights()

    def _validate_weights(self) -> None:
        total = round(sum(c.weight for c in self.criteria), 6)
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Rubric weights must sum to 1.0, got {total}. "
                f"Weights: {[c.weight for c in self.criteria]}"
            )

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    def compute_weighted_score(self, criterion_scores: dict[str, float]) -> float:
        """
        Compute the overall weighted score (0–100) from per-criterion scores (0–10).

        Args:
            criterion_scores: mapping of criterion key → raw score (0–10)

        Returns:
            Weighted score as a float in [0, 100].
        """
        total = 0.0
        for criterion in self.criteria:
            raw_score = criterion_scores.get(criterion.key, 0.0)
            # Clamp to [0, max_score]
            clamped = max(0.0, min(float(raw_score), float(criterion.max_score)))
            # Normalise to [0, 1] then apply weight × 100
            total += (clamped / criterion.max_score) * criterion.weight * 100
        return round(total, 2)

    def get_recommendation(self, weighted_score: float) -> str:
        """Map a weighted score to a recommendation string."""
        if weighted_score >= THRESHOLDS.interview:
            return "Interview"
        elif weighted_score >= THRESHOLDS.hold:
            return "Hold"
        return "Reject"

    def get_criterion(self, key: str) -> RubricCriterion | None:
        for c in self.criteria:
            if c.key == key:
                return c
        return None

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "criteria": [c.to_dict() for c in self.criteria],
            "thresholds": {
                "interview": THRESHOLDS.interview,
                "hold": THRESHOLDS.hold,
                "reject": 0,
            },
            "total_weight": sum(c.weight for c in self.criteria),
        }

    def to_json_string(self) -> str:
        """Return JSON string suitable for embedding in prompts."""
        import json
        return json.dumps(self.to_dict(), indent=2)

    def criterion_labels(self) -> list[str]:
        return [c.label for c in self.criteria]

    def criterion_keys(self) -> list[str]:
        return [c.key for c in self.criteria]

    def weights_vector(self) -> list[float]:
        """Return weights in order, multiplied by 100 for display."""
        return [c.weight * 100 for c in self.criteria]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

RUBRIC = Rubric()
