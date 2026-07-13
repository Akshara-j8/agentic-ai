"""
Utility module for the College FAQ RAG Chatbot.

Provides:
- Logging setup
- Timer context manager / decorator
- Token estimation helpers
- Text formatting helpers
- Metadata formatting for UI display
"""
import logging
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────────────────────────────────────

def setup_logger(
    name: str = "college_faq_chatbot",
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Configure and return a named logger with optional file output.

    Args:
        name:     Logger name.
        log_file: Optional path; if given, logs are also written to this file.
        level:    Logging level (e.g. logging.DEBUG).

    Returns:
        Configured Logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    # Avoid adding duplicate handlers on re-import
    if logger.handlers:
        logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


# ─────────────────────────────────────────────────────────────────────────────
#  Timer utilities
# ─────────────────────────────────────────────────────────────────────────────

class Timer:
    """Context manager that records wall-clock elapsed time.

    Example::

        with Timer() as t:
            do_work()
        print(t.get_formatted())   # "1.23s"
    """

    def __init__(self) -> None:
        self._start: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.elapsed = time.perf_counter() - self._start

    def get_elapsed(self) -> float:
        """Return elapsed time in seconds."""
        return self.elapsed

    def get_formatted(self) -> str:
        """Return elapsed time as a human-readable string, e.g. '1.23s'."""
        return f"{self.elapsed:.2f}s"


def time_it(func: Callable[..., Any]) -> Callable[..., Tuple[Any, float]]:
    """Decorator that times *func* and returns ``(result, elapsed_seconds)``.

    Example::

        @time_it
        def slow():
            time.sleep(1)

        result, elapsed = slow()
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Tuple[Any, float]:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        return result, elapsed
    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
#  Token helpers
# ─────────────────────────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """Rough token count estimate — 1 token ≈ 4 characters (English text).

    Args:
        text: Input string.

    Returns:
        Estimated token count.
    """
    return max(1, len(text) // 4)


def format_token_usage(
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> str:
    """Format token usage statistics into a readable string.

    Args:
        prompt_tokens:     Tokens in the prompt.
        completion_tokens: Tokens in the completion.
        total_tokens:      Combined total.

    Returns:
        Formatted string, e.g. "Prompt: 120 | Completion: 45 | Total: 165".
    """
    return (
        f"Prompt: {prompt_tokens} | "
        f"Completion: {completion_tokens} | "
        f"Total: {total_tokens}"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Text helpers
# ─────────────────────────────────────────────────────────────────────────────

def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate *text* to *max_length* characters, appending '…' if cut.

    Args:
        text:       The string to truncate.
        max_length: Maximum allowed character count.

    Returns:
        Original or truncated string.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def format_source_citation(metadata: dict) -> str:
    """Build a citation string from chunk metadata.

    Args:
        metadata: Dict containing optional keys 'section_heading' and 'page'.

    Returns:
        Citation string, e.g. "[Admissions | Page 3]".
    """
    section = metadata.get("section_heading", "General")
    page = metadata.get("page", "N/A")
    return f"[{section} | Page {page}]"


def format_chunks_for_context(docs: list) -> str:
    """Concatenate retrieved document chunks into a single context string.

    Each chunk is prefixed with its citation so the LLM can reference it.

    Args:
        docs: List of LangChain Document objects.

    Returns:
        Formatted multi-chunk context string.
    """
    parts: list[str] = []
    for i, doc in enumerate(docs, start=1):
        citation = format_source_citation(doc.metadata)
        parts.append(f"[Chunk {i}] {citation}\n{doc.page_content.strip()}")
    return "\n\n---\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
#  Metadata display helpers (used by Streamlit sidebar)
# ─────────────────────────────────────────────────────────────────────────────

def format_debug_chunks(docs: list) -> str:
    """Format retrieved chunks for display in the debug panel.

    Args:
        docs: List of LangChain Document objects.

    Returns:
        Markdown-friendly string showing chunk content and metadata.
    """
    lines: list[str] = []
    for i, doc in enumerate(docs, start=1):
        citation = format_source_citation(doc.metadata)
        preview = truncate_text(doc.page_content.strip(), 300)
        lines.append(
            f"**Chunk {i}** {citation}\n```\n{preview}\n```"
        )
    return "\n\n".join(lines)
