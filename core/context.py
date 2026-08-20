"""Short-lived context for references such as 'close it'."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class ContextEvent:
    prompt: str
    intent: str | None = None
    target: str | None = None
    result: str | None = None


class ContextStore:
    def __init__(self, max_events: int = 20) -> None:
        self._events: deque[ContextEvent] = deque(maxlen=max_events)

    def remember(self, prompt: str, *, intent: str | None = None, target: str | None = None, result: str | None = None) -> None:
        self._events.append(ContextEvent(prompt, intent, target, result))

    def latest_target(self) -> str | None:
        for event in reversed(self._events):
            if event.target:
                return event.target
        return None

    def resolve(self, prompt: str) -> str:
        text = prompt.strip()
        if text.lower() in {"close it", "quit it", "open it", "focus it"}:
            target = self.latest_target()
            if target:
                return text.rsplit(" ", 1)[0] + " " + target
        return text

    def recent(self, limit: int = 5) -> list[ContextEvent]:
        return list(self._events)[-limit:]
