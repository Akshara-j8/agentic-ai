"""
Configuration module for the College FAQ RAG Chatbot.

Centralises every constant and environment variable used across the project.
OpenAI API is used directly for embeddings (text-embedding-3-small) since
OpenRouter does NOT support the embeddings endpoint.
OpenRouter is used for the chat/completion LLM (gpt-4o-mini).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load environment variables from .env ─────────────────────────────────────
load_dotenv()

# ── Directory layout ──────────────────────────────────────────────────────────
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"
CHROMA_DB_DIR: Path = BASE_DIR / "chroma_db"
TEST_CASES_DIR: Path = BASE_DIR / "test_cases"
EVALUATION_DIR: Path = BASE_DIR / "evaluation"

# ── Knowledge base ────────────────────────────────────────────────────────────
KNOWLEDGE_BASE_FILE: str = "knowledge_base.docx"
KNOWLEDGE_BASE_PATH: Path = DATA_DIR / KNOWLEDGE_BASE_FILE

# ── Chunking parameters ───────────────────────────────────────────────────────
CHUNK_SIZE: int = 500
CHUNK_OVERLAP: int = 50

# ── Embedding model  (local HuggingFace — no API key required) ───────────────
EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

# OpenAI key — not required when using local embeddings
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# ── LLM via OpenRouter ────────────────────────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
LLM_TEMPERATURE: float = 0.0
LLM_MAX_TOKENS: int = 1024

# ── Retrieval ─────────────────────────────────────────────────────────────────
TOP_K: int = 5

# ── Streamlit UI ──────────────────────────────────────────────────────────────
APP_TITLE: str = "BVRITH College FAQ Chatbot"
DEBUG_MODE_DEFAULT: bool = False

# ── Evaluation (RAGAS) ────────────────────────────────────────────────────────
EVALUATION_REPORT_FILE: str = "report.json"
DEFAULT_TEST_COUNT: int = 10
# RAGAS uses OpenAI directly (not OpenRouter) for its internal LLM / embeddings
RAGAS_LLM_MODEL: str = "gpt-4o-mini"
RAGAS_EMBEDDING_MODEL: str = "text-embedding-3-small"

# ── ChromaDB collection name ──────────────────────────────────────────────────
CHROMA_COLLECTION_NAME: str = "college_faq"


def validate_config() -> None:
    """Raise ValueError if any mandatory configuration value is missing."""
    errors: list[str] = []
    if not OPENROUTER_API_KEY:
        errors.append(
            "OPENROUTER_API_KEY is not set in .env  "
            "(required for the LLM via OpenRouter)"
        )
    if not KNOWLEDGE_BASE_PATH.exists():
        errors.append(f"Knowledge base not found at: {KNOWLEDGE_BASE_PATH}")
    if errors:
        raise ValueError("Configuration errors:\n  • " + "\n  • ".join(errors))
