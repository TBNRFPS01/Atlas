"""Planner for breaking goals into executable tasks."""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from typing import Any

from core.router import Router
from planner.task import Task, TaskStatus


class Planner:
    """Decompose goals into tasks and execute them sequentially."""

    SYSTEM_DECOMPOSE = (
        "You are ATLAS's task planner. Break the user's goal into a JSON array of steps. "
        "Each step must have: description (str), tool_name (str or null), tool_args (object). "
        "Available tools: file (read/write/append/delete/list), system (info), web (search/fetch), "
        "screenshot (capture), automation (keyboard_type/click/windows_launch/process/context), "
        "media (play), minecraft (status). "
        "Use automation for anything on the computer itself. "
        "If no tool fits, use null. Output ONLY valid JSON array. No markdown, no explanation."
    )

    def __init__(self, router: Router | None = None) -> None:
        self.router = router or Router()
        self._tasks: dict[str, Task] = {}
        self._task_order: list[str] = []

    def create_plan(self, goal: str) -> list[Task]:
        """Break a goal into a sequence of executable tasks."""
        self._tasks.clear()
        self._task_order.clear()

        steps = self._decompose(goal)
        for i, step in enumerate(steps):
            task = Task(
                id=f"task_{i}",
                description=step.get("description", ""),
                tool_name=step.get("tool_name") or "",
                tool_args=step.get("tool_args", {}),
            )
            self._tasks[task.id] = task
            self._task_order.append(task.id)

        return [self._tasks[tid] for tid in self._task_order]

    def _decompose(self, goal: str) -> list[dict[str, Any]]:
        """Use LLM to convert a goal into structured steps with tool assignments."""
        prompt = f"{self.SYSTEM_DECOMPOSE}\n\nGoal: {goal}\n\nReturn the JSON array only."
        try:
            response = self.router.brain.ask(prompt)
            data = json.loads(response)
            if isinstance(data, list):
                return data
        except Exception:
            pass

        # Fallback: simple heuristic
        return self._fallback_decompose(goal)

    def _fallback_decompose(self, goal: str) -> list[dict[str, Any]]:
        """Keyword-based fallback if LLM fails."""
        g = goal.lower()

        if "open" in g and "close" not in g and "window" not in g and "file" not in g:
            app = goal.split("open", 1)[1].strip().strip(".,;!?")
            return [{"description": f"Open application: {app}", "tool_name": "automation", "tool_args": {"action": "windows_launch", "path": app}}]

        if "close window" in g and "the window" in g:
            title = goal.split("close", 1)[1].strip().strip(".,;!?")
            return [{"description": f"Close window: {title}", "tool_name": "automation", "tool_args": {"action": "windows_close", "title": title}}]

        if "kill" in g or ("stop" in g and "process" in g):
            name = (goal.split("kill", 1)[1] if "kill" in g else goal.split("stop", 1)[1]).strip().strip(".,;!?")
            return [{"description": f"Terminate process: {name}", "tool_name": "automation", "tool_args": {"action": "process_kill", "name": name}}]

        if "type" in g:
            text = goal.split("type", 1)[1].strip().strip(".,;!?\"'")
            return [{"description": f"Type text: {text}", "tool_name": "automation", "tool_args": {"action": "keyboard_type", "text": text}}]

        if "click" in g:
            coords = re.findall(r"\d+", goal)
            args: dict[str, Any] = {"action": "mouse_click"}
            if len(coords) >= 2:
                args["x"] = int(coords[0])
                args["y"] = int(coords[1])
            return [{"description": "Click mouse", "tool_name": "automation", "tool_args": args}]

        if "press" in g:
            keys = goal.split("press", 1)[1].strip().split(",")
            keys = [k.strip().lower() for k in keys if k.strip()]
            if len(keys) > 1:
                return [{"description": f"Press hotkey: {keys}", "tool_name": "automation", "tool_args": {"action": "hotkey", "keys": ",".join(keys)}}]
            key = keys[0] if keys else ""
            return [{"description": f"Press key: {key}", "tool_name": "automation", "tool_args": {"action": "keyboard_press", "key": key}}]

        if "move mouse" in g or ("move" in g and "to" in g):
            coords = re.findall(r"\d+", goal)
            if len(coords) >= 2:
                return [{"description": "Move mouse", "tool_name": "automation", "tool_args": {"action": "mouse_move", "x": int(coords[0]), "y": int(coords[1])}}]

        if "copy" in g and "clipboard" in g:
            text = goal.split("copy", 1)[1].split("clipboard", 1)[0].strip().strip(".,;!?\"'")
            return [{"description": f"Copy to clipboard: {text}", "tool_name": "automation", "tool_args": {"action": "clipboard_set", "text": text}}]

        if "activate" in g or "focus" in g or ("switch to" in g and "window" in g):
            title = (goal.split("activate", 1)[1] if "activate" in g else goal.split("focus", 1)[1] if "focus" in g else goal.split("switch to", 1)[1]).strip().strip(".,;!?")
            return [{"description": f"Activate window: {title}", "tool_name": "automation", "tool_args": {"action": "windows_activate", "title": title}}]

        if "screenshot" in g:
            return [{"description": "Take a screenshot", "tool_name": "screenshot", "tool_args": {}}]
        if "search" in g or "look up" in g or "find" in g:
            return [{"description": goal, "tool_name": "web", "tool_args": {"action": "search", "query": goal}}]
        return [{"description": f"Process goal: {goal}", "tool_name": None, "tool_args": {}}]

    def execute(self, task_id: str) -> Task:
        """Execute a single task, retrying on transient failures."""
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"Unknown task: {task_id}")

        task.start()

        last_error = "Unknown error"
        while True:
            try:
                if task.tool_name:
                    result = self._execute_tool(task)
                else:
                    result = self.router.route(task.description)

                task.complete(result)
                return task
            except Exception as exc:
                last_error = str(exc)
                if task.should_retry():
                    task.increment_retry()
                    time.sleep(1)
                    continue
                task.fail(last_error)
                return task

    def _execute_tool(self, task: Task) -> str:
        """Execute a tool by name with the task's arguments.

        In autonomous mode destructive/permission-gated actions are allowed
        only if no explicit deny rule exists; an autonomous run is treated as
        pre-confirmed so a destructive step still proceeds. ``deny`` rules,
        however, are always honoured.
        """
        registry = getattr(self, "_registry", None)
        if registry is None:
            from tools.registry import ToolRegistry

            registry = ToolRegistry()
            registry.discover()
            self._registry = registry

        tool = registry.get(task.tool_name)
        if tool is None:
            raise ValueError(f"Tool not found: {task.tool_name}")

        decision = self._permission_decision(task.tool_name, task.tool_args)
        if decision == "deny":
            raise PermissionError(f"Permission denied for {task.tool_name} by policy")

        return tool.execute(**task.tool_args)

    def _permission_decision(self, tool_name: str, tool_args: dict) -> str:
        """Resolve the permission outcome for a planner tool step.

        Returns ``"deny"``, ``"ask"`` or ``"allow"``. Hard safety boundaries
        always win, and autonomous execution is treated as confirmed so only
        explicit ``deny`` rules or safety violations stop a step.
        """
        router = getattr(self, "router", None)
        if router is not None:
            safety = getattr(router, "_safety", None)
            if safety is not None:
                action = str(tool_args.get("action", "") or "")
                path = str(tool_args.get("path") or tool_args.get("title") or "")
                if not safety.is_safe(tool_name, action, path):
                    return "deny"

        manager = getattr(router, "_permissions", None) if router is not None else None
        if manager is None:
            return "allow"

        action = str(tool_args.get("action", "") or "")
        # Autonomous runs act without prompting: treat as confirmed.
        return manager.decide(tool_name, action, confirmed=True)

    def _verify_task(self, task: Task) -> bool:
        """Lightweight success check for a completed task.

        Returns ``False`` when the task is not completed or the recorded result
        contains obvious failure markers. Automation outcomes are verified only
        by their textual status (a real state check would require tool-specific
        introspection), which is a reasonable heuristic here.
        """
        if task.status != TaskStatus.COMPLETED:
            return False
        result = (task.result or "").lower()
        failure_markers = (
            "failed", "error", "not found", "unavailable", "denied",
            "could not", "cannot", "refused", "no media", "not loaded",
        )
        return not any(marker in result for marker in failure_markers)

    def _recover_task(self, task: Task) -> Task:
        """Attempt a single LLM-guided recovery for a failed/verified-bad task.

        The planner asks the brain to propose one alternative step that achieves
        the same goal fragment, then re-executes it once. If the LLM is not
        available or the suggestion is unusable, the original task is returned
        unchanged so the plan can still report failure.
        """
        brain = getattr(self.router, "brain", None)
        if brain is None or not hasattr(brain, "ask"):
            return task

        recovery_prompt = (
            "A task step failed and needs a different approach. "
            f"Original step: {task.description}\n"
            f"Result/error: {task.error or task.result}\n"
            "Propose ONE replacement step as a JSON object with keys: "
            "description, tool_name, tool_args. Use only these tools: "
            "file, system, web, screenshot, automation, media, minecraft. "
            "Output ONLY the JSON object, no markdown."
        )
        try:
            response = brain.ask(recovery_prompt)
            import json

            data = json.loads(response)
            if isinstance(data, dict) and data.get("tool_name"):
                task.tool_name = str(data.get("tool_name"))
                task.tool_args = data.get("tool_args", {}) or {}
                task.description = str(data.get("description", task.description))
                task.status = TaskStatus.PENDING
                task.error = ""
                task.result = ""
                return self.execute(task.id)
        except Exception:
            pass
        return task

    def run_plan(self, goal: str) -> dict[str, Any]:
        """Create and execute a plan from a goal description.

        After each step, the plan is verified; a single LLM-guided recovery is
        attempted for any step that fails or fails verification before the plan
        reports overall failure.
        """
        tasks = self.create_plan(goal)
        results = []
        failed = False

        for task in tasks:
            result = self.execute(task.id)
            if not self._verify_task(task):
                recovered = self._recover_task(task)
                if self._verify_task(recovered):
                    task = recovered
                else:
                    failed = True
            if task.status == TaskStatus.FAILED:
                failed = True
            results.append(
                {
                    "id": task.id,
                    "description": task.description,
                    "status": task.status.value,
                    "result": task.result,
                    "error": task.error,
                }
            )
            if failed:
                break

        return {
            "goal": goal,
            "success": not failed,
            "tasks": results,
        }

    def run_mission(self, goal: str) -> dict[str, Any]:
        """Run a goal as a full mission and produce a finish report.

        Extends :meth:`run_plan` with a higher-level summary: how many steps
        completed, how many were recovered after a failure, and whether the
        overall mission finished successfully. This is the top of the agent
        loop: plan -> execute -> verify -> recover -> finish.
        """
        plan = self.run_plan(goal)
        tasks = plan.get("tasks", [])
        completed = sum(1 for t in tasks if t["status"] == "completed")
        failed = sum(1 for t in tasks if t["status"] == "failed")
        recovered = sum(
            1
            for i, t in enumerate(tasks)
            if t["status"] == "completed" and i > 0 and tasks[i - 1]["status"] == "failed"
        )

        if plan["success"] and tasks:
            verdict = "MISSION COMPLETE"
        elif completed > 0:
            verdict = "MISSION PARTIAL"
        else:
            verdict = "MISSION FAILED"

        summary_lines = [
            f"Goal: {goal}",
            f"Verdict: {verdict}",
            f"Steps: {completed}/{len(tasks)} completed, {failed} failed, {recovered} recovered.",
        ]
        for task in tasks:
            status_mark = "+" if task["status"] == "completed" else "!"
            summary_lines.append(f"  [{status_mark}] {task['description']}")
            if task["error"]:
                summary_lines.append(f"        error: {task['error'][:120]}")

        return {
            "goal": goal,
            "success": plan["success"],
            "verdict": verdict,
            "completed": completed,
            "failed": failed,
            "recovered": recovered,
            "tasks": tasks,
            "summary": "\n".join(summary_lines),
        }

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending or running task."""
        task = self._tasks.get(task_id)
        if task is None:
            return False

        if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
            task.cancel()
            return True
        return False

    def get_task(self, task_id: str) -> Task | None:
        """Retrieve a task by its ID."""
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        """Return all tasks in the plan."""
        return [self._tasks[tid] for tid in self._task_order if tid in self._tasks]

    def clear(self) -> None:
        """Clear all tasks from the current plan."""
        self._tasks.clear()
        self._task_order.clear()