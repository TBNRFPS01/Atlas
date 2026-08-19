"""Convenience API for composing ATLAS's advanced runtime components."""
from __future__ import annotations

from typing import Any, Callable

from core.agent_runtime import AgentRuntime, ModelCandidate, SubagentSpec, FunctionSubagent


def build_runtime(models: list[dict[str, Any]] | None = None) -> AgentRuntime:
    runtime = AgentRuntime()
    for model in models or []:
        runtime.models.add(ModelCandidate(
            name=str(model["name"]),
            provider=str(model.get("provider", "local")),
            capabilities=set(model.get("capabilities", ["general"])),
            priority=int(model.get("priority", 0)),
        ))
    return runtime


def register_subagent(runtime: AgentRuntime, name: str, purpose: str,
                       handler: Callable[[str, SubagentSpec], str], max_steps: int = 8) -> None:
    spec = SubagentSpec(name=name, purpose=purpose, max_steps=max_steps)
    runtime.team.register(spec, FunctionSubagent(handler))
