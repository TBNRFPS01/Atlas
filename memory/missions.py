from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MISSION_STATUSES = {
    "pending",
    "running",
    "paused",
    "blocked",
    "completed",
    "failed",
    "cancelled",
}


@dataclass(slots=True)
class Mission:
    id: int | None = None
    goal: str = ""
    status: str = "pending"
    priority: int = 0
    created_at: str = ""
    updated_at: str = ""
    deadline: str | None = None
    current_step: str | None = None
    checkpoint: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    failure: dict[str, Any] | None = None


class MissionStore:
    """Durable mission/checkpoint storage for long-running ATLAS work."""

    def __init__(self, db_path: str = "atlas_memory.db") -> None:
        self.db_path = Path(db_path)
        self._ensure_database()

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_database(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS missions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deadline TEXT,
                    current_step TEXT,
                    checkpoint TEXT,
                    context_json TEXT NOT NULL DEFAULT '{}',
                    result_json TEXT,
                    failure_json TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_missions_status_updated ON missions(status, updated_at DESC)"
            )
            conn.commit()

    @staticmethod
    def _mission(row: sqlite3.Row) -> Mission:
        return Mission(
            id=row["id"],
            goal=row["goal"],
            status=row["status"],
            priority=row["priority"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deadline=row["deadline"],
            current_step=row["current_step"],
            checkpoint=row["checkpoint"],
            context=json.loads(row["context_json"] or "{}"),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            failure=json.loads(row["failure_json"]) if row["failure_json"] else None,
        )

    def create(
        self,
        goal: str,
        *,
        priority: int = 0,
        deadline: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> Mission:
        if not goal.strip():
            raise ValueError("Mission goal cannot be empty")
        now = self._timestamp()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO missions
                (goal, status, priority, created_at, updated_at, deadline, context_json)
                VALUES (?, 'pending', ?, ?, ?, ?, ?)
                """,
                (goal.strip(), priority, now, now, deadline, json.dumps(context or {})),
            )
            mission_id = cursor.lastrowid
            conn.commit()
        return self.get(mission_id)

    def get(self, mission_id: int | None) -> Mission | None:
        if mission_id is None:
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM missions WHERE id = ?", (mission_id,)).fetchone()
        return self._mission(row) if row else None

    def list_active(self, limit: int = 20) -> list[Mission]:
        if limit < 1:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM missions
                WHERE status IN ('pending', 'running', 'paused', 'blocked')
                ORDER BY priority DESC, updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._mission(row) for row in rows]

    def resume_candidates(self, limit: int = 20) -> list[Mission]:
        """Return unfinished missions suitable for startup/resume handling."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM missions
                WHERE status IN ('pending', 'running', 'paused', 'blocked')
                ORDER BY priority DESC, updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._mission(row) for row in rows]

    def checkpoint(
        self,
        mission_id: int,
        *,
        current_step: str | None = None,
        checkpoint: str | None = None,
        context: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> Mission | None:
        if status is not None and status not in MISSION_STATUSES:
            raise ValueError(f"Invalid mission status: {status}")

        mission = self.get(mission_id)
        if mission is None:
            return None

        next_context = mission.context.copy()
        if context is not None:
            next_context.update(context)

        next_status = status or mission.status
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE missions
                SET status = ?, updated_at = ?, current_step = ?, checkpoint = ?, context_json = ?
                WHERE id = ?
                """,
                (
                    next_status,
                    self._timestamp(),
                    current_step if current_step is not None else mission.current_step,
                    checkpoint if checkpoint is not None else mission.checkpoint,
                    json.dumps(next_context),
                    mission_id,
                ),
            )
            conn.commit()
        return self.get(mission_id)

    def complete(self, mission_id: int, result: dict[str, Any] | None = None) -> Mission | None:
        mission = self.get(mission_id)
        if mission is None:
            return None
        with self._connect() as conn:
            conn.execute(
                "UPDATE missions SET status = 'completed', updated_at = ?, result_json = ?, failure_json = NULL WHERE id = ?",
                (self._timestamp(), json.dumps(result or {}), mission_id),
            )
            conn.commit()
        return self.get(mission_id)

    def fail(self, mission_id: int, failure: dict[str, Any] | None = None) -> Mission | None:
        mission = self.get(mission_id)
        if mission is None:
            return None
        with self._connect() as conn:
            conn.execute(
                "UPDATE missions SET status = 'failed', updated_at = ?, failure_json = ?, result_json = NULL WHERE id = ?",
                (self._timestamp(), json.dumps(failure or {}), mission_id),
            )
            conn.commit()
        return self.get(mission_id)

    def pause(self, mission_id: int, reason: str | None = None) -> Mission | None:
        return self.checkpoint(
            mission_id,
            status="paused",
            context={"pause_reason": reason} if reason else None,
        )

    def block(self, mission_id: int, reason: str | None = None) -> Mission | None:
        return self.checkpoint(
            mission_id,
            status="blocked",
            context={"blocked_reason": reason} if reason else None,
        )

    def cancel(self, mission_id: int, reason: str | None = None) -> Mission | None:
        return self.checkpoint(
            mission_id,
            status="cancelled",
            context={"cancel_reason": reason} if reason else None,
        )
