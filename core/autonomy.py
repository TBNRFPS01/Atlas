"""Autonomous mission controller for ATLAS.

Wraps planning, execution, self-evaluation, experience recording, and
persistent goal/plan checkpointing behind a single API used by both the
interactive ``/auto`` command and the background goal service.

Safety invariants preserved here:
  * Hard safety boundaries always win (enforced by the planner's permission
    decision, which the controller can never bypass).
  * Background (``consent="agent"``) runs never auto-approve destructive or
    elevated actions; if one is needed, the goal is parked until the user
    confirms or changes policy.
  * Every mission's plan is checkpointed in persistent agent state, so a
    crash or restart resumes the same goal instead of restarting it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from memory.goals import GoalManager, GoalStatus


@dataclass(slots=True)
class MissionReport:
    """Result of running (part of) a goal, ready for display/persistence."""

    goal: str
    success: bool
    verdict: str
    score: float
    tasks: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    lessons: list[str] = field(default_factory=list)
    goal_id: int | None = None
    task_type: str = ""
    strategy_key: str = ""
    message: str = ""

    def to_text(self) -> str:
        lines = [f"Goal: {self.goal}"]
        if self.message:
            lines.append(f"Status: {self.message}")
        if self.verdict:
            lines.append(f"Verdict: {self.verdict.upper()} (score {self.score:.2f})")
        for task in self.tasks:
            mark = "+" if task.get("status") == "completed" else "!"
            lines.append(f"  [{mark}] {task.get('description', '')}")
            if task.get("result"):
                lines.append(f"        -> {task['result'][:160]}")
            if task.get("error"):
                lines.append(f"        ! {task['error'][:160]}")
        if self.summary:
            lines.append(f"Summary: {self.summary}")
        if self.lessons:
            lines.append("Learned:")
            for lesson in self.lessons[:3]:
                lines.append(f"  - {lesson[:180]}")
        return "\n".join(lines)


class AutonomyController:
    """Glue for adaptive, self-evaluating, goal-backed autonomy."""

    def __init__(
        self,
        router: Any | None = None,
        state_store: Any | None = None,
        goals: GoalManager | None = None,
        experiences: Any | None = None,
        selector: Any | None = None,
        evaluator: Any | None = None,
    ) -> None:
        self.router = router
        self._state = state_store
        self._goals = goals
        self._experiences = experiences
        self._selector = selector
        self._evaluator = evaluator
        self._planner_inst: Any | None = None

    # -- lazy deps ------------------------------------------------------
    def _planner(self) -> Any:
        if self._planner_inst is None:
            from planner.planner import Planner

            self._planner_inst = Planner(router=self.router)
        return self._planner_inst

    def _select(self, goal: str) -> Any:
        if self._selector is None:
            from planner.strategies import StrategySelector

            self._selector = StrategySelector()
        return self._selector.select(goal, experiences=self._experiences)

    def _eval(self) -> Any:
        if self._evaluator is None:
            from planner.evaluator import SelfEvaluator

            brain = getattr(self.router, "brain", None) if self.router is not None else None
            self._evaluator = SelfEvaluator(experiences=self._experiences, brain=brain)
        return self._evaluator

    # -- state helpers --------------------------------------------------
    def _plan_key(self, goal_id: int) -> str:
        return f"mission.plan:{goal_id}"

    def _save_plan(self, goal_id: int, plan: dict[str, Any]) -> None:
        if self._state is not None:
            self._state.set(self._plan_key(goal_id), plan)

    def _load_plan(self, goal_id: int) -> dict[str, Any] | None:
        if self._state is None:
            return None
        plan = self._state.get(self._plan_key(goal_id))
        return plan if isinstance(plan, dict) else None

    # -- recording ------------------------------------------------------
    def _record_experience(
        self,
        task_type: str,
        strategy_key: str,
        success: bool,
        strategy: str = "",
        notes: str = "",
    ) -> None:
        if self._experiences is None:
            return
        try:
            self._experiences.record_attempt(
                task_type,
                strategy_key or "llm",
                success,
                strategy=strategy,
                notes=notes,
            )
        except Exception:
            pass

    # -- full user-initiated mission ------------------------------------
    def run_auto(self, goal_text: str, source: str = "user") -> MissionReport:
        """Run a full goal as an autonomous mission (used by ``/auto``).

        Creates (or reuses) a persistent goal, adaptively plans, executes,
        self-evaluates, records what was learned, and updates the goal's
        status/progress. ``consent`` is user-initiated, matching existing
        ``/auto`` semantics.
        """
        goal_text = goal_text.strip()
        selection = self._select(goal_text)
        task_type, strategy_key = selection.task_type, selection.strategy_key

        goal = None
        if self._goals is not None:
            goal = self._goals.create_goal(goal_text, source=source)

        plan = self._planner().run_mission(
            goal_text,
            strategy_hint=selection.hint,
            consent="user",
        )
        success = bool(plan.get("success"))

        evaluation = self._eval().evaluate_mission(
            goal_text,
            plan,
            task_type=task_type,
            strategy_key=strategy_key,
        )

        # Learn from the outcome (per-task tool success + overall mission).
        for task in plan.get("tasks", []):
            self._record_experience(
                task_type,
                task.get("tool_name") or "llm",
                task.get("status") == "completed",
                strategy=selection.strategy,
                notes=task.get("description", ""),
            )
        self._record_experience(
            task_type,
            f"mission:{strategy_key}",
            success,
            strategy=selection.strategy,
            notes=evaluation.summary,
        )

        if goal is not None:
            if success:
                self._goals.complete_goal(goal.id)
            else:
                # The plan was fully executed but the mission failed or was
                # unverified. Park it for review instead of leaving it active,
                # which would otherwise loop forever in the background service.
                self._goals.set_progress(goal.id, evaluation.score)
                self._goals.block_goal(goal.id, reason="mission finished with issues; review before retrying")
            self._goals.touch(goal.id)
            goal = self._goals.get_goal(goal.id)

        # Persist the finished plan as a checkpoint.
        checkpoint = {
            "steps": [
                {"description": t.get("description", ""), "tool_name": t.get("tool_name") or "",
                 "tool_args": {}, "status": t.get("status")}
                for t in plan.get("tasks", [])
            ],
            "index": len(plan.get("tasks", [])),
            "active": False,
        }
        if goal is not None:
            self._save_plan(goal.id, checkpoint)

        report = MissionReport(
            goal=goal_text,
            success=success,
            verdict=evaluation.verdict,
            score=evaluation.score,
            tasks=plan.get("tasks", []),
            summary=evaluation.summary,
            lessons=evaluation.lessons,
            goal_id=goal.id if goal is not None else None,
            task_type=task_type,
            strategy_key=strategy_key,
        )
        self._eval().persist_lessons(evaluation)
        return report

    # -- incremental background advancement ------------------------------
    def advance_goal(self, goal_id: int, max_tasks: int = 1, consent: str = "agent") -> MissionReport:
        """Execute the next chunk of work for an existing goal.

        Resumes a checkpointed plan (or creates one), runs up to ``max_tasks``
        steps with the given consent, records outcomes, and advances the goal's
        progress. When the final step completes, the goal is self-evaluated and
        closed (or parked) accordingly.
        """
        goal = self._goals.get_goal(goal_id) if self._goals is not None else None
        if goal is None:
            return MissionReport(goal=f"#{goal_id}", success=False, verdict="failed", score=0.0,
                                 message="goal not found")
        if goal.status != GoalStatus.ACTIVE:
            return MissionReport(goal=goal.title, success=False, verdict="idle", score=goal.progress,
                                 message=f"goal is {goal.status}")

        selection = self._select(goal.title)
        task_type, strategy_key = selection.task_type, selection.strategy_key

        plan = self._load_plan(goal_id)
        if plan is None:
            steps = self._planner().create_plan(goal.title, strategy_hint=selection.hint)
            plan = {
                "steps": [
                    {"description": t.description, "tool_name": t.tool_name, "tool_args": t.tool_args}
                    for t in steps
                ],
                "index": 0,
                "active": True,
            }
            self._save_plan(goal_id, plan)

        steps = plan.get("steps", [])
        index = int(plan.get("index", 0))
        if index >= len(steps):
            plan["active"] = False
            self._save_plan(goal_id, plan)
            return self._finalize_goal(goal_id, goal.title, selection, plan)

        planner = self._planner()
        planner.create_plan_from_steps(goal.title, steps)

        end = min(index + max(max_tasks, 1), len(steps))
        blocked = False
        for i in range(index, end):
            task = planner.execute(f"task_{i}", consent=consent)
            ok = task.status.value == "completed"
            notes = task.description or ""
            if task.status.value == "failed" and task.error:
                notes = f"{notes} :: {task.error}"
            self._record_experience(task_type, task.tool_name or "llm", ok, strategy=selection.strategy, notes=notes)
            if task.status.value == "failed" and "requires user confirmation" in (task.error or ""):
                blocked = True
            plan["steps"][i]["status"] = task.status.value
            plan["steps"][i]["result"] = task.result

        plan["index"] = end
        self._save_plan(goal_id, plan)

        if blocked:
            self._goals.block_goal(goal_id, reason="requires user confirmation for a step")
            return MissionReport(
                goal=goal.title, success=False, verdict="blocked", score=goal.progress,
                goal_id=goal_id, task_type=task_type, strategy_key=strategy_key,
                message="paused for user confirmation; run /goals resume <id> after approving",
            )

        if end >= len(steps):
            plan["active"] = False
            self._save_plan(goal_id, plan)
            return self._finalize_goal(goal_id, goal.title, selection, plan)

        progress = end / float(len(steps))
        self._goals.set_progress(goal_id, progress)
        self._goals.touch(goal_id)
        return MissionReport(
            goal=goal.title, success=True, verdict="in_progress", score=progress,
            tasks=[{"id": f"task_{i}", "description": steps[i].get("description", ""),
                    "status": steps[i].get("status", "pending"), "result": steps[i].get("result", ""),
                    "error": ""} for i in range(index, end)],
            goal_id=goal_id, task_type=task_type, strategy_key=strategy_key,
            message=f"advanced {end - index}/{len(steps)} steps",
        )

    def _finalize_goal(self, goal_id: int, title: str, selection: Any, plan: dict[str, Any]) -> MissionReport:
        """Evaluate a completed plan and close or park the goal accordingly."""
        tasks = [{"id": f"task_{i}", "description": s.get("description", ""), "status": s.get("status", "pending"),
                  "result": s.get("result", ""), "error": ""} for i, s in enumerate(plan.get("steps", []))]
        plan_result = {"goal": title, "success": all(t["status"] == "completed" for t in tasks), "tasks": tasks}
        evaluation = self._eval().evaluate_mission(
            title,
            plan_result,
            task_type=selection.task_type,
            strategy_key=selection.strategy_key,
        )
        for task in tasks:
            self._record_experience(selection.task_type, task.get("tool_name") or "llm",
                                    task.get("status") == "completed", notes=task.get("description", ""))
        self._record_experience(selection.task_type, f"mission:{selection.strategy_key}",
                                plan_result["success"], notes=evaluation.summary)

        if plan_result["success"]:
            self._goals.complete_goal(goal_id)
        else:
            self._goals.set_progress(goal_id, evaluation.score)
            self._goals.block_goal(goal_id, reason="mission finished with issues; review before retrying")
        self._goals.touch(goal_id)
        self._eval().persist_lessons(evaluation)

        return MissionReport(
            goal=title, success=plan_result["success"], verdict=evaluation.verdict,
            score=evaluation.score, tasks=tasks, summary=evaluation.summary,
            lessons=evaluation.lessons, goal_id=goal_id,
            task_type=selection.task_type, strategy_key=selection.strategy_key,
        )

    # -- convenience ----------------------------------------------------
    def pick_and_advance(self, max_tasks: int = 1, consent: str = "agent") -> MissionReport | None:
        """Advance whichever active goal is next (used by the goal service)."""
        if self._goals is None:
            return None
        goal = self._goals.pick_next()
        if goal is None:
            return None
        return self.advance_goal(goal.id, max_tasks=max_tasks, consent=consent)