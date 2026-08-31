"""Bounded post-task reflection helpers for ATLAS.

Inspired by reflection/learning loops in the user's Web Agent and OpenAgent
forks. Reflection is deliberately data-only: it never executes tools itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class Reflection:
    task: str
    outcome: str
    success: bool
    lessons: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ReflectionEngine:
    """Create compact, persistence-friendly reflections without an LLM call."""

    def evaluate(self, task: str, result: Any, *, success: bool, error: str | None = None) -> Reflection:
        if success:
            outcome = "completed"
            lessons = ["Record the successful tool/model path for future routing."]
            next_actions: list[str] = []
        else:
            outcome = error or "failed"
            lessons = ["Record the failure category and avoid immediately repeating the same path."]
            next_actions = ["Retry with an alternative provider, tool, or narrower plan."]
        return Reflection(task=task, outcome=outcome, success=success, lessons=lessons, next_actions=next_actions)

    @staticmethod
    def to_dict(reflection: Reflection) -> dict[str, Any]:
        return {
            "task": reflection.task,
            "outcome": reflection.outcome,
            "success": reflection.success,
            "lessons": list(reflection.lessons),
            "next_actions": list(reflection.next_actions),
            "created_at": reflection.created_at,
        }
