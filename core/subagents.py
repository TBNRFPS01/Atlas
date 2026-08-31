"""Small specialist-agent coordinator for ATLAS.

Inspired by lead/worker patterns in OpenAgent and OpenClaw. This module only
coordinates jobs; the caller supplies the actual LLM/tool execution function.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from typing import Any, Callable
import uuid


@dataclass(slots=True)
class AgentJob:
    id: str
    role: str
    task: str
    status: str = "queued"
    result: Any = None
    error: str | None = None


class SpecialistPool:
    """Bounded pool for independent specialist tasks."""

    def __init__(self, max_workers: int = 3) -> None:
        self.max_workers = max(1, min(max_workers, 8))
        self.jobs: dict[str, AgentJob] = {}
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="atlas-agent")

    def submit(self, role: str, task: str, worker: Callable[[str, str], Any]) -> AgentJob:
        job = AgentJob(id=uuid.uuid4().hex[:10], role=role, task=task)
        self.jobs[job.id] = job

        def run() -> None:
            job.status = "running"
            try:
                job.result = worker(role, task)
                job.status = "completed"
            except Exception as exc:
                job.error = str(exc)
                job.status = "failed"

        self._executor.submit(run)
        return job

    def submit_many(self, tasks: list[tuple[str, str]], worker: Callable[[str, str], Any]) -> list[AgentJob]:
        return [self.submit(role, task, worker) for role, task in tasks]

    def status(self, job_id: str) -> AgentJob | None:
        return self.jobs.get(job_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
