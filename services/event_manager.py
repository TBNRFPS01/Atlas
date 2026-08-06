"""Event manager for ATLAS pub/sub messaging."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Callable


class EventManager:
    """Thread-safe event bus for inter-module communication."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[..., None]]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_name: str, callback: Callable[..., None]) -> None:
        """Register a callback to receive events of the given type."""
        with self._lock:
            self._listeners[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable[..., None]) -> None:
        """Remove a previously registered callback."""
        with self._lock:
            if callback in self._listeners.get(event_name, []):
                self._listeners[event_name].remove(callback)

    def emit(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event to all registered listeners."""
        with self._lock:
            listeners = list(self._listeners.get(event_name, []))

        for callback in listeners:
            try:
                callback(*args, **kwargs)
            except Exception:
                pass

    def emit_async(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event asynchronously in a background thread."""
        threading.Thread(target=self.emit, args=(event_name, *args), kwargs=kwargs, daemon=True).start()

    def clear(self) -> None:
        """Remove all registered listeners."""
        with self._lock:
            self._listeners.clear()