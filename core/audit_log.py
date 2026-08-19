from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Immutable record of a significant ATLAS runtime event."""

    timestamp: float
    event: str
    tool: str = ""
    action: str = ""
    status: str = ""
    detail: str = ""
    metadata: dict[str, Any] | None = None


class AuditLog:
    """Append-only JSONL audit log with bounded in-memory history.

    The logger is deliberately independent from the LLM. Model output can be
    recorded as data, but it cannot create or alter an authorization decision.
    """

    def __init__(self, path: str | Path = "atlas_audit.jsonl", max_memory: int = 1000) -> None:
        self.path = Path(path)
        self.max_memory = max(1, max_memory)
        self._events: list[AuditEvent] = []
        self._lock = threading.Lock()

    def record(
        self,
        event: str,
        *,
        tool: str = "",
        action: str = "",
        status: str = "",
        detail: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        item = AuditEvent(time.time(), event, tool, action, status, detail, metadata)
        with self._lock:
            self._events.append(item)
            if len(self._events) > self.max_memory:
                del self._events[:-self.max_memory]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(item), ensure_ascii=False, default=str) + "\n")
        return item

    def recent(self, limit: int = 50) -> list[AuditEvent]:
        with self._lock:
            return list(self._events[-max(1, limit):])

    def clear_memory(self) -> None:
        with self._lock:
            self._events.clear()
