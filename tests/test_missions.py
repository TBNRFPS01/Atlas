from __future__ import annotations

from pathlib import Path

import pytest

from memory.missions import MissionStore


def store(tmp_path: Path) -> MissionStore:
    return MissionStore(str(tmp_path / "atlas_memory.db"))


def test_create_persists_goal_and_context(tmp_path: Path) -> None:
    missions = store(tmp_path)
    mission = missions.create("finish server setup", priority=5, context={"source": "user"})

    loaded = missions.get(mission.id)

    assert loaded is not None
    assert loaded.goal == "finish server setup"
    assert loaded.status == "pending"
    assert loaded.priority == 5
    assert loaded.context == {"source": "user"}


def test_checkpoint_merges_context_and_tracks_step(tmp_path: Path) -> None:
    missions = store(tmp_path)
    mission = missions.create("build project")

    updated = missions.checkpoint(
        mission.id,
        status="running",
        current_step="compile",
        checkpoint="dependencies installed",
        context={"attempt": 1},
    )

    assert updated is not None
    assert updated.status == "running"
    assert updated.current_step == "compile"
    assert updated.checkpoint == "dependencies installed"
    assert updated.context == {"attempt": 1}


def test_resume_candidates_survive_new_store_instance(tmp_path: Path) -> None:
    missions = store(tmp_path)
    mission = missions.create("resume after restart")
    missions.checkpoint(mission.id, status="paused", checkpoint="step 2")

    restarted = store(tmp_path)
    candidates = restarted.resume_candidates()

    assert [item.id for item in candidates] == [mission.id]
    assert candidates[0].checkpoint == "step 2"


def test_complete_clears_failure_and_stores_result(tmp_path: Path) -> None:
    missions = store(tmp_path)
    mission = missions.create("complete task")
    missions.fail(mission.id, {"error": "temporary"})

    completed = missions.complete(mission.id, {"verified": True})

    assert completed is not None
    assert completed.status == "completed"
    assert completed.result == {"verified": True}
    assert completed.failure is None


def test_fail_stores_structured_failure(tmp_path: Path) -> None:
    missions = store(tmp_path)
    mission = missions.create("failing task")

    failed = missions.fail(mission.id, {"reason": "permission denied", "attempts": 2})

    assert failed is not None
    assert failed.status == "failed"
    assert failed.failure == {"reason": "permission denied", "attempts": 2}
    assert failed.result is None


def test_empty_goal_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        store(tmp_path).create("   ")


def test_invalid_status_is_rejected(tmp_path: Path) -> None:
    missions = store(tmp_path)
    mission = missions.create("validate status")

    with pytest.raises(ValueError):
        missions.checkpoint(mission.id, status="not-a-status")
