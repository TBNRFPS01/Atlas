"""Unified execution pipeline for ATLAS.

The orchestrator is intentionally a thin composition layer over the existing
AutonomyController/Planner/Router.  It gives foreground and queued work the
same lifecycle without duplicating planning, permissions, safety, memory, or
evaluation logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from core.agent_runtime import AgentRuntime, SubagentResult
from services.task_queue import TaskQueue


@dataclass(slots=True)
class MissionResult:
    success: bool
    output: str
    verified: bool = False
    error: str = ""
    goal_id: int | None = None
    score: float = 0.0


class Orchestrator:
    """Single entry point for mission execution, delegation and queued work."""

    def __init__(self, router: Any, runtime: AgentRuntime | None = None,
                 queue: TaskQueue | None = None) -> None:
        self.router = router
        self.runtime = runtime or AgentRuntime()
        self.queue = queue or TaskQueue()

    def _report_to_result(self, report: Any) -> MissionResult:
        output = report.to_text() if hasattr(report, "to_text") else str(report)
        success = bool(getattr(report, "success", bool(output.strip())))
        score = float(getattr(report, "score", 1.0 if success else 0.0))
        return MissionResult(success, output, success, "" if success else "mission failed",
                             getattr(report, "goal_id", None), score)

    def run(self, goal: str, *, verify: Callable[[str], bool] | None = None,
            source: str = "user") -> MissionResult:
        goal = goal.strip()
        if not goal:
            return MissionResult(False, "", False, "goal cannot be empty")
        self.runtime.context.add("user", goal, priority=10)
        self.runtime.trace.record("mission", "start", goal=goal, source=source)

        def operation() -> Any:
            autonomy = getattr(self.router, "_autonomy", None)
            if autonomy is None:
                raise RuntimeError("ATLAS autonomy controller is unavailable")
            return autonomy.run_auto(goal, source=source)

        ok, report_or_error, attempts = self.runtime.recovery.run(operation)
        if not ok:
            error = str(report_or_error)
            self.runtime.trace.record("mission", "error", "error", goal=goal, error=error, attempts=attempts)
            return MissionResult(False, "", False, error)

        result = self._report_to_result(report_or_error)
        if verify is not None:
            try:
                result.verified = bool(verify(result.output))
            except Exception as exc:
                result.verified = False
                result.error = f"verification error: {exc}"
            if not result.verified:
                result.success = False
                result.error = result.error or "verification failed"
        self.runtime.context.add("result", result.output, priority=7)
        self.runtime.trace.record("mission", "complete" if result.success else "failed",
                                  "ok" if result.success else "error", goal=goal,
                                  verified=result.verified, score=result.score)
        return result

    def delegate(self, agent: str, task: str) -> SubagentResult:
        self.runtime.context.add("task", task, priority=8)
        return self.runtime.team.delegate(agent, task)

    def enqueue(self, goal: str, priority: int = 0) -> str:
        task = self.queue.add(goal, priority)
        self.runtime.trace.record("queue", "enqueue", goal=goal, task_id=task.id, priority=priority)
        return task.id

    def run_next(self) -> MissionResult | None:
        task = self.queue.next()
        if task is None:
            return None
        self.queue.mark(task.id, "running")
        result = self.run(task.goal, source="queue")
        self.queue.mark(task.id, "completed" if result.success else "failed")
        return result

    def checkpoint(self, path: str | Path) -> None:
        self.runtime.save_checkpoint(path)
