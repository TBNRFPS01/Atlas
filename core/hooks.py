"""Lifecycle hooks for policy, observation, and verification around tool actions."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

Hook = Callable[..., Any]


class HookRegistry:
    EVENTS = ("before_tool", "after_tool", "before_commit", "after_task", "on_error")

    def __init__(self) -> None:
        self._hooks: dict[str, list[Hook]] = defaultdict(list)

    def register(self, event: str, hook: Hook) -> None:
        if event not in self.EVENTS:
            raise ValueError(f"unsupported hook event: {event}")
        self._hooks[event].append(hook)

    def emit(self, event: str, **payload: Any) -> list[Any]:
        if event not in self.EVENTS:
            raise ValueError(f"unsupported hook event: {event}")
        results: list[Any] = []
        for hook in tuple(self._hooks[event]):
            results.append(hook(**payload))
        return results
