"""Configuration: load API keys from .env file."""

import os
from dotenv import load_dotenv

load_dotenv()


def get(key: str) -> str:
    """Return environment variable value or raise if missing."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return value


OPENROUTER_API_KEY: str = get("OPENROUTER_API_KEY")              # text generation
OPENROUTER_IMAGE_API_KEY: str = get("OPENROUTER_IMAGE_API_KEY")  # image generation
OPENROUTER_VIDEO_API_KEY: str = get("OPENROUTER_VIDEO_API_KEY")  # video generation
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")            # optional
RUNWAY_API_KEY: str = os.getenv("RUNWAY_API_KEY", "")            # optional

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "openai/gpt-4o"
IMAGE_MODEL = "black-forest-labs/flux.2-pro"  # FLUX via OpenRouter image API
