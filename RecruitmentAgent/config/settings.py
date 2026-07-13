"""
TechVest Recruitment Agent — Application Settings
Centralised configuration using Pydantic v2 BaseSettings.
All values can be overridden via environment variables or .env file.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Project root helper
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class AppSettings(BaseSettings):
    """
    Global application settings for TechVest Recruitment Agent.
    Values are loaded from environment variables / .env file.
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application metadata
    # ------------------------------------------------------------------
    app_title: str = Field(default="TechVest Recruitment Agent", description="Application display title")
    app_version: str = Field(default="1.0.0", description="Semantic version")
    app_theme: Literal["dark", "light"] = Field(default="dark", description="UI theme")

    # ------------------------------------------------------------------
    # OpenRouter / LLM
    # ------------------------------------------------------------------
    openrouter_api_key: str = Field(default="", description="OpenRouter API key")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter base URL",
    )
    default_model: str = Field(
        default="openai/gpt-4o-mini",
        description="Primary LLM model identifier on OpenRouter",
    )
    fallback_model: str = Field(
        default="openai/gpt-3.5-turbo",
        description="Fallback LLM model identifier",
    )
    default_temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="LLM sampling temperature")
    default_max_tokens: int = Field(default=4096, ge=256, le=32768, description="Max tokens per LLM call")

    # ------------------------------------------------------------------
    # LangGraph
    # ------------------------------------------------------------------
    recursion_limit: int = Field(default=100, ge=5, le=500, description="LangGraph recursion limit")
    max_iterations: int = Field(default=50, ge=1, le=200, description="Max agent iterations")
    step_limit: int = Field(default=200, ge=10, le=1000, description="Hard step limit for the graph")

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    database_path: str = Field(default="./data/techvest.db", description="SQLite database file path")
    audit_log_path: str = Field(default="./data/audit.log", description="Structured audit log path")

    # ------------------------------------------------------------------
    # Security & Guardrails
    # ------------------------------------------------------------------
    secret_key: str = Field(default="techvest-secret-key-change-in-production")
    enable_guardrails: bool = Field(default=True, description="Master switch for all guardrails")
    human_approval_required: bool = Field(default=True, description="Require human approval before scheduling")

    # ------------------------------------------------------------------
    # Guardrail thresholds
    # ------------------------------------------------------------------
    min_score_threshold: float = Field(default=50.0, ge=0.0, le=100.0, description="Minimum score to pass to interview stage")
    fairness_strict_mode: bool = Field(default=True, description="Strict bias/fairness validation")
    injection_sensitivity: Literal["low", "medium", "high"] = Field(
        default="high", description="Prompt injection detection sensitivity"
    )

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    verbose_logging: bool = Field(default=True, description="Enable verbose LangGraph event logging")
    auto_save: bool = Field(default=True, description="Auto-save results to database")

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("openrouter_api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Strip whitespace from API key."""
        return str(v).strip() if v else ""

    @field_validator("database_path", "audit_log_path", mode="before")
    @classmethod
    def ensure_parent_dir(cls, v: str) -> str:
        """Ensure parent directory exists."""
        path = Path(v)
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    # ------------------------------------------------------------------
    # Computed helpers
    # ------------------------------------------------------------------
    @property
    def is_configured(self) -> bool:
        """Return True when a valid OpenRouter API key is present."""
        return bool(self.openrouter_api_key) and self.openrouter_api_key.startswith("sk-")

    @property
    def db_path(self) -> Path:
        return Path(self.database_path)

    @property
    def log_path(self) -> Path:
        return Path(self.audit_log_path)

    @property
    def openrouter_headers(self) -> dict[str, str]:
        """Headers required by OpenRouter API."""
        return {
            "HTTP-Referer": "https://techvest.ai",
            "X-Title": self.app_title,
        }


# ---------------------------------------------------------------------------
# UI / Theming constants (not env-driven — compile-time constants)
# ---------------------------------------------------------------------------
class UIConstants:
    """Visual design constants for the enterprise UI."""

    # Colour palette
    PRIMARY = "#6366F1"          # Indigo
    PRIMARY_DARK = "#4F46E5"
    SECONDARY = "#8B5CF6"        # Violet
    ACCENT = "#06B6D4"           # Cyan
    SUCCESS = "#10B981"          # Emerald
    WARNING = "#F59E0B"          # Amber
    DANGER = "#EF4444"           # Red
    INFO = "#3B82F6"             # Blue

    # Backgrounds
    BG_PRIMARY = "#0F172A"       # Slate-900
    BG_SECONDARY = "#1E293B"     # Slate-800
    BG_CARD = "#1E293B"
    BG_SIDEBAR = "#0F172A"

    # Text
    TEXT_PRIMARY = "#F1F5F9"     # Slate-100
    TEXT_SECONDARY = "#94A3B8"   # Slate-400
    TEXT_MUTED = "#64748B"       # Slate-500

    # Borders
    BORDER = "#334155"           # Slate-700
    BORDER_LIGHT = "#475569"

    # Card / glass styles
    CARD_RADIUS = "12px"
    CARD_SHADOW = "0 4px 24px rgba(0,0,0,0.4)"
    GLASS_BG = "rgba(30, 41, 59, 0.7)"
    GLASS_BORDER = "1px solid rgba(255,255,255,0.08)"

    # Recommendation badge colours
    BADGE_INTERVIEW = SUCCESS
    BADGE_HOLD = WARNING
    BADGE_REJECT = DANGER

    # Score gradient
    SCORE_HIGH = SUCCESS         # >= 75
    SCORE_MED = WARNING          # 50 – 74
    SCORE_LOW = DANGER           # < 50

    # Chart colours
    CHART_PALETTE = [
        "#6366F1", "#8B5CF6", "#06B6D4",
        "#10B981", "#F59E0B", "#EF4444", "#3B82F6",
    ]

    @staticmethod
    def score_color(score: float) -> str:
        if score >= 75:
            return UIConstants.SCORE_HIGH
        elif score >= 50:
            return UIConstants.SCORE_MED
        return UIConstants.SCORE_LOW


# ---------------------------------------------------------------------------
# Node name registry (single source of truth)
# ---------------------------------------------------------------------------
class NodeNames:
    PLAN = "plan_node"
    PARSE = "parse_resume_node"
    SCORE = "score_candidate_node"
    AVAILABILITY = "availability_node"
    DECISION = "decision_node"
    GUARDRAIL = "guardrail_node"
    HUMAN_APPROVAL = "human_approval_node"
    SCHEDULER = "scheduler_node"
    AUDIT = "audit_node"
    FINISH = "finish_node"


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return cached application settings (loaded once at startup)."""
    return AppSettings()


# Convenience re-exports
settings = get_settings()
ui = UIConstants()
nodes = NodeNames()
