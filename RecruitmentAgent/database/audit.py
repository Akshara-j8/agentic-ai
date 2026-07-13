"""
TechVest Recruitment Agent — Structured Audit Logger
Provides a high-level audit API that writes to both SQLite and a structured log file.
Every agent action, guardrail event, and decision is immutably recorded.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Audit categories and levels
# ---------------------------------------------------------------------------

class AuditCategory(str, Enum):
    SYSTEM = "system"
    AGENT = "agent"
    TOOL = "tool"
    GUARDRAIL = "guardrail"
    SECURITY = "security"
    DECISION = "decision"
    SCHEDULING = "scheduling"
    USER = "user"
    DATABASE = "database"
    LLM = "llm"


class AuditLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    SECURITY = "SECURITY"


# ---------------------------------------------------------------------------
# Audit event model
# ---------------------------------------------------------------------------

class AuditEvent:
    """Structured audit event."""

    def __init__(
        self,
        action: str,
        *,
        run_id: Optional[str] = None,
        level: AuditLevel = AuditLevel.INFO,
        category: AuditCategory = AuditCategory.SYSTEM,
        actor: str = "agent",
        target: Optional[str] = None,
        details: Optional[Any] = None,
        session_id: Optional[str] = None,
    ) -> None:
        self.audit_id = self._generate_id()
        self.timestamp = datetime.utcnow()
        self.action = action
        self.run_id = run_id
        self.level = level
        self.category = category
        self.actor = actor
        self.target = target
        self.details = details
        self.session_id = session_id

    @staticmethod
    def _generate_id() -> str:
        import uuid
        return str(uuid.uuid4())

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp.isoformat(),
            "run_id": self.run_id,
            "level": self.level.value,
            "category": self.category.value,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "details": self.details,
            "session_id": self.session_id,
        }

    def to_log_line(self) -> str:
        detail_str = ""
        if self.details:
            if isinstance(self.details, (dict, list)):
                detail_str = f" | {json.dumps(self.details, default=str)}"
            else:
                detail_str = f" | {self.details}"
        return (
            f"[{self.timestamp.isoformat()}] "
            f"[{self.level.value}] "
            f"[{self.category.value.upper()}] "
            f"actor={self.actor} "
            f"action={self.action!r}"
            f"{' target=' + repr(self.target) if self.target else ''}"
            f"{detail_str}"
        )


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------

class AuditLogger:
    """
    Dual-sink audit logger:
    1. Structured JSON-lines file for immutable audit trail
    2. SQLite via DatabaseManager for queryable storage
    3. Standard Python logger for console/file log output
    """

    def __init__(
        self,
        log_path: Optional[str] = None,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self._log_path = Path(log_path or settings.audit_log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._run_id = run_id
        self._session_id = session_id
        self._event_buffer: list[AuditEvent] = []
        self._db: Optional[Any] = None  # Lazy import to avoid circular deps

    def _get_db(self):
        if self._db is None:
            from database.sqlite import get_db
            self._db = get_db()
        return self._db

    # ------------------------------------------------------------------
    # Public logging API
    # ------------------------------------------------------------------

    def log(
        self,
        action: str,
        *,
        level: AuditLevel = AuditLevel.INFO,
        category: AuditCategory = AuditCategory.SYSTEM,
        actor: str = "agent",
        target: Optional[str] = None,
        details: Optional[Any] = None,
        run_id: Optional[str] = None,
    ) -> AuditEvent:
        """Record a generic audit event."""
        event = AuditEvent(
            action=action,
            run_id=run_id or self._run_id,
            level=level,
            category=category,
            actor=actor,
            target=target,
            details=details,
            session_id=self._session_id,
        )
        self._persist(event)
        return event

    def info(self, action: str, **kwargs) -> AuditEvent:
        return self.log(action, level=AuditLevel.INFO, **kwargs)

    def warning(self, action: str, **kwargs) -> AuditEvent:
        return self.log(action, level=AuditLevel.WARNING, **kwargs)

    def error(self, action: str, **kwargs) -> AuditEvent:
        return self.log(action, level=AuditLevel.ERROR, **kwargs)

    def security(self, action: str, **kwargs) -> AuditEvent:
        return self.log(action, level=AuditLevel.SECURITY,
                        category=AuditCategory.SECURITY, **kwargs)

    # ------------------------------------------------------------------
    # Domain-specific helpers
    # ------------------------------------------------------------------

    def log_tool_call(
        self,
        tool_name: str,
        input_data: Optional[dict] = None,
        output_data: Optional[Any] = None,
        success: bool = True,
        duration_ms: Optional[float] = None,
        run_id: Optional[str] = None,
    ) -> None:
        """Log a LangChain tool invocation."""
        details = {
            "tool": tool_name,
            "success": success,
            "duration_ms": duration_ms,
        }
        if input_data:
            details["input"] = {k: str(v)[:200] for k, v in input_data.items()}
        if output_data:
            out = output_data if isinstance(output_data, str) else json.dumps(output_data, default=str)
            details["output_preview"] = out[:300]

        self.log(
            f"tool_call:{tool_name}",
            level=AuditLevel.INFO if success else AuditLevel.ERROR,
            category=AuditCategory.TOOL,
            details=details,
            run_id=run_id or self._run_id,
        )

    def log_llm_call(
        self,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        success: bool = True,
        node: str = "",
        run_id: Optional[str] = None,
    ) -> None:
        """Log an LLM API call."""
        self.log(
            "llm_invoke",
            level=AuditLevel.INFO if success else AuditLevel.ERROR,
            category=AuditCategory.LLM,
            target=model,
            details={
                "node": node,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "success": success,
            },
            run_id=run_id or self._run_id,
        )

    def log_guardrail(
        self,
        guardrail_type: str,
        status: str,
        candidate_name: Optional[str] = None,
        details: Optional[dict] = None,
        severity: str = "none",
        action_taken: str = "",
        run_id: Optional[str] = None,
    ) -> None:
        """Log a guardrail check result."""
        run = run_id or self._run_id

        # Save to guardrail events table
        try:
            self._get_db().save_guardrail_event(run or "unknown", {
                "guardrail_type": guardrail_type,
                "status": status,
                "candidate_name": candidate_name,
                "details": details or {},
                "severity": severity,
                "action_taken": action_taken,
            })
        except Exception as exc:
            logger.warning(f"Failed to persist guardrail event: {exc}")

        level = AuditLevel.WARNING if status == "FAIL" else AuditLevel.INFO
        if severity in ("high", "critical"):
            level = AuditLevel.SECURITY

        self.log(
            f"guardrail:{guardrail_type}:{status}",
            level=level,
            category=AuditCategory.GUARDRAIL,
            target=candidate_name,
            details={"severity": severity, "action": action_taken, **(details or {})},
            run_id=run,
        )

    def log_decision(
        self,
        candidate_name: str,
        recommendation: str,
        score: float,
        reasoning: str = "",
        run_id: Optional[str] = None,
    ) -> None:
        """Log a hiring decision."""
        self.log(
            f"decision:{recommendation}",
            level=AuditLevel.INFO,
            category=AuditCategory.DECISION,
            actor="agent",
            target=candidate_name,
            details={
                "recommendation": recommendation,
                "weighted_score": score,
                "reasoning": reasoning[:200],
            },
            run_id=run_id or self._run_id,
        )

    def log_human_approval(
        self,
        approver: str,
        approved: bool,
        candidates: list[str],
        notes: str = "",
        run_id: Optional[str] = None,
    ) -> None:
        """Log a human approval gate event."""
        self.log(
            f"human_approval:{'approved' if approved else 'rejected'}",
            level=AuditLevel.INFO,
            category=AuditCategory.USER,
            actor=approver,
            target=", ".join(candidates),
            details={"approved": approved, "candidates": candidates, "notes": notes},
            run_id=run_id or self._run_id,
        )

    def log_injection_attack(
        self,
        candidate_name: str,
        severity: str,
        flagged_text: list[str],
        run_id: Optional[str] = None,
    ) -> None:
        """Log a prompt injection detection event."""
        self.security(
            "prompt_injection_detected",
            category=AuditCategory.SECURITY,
            actor="guardrail",
            target=candidate_name,
            details={
                "severity": severity,
                "flagged_snippets": flagged_text[:5],
                "candidate": candidate_name,
            },
            run_id=run_id or self._run_id,
        )
        # Also save to guardrail events
        self.log_guardrail(
            guardrail_type="prompt_injection",
            status="FAIL",
            candidate_name=candidate_name,
            details={"flagged_text": flagged_text, "severity": severity},
            severity=severity,
            action_taken="quarantine_and_continue",
            run_id=run_id or self._run_id,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist(self, event: AuditEvent) -> None:
        """Write event to both file and SQLite."""
        # 1. Append to JSONL file
        try:
            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), default=str) + "\n")
        except OSError as exc:
            logger.warning(f"Audit file write failed: {exc}")

        # 2. Write to SQLite
        try:
            db = self._get_db()
            db.log_audit(
                action=event.action,
                run_id=event.run_id,
                level=event.level.value,
                category=event.category.value,
                actor=event.actor,
                target=event.target,
                details=event.details,
                session_id=event.session_id,
            )
        except Exception as exc:
            logger.warning(f"Audit DB write failed: {exc}")

        # 3. Python logger
        py_level = getattr(logging, event.level.value if event.level.value != "SECURITY" else "WARNING", logging.INFO)
        logger.log(py_level, event.to_log_line())

        # 4. Buffer for in-memory access
        self._event_buffer.append(event)
        # Keep buffer bounded
        if len(self._event_buffer) > 500:
            self._event_buffer = self._event_buffer[-500:]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_recent_events(self, n: int = 50) -> list[dict[str, Any]]:
        """Return most recent in-memory events."""
        return [e.to_dict() for e in self._event_buffer[-n:]]

    def set_run_id(self, run_id: str) -> None:
        """Update the current run ID."""
        self._run_id = run_id

    def set_session_id(self, session_id: str) -> None:
        self._session_id = session_id


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_audit_logger_instance: Optional[AuditLogger] = None


def get_audit_logger(
    run_id: Optional[str] = None,
    session_id: Optional[str] = None,
    *,
    force_new: bool = False,
) -> AuditLogger:
    """Return the singleton AuditLogger, creating if needed."""
    global _audit_logger_instance
    if force_new or _audit_logger_instance is None:
        _audit_logger_instance = AuditLogger(run_id=run_id, session_id=session_id)
    elif run_id:
        _audit_logger_instance.set_run_id(run_id)
    return _audit_logger_instance
