from __future__ import annotations

from collections import defaultdict
from typing import Callable


class EventBus:
    """Small event bus for ATLAS startup, memory, and tool events."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def on(self, event_name: str, callback: Callable[..., None]) -> None:
        self._listeners[event_name].append(callback)

    def emit(self, event_name: str, *args, **kwargs) -> None:
        for callback in self._listeners.get(event_name, []):
            callback(*args, **kwargs)
