"""Simple per-key rate limiting for autonomous and tool operations."""
from __future__ import annotations

from time import monotonic


class RateLimiter:
    def __init__(self, limit: int = 30, window_seconds: float = 60.0) -> None:
        if limit < 1 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = monotonic()
        events = [t for t in self._events.get(key, []) if now - t < self.window_seconds]
        if len(events) >= self.limit:
            self._events[key] = events
            return False
        events.append(now)
        self._events[key] = events
        return True

    def remaining(self, key: str) -> int:
        now = monotonic()
        events = [t for t in self._events.get(key, []) if now - t < self.window_seconds]
        self._events[key] = events
        return max(0, self.limit - len(events))

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._events.clear()
        else:
            self._events.pop(key, None)
