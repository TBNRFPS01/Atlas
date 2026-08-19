"""Compact, structured handoffs between long-running ATLAS sessions."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json


@dataclass
class SessionHandoff:
    goal: str
    decisions: list[str]
    completed: list[str]
    pending: list[str]
    failures: list[str]
    changed_resources: list[str]
    constraints: list[str]
    created_at: str

    @classmethod
    def create(cls, goal: str, **kwargs) -> "SessionHandoff":
        return cls(
            goal=goal,
            decisions=list(kwargs.get("decisions", [])),
            completed=list(kwargs.get("completed", [])),
            pending=list(kwargs.get("pending", [])),
            failures=list(kwargs.get("failures", [])),
            changed_resources=list(kwargs.get("changed_resources", [])),
            constraints=list(kwargs.get("constraints", [])),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, value: str) -> "SessionHandoff":
        return cls(**json.loads(value))
