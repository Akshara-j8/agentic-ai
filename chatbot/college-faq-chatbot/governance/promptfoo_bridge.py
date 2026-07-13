"""
governance/promptfoo_bridge.py
==============================
Python bridge so that Promptfoo (Node.js) can call the BVRITH chatbot.

Promptfoo's "python:" provider calls the function answer(prompt, options, context)
and expects it to return a string or a dict with an 'output' key.

Reference: https://promptfoo.dev/docs/providers/python/
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def answer(prompt: str, options: dict = None, context: dict = None) -> dict:
    """Bridge function called by Promptfoo for each test case.

    Args:
        prompt:  The user question string passed by Promptfoo.
        options: Provider options (unused).
        context: Test context (unused).

    Returns:
        Dict with 'output' key containing the chatbot's response.
    """
    try:
        from rag import query as rag_query
        result = rag_query(question=prompt, chat_history=[], top_k=5)
        return {"output": result.answer}
    except Exception as exc:
        return {"output": f"[ERROR] {exc}", "error": str(exc)}
