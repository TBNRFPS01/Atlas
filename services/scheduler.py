"""Persistent, bounded scheduler for background ATLAS work."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass(slots=True)
class ScheduledJob:
    id: str
    name: str
    interval_seconds: float
    payload: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    next_run: float = field(default_factory=time.time)
    last_run: float | None = None
    failures: int = 0


class JobScheduler:
    """Small persistent scheduler that never executes jobs concurrently."""

    def __init__(self, state_path: str | Path | None = None) -> None:
        self.state_path = Path(state_path or (Path.home() / ".atlas" / "scheduler.json"))
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, ScheduledJob] = {}
        self.load()

    def add(self, name: str, interval_seconds: float, payload: dict[str, Any] | None = None) -> ScheduledJob:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        job = ScheduledJob(str(uuid.uuid4()), name, interval_seconds, payload or {})
        self.jobs[job.id] = job
        self.save()
        return job

    def remove(self, job_id: str) -> bool:
        if job_id not in self.jobs:
            return False
        del self.jobs[job_id]
        self.save()
        return True

    def due(self, now: float | None = None) -> list[ScheduledJob]:
        current = time.time() if now is None else now
        return [job for job in self.jobs.values() if job.enabled and job.next_run <= current]

    def run_due(self, handler: Callable[[ScheduledJob], Any], now: float | None = None, max_jobs: int = 4) -> list[Any]:
        results: list[Any] = []
        for job in self.due(now)[:max(1, max_jobs)]:
            try:
                result = handler(job)
                job.failures = 0
                results.append(result)
            except Exception:
                job.failures += 1
                results.append(None)
            finally:
                job.last_run = time.time()
                job.next_run = job.last_run + job.interval_seconds
        self.save()
        return results

    def save(self) -> None:
        self.state_path.write_text(
            json.dumps([asdict(job) for job in self.jobs.values()], indent=2),
            encoding="utf-8",
        )

    def load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            rows = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.jobs = {row["id"]: ScheduledJob(**row) for row in rows}
        except (OSError, ValueError, TypeError, KeyError):
            self.jobs = {}
