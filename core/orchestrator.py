"""Unified execution pipeline for ATLAS.

The orchestrator is intentionally a thin composition layer over the existing
AutonomyController/Planner/Router. It gives foreground and queued work the
same lifecycle without duplicating planning, permissions, safety, memory, or
evaluation logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from core.agent_runtime import AgentRuntime, SubagentResult
from memory.missions import Mission, MissionStore
from services.task_queue import TaskQueue


@dataclass(slots=True)
class MissionResult:
    success: bool
    output: str
    verified: bool = False
    error: str = ""
    goal_id: int | None = None
    score: float = 0.0
    mission_id: int | None = None


class Orchestrator:
    """Single entry point for mission execution, delegation and queued work."""

    def __init__(
        self,
        router: Any,
        runtime: AgentRuntime | None = None,
        queue: TaskQueue | None = None,
        mission_store: MissionStore | None = None,
    ) -> None:
        self.router = router
        self.runtime = runtime or AgentRuntime()
        self.queue = queue or TaskQueue()
        self.missions = mission_store or MissionStore()

    def _report_to_result(self, report: Any, mission_id: int | None = None) -> MissionResult:
        output = report.to_text() if hasattr(report, "to_text") else str(report)
        success = bool(getattr(report, "success", bool(output.strip())))
        score = float(getattr(report, "score", 1.0 if success else 0.0))
        return MissionResult(
            success,
            output,
            success,
            "" if success else "mission failed",
            getattr(report, "goal_id", None),
            score,
            mission_id,
        )

    def run(
        self,
        goal: str,
        *,
        verify: Callable[[str], bool] | None = None,
        source: str = "user",
        mission_id: int | None = None,
    ) -> MissionResult:
        goal = goal.strip()
        if not goal:
            return MissionResult(False, "", False, "goal cannot be empty")

        mission = self.missions.get(mission_id) if mission_id is not None else None
        if mission is None:
            mission = self.missions.create(goal, context={"source": source})
        elif mission.goal != goal:
            raise ValueError("mission goal does not match the requested goal")

        self.missions.checkpoint(
            mission.id,
            status="running",
            current_step=mission.current_step or "planning",
            context={"source": source, "last_run_started": self.missions._timestamp()},
        )
        self.runtime.context.add("mission", goal, priority=10)
        self.runtime.trace.record("mission", "start", goal=goal, source=source, mission_id=mission.id)

        def operation() -> Any:
            autonomy = getattr(self.router, "_autonomy", None)
            if autonomy is None:
                raise RuntimeError("ATLAS autonomy controller is unavailable")
            return autonomy.run_auto(goal, source=source)

        ok, report_or_error, attempts = self.runtime.recovery.run(operation)
        if not ok:
            error = str(report_or_error)
            self.missions.fail(mission.id, {"error": error, "attempts": attempts})
            self.runtime.trace.record(
                "mission", "error", "error", goal=goal, mission_id=mission.id,
                error=error, attempts=attempts,
            )
            return MissionResult(False, "", False, error, mission_id=mission.id)

        result = self._report_to_result(report_or_error, mission.id)
        self.missions.checkpoint(
            mission.id,
            current_step="verification" if verify is not None else "completion",
            checkpoint="agent execution finished",
            context={"last_output": result.output[-12000:], "attempts": attempts},
        )

        if verify is not None:
            try:
                result.verified = bool(verify(result.output))
            except Exception as exc:
                result.verified = False
                result.error = f"verification error: {exc}"
            if not result.verified:
                result.success = False
                result.error = result.error or "verification failed"

        if result.success and result.verified:
            self.missions.complete(
                mission.id,
                {
                    "output": result.output[-12000:],
                    "score": result.score,
                    "verified": True,
                    "attempts": attempts,
                },
            )
        elif result.success and verify is None:
            # The existing autonomy/evaluator is the primary verifier when no
            # external verifier is supplied. Preserve that result as complete.
            self.missions.complete(
                mission.id,
                {
                    "output": result.output[-12000:],
                    "score": result.score,
                    "verified": True,
                    "attempts": attempts,
                    "verification_source": "autonomy",
                },
            )
        else:
            self.missions.fail(
                mission.id,
                {
                    "error": result.error or "mission failed",
                    "output": result.output[-12000:],
                    "score": result.score,
                    "verified": result.verified,
                    "attempts": attempts,
                },
            )

        self.runtime.context.add("result", result.output, priority=7)
        self.runtime.trace.record(
            "mission", "complete" if result.success else "failed",
            "ok" if result.success else "error", goal=goal, mission_id=mission.id,
            verified=result.verified, score=result.score,
        )
        return result

    def resume_candidates(self, limit: int = 20) -> list[Mission]:
        """Return persisted missions that can be resumed by a scheduler/UI."""
        return self.missions.resume_candidates(limit)

    def resume(self, mission_id: int) -> MissionResult:
        """Resume a persisted mission using its saved goal and context."""
        mission = self.missions.get(mission_id)
        if mission is None:
            return MissionResult(False, "", False, f"mission {mission_id} not found", mission_id=mission_id)
        if mission.status in {"completed", "cancelled"}:
            return MissionResult(
                mission.status == "completed",
                str(mission.result or mission.failure or {}),
                mission.status == "completed",
                "" if mission.status == "completed" else f"mission is {mission.status}",
                mission_id=mission.id,
            )
        return self.run(mission.goal, source="resume", mission_id=mission.id)

    def pause(self, mission_id: int, reason: str | None = None) -> Mission | None:
        return self.missions.pause(mission_id, reason)

    def block(self, mission_id: int, reason: str | None = None) -> Mission | None:
        return self.missions.block(mission_id, reason)

    def cancel(self, mission_id: int, reason: str | None = None) -> Mission | None:
        return self.missions.cancel(mission_id, reason)

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
