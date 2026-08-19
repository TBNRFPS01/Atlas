"""Persistent agent state for ATLAS.

Agent state belongs to ATLAS itself (not the user) and must survive
restarts: progress counters, runtime flags, the last goal worked on, and
checkpointed plans for autonomous missions. It is the durable backbone for
autonomy -- the difference between "finish that thing from yesterday" and
starting over every run.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentStateStore:
    """SQLite-backed key/value store for ATLAS's own persistent state.

    Values are JSON-serialized so any Python object can be stored. Callers
    should namespace their keys with a component prefix (for example
    ``goals.current_goal_id`` or ``mission.plan:3``).
    """

    def __init__(self, db_path: str = "atlas_memory.db") -> None:
        self.db_path = Path(db_path)
        self._ensure_database()

    # -- storage --------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_database(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS agent_state ("
                "  key TEXT PRIMARY KEY,"
                "  value TEXT NOT NULL,"
                "  updated_at TEXT NOT NULL"
                ")"
            )
            conn.commit()

    # -- reading / writing ---------------------------------------------
    def set(self, key: str, value: Any) -> None:
        """Persist ``value`` under ``key`` (JSON serialized)."""
        payload = json.dumps(value)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO agent_state(key, value, updated_at) VALUES(?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "updated_at = excluded.updated_at",
                (key, payload, _utc_now()),
            )
            conn.commit()

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve the value stored under ``key`` or ``default``."""
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM agent_state WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return default

    def delete(self, key: str) -> bool:
        """Remove a key and return whether it existed."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM agent_state WHERE key = ?", (key,))
            conn.commit()
        return cursor.rowcount > 0

    def has(self, key: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM agent_state WHERE key = ?", (key,)).fetchone()
        return row is not None

    # -- helpers --------------------------------------------------------
    def increment(self, key: str, step: int = 1, default: int = 0) -> int:
        """Atomically-ish bump an integer counter and return the new value."""
        value = self.get(key, default)
        try:
            value = int(value) + step
        except (TypeError, ValueError):
            value = default + step
        self.set(key, value)
        return value

    def counter(self, key: str) -> int:
        """Read an integer counter, tolerating missing or non-numeric values."""
        value = self.get(key, 0)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def keys(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key FROM agent_state ORDER BY key").fetchall()
        return [row[0] for row in rows]

    def all(self) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM agent_state").fetchall()
        out: dict[str, Any] = {}
        for key, raw in rows:
            try:
                out[key] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                out[key] = raw
        return out

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM agent_state").fetchone()
        return int(row[0] if row else 0)