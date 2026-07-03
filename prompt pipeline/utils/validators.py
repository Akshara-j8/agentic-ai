"""
utils/validators.py — Input validation helpers.
"""

from __future__ import annotations
import re


def is_valid_api_key(key: str) -> bool:
    """
    Basic sanity check for an OpenRouter API key.
    OpenRouter keys typically start with 'sk-or-' and are at least 20 chars.
    """
    if not key or not isinstance(key, str):
        return False
    key = key.strip()
    return len(key) >= 20


def is_meaningful_input(text: str, min_words: int = 5) -> bool:
    """
    Check that the user's raw input has enough words to be useful.
    Rejects empty strings, whitespace-only, or very short inputs.
    """
    if not text or not isinstance(text, str):
        return False
    words = re.findall(r"\S+", text.strip())
    return len(words) >= min_words
