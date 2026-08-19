"""Failure containment for autonomous ATLAS operations."""
from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float | None = None


class CircuitBreaker:
    """Stops repeated failures from becoming an autonomy runaway."""

    def __init__(self, failure_limit: int = 3, cooldown_seconds: float = 30.0) -> None:
        if failure_limit < 1:
            raise ValueError("failure_limit must be positive")
        self.failure_limit = failure_limit
        self.cooldown_seconds = cooldown_seconds
        self._states: dict[str, CircuitState] = {}

    def allow(self, key: str) -> bool:
        state = self._states.setdefault(key, CircuitState())
        if state.opened_at is None:
            return True
        if monotonic() - state.opened_at >= self.cooldown_seconds:
            state.opened_at = None
            state.failures = 0
            return True
        return False

    def success(self, key: str) -> None:
        self._states[key] = CircuitState()

    def failure(self, key: str) -> None:
        state = self._states.setdefault(key, CircuitState())
        state.failures += 1
        if state.failures >= self.failure_limit:
            state.opened_at = monotonic()

    def reset(self, key: str) -> None:
        self._states.pop(key, None)
