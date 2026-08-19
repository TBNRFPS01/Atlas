"""Unified execution pipeline for ATLAS.

Keeps existing Router/Planner/tool systems as workers while giving missions one
consistent lifecycle: context -> plan -> execute -> verify -> learn.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from core.agent_runtime import AgentRuntime, SubagentResult


@dataclass(slots=True)
class MissionResult:
    success: bool
    output: str
    verified: bool = False
    error: str = ""


class Orchestrator:
    def __init__(self, router: Any, runtime: AgentRuntime | None = None) -> None:
        self.router = router
        self.runtime = runtime or AgentRuntime()

    def run(self, goal: str, *, verify: Callable[[str], bool] | None = None) -> MissionResult:
        self.runtime.context.add("user", goal, priority=10)
        self.runtime.trace.record("mission", "start", goal=goal)
        try:
            output = str(self.router._run_autonomous_mission(goal))
            verified = bool(verify(output)) if verify else bool(output.strip())
            if not verified:
                self.runtime.trace.record("mission", "verification_failed", goal=goal)
                return MissionResult(False, output, False, "verification failed")
            self.runtime.trace.record("mission", "complete", goal=goal)
            return MissionResult(True, output, True)
        except Exception as exc:
            self.runtime.trace.record("mission", "error", status="error", goal=goal, error=str(exc))
            return MissionResult(False, "", False, str(exc))

    def delegate(self, agent: str, task: str) -> SubagentResult:
        self.runtime.context.add("task", task, priority=8)
        return self.runtime.team.delegate(agent, task)

    def checkpoint(self, state: dict[str, Any], path: str) -> None:
        self.runtime.save_checkpoint(path, extra=state)
