"""Persistent, autonomous goal management for ATLAS.

Goals are first-class, durable objects. They track status, priority, and
progress, survive restarts, and are what turns one-shot missions into
long-running work ATLAS can return to autonomously and safely.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class GoalStatus:
    """Lifecycle states for a persistent goal."""

    ACTIVE = "active"
    PAUSED = "paused"
    DONE = "done"
    ABANDONED = "abandoned"
    BLOCKED = "blocked"

    OPEN = (ACTIVE, PAUSED, BLOCKED)
    CLOSED = (DONE, ABANDONED)


@dataclass(slots=True)
class Goal:
    """A single persistent goal."""

    id: int
    title: str
    description: str = ""
    status: str = GoalStatus.ACTIVE
    priority: float = 0.0
    progress: float = 0.0
    source: str = "user"
    parent_id: int | None = None
    created_at: str = ""
    updated_at: str = ""
    last_advance_at: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return self.status in GoalStatus.OPEN

    @property
    def is_active(self) -> bool:
        return self.status == GoalStatus.ACTIVE


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GoalManager:
    """CRUD + selection over persistent goals stored in SQLite.

    ``memory`` is an optional :class:`memory.facts.FactStore`. When provided,
    goals are mirrored into the fact store under ``goal`` category entries so
    they also surface through the existing memory retrieval and daily
    briefing pipeline.
    """

    def __init__(self, db_path: str = "atlas_memory.db", memory: Any | None = None) -> None:
        self.db_path = Path(db_path)
        self.memory = memory
        self._ensure_database()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_database(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS goals ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  title TEXT NOT NULL,"
                "  description TEXT NOT NULL DEFAULT '',"
                "  status TEXT NOT NULL DEFAULT 'active',"
                "  priority REAL NOT NULL DEFAULT 0.0,"
                "  progress REAL NOT NULL DEFAULT 0.0,"
                "  source TEXT NOT NULL DEFAULT 'user',"
                "  parent_id INTEGER,"
                "  created_at TEXT NOT NULL,"
                "  updated_at TEXT NOT NULL,"
                "  last_advance_at TEXT NOT NULL DEFAULT '',"
                "  meta TEXT NOT NULL DEFAULT '{}'"
                ")"
            )
            conn.commit()

    # -- internal helpers ----------------------------------------------
    @staticmethod
    def _normalize(title: str) -> str:
        return re.sub(r"\s+", " ", title.strip().lower())

    @classmethod
    def _from_row(cls, row: sqlite3.Row) -> Goal:
        meta: dict[str, Any] = {}
        try:
            meta = json.loads(row["meta"] or "{}")
        except (json.JSONDecodeError, TypeError):
            meta = {}
        return Goal(
            id=row["id"],
            title=row["title"],
            description=row["description"] or "",
            status=row["status"],
            priority=row["priority"],
            progress=row["progress"],
            source=row["source"],
            parent_id=row["parent_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_advance_at=row["last_advance_at"] or "",
            meta=meta,
        )

    def _mirror(self, goal: Goal) -> None:
        """Mirror an open goal into the fact store so briefings see it."""
        if self.memory is None:
            return
        try:
            self.memory.remember_goal(f"goal:{goal.id}", goal.title[:200], importance=1.5 if goal.is_active else 0.5)
        except Exception:
            pass

    # -- create / read --------------------------------------------------
    def create_goal(
        self,
        title: str,
        description: str = "",
        priority: float = 1.0,
        source: str = "user",
        parent_id: int | None = None,
    ) -> Goal:
        """Create a goal, or return the existing open goal with the same title."""
        title = title.strip()
        if not title:
            raise ValueError("Goal title is required")

        existing = self.find_open_by_title(title)
        if existing is not None:
            if description and description != existing.description:
                self.update_goal(existing.id, description=description)
            return self.get_goal(existing.id)  # type: ignore[return-value]

        now = _utc_now()
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO goals(title, description, status, priority, progress, source, "
                "parent_id, created_at, updated_at, meta) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, '{}')",
                (title, description, GoalStatus.ACTIVE, float(priority), 0.0, source, parent_id, now, now),
            )
            gid = cursor.lastrowid
            conn.commit()
        goal = self.get_goal(gid)
        if goal is not None:
            self._mirror(goal)
        return goal  # type: ignore[return-value]

    def get_goal(self, goal_id: int) -> Goal | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        return self._from_row(row) if row else None

    def find_open_by_title(self, title: str) -> Goal | None:
        normalized = self._normalize(title)
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM goals WHERE status IN ('active', 'paused', 'blocked')").fetchall()
        for row in rows:
            if self._normalize(row["title"]) == normalized:
                return self._from_row(row)
        return None

    def list_goals(self, status: str | set[str] | None = None, limit: int | None = None) -> list[Goal]:
        """List goals, optionally filtered by one or more statuses."""
        query = "SELECT * FROM goals"
        params: list[Any] = []
        if isinstance(status, str):
            query += " WHERE status = ?"
            params.append(status)
        elif isinstance(status, (set, frozenset)) and status:
            query += f" WHERE status IN ({','.join('?' * len(status))})"
            params.extend(sorted(status))
        query += " ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'blocked' THEN 1 "
        query += "WHEN 'paused' THEN 2 WHEN 'done' THEN 3 ELSE 4 END, priority DESC, updated_at DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [self._from_row(row) for row in rows]

    def active_goals(self, limit: int | None = None) -> list[Goal]:
        return self.list_goals(GoalStatus.ACTIVE, limit=limit)

    def open_goals(self, limit: int | None = None) -> list[Goal]:
        return self.list_goals(GoalStatus.OPEN, limit=limit)

    # -- update ---------------------------------------------------------
    def update_goal(
        self,
        goal_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: float | None = None,
        progress: float | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Goal | None:
        goal = self.get_goal(goal_id)
        if goal is None:
            return None
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
            if row is None:
                return None
            next_title = title if title is not None else row["title"]
            next_desc = description if description is not None else row["description"]
            next_status = status if status is not None else row["status"]
            next_priority = priority if priority is not None else row["priority"]
            next_progress = progress if progress is not None else row["progress"]
            next_meta = meta if meta is not None else json.loads(row["meta"] or "{}")
            next_progress = max(0.0, min(1.0, float(next_progress)))
            conn.execute(
                "UPDATE goals SET title = ?, description = ?, status = ?, priority = ?, "
                "progress = ?, meta = ?, updated_at = ? WHERE id = ?",
                (next_title, next_desc, next_status, float(next_priority), next_progress,
                 json.dumps(next_meta), _utc_now(), goal_id),
            )
            conn.commit()
        updated = self.get_goal(goal_id)
        if updated is not None:
            self._mirror(updated)
        return updated

    def set_status(self, goal_id: int, status: str) -> Goal | None:
        return self.update_goal(goal_id, status=status)

    def set_progress(self, goal_id: int, progress: float) -> Goal | None:
        return self.update_goal(goal_id, progress=progress)

    def pause_goal(self, goal_id: int) -> Goal | None:
        return self.set_status(goal_id, GoalStatus.PAUSED)

    def resume_goal(self, goal_id: int) -> Goal | None:
        return self.set_status(goal_id, GoalStatus.ACTIVE)

    def block_goal(self, goal_id: int, reason: str = "") -> Goal | None:
        return self.update_goal(goal_id, status=GoalStatus.BLOCKED, meta={"block_reason": reason})

    def complete_goal(self, goal_id: int) -> Goal | None:
        return self.update_goal(goal_id, status=GoalStatus.DONE, progress=1.0)

    def abandon_goal(self, goal_id: int) -> Goal | None:
        return self.set_status(goal_id, GoalStatus.ABANDONED)

    def touch(self, goal_id: int) -> Goal | None:
        """Mark a goal as just advanced (for round-robin fairness)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE goals SET last_advance_at = ?, updated_at = ? WHERE id = ?",
                (_utc_now(), _utc_now(), goal_id),
            )
            conn.commit()
        return self.get_goal(goal_id)

    # -- selection ------------------------------------------------------
    def pick_next(self) -> Goal | None:
        """Pick the goal to work on next.

        Active goals are chosen by descending priority; ties go to the goal
        least-recently advanced so no single goal is starved.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM goals WHERE status = 'active' "
                "ORDER BY priority DESC, last_advance_at ASC, created_at ASC LIMIT 1"
            ).fetchone()
        return self._from_row(row) if row else None