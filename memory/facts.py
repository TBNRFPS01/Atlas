from __future__ import annotations

from memory.database import MemoryDatabase, MemoryRecord


class FactStore:
    """Convenience wrapper around ATLAS SQLite memory storage."""

    def __init__(self, db_path: str = "atlas_memory.db") -> None:
        self.db = MemoryDatabase(db_path)

    def remember(self, key: str, value: str, category: str = "fact", source: str = "user") -> MemoryRecord:
        # Check for duplicate before storing
        existing = self.db.recall(category=category, content=f"{key}={value}")
        if existing is not None:
            return existing
        return self.db.remember(category, f"{key}={value}", source=source)

    def update(self, key: str, value: str, category: str = "fact") -> MemoryRecord | None:
        record = self.db.recall(category=category, content=f"{key}={value}")
        if record is None:
            return self.remember(key, value, category=category)
        return self.db.update(record.id, content=f"{key}={value}")

    def forget(self, key: str) -> bool:
        return self.db.forget_by_key(key)

    def recall(self, key: str) -> str | None:
        return self.db.recall_by_key(key)

    def search(self, term: str, limit: int = 5) -> list[str]:
        return [item.content for item in self.db.search(term, limit=limit)]

    def recent(self, limit: int = 5) -> list[MemoryRecord]:
        return self.db.recent(limit=limit)

    def remember_short_term(self, key: str, value: str) -> MemoryRecord:
        return self.db.remember("short_term", f"{key}={value}", source="short_term")

    def remember_long_term(self, key: str, value: str, relevance: float = 0.0) -> MemoryRecord:
        return self.db.remember("long_term", f"{key}={value}", source="long_term", importance=relevance)

    def remember_preference(self, key: str, value: str) -> MemoryRecord:
        return self.db.remember("preference", f"{key}={value}", source="preference")

    def remember_event(self, key: str, value: str) -> MemoryRecord:
        return self.db.remember("event", f"{key}={value}", source="event")

    def remember_goal(self, key: str, value: str, importance: float = 1.0) -> MemoryRecord:
        return self.db.remember("goal", f"{key}={value}", source="goal", importance=importance)

    def remember_task(self, key: str, value: str, importance: float = 0.5) -> MemoryRecord:
        return self.db.remember("task", f"{key}={value}", source="task", importance=importance)

    def remember_project(self, key: str, value: str, importance: float = 1.5) -> MemoryRecord:
        return self.db.remember("project", f"{key}={value}", source="project", importance=importance)

    def semantic_search(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        return self.db.semantic_search(query, limit=limit)

    def consolidate(self) -> int:
        return self.db.consolidate_memories()

    def cleanup_old_memories(self, max_age_days: int = 30) -> int:
        return self.db.cleanup_old_memories(max_age_days)
