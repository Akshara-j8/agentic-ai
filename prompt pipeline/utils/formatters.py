"""
utils/formatters.py — String and data formatting helpers.
"""

from __future__ import annotations
import json


def format_json(data: dict | list | str, indent: int = 2) -> str:
    """Pretty-print a dict/list to a JSON string.  Returns the string unchanged
    if it is already a string."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return data
    try:
        return json.dumps(data, indent=indent, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(data)


def format_duration(ms: float) -> str:
    """Format milliseconds into a human-friendly string."""
    if ms < 1000:
        return f"{ms:.0f} ms"
    return f"{ms / 1000:.2f} s"


def truncate(text: str, max_len: int = 120) -> str:
    """Truncate a string for display purposes."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
