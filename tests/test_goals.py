from pathlib import Path

from memory.goals import GoalManager, GoalStatus


def _manager(path: Path) -> GoalManager:
    return GoalManager(str(path / "atlas_memory.db"))


def test_create_and_get_goal(tmp_path: Path) -> None:
    gm = _manager(tmp_path)
    goal = gm.create_goal("Write a monthly report", priority=2.0)
    assert goal.id == 1
    assert goal.title == "Write a monthly report"
    assert goal.status == GoalStatus.ACTIVE
    assert goal.priority == 2.0
    assert gm.get_goal(goal.id) is not None


def test_create_dedupes_open_goal(tmp_path: Path) -> None:
    gm = _manager(tmp_path)
    first = gm.create_goal("Organize the desktop")
    second = gm.create_goal("organize the desktop")
    assert first.id == second.id
    assert gm.active_goals().__len__() == 1


def test_goal_lifecycle(tmp_path: Path) -> None:
    gm = _manager(tmp_path)
    goal = gm.create_goal("Plan the trip")
    gm.pause_goal(goal.id)
    assert gm.get_goal(goal.id).status == GoalStatus.PAUSED  # type: ignore[union-attr]
    gm.resume_goal(goal.id)
    assert gm.get_goal(goal.id).status == GoalStatus.ACTIVE  # type: ignore[union-attr]
    gm.complete_goal(goal.id)
    assert gm.get_goal(goal.id).status == GoalStatus.DONE  # type: ignore[union-attr]
    assert gm.get_goal(goal.id).progress == 1.0  # type: ignore[union-attr]


def test_progress_and_priority_updates(tmp_path: Path) -> None:
    gm = _manager(tmp_path)
    goal = gm.create_goal("Study")
    gm.set_progress(goal.id, 0.5)
    gm.update_goal(goal.id, priority=5.0)
    updated = gm.get_goal(goal.id)
    assert updated is not None
    assert updated.progress == 0.5
    assert updated.priority == 5.0
    # progress is clamped to [0, 1]
    gm.set_progress(goal.id, 99.0)
    assert gm.get_goal(goal.id).progress == 1.0  # type: ignore[union-attr]


def test_pick_next_prioritizes_by_priority_then_starvation(tmp_path: Path) -> None:
    gm = _manager(tmp_path)
    low = gm.create_goal("low", priority=1.0)
    high = gm.create_goal("high", priority=9.0)
    assert gm.pick_next().id == high.id  # type: ignore[union-attr]

    # After advancing the high one, it should not be re-selected forever
    # when a lower one has never been touched.
    gm.complete_goal(high.id)
    assert gm.pick_next().id == low.id  # type: ignore[union-attr]


def test_pick_next_round_robins_equal_priority(tmp_path: Path) -> None:
    gm = _manager(tmp_path)
    a = gm.create_goal("a", priority=1.0)
    b = gm.create_goal("b", priority=1.0)
    first = gm.pick_next()
    assert first is not None
    gm.touch(first.id)
    second = gm.pick_next()
    assert second is not None
    assert second.id != first.id
    assert second.id in (a.id, b.id)


def test_block_and_abandon(tmp_path: Path) -> None:
    gm = _manager(tmp_path)
    goal = gm.create_goal("Needs attention")
    gm.block_goal(goal.id, reason="requires confirmation")
    blocked = gm.get_goal(goal.id)
    assert blocked is not None
    assert blocked.status == GoalStatus.BLOCKED
    assert blocked.meta.get("block_reason") == "requires confirmation"
    gm.abandon_goal(goal.id)
    assert gm.get_goal(goal.id).status == GoalStatus.ABANDONED  # type: ignore[union-attr]
    assert gm.pick_next() is None


def test_list_filters_by_status(tmp_path: Path) -> None:
    gm = _manager(tmp_path)
    gm.create_goal("one")
    gm.create_goal("two")
    assert len(gm.list_goals(GoalStatus.ACTIVE)) == 2
    assert len(gm.list_goals(GoalStatus.OPEN)) == 2
    assert len(gm.list_goals({GoalStatus.ACTIVE, GoalStatus.PAUSED})) == 2
    assert len(gm.list_goals(GoalStatus.DONE)) == 0
