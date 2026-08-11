"""Planner for breaking goals into executable tasks."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from core.router import Router
from planner.task import Task, TaskStatus


class Planner:
    """Decompose goals into tasks and execute them sequentially."""

    SYSTEM_DECOMPOSE = (
        "You are ATLAS's task planner. Break the user's goal into a JSON array of steps. "
        "Each step must have: description (str), tool_name (str or null), tool_args (object). "
        "Available tools: file (read/write/append/delete/list), system (info), web (search/fetch), screenshot (capture). "
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
        prompt = f"Goal: {goal}\n\nReturn JSON array of steps."
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
        if "open" in g and "close" not in g:
            app = goal.split("open", 1)[1].strip() if "open" in goal else ""
            return [{"description": f"Open application: {app}", "tool_name": None, "tool_args": {}}]
        if "type" in g:
            text = goal.split("type", 1)[1].strip() if "type" in goal else ""
            return [{"description": f"Type text: {text}", "tool_name": None, "tool_args": {}}]
        if "click" in g:
            return [{"description": "Click at current position", "tool_name": None, "tool_args": {}}]
        if "screenshot" in g:
            return [{"description": "Take a screenshot", "tool_name": "screenshot", "tool_args": {}}]
        if "search" in g or "look up" in g or "find" in g:
            return [{"description": goal, "tool_name": "web", "tool_args": {"action": "search", "query": goal}}]
        return [{"description": f"Process goal: {goal}", "tool_name": None, "tool_args": {}}]

    def execute(self, task_id: str) -> Task:
        """Execute a single task and return the result."""
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"Unknown task: {task_id}")

        task.start()

        try:
            if task.tool_name:
                result = self._execute_tool(task)
            else:
                result = self.router.route(task.description)

            task.complete(result)
        except Exception as exc:
            if task.should_retry():
                task.increment_retry()
                task.fail(str(exc))
            else:
                task.fail(str(exc))

        return task

    def _execute_tool(self, task: Task) -> str:
        """Execute a tool by name with the task's arguments."""
        registry = getattr(self, "_registry", None)
        if registry is None:
            from tools.registry import ToolRegistry

            registry = ToolRegistry()
            registry.discover()
            self._registry = registry

        tool = registry.get(task.tool_name)
        if tool is None:
            raise ValueError(f"Tool not found: {task.tool_name}")

        return tool.execute(**task.tool_args)

    def run_plan(self, goal: str) -> dict[str, Any]:
        """Create and execute a plan from a goal description."""
        tasks = self.create_plan(goal)
        results = []
        failed = False

        for task in tasks:
            result = self.execute(task.id)
            results.append(
                {
                    "id": task.id,
                    "description": task.description,
                    "status": task.status.value,
                    "result": task.result,
                    "error": task.error,
                }
            )
            if task.status == TaskStatus.FAILED:
                failed = True
                break

        return {
            "goal": goal,
            "success": not failed,
            "tasks": results,
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