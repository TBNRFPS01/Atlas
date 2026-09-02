"""Dynamic tool selection for ATLAS.

Keeps prompts small by exposing only tools relevant to the current task while
ensuring runtime risk metadata is enforced before a handler can execute.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    schema: dict[str, Any]
    handler: Callable[..., Any] | None = None
    keywords: tuple[str, ...] = ()
    risk: str = "safe"


class ToolRegistry:
    def __init__(self, permission_manager: Any | None = None) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._permissions = permission_manager

    def register(self, spec: ToolSpec) -> None:
        if spec.risk not in {"safe", "elevated", "dangerous"}:
            raise ValueError(f"Invalid risk level for '{spec.name}': {spec.risk}")
        self._tools[spec.name] = spec

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def all(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def select(self, prompt: str, limit: int = 12) -> list[ToolSpec]:
        text = prompt.lower()
        scored: list[tuple[int, ToolSpec]] = []
        for spec in self._tools.values():
            score = sum(2 for word in spec.keywords if re.search(r"\b" + re.escape(word.lower()) + r"\b", text))
            score += 1 if spec.name.lower() in text else 0
            scored.append((score, spec))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        selected = [spec for score, spec in scored if score > 0][:limit]
        if not selected:
            selected = [spec for _, spec in scored[:limit]]
        return selected

    def schemas_for(self, prompt: str, limit: int = 12) -> list[dict[str, Any]]:
        return [spec.schema for spec in self.select(prompt, limit=limit)]

    def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        confirmed: bool = False,
    ) -> Any:
        spec = self.get(name)
        if spec is None:
            raise KeyError(f"Unknown tool: {name}")
        if spec.handler is None:
            raise RuntimeError(f"Tool '{name}' has no handler")

        action = str((arguments or {}).get("action", "execute"))
        level = {"safe": "basic", "elevated": "elevated", "dangerous": "destructive"}[spec.risk]
        if self._permissions is None:
            if spec.risk != "safe":
                raise PermissionError(
                    f"Dynamic tool '{name}' is {spec.risk} and has no authorization context"
                )
        else:
            decision = self._permissions.decide(
                name,
                action,
                permission_level=level,
                confirmed=confirmed,
            )
            if decision == "deny":
                raise PermissionError(f"Permission denied for dynamic tool '{name}'")
            if decision == "ask":
                raise PermissionError(f"Confirmation required for dynamic tool '{name}'")

        return spec.handler(**(arguments or {}))
