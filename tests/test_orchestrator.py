from __future__ import annotations

from pathlib import Path

from core.orchestrator import Orchestrator
from services.task_queue import TaskQueue


class Report:
    success = True
    goal_id = 7
    score = 0.9

    def to_text(self) -> str:
        return "mission complete"


class Autonomy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def run_auto(self, goal: str, source: str = "user") -> Report:
        self.calls.append((goal, source))
        return Report()


class Router:
    def __init__(self) -> None:
        self._autonomy = Autonomy()


def test_orchestrator_runs_existing_autonomy(tmp_path: Path) -> None:
    router = Router()
    queue = TaskQueue(tmp_path / "queue.json")
    result = Orchestrator(router, queue=queue).run("test mission")
    assert result.success
    assert result.verified
    assert result.goal_id == 7
    assert router._autonomy.calls == [("test mission", "user")]


def test_orchestrator_queue_runs_task(tmp_path: Path) -> None:
    router = Router()
    queue = TaskQueue(tmp_path / "queue.json")
    orchestrator = Orchestrator(router, queue=queue)
    orchestrator.enqueue("queued mission", priority=10)
    result = orchestrator.run_next()
    assert result is not None and result.success
    assert queue.next() is None
