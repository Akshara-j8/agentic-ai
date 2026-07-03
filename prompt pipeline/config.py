"""
config.py — Central configuration for the Prompt Pipeline application.

Loads environment variables from .env, defines model lists, task metadata,
retry/timeout settings, and logging configuration.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ─── Load .env ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# ─── OpenRouter API ───────────────────────────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = os.getenv(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
)
OPENROUTER_REFERER: str = os.getenv(
    "OPENROUTER_REFERER", "https://prompt-pipeline-app"
)
OPENROUTER_APP_TITLE: str = os.getenv("OPENROUTER_APP_TITLE", "Prompt Pipeline")

# ─── Available Models ─────────────────────────────────────────────────────────
AVAILABLE_MODELS: dict[str, str] = {
    "GPT-4o Mini (Fast & Cheap)":        "openai/gpt-4o-mini",
    "GPT-4o (Best Quality)":             "openai/gpt-4o",
    "Claude 3.5 Haiku (Fast)":           "anthropic/claude-3-5-haiku",
    "Claude 3.5 Sonnet (Balanced)":      "anthropic/claude-3-5-sonnet",
    "Gemini Flash 1.5 (Google)":         "google/gemini-flash-1.5",
    "Llama 3.1 8B (Free)":              "meta-llama/llama-3.1-8b-instruct:free",
    "Mistral 7B (Free)":                 "mistralai/mistral-7b-instruct:free",
}

DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "openai/gpt-4o-mini")

# ─── Request / Retry Settings ─────────────────────────────────────────────────
REQUEST_TIMEOUT: int    = int(os.getenv("REQUEST_TIMEOUT", "60"))
MAX_RETRIES: int         = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY: float       = float(os.getenv("RETRY_DELAY", "2.0"))   # seconds between retries
MAX_TOKENS: int          = int(os.getenv("MAX_TOKENS", "2048"))
TEMPERATURE: float       = float(os.getenv("TEMPERATURE", "0.3"))

# ─── Pipeline Tasks ───────────────────────────────────────────────────────────
PIPELINE_TASKS: dict[str, dict] = {
    "Support Ticket Triage": {
        "id":          "support_triage",
        "description": "Classify and prioritize customer support tickets",
        "icon":        "🎫",
        "stages":      4,
        "placeholder": "Paste a raw customer support ticket here...",
    },
    "Essay Grader": {
        "id":          "essay_grader",
        "description": "Evaluate student essays and provide structured feedback",
        "icon":        "📝",
        "stages":      4,
        "placeholder": "Paste the student essay here...",
    },
    "Bug Report Triage": {
        "id":          "bug_triage",
        "description": "Analyze and prioritize software bug reports",
        "icon":        "🐛",
        "stages":      4,
        "placeholder": "Paste the bug report here...",
    },
    "Meeting Notes to Actions": {
        "id":          "meeting_notes",
        "description": "Extract action items and summaries from meeting notes",
        "icon":        "📋",
        "stages":      4,
        "placeholder": "Paste raw meeting notes here...",
    },
    "Recipe Adapter": {
        "id":          "recipe_adapter",
        "description": "Adapt recipes for dietary restrictions and preferences",
        "icon":        "🍽️",
        "stages":      4,
        "placeholder": "Paste a recipe and your dietary requirements here...",
    },
    "Trip Planner": {
        "id":          "trip_planner",
        "description": "Create a structured travel itinerary from a request",
        "icon":        "✈️",
        "stages":      4,
        "placeholder": "Describe your trip requirements here...",
    },
}

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_DIR: Path      = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_LEVEL: str     = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: Path     = LOG_DIR / "pipeline.log"

def setup_logging() -> logging.Logger:
    """Configure root logger to write to file and console."""
    logger = logging.getLogger("prompt_pipeline")
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    if not logger.handlers:
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # File handler (always)
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # Console handler
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger


logger: logging.Logger = setup_logging()
