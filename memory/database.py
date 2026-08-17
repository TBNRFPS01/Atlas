from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class MemoryRecord:
    """A single ATLAS memory record."""

    id: int | None = None
    category: str = "fact"
    content: str = ""
    created_at: str = ""
    updated_at: str = ""
    importance: float = 0.0
    times_used: int = 0
    source: str = "user"


class MemoryDatabase:
    """SQLite-backed memory engine for ATLAS.

    The database stores user facts, preferences, important events,
    and long-term memories with relevance ranking and duplicate prevention.
    """

    def __init__(self, db_path: str = "atlas_memory.db") -> None:
        self.db_path = Path(db_path)
        self._ensure_database()

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ensure_database(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    importance REAL NOT NULL DEFAULT 0.0,
                    times_used INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'user',
                    UNIQUE(category, content)
                )
                """
            )
            conn.commit()

    def remember(
        self,
        category: str,
        content: str,
        source: str = "user",
        importance: float = 1.0,
    ) -> MemoryRecord:
        timestamp = self._timestamp()
        with sqlite3.connect(self.db_path) as conn:
            # Check for exact duplicate first
            row = conn.execute(
                "SELECT id, importance, times_used FROM memories WHERE category = ? AND content = ?",
                (category, content),
            ).fetchone()

            if row is None:
                # Check for semantic duplicate (same key with different value)
                if "=" in content:
                    key = content.split("=", 1)[0]
                    dup_row = conn.execute(
                        "SELECT id, content FROM memories WHERE category = ? AND content LIKE ?",
                        (category, f"{key}=%"),
                    ).fetchone()
                    if dup_row is not None:
                        # Update existing memory instead of creating duplicate
                        memory_id = dup_row[0]
                        conn.execute(
                            "UPDATE memories SET content = ?, updated_at = ?, importance = importance + 0.1 WHERE id = ?",
                            (content, timestamp, memory_id),
                        )
                        conn.commit()
                        return self.recall_by_id(memory_id)

                # No duplicate found, insert new
                cursor = conn.execute(
                    "INSERT INTO memories(category, content, created_at, updated_at, importance, times_used, source) VALUES(?, ?, ?, ?, ?, ?, ?)",
                    (category, content, timestamp, timestamp, importance, 1, source),
                )
                memory_id = cursor.lastrowid
            else:
                memory_id = row[0]
                new_importance = float(row[1]) + 0.5
                new_times_used = int(row[2]) + 1
                conn.execute(
                    "UPDATE memories SET importance = ?, times_used = ?, updated_at = ?, source = ? WHERE id = ?",
                    (new_importance, new_times_used, timestamp, source, memory_id),
                )

            conn.commit()
            return self.recall_by_id(memory_id)

    def update(self, memory_id: int, *, content: str | None = None, importance: float | None = None, category: str | None = None) -> MemoryRecord | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT category, content, importance FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if row is None:
                return None

            next_category = category or row[0]
            next_content = content or row[1]
            next_importance = importance if importance is not None else float(row[2])

            conn.execute(
                "UPDATE memories SET category = ?, content = ?, importance = ?, updated_at = ? WHERE id = ?",
                (next_category, next_content, next_importance, self._timestamp(), memory_id),
            )
            conn.commit()

            return self.recall_by_id(memory_id)

    def forget(self, memory_id: int | None = None, category: str | None = None, content: str | None = None) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            if memory_id is not None:
                cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            elif category and content:
                cursor = conn.execute("DELETE FROM memories WHERE category = ? AND content = ?", (category, content))
            elif category:
                cursor = conn.execute("DELETE FROM memories WHERE category = ?", (category,))
            else:
                return False

            conn.commit()
            return cursor.rowcount > 0

    def recall_by_id(self, memory_id: int) -> MemoryRecord | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, category, content, created_at, updated_at, importance, times_used, source FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()

            if row is None:
                return None

            return MemoryRecord(*row)

    def recall(self, memory_id: int | None = None, category: str | None = None, content: str | None = None) -> MemoryRecord | None:
        with sqlite3.connect(self.db_path) as conn:
            if memory_id is not None:
                row = conn.execute(
                    "SELECT id, category, content, created_at, updated_at, importance, times_used, source FROM memories WHERE id = ?",
                    (memory_id,),
                ).fetchone()
            elif category and content:
                row = conn.execute(
                    "SELECT id, category, content, created_at, updated_at, importance, times_used, source FROM memories WHERE category = ? AND content = ?",
                    (category, content),
                ).fetchone()
            else:
                row = None

            if row is None:
                return None
            return MemoryRecord(*row)

    def search(self, term: str, limit: int = 5) -> list[MemoryRecord]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, category, content, created_at, updated_at, importance, times_used, source FROM memories WHERE content LIKE ? ORDER BY importance DESC, times_used DESC, updated_at DESC LIMIT ?",
                (f"%{term}%", limit),
            ).fetchall()
            return [MemoryRecord(*row) for row in rows]

    def recent(self, limit: int = 5) -> list[MemoryRecord]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, category, content, created_at, updated_at, importance, times_used, source FROM memories ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [MemoryRecord(*row) for row in rows]

    def serialize(self) -> str:
        return json.dumps([record.__dict__ for record in self.recent(limit=100)])

    def set_fact(self, key: str, value: str) -> None:
        self.remember("fact", f"{key}={value}", source="fact")

    def get_fact(self, key: str) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT content FROM memories WHERE category = 'fact' AND content LIKE ?",
                (f"{key}=%",),
            ).fetchone()
            return row[0].split("=", 1)[1] if row else None

    def remember_short_term(self, key: str, value: str) -> None:
        self.remember("short_term", f"{key}={value}", source="short_term")

    def remember_long_term(self, key: str, value: str, relevance: float = 0.0) -> None:
        self.remember("long_term", f"{key}={value}", source="long_term", importance=relevance)

    def remember_preference(self, key: str, value: str) -> None:
        self.remember("preference", f"{key}={value}", source="preference")

    def remember_event(self, key: str, value: str) -> None:
        self.remember("event", f"{key}={value}", source="event")

    def forget_by_key(self, key: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM memories WHERE content LIKE ?", (f"{key}=%",))
            conn.commit()
            return cursor.rowcount > 0

    def recall_by_key(self, key: str) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT content FROM memories WHERE content LIKE ? ORDER BY updated_at DESC LIMIT 1", (f"{key}=%",)).fetchone()
            if row is None:
                return None
            return row[0].split("=", 1)[1]

    def semantic_search(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Perform a semantic-like search using keyword matching and relevance scoring."""
        with sqlite3.connect(self.db_path) as conn:
            terms = [t for t in query.lower().split() if len(t) > 2]
            if not terms:
                return []

            like_patterns = " OR ".join(["content LIKE ?"] * len(terms))
            params = [f"%{t}%" for t in terms]

            rows = conn.execute(
                f"SELECT id, category, content, created_at, updated_at, importance, times_used, source FROM memories WHERE {like_patterns} ORDER BY importance DESC, times_used DESC, updated_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()
            return [MemoryRecord(*row) for row in rows]

    def retrieve(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Return the most relevant memories for ``query`` using a blended score.

        The score combines:
          * term overlap between the query and the stored content,
          * the stored ``importance`` weight,
          * how often the memory has been used (``times_used``),
          * recency (memories updated recently rank slightly higher).

        Memories with no term overlap are excluded entirely.
        """
        import re

        terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 1]
        if not terms:
            return []

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, category, content, created_at, updated_at, importance, times_used, source FROM memories"
            ).fetchall()

        now = datetime.now(timezone.utc)
        scored: list[tuple[float, MemoryRecord]] = []
        for row in rows:
            record = MemoryRecord(*row)
            content_l = record.content.lower()
            overlap = sum(1 for t in terms if t in content_l)
            if overlap == 0:
                continue
            try:
                age_days = (now - datetime.fromisoformat(record.updated_at)).total_seconds() / 86400.0
            except Exception:
                age_days = 0.0
            recency = 1.0 / (1.0 + age_days / 30.0)
            title_boost = 2.0 if content_l.startswith(tuple(terms)) else 1.0
            score = (overlap * 2.0 * title_boost) + float(record.importance) + float(record.times_used) * 0.5 + recency
            scored.append((score, record))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [record for _, record in scored[:limit]]

    def consolidate_memories(self) -> int:
        """Merge duplicate memories and update importance scores. Returns count of merged records."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE memories SET importance = importance + 0.1, times_used = times_used + 1
                WHERE id IN (
                    SELECT id FROM memories WHERE rowid NOT IN (
                        SELECT MIN(rowid) FROM memories GROUP BY category, content
                    )
                )
                """
            )
            conn.commit()
            return cursor.rowcount

    def cleanup_old_memories(self, max_age_days: int = 30) -> int:
        """Remove memories older than the specified number of days. Returns count of deleted records."""
        from datetime import datetime, timedelta, timezone

        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM memories WHERE updated_at < ?", (cutoff,))
            conn.commit()
            return cursor.rowcount
