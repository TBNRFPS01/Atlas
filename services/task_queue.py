"""Small persistent priority queue for bounded ATLAS background work."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(order=True, slots=True)
class QueuedTask:
    priority: int
    created_at: float
    id: str = field(compare=False)
    goal: str = field(compare=False)
    status: str = field(default="pending", compare=False)
    attempts: int = field(default=0, compare=False)


class TaskQueue:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or (Path.home() / ".atlas" / "task_queue.json"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tasks: list[QueuedTask] = []
        self.load()

    def add(self, goal: str, priority: int = 0) -> QueuedTask:
        task = QueuedTask(-priority, time.time(), str(uuid.uuid4()), goal)
        self.tasks.append(task)
        self.save()
        return task

    def next(self) -> QueuedTask | None:
        pending = [task for task in self.tasks if task.status == "pending"]
        return sorted(pending)[0] if pending else None

    def mark(self, task_id: str, status: str) -> bool:
        for task in self.tasks:
            if task.id == task_id:
                task.status = status
                if status == "running":
                    task.attempts += 1
                self.save()
                return True
        return False

    def save(self) -> None:
        self.path.write_text(json.dumps([asdict(task) for task in self.tasks], indent=2), encoding="utf-8")

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            self.tasks = [QueuedTask(**item) for item in json.loads(self.path.read_text(encoding="utf-8"))]
        except (OSError, ValueError, TypeError):
            self.tasks = []
