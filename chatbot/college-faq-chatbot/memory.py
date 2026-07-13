"""
memory.py
=========
Persistent session memory for the BVRITH FAQ Chatbot.

Stores per-user session data (name + chat history) in a JSON file so it
survives browser refresh.

Storage layout:
    memory/
        sessions.json   ← dict keyed by session_id
            {
                "<session_id>": {
                    "user_name":   "Ravi",
                    "created_at":  "2026-07-13T14:00:00",
                    "updated_at":  "2026-07-13T14:05:00",
                    "messages": [
                        {"role": "user",      "content": "..."},
                        {"role": "assistant", "content": "...", "meta": {...}}
                    ]
                }
            }

Session ID is generated once per browser session using a UUID and stored
in the browser via a Streamlit query-param cookie-like mechanism.

Usage:
    from memory import SessionMemory
    mem = SessionMemory(session_id="abc123")
    mem.set_name("Ravi")
    mem.save_message({"role": "user", "content": "Hello"})
    data = mem.load()          # {"user_name": ..., "messages": [...]}
    mem.clear()                # erase this session
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Storage location ────────────────────────────────────────────────────────
_BASE = Path(__file__).resolve().parent
MEMORY_DIR = _BASE / "memory"
SESSIONS_FILE = MEMORY_DIR / "sessions.json"

# Max messages to persist per session (keeps the file manageable)
MAX_MESSAGES = 100


# ─────────────────────────────────────────────────────────────────────────────
#  Low-level file helpers
# ─────────────────────────────────────────────────────────────────────────────

def _read_all() -> Dict[str, Any]:
    """Read the full sessions file. Returns empty dict on any error."""
    try:
        if SESSIONS_FILE.exists():
            return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write_all(data: Dict[str, Any]) -> None:
    """Write the full sessions dict back to disk safely."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    # Write directly — Windows doesn't allow atomic rename over existing files
    # without elevated privileges, so we just overwrite directly.
    SESSIONS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def generate_session_id() -> str:
    """Generate a new random session ID (UUID4, no dashes)."""
    return uuid.uuid4().hex


# ─────────────────────────────────────────────────────────────────────────────
#  SessionMemory class
# ─────────────────────────────────────────────────────────────────────────────

class SessionMemory:
    """Read/write persistent memory for a single browser session.

    Args:
        session_id: Unique identifier for this browser session.
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    # ── Internal helpers ───────────────────────────────────────────────────

    def _get_session(self) -> Dict[str, Any]:
        """Return this session's data dict, or a fresh empty one."""
        all_sessions = _read_all()
        return all_sessions.get(self.session_id, {
            "user_name":  None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "messages":   [],
        })

    def _save_session(self, session: Dict[str, Any]) -> None:
        """Write this session's data back to disk."""
        session["updated_at"] = datetime.utcnow().isoformat()
        all_sessions = _read_all()
        all_sessions[self.session_id] = session
        _write_all(all_sessions)

    # ── Public API ─────────────────────────────────────────────────────────

    def load(self) -> Dict[str, Any]:
        """Load this session's data.

        Returns:
            Dict with keys: user_name, messages, created_at, updated_at.
        """
        return self._get_session()

    def set_name(self, name: str) -> None:
        """Persist the user's name for this session.

        Args:
            name: The name the user provided.
        """
        session = self._get_session()
        session["user_name"] = name.strip()
        self._save_session(session)

    def get_name(self) -> Optional[str]:
        """Return the stored user name, or None if not set yet.

        Returns:
            Name string or None.
        """
        return self._get_session().get("user_name")

    def save_message(self, message: Dict[str, Any]) -> None:
        """Append one message to the persistent history.

        Args:
            message: Dict with at minimum {"role": ..., "content": ...}.
                     The "meta" key (citations, latency) is kept if present.
        """
        session = self._get_session()
        # Only persist role + content + minimal meta (skip large debug data)
        slim = {"role": message["role"], "content": message["content"]}
        if "meta" in message:
            meta = message["meta"]
            slim["meta"] = {
                "elapsed":   meta.get("elapsed"),
                "chunks":    meta.get("chunks"),
                "citations": meta.get("citations", []),
            }
        session["messages"].append(slim)
        # Cap history length
        if len(session["messages"]) > MAX_MESSAGES:
            session["messages"] = session["messages"][-MAX_MESSAGES:]
        self._save_session(session)

    def save_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Replace the entire message list (used on initial load-back).

        Args:
            messages: Full message list from st.session_state.
        """
        session = self._get_session()
        slim_list = []
        for message in messages[-MAX_MESSAGES:]:
            slim = {"role": message["role"], "content": message["content"]}
            if "meta" in message:
                meta = message["meta"]
                slim["meta"] = {
                    "elapsed":   meta.get("elapsed"),
                    "chunks":    meta.get("chunks"),
                    "citations": meta.get("citations", []),
                }
            slim_list.append(slim)
        session["messages"] = slim_list
        self._save_session(session)

    def clear(self) -> None:
        """Erase all data for this session."""
        all_sessions = _read_all()
        all_sessions.pop(self.session_id, None)
        _write_all(all_sessions)

    def exists(self) -> bool:
        """Return True if this session ID already has saved data."""
        return self.session_id in _read_all()
