from pathlib import Path

from core.router import Router
from memory.experience import ExperienceStore
from memory.facts import FactStore
from memory.goals import GoalManager, GoalStatus
from memory.state import AgentStateStore
from tools.registry import ToolRegistry


class _FakeBrain:
    def ask(self, prompt: str) -> str:
        if "Break the user's goal" in prompt:
            return '[{"description": "do a thing", "tool_name": null, "tool_args": {}}]'
        return "Good approach; keep verifying each step."


def _router(tmp_path: Path) -> Router:
    memory = FactStore(str(tmp_path / "atlas_memory.db"))
    goals = GoalManager(str(tmp_path / "atlas_memory.db"), memory=memory)
    experiences = ExperienceStore(str(tmp_path / "atlas_memory.db"), memory=memory)
    state = AgentStateStore(str(tmp_path / "atlas_memory.db"))
    return Router(
        brain=_FakeBrain(),
        memory=memory,
        registry=ToolRegistry(),
        state_store=state,
        goals=goals,
        experiences=experiences,
    )


def test_goals_command_empty(tmp_path: Path) -> None:
    out = _router(tmp_path).route("/goals")
    assert "No goals yet" in out


def test_goals_add_and_list(tmp_path: Path) -> None:
    router = _router(tmp_path)
    added = router.route("/goals add organize the desktop")
    assert "created" in added
    listed = router.route("/goals")
    assert "organize the desktop" in listed
    assert "[active" in listed


def test_goals_done(tmp_path: Path) -> None:
    router = _router(tmp_path)
    router.route("/goals add tidy up")
    done = router.route("/goals done 1")
    assert "done" in done
    assert router._goals.get_goal(1).status == GoalStatus.DONE  # type: ignore[union-attr]


def test_goals_priority(tmp_path: Path) -> None:
    router = _router(tmp_path)
    router.route("/goals add urgent thing")
    out = router.route("/goals priority 1 8")
    assert "8" in out
    assert router._goals.get_goal(1).priority == 8.0  # type: ignore[union-attr]


def test_goals_next_advances(tmp_path: Path) -> None:
    router = _router(tmp_path)
    router.route("/goals add run a goal")
    out = router.route("/goals next")
    assert "Verdict" in out
    assert router._goals.get_goal(1).status == GoalStatus.DONE  # type: ignore[union-attr]


def test_auto_is_persistent_goal_and_self_evaluated(tmp_path: Path) -> None:
    router = _router(tmp_path)
    out = router.route("/auto finish the monthly summary")
    assert "Goal:" in out
    assert "Verdict: SUCCESS" in out
    goals = router._goals.active_goals()
    done = router._goals.list_goals(GoalStatus.DONE)
    assert len(goals) == 0
    assert len(done) == 1
    # Learning happened.
    assert router._experiences.count() >= 1


def test_lessons_and_state_commands(tmp_path: Path) -> None:
    router = _router(tmp_path)
    router.route("/auto research something")
    lessons = router.route("/lessons")
    assert "Learned strategies" in lessons
    state = router.route("/state")
    assert "Persistent agent state" in state