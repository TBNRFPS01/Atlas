"""Experience-based learning for ATLAS.

ATLAS records which strategy (typically which tool + approach) worked for a
given task type and how often, so future autonomous runs can bias toward
proven strategies and away from repeatedly failing ones. Reusable lessons
are also stored as first-class memories (category ``lesson``) so they flow
back into the model's memory context automatically.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExperienceStore:
    """Persist strategy success statistics and distilled lessons.

    Strategies are keyed by ``(task_type, strategy_key)`` (the strategy key
    is usually the tool name used, e.g. ``web`` or ``browser``). Each attempt
    updates a running success average, so :meth:`best_strategy` answers
    "what tends to work for this kind of task".
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
                "CREATE TABLE IF NOT EXISTS strategies ("
                "  task_type TEXT NOT NULL,"
                "  strategy_key TEXT NOT NULL,"
                "  strategy TEXT NOT NULL DEFAULT '',"
                "  avg_success REAL NOT NULL DEFAULT 0.0,"
                "  run_count INTEGER NOT NULL DEFAULT 0,"
                "  notes TEXT NOT NULL DEFAULT '',"
                "  first_used TEXT NOT NULL,"
                "  last_used TEXT NOT NULL,"
                "  PRIMARY KEY(task_type, strategy_key)"
                ")"
            )
            conn.commit()

    # -- attempt recording ---------------------------------------------
    def record_attempt(
        self,
        task_type: str,
        strategy_key: str,
        success: bool,
        *,
        strategy: str = "",
        notes: str = "",
    ) -> None:
        """Record one execution result for a (task_type, strategy_key) pair."""
        task_type = task_type or "general"
        strategy_key = strategy_key or "llm"
        now = _utc_now()
        success_f = 1.0 if success else 0.0
        note_fragment = f"last: {'ok' if success else 'FAIL'} - {notes[:200]}" if notes else (
            "last: ok" if success else "last: FAIL"
        )
        with self._connect() as conn:
            row = conn.execute(
                "SELECT avg_success, run_count FROM strategies WHERE task_type = ? AND strategy_key = ?",
                (task_type, strategy_key),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO strategies(task_type, strategy_key, strategy, avg_success, run_count, "
                    "notes, first_used, last_used) VALUES(?, ?, ?, ?, 1, ?, ?, ?)",
                    (task_type, strategy_key, strategy, success_f, note_fragment, now, now),
                )
            else:
                prior_avg, count = row
                new_avg = (prior_avg * count + success_f) / (count + 1)
                conn.execute(
                    "UPDATE strategies SET avg_success = ?, run_count = run_count + 1, "
                    "strategy = CASE WHEN ? != '' THEN ? ELSE strategy END, "
                    "notes = ?, last_used = ? WHERE task_type = ? AND strategy_key = ?",
                    (new_avg, strategy, strategy, note_fragment, now, task_type, strategy_key),
                )
            conn.commit()

    # -- selection ------------------------------------------------------
    def best_strategy(self, task_type: str, min_runs: int = 2) -> dict[str, Any] | None:
        """Return the best-known strategy for a task type.

        ``min_runs`` keeps one-off luck from overriding a well-tested default.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT task_type, strategy_key, strategy, avg_success, run_count, notes "
                "FROM strategies WHERE task_type = ? AND run_count >= ? "
                "ORDER BY avg_success DESC, run_count DESC LIMIT 1",
                (task_type, min_runs),
            ).fetchone()
        return dict(row) if row else None

    def strategies_for(self, task_type: str, limit: int = 5) -> list[dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT task_type, strategy_key, strategy, avg_success, run_count, notes "
                "FROM strategies WHERE task_type = ? ORDER BY avg_success DESC, run_count DESC LIMIT ?",
                (task_type, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def all_strategies(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT task_type, strategy_key, strategy, avg_success, run_count, notes "
                "FROM strategies ORDER BY run_count DESC, avg_success DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        """Number of recorded (task_type, strategy) pairs."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM strategies").fetchone()
        return int(row[0] if row else 0)

    def strategy_stats(self, task_type: str) -> dict[str, Any]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(run_count), 0) AS runs, "
                "COALESCE(SUM(run_count * avg_success), 0) AS success_weighted "
                "FROM strategies WHERE task_type = ?",
                (task_type,),
            ).fetchone()
        result = dict(row) if row else {"n": 0, "runs": 0, "success_weighted": 0}
        result["success_rate"] = (result["success_weighted"] / result["runs"]) if result["runs"] else 0.0
        return result

    # -- lessons --------------------------------------------------------
    def record_lesson(self, title: str, content: str, importance: float = 1.2) -> Any:
        """Store a distilled lesson as a ``lesson`` memory record.

        Lessons are written to the underlying memory database with the
        ``lesson`` category so they surface through normal context retrieval.
        """
        if self.memory is None:
            return None
        try:
            return self.memory.db.remember(
                "lesson",
                f"{title}: {content}",
                source="lesson",
                importance=importance,
            )
        except Exception:
            return None

    def recent_lessons(self, limit: int = 5) -> list[str]:
        """Return recent lesson texts (best-effort)."""
        if self.memory is None:
            return []
        try:
            recent = self.memory.recent(limit=50)
        except Exception:
            return []
        return [r.content for r in recent if getattr(r, "category", "") == "lesson"][:limit]