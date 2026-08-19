from __future__ import annotations

import json
from pathlib import Path

from core.skill_registry import SkillRegistry
from services.scheduler import JobScheduler


def test_scheduler_persists_and_runs_due_job(tmp_path: Path) -> None:
    scheduler = JobScheduler(tmp_path / "scheduler.json")
    job = scheduler.add("briefing", 60, {"goal": "today"})
    job.next_run = 0
    called = []
    results = scheduler.run_due(lambda item: called.append(item.name) or "ok", now=1)
    assert results == ["ok"]
    assert called == ["briefing"]

    restored = JobScheduler(tmp_path / "scheduler.json")
    assert restored.jobs[job.id].last_run is not None


def test_skill_registry_discovers_manifest(tmp_path: Path) -> None:
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    (skill_dir / "skill.py").write_text("def run(): return 'ok'", encoding="utf-8")
    (skill_dir / "skill.json").write_text(
        json.dumps({
            "name": "demo",
            "version": "1.2.0",
            "description": "demo skill",
            "capabilities": ["demo"],
        }),
        encoding="utf-8",
    )
    registry = SkillRegistry(tmp_path)
    skills = registry.discover()
    assert skills[0].name == "demo"
    assert skills[0].version == "1.2.0"
    assert registry.capability_index()["demo"] == ["demo"]
