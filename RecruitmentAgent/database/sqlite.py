"""
TechVest Recruitment Agent — SQLite Database Layer
Manages persistent storage for candidates, runs, trajectory, audit, and rankings.
Uses stdlib sqlite3 — no ORM dependency.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

_DDL_STATEMENTS = [
    # ------------------------------------------------------------------
    # Agent runs — top-level run record
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS agent_runs (
        run_id          TEXT PRIMARY KEY,
        started_at      TEXT NOT NULL,
        completed_at    TEXT,
        status          TEXT NOT NULL DEFAULT 'running',
        job_description TEXT,
        total_candidates INTEGER DEFAULT 0,
        interview_count  INTEGER DEFAULT 0,
        hold_count       INTEGER DEFAULT 0,
        reject_count     INTEGER DEFAULT 0,
        avg_score        REAL DEFAULT 0.0,
        top_candidate    TEXT,
        total_tool_calls INTEGER DEFAULT 0,
        total_llm_calls  INTEGER DEFAULT 0,
        injection_detected INTEGER DEFAULT 0,
        fairness_status  TEXT DEFAULT 'PASS',
        duration_seconds REAL DEFAULT 0.0,
        metadata         TEXT
    )
    """,

    # ------------------------------------------------------------------
    # Parsed profiles
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS candidate_profiles (
        profile_id      TEXT PRIMARY KEY,
        run_id          TEXT NOT NULL,
        name            TEXT NOT NULL,
        email           TEXT,
        phone           TEXT,
        location        TEXT,
        years_experience INTEGER DEFAULT 0,
        summary         TEXT,
        skills          TEXT,          -- JSON array
        education       TEXT,          -- JSON array
        experience      TEXT,          -- JSON array
        projects        TEXT,          -- JSON array
        certifications  TEXT,          -- JSON array
        resume_filename TEXT,
        injection_detected INTEGER DEFAULT 0,
        injection_severity TEXT DEFAULT 'none',
        parse_timestamp TEXT,
        raw_text_snippet TEXT,
        FOREIGN KEY (run_id) REFERENCES agent_runs(run_id)
    )
    """,

    # ------------------------------------------------------------------
    # Scorecards
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS scorecards (
        scorecard_id    TEXT PRIMARY KEY,
        run_id          TEXT NOT NULL,
        candidate_name  TEXT NOT NULL,
        criterion_scores TEXT,         -- JSON object
        overall_weighted_score REAL DEFAULT 0.0,
        recommendation  TEXT,
        confidence      REAL DEFAULT 0.5,
        strengths       TEXT,          -- JSON array
        gaps            TEXT,          -- JSON array
        reasoning       TEXT,
        injection_penalty_applied INTEGER DEFAULT 0,
        fairness_reviewed INTEGER DEFAULT 0,
        score_timestamp TEXT,
        FOREIGN KEY (run_id) REFERENCES agent_runs(run_id)
    )
    """,

    # ------------------------------------------------------------------
    # Interview decisions
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS interview_decisions (
        decision_id     TEXT PRIMARY KEY,
        run_id          TEXT NOT NULL,
        candidate_name  TEXT NOT NULL,
        final_recommendation TEXT,
        rank            INTEGER DEFAULT 0,
        weighted_score  REAL DEFAULT 0.0,
        confidence      REAL DEFAULT 0.5,
        reasoning       TEXT,
        priority_flag   INTEGER DEFAULT 0,
        approved_by     TEXT,
        approved_at     TEXT,
        FOREIGN KEY (run_id) REFERENCES agent_runs(run_id)
    )
    """,

    # ------------------------------------------------------------------
    # Interview slots
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS interview_slots (
        slot_id         TEXT PRIMARY KEY,
        run_id          TEXT NOT NULL,
        candidate_name  TEXT NOT NULL,
        slot_date       TEXT,
        slot_time       TEXT,
        timezone        TEXT DEFAULT 'Asia/Kolkata',
        interviewer     TEXT,
        duration_minutes INTEGER DEFAULT 60,
        format          TEXT DEFAULT 'Video',
        interview_type  TEXT DEFAULT 'Technical',
        confirmed       INTEGER DEFAULT 0,
        created_at      TEXT,
        FOREIGN KEY (run_id) REFERENCES agent_runs(run_id)
    )
    """,

    # ------------------------------------------------------------------
    # Trajectory events
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS trajectory_events (
        event_id        TEXT PRIMARY KEY,
        run_id          TEXT NOT NULL,
        event_type      TEXT NOT NULL,
        node            TEXT,
        title           TEXT,
        content         TEXT,
        metadata        TEXT,          -- JSON object
        timestamp       TEXT NOT NULL,
        duration_ms     REAL,
        success         INTEGER DEFAULT 1,
        FOREIGN KEY (run_id) REFERENCES agent_runs(run_id)
    )
    """,

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        audit_id        TEXT PRIMARY KEY,
        run_id          TEXT,
        timestamp       TEXT NOT NULL,
        level           TEXT NOT NULL DEFAULT 'INFO',
        category        TEXT,
        actor           TEXT DEFAULT 'system',
        action          TEXT NOT NULL,
        target          TEXT,
        details         TEXT,          -- JSON or plain text
        ip_address      TEXT,
        session_id      TEXT
    )
    """,

    # ------------------------------------------------------------------
    # Guardrail events
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS guardrail_events (
        guardrail_id    TEXT PRIMARY KEY,
        run_id          TEXT,
        timestamp       TEXT NOT NULL,
        guardrail_type  TEXT NOT NULL,
        status          TEXT NOT NULL,
        candidate_name  TEXT,
        details         TEXT,          -- JSON
        severity        TEXT DEFAULT 'none',
        action_taken    TEXT,
        FOREIGN KEY (run_id) REFERENCES agent_runs(run_id)
    )
    """,

    # ------------------------------------------------------------------
    # Indexes for performance
    # ------------------------------------------------------------------
    "CREATE INDEX IF NOT EXISTS idx_profiles_run ON candidate_profiles(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_scorecards_run ON scorecards(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_decisions_run ON interview_decisions(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_trajectory_run ON trajectory_events(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_run ON audit_log(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_guardrail_run ON guardrail_events(run_id)",
]


# ---------------------------------------------------------------------------
# Database manager
# ---------------------------------------------------------------------------

class DatabaseManager:
    """
    Manages SQLite connections and CRUD operations.
    Thread-safe via connection-per-call pattern.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        settings = get_settings()
        self.db_path = Path(db_path or settings.database_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager yielding a configured SQLite connection."""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row          # Dict-like row access
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialise(self) -> None:
        """Run DDL to create tables and indexes."""
        with self._connect() as conn:
            for stmt in _DDL_STATEMENTS:
                conn.execute(stmt)
        logger.info(f"Database initialised at: {self.db_path}")

    # ------------------------------------------------------------------
    # Agent runs
    # ------------------------------------------------------------------

    def create_run(self, run_id: str, job_description: str = "") -> None:
        sql = """
            INSERT INTO agent_runs (run_id, started_at, status, job_description)
            VALUES (?, ?, 'running', ?)
        """
        with self._connect() as conn:
            conn.execute(sql, (run_id, datetime.utcnow().isoformat(), job_description))

    def update_run(self, run_id: str, updates: dict[str, Any]) -> None:
        if not updates:
            return
        cols = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [run_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE agent_runs SET {cols} WHERE run_id = ?", vals)

    def complete_run(self, run_id: str, summary_data: dict[str, Any]) -> None:
        summary_data["completed_at"] = datetime.utcnow().isoformat()
        summary_data["status"] = "completed"
        self.update_run(run_id, summary_data)

    def get_run(self, run_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Candidate profiles
    # ------------------------------------------------------------------

    def save_profile(self, run_id: str, profile: dict[str, Any]) -> str:
        import uuid
        profile_id = str(uuid.uuid4())
        sql = """
            INSERT INTO candidate_profiles
            (profile_id, run_id, name, email, phone, location, years_experience,
             summary, skills, education, experience, projects, certifications,
             resume_filename, injection_detected, injection_severity,
             parse_timestamp, raw_text_snippet)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            conn.execute(sql, (
                profile_id, run_id,
                profile.get("name", ""),
                profile.get("email"),
                profile.get("phone"),
                profile.get("location"),
                profile.get("years_experience", 0),
                profile.get("summary", ""),
                json.dumps(profile.get("skills", [])),
                json.dumps(profile.get("education", [])),
                json.dumps(profile.get("experience", [])),
                json.dumps(profile.get("projects", [])),
                json.dumps(profile.get("certifications", [])),
                profile.get("resume_filename", ""),
                int(profile.get("injection_detected", False)),
                profile.get("injection_severity", "none"),
                datetime.utcnow().isoformat(),
                profile.get("raw_text_snippet", ""),
            ))
        return profile_id

    def get_profiles(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM candidate_profiles WHERE run_id = ?", (run_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Scorecards
    # ------------------------------------------------------------------

    def save_scorecard(self, run_id: str, scorecard: dict[str, Any]) -> str:
        import uuid
        scorecard_id = str(uuid.uuid4())
        sql = """
            INSERT INTO scorecards
            (scorecard_id, run_id, candidate_name, criterion_scores,
             overall_weighted_score, recommendation, confidence,
             strengths, gaps, reasoning, injection_penalty_applied,
             fairness_reviewed, score_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            conn.execute(sql, (
                scorecard_id, run_id,
                scorecard.get("candidate_name", ""),
                json.dumps(scorecard.get("criterion_scores", {})),
                scorecard.get("overall_weighted_score", 0.0),
                scorecard.get("recommendation", "Reject"),
                scorecard.get("confidence", 0.5),
                json.dumps(scorecard.get("strengths", [])),
                json.dumps(scorecard.get("gaps", [])),
                scorecard.get("reasoning", ""),
                int(scorecard.get("injection_penalty_applied", False)),
                int(scorecard.get("fairness_reviewed", False)),
                datetime.utcnow().isoformat(),
            ))
        return scorecard_id

    def get_scorecards(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM scorecards WHERE run_id = ? ORDER BY overall_weighted_score DESC",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Interview decisions & slots
    # ------------------------------------------------------------------

    def save_decision(self, run_id: str, decision: dict[str, Any]) -> str:
        import uuid
        decision_id = str(uuid.uuid4())
        sql = """
            INSERT INTO interview_decisions
            (decision_id, run_id, candidate_name, final_recommendation,
             rank, weighted_score, confidence, reasoning, priority_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            conn.execute(sql, (
                decision_id, run_id,
                decision.get("candidate_name", ""),
                decision.get("final_recommendation", "Reject"),
                decision.get("rank", 0),
                decision.get("weighted_score", 0.0),
                decision.get("confidence", 0.5),
                decision.get("reasoning", ""),
                int(decision.get("priority_flag", False)),
            ))
        return decision_id

    def save_interview_slot(self, run_id: str, slot: dict[str, Any]) -> str:
        import uuid
        slot_id = str(uuid.uuid4())
        sql = """
            INSERT INTO interview_slots
            (slot_id, run_id, candidate_name, slot_date, slot_time,
             timezone, interviewer, duration_minutes, format,
             interview_type, confirmed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            conn.execute(sql, (
                slot_id, run_id,
                slot.get("candidate_name", ""),
                slot.get("date", ""),
                slot.get("time", ""),
                slot.get("timezone", "Asia/Kolkata"),
                slot.get("interviewer", ""),
                slot.get("duration_minutes", 60),
                slot.get("format", "Video"),
                slot.get("interview_type", "Technical"),
                int(slot.get("confirmed", False)),
                datetime.utcnow().isoformat(),
            ))
        return slot_id

    def get_decisions(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM interview_decisions WHERE run_id = ? ORDER BY rank",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_interview_slots(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM interview_slots WHERE run_id = ?",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Trajectory events
    # ------------------------------------------------------------------

    def save_trajectory_event(self, run_id: str, event: dict[str, Any]) -> None:
        import uuid
        sql = """
            INSERT INTO trajectory_events
            (event_id, run_id, event_type, node, title, content,
             metadata, timestamp, duration_ms, success)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            conn.execute(sql, (
                event.get("event_id") or str(uuid.uuid4()),
                run_id,
                event.get("event_type", "action"),
                event.get("node", ""),
                event.get("title", ""),
                event.get("content", ""),
                json.dumps(event.get("metadata", {})),
                event.get("timestamp", datetime.utcnow().isoformat()),
                event.get("duration_ms"),
                int(event.get("success", True)),
            ))

    def get_trajectory(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trajectory_events WHERE run_id = ? ORDER BY timestamp",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Guardrail events
    # ------------------------------------------------------------------

    def save_guardrail_event(self, run_id: str, event: dict[str, Any]) -> None:
        import uuid
        sql = """
            INSERT INTO guardrail_events
            (guardrail_id, run_id, timestamp, guardrail_type, status,
             candidate_name, details, severity, action_taken)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            conn.execute(sql, (
                str(uuid.uuid4()),
                run_id,
                datetime.utcnow().isoformat(),
                event.get("guardrail_type", "unknown"),
                event.get("status", "PASS"),
                event.get("candidate_name"),
                json.dumps(event.get("details", {})),
                event.get("severity", "none"),
                event.get("action_taken", ""),
            ))

    def get_guardrail_events(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM guardrail_events WHERE run_id = ? ORDER BY timestamp",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def log_audit(
        self,
        action: str,
        *,
        run_id: Optional[str] = None,
        level: str = "INFO",
        category: str = "system",
        actor: str = "agent",
        target: Optional[str] = None,
        details: Optional[Any] = None,
        session_id: Optional[str] = None,
    ) -> None:
        import uuid
        details_str = json.dumps(details) if not isinstance(details, str) else details
        sql = """
            INSERT INTO audit_log
            (audit_id, run_id, timestamp, level, category,
             actor, action, target, details, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            conn.execute(sql, (
                str(uuid.uuid4()),
                run_id,
                datetime.utcnow().isoformat(),
                level,
                category,
                actor,
                action,
                target,
                details_str,
                session_id,
            ))

    def get_audit_log(
        self,
        run_id: Optional[str] = None,
        limit: int = 200,
        level: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if run_id:
            conditions.append("run_id = ?")
            params.append(run_id)
        if level:
            conditions.append("level = ?")
            params.append(level)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM audit_log {where} ORDER BY timestamp DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def execute_query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute arbitrary read-only SQL and return rows."""
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_run_stats(self, run_id: str) -> dict[str, Any]:
        """Return aggregate statistics for a run."""
        stats: dict[str, Any] = {}
        with self._connect() as conn:
            # Profile count
            stats["total_profiles"] = conn.execute(
                "SELECT COUNT(*) FROM candidate_profiles WHERE run_id = ?", (run_id,)
            ).fetchone()[0]

            # Score stats
            row = conn.execute(
                """SELECT AVG(overall_weighted_score), MAX(overall_weighted_score),
                          MIN(overall_weighted_score), COUNT(*)
                   FROM scorecards WHERE run_id = ?""",
                (run_id,),
            ).fetchone()
            stats["avg_score"] = round(row[0] or 0.0, 2)
            stats["max_score"] = round(row[1] or 0.0, 2)
            stats["min_score"] = round(row[2] or 0.0, 2)
            stats["scored_count"] = row[3] or 0

            # Recommendation breakdown
            for rec in ("Interview", "Hold", "Reject"):
                count = conn.execute(
                    "SELECT COUNT(*) FROM scorecards WHERE run_id = ? AND recommendation = ?",
                    (run_id, rec),
                ).fetchone()[0]
                stats[rec.lower() + "_count"] = count

            # Trajectory event count
            stats["event_count"] = conn.execute(
                "SELECT COUNT(*) FROM trajectory_events WHERE run_id = ?", (run_id,)
            ).fetchone()[0]

            # Guardrail stats
            stats["guardrail_pass"] = conn.execute(
                "SELECT COUNT(*) FROM guardrail_events WHERE run_id = ? AND status = 'PASS'",
                (run_id,),
            ).fetchone()[0]
            stats["guardrail_fail"] = conn.execute(
                "SELECT COUNT(*) FROM guardrail_events WHERE run_id = ? AND status = 'FAIL'",
                (run_id,),
            ).fetchone()[0]

        return stats

    def drop_run_data(self, run_id: str) -> None:
        """Delete all data for a run (used in reset operations)."""
        tables = [
            "trajectory_events", "guardrail_events", "audit_log",
            "interview_slots", "interview_decisions", "scorecards",
            "candidate_profiles",
        ]
        with self._connect() as conn:
            for table in tables:
                conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM agent_runs WHERE run_id = ?", (run_id,))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_db_instance: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """Return singleton DatabaseManager."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
