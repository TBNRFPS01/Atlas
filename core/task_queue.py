from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass(slots=True)
class Task:
    id: str
    name: str
    fn: Callable[[], Any]
    status: str = "queued"
    result: Any = None
    error: str = ""


class TaskQueue:
    """Small bounded worker queue for resumable ATLAS background work."""

    def __init__(self, workers: int = 1, maxsize: int = 32) -> None:
        if workers < 1 or maxsize < 1:
            raise ValueError("workers and maxsize must be positive")
        self._tasks: dict[str, Task] = {}
        self._queue: queue.Queue[Task | None] = queue.Queue(maxsize=maxsize)
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []
        for index in range(workers):
            thread = threading.Thread(target=self._worker, name=f"atlas-task-{index}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def submit(self, name: str, fn: Callable[[], Any]) -> str:
        task = Task(uuid.uuid4().hex, name, fn)
        with self._lock:
            self._tasks[task.id] = task
        try:
            self._queue.put_nowait(task)
        except queue.Full:
            with self._lock:
                self._tasks.pop(task.id, None)
            raise RuntimeError("ATLAS task queue is full") from None
        return task.id

    def status(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def snapshot(self) -> list[Task]:
        with self._lock:
            return list(self._tasks.values())

    def _worker(self) -> None:
        while True:
            task = self._queue.get()
            if task is None:
                self._queue.task_done()
                return
            with self._lock:
                task.status = "running"
            try:
                task.result = task.fn()
                task.status = "completed"
            except Exception as exc:
                task.error = str(exc)
                task.status = "failed"
            finally:
                self._queue.task_done()
