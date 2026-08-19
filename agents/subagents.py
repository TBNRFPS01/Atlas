"""Isolated subagent specifications and orchestration primitives for ATLAS V1."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class AgentSpec:
    name: str
    role: str
    capabilities: frozenset[str] = frozenset()
    model: str | None = None
    max_turns: int = 12
    timeout_seconds: float = 300.0


@dataclass
class AgentResult:
    agent: str
    success: bool
    output: Any = None
    error: str | None = None


class SubagentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentSpec] = {}

    def register(self, spec: AgentSpec) -> None:
        self._agents[spec.name] = spec

    def get(self, name: str) -> AgentSpec | None:
        return self._agents.get(name)

    def list(self) -> list[AgentSpec]:
        return list(self._agents.values())

    def run_isolated(self, name: str, runner: Callable[[AgentSpec], Any]) -> AgentResult:
        spec = self.get(name)
        if spec is None:
            return AgentResult(name, False, error="unknown agent")
        try:
            return AgentResult(name, True, output=runner(spec))
        except Exception as exc:  # agent failures must not crash the orchestrator
            return AgentResult(name, False, error=str(exc))
