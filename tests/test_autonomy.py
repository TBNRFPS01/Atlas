from pathlib import Path
from types import SimpleNamespace

from core.autonomy import AutonomyController
from core.permissions import PermissionManager
from core.safety import HardSafety
from memory.experience import ExperienceStore
from memory.facts import FactStore
from memory.goals import GoalManager, GoalStatus
from memory.state import AgentStateStore
from planner.evaluator import SelfEvaluator
from planner.strategies import StrategySelector


class _FakeBrain:
    def __init__(self, plan_json: str = "[]") -> None:
        self.plan_json = plan_json
        self.plan_calls = 0

    def ask(self, prompt: str) -> str:
        if "Break the user's goal" in prompt:
            self.plan_calls += 1
            return self.plan_json
        return "Keep doing what works."


def _build(tmp_path: Path, plan_json: str = "[]", route_result: str = "done"):
    brain = _FakeBrain(plan_json=plan_json)
    router = SimpleNamespace(
        brain=brain,
        route=lambda text: route_result,
        _permissions=PermissionManager(),
        _safety=HardSafety(),
    )
    memory = FactStore(str(tmp_path / "atlas_memory.db"))
    goals = GoalManager(str(tmp_path / "atlas_memory.db"), memory=memory)
    experiences = ExperienceStore(str(tmp_path / "atlas_memory.db"), memory=memory)
    state = AgentStateStore(str(tmp_path / "atlas_memory.db"))
    selector = StrategySelector()
    evaluator = SelfEvaluator(experiences=experiences, brain=brain)
    autonomy = AutonomyController(
        router=router,
        state_store=state,
        goals=goals,
        experiences=experiences,
        selector=selector,
        evaluator=evaluator,
    )
    return autonomy, goals, experiences, state


def test_run_auto_creates_and_completes_goal(tmp_path: Path) -> None:
    autonomy, goals, _, _ = _build(
        tmp_path,
        plan_json='[{"description": "do a thing", "tool_name": null, "tool_args": {}}]',
    )
    report = autonomy.run_auto("complete the onboarding checklist")
    assert report.success is True
    assert report.verdict == "success"
    assert report.goal_id is not None
    goal = goals.get_goal(report.goal_id)
    assert goal is not None
    assert goal.status == GoalStatus.DONE
    assert goal.progress == 1.0


def test_run_auto_records_experience_and_lessons(tmp_path: Path) -> None:
    autonomy, _, experiences, _ = _build(
        tmp_path,
        plan_json='[{"description": "do a thing", "tool_name": null, "tool_args": {}}]',
    )
    autonomy.run_auto("search the web for news")
    assert experiences.count() >= 1
    assert any(lesson for lesson in experiences.recent_lessons(limit=5))


def test_run_auto_blocks_goal_on_failure(tmp_path: Path) -> None:
    autonomy, goals, _, _ = _build(
        tmp_path,
        plan_json='[{"description": "risky step", "tool_name": null, "tool_args": {}}]',
        route_result="Failed to complete the risky step",
    )
    report = autonomy.run_auto("attempt something risky")
    assert report.success is False
    assert report.verdict in ("partial", "failed")
    goal = goals.get_goal(report.goal_id)  # type: ignore[arg-type]
    assert goal is not None
    assert goal.status == GoalStatus.BLOCKED


def test_advance_goal_incremental_then_completes(tmp_path: Path) -> None:
    autonomy, goals, _, _ = _build(
        tmp_path,
        plan_json=(
            '[{"description": "step one", "tool_name": null, "tool_args": {}},'
            '{"description": "step two", "tool_name": null, "tool_args": {}}]'
        ),
    )
    goal = goals.create_goal("a two step goal")
    first = autonomy.advance_goal(goal.id, max_tasks=1, consent="agent")
    assert first.verdict == "in_progress"
    assert round(first.score, 2) == 0.5
    second = autonomy.advance_goal(goal.id, max_tasks=1, consent="agent")
    assert second.verdict == "success"
    assert goals.get_goal(goal.id).status == GoalStatus.DONE  # type: ignore[union-attr]


def test_advance_goal_resumes_from_checkpoint(tmp_path: Path) -> None:
    autonomy, goals, _, state = _build(
        tmp_path,
        plan_json=(
            '[{"description": "step one", "tool_name": null, "tool_args": {}},'
            '{"description": "step two", "tool_name": null, "tool_args": {}}]'
        ),
    )
    goal = goals.create_goal("checkpointed goal")
    autonomy.advance_goal(goal.id, max_tasks=1, consent="agent")

    # A brand-new controller (simulating a restart) must pick up where it left off.
    restarted, goals2, _, state2 = _build(tmp_path)
    stored = state.get(f"mission.plan:{goal.id}")
    assert stored is not None
    assert stored["index"] == 1
    assert state2.get(f"mission.plan:{goal.id}") is not None
    second = restarted.advance_goal(goal.id, max_tasks=1, consent="agent")
    assert second.verdict == "success"


def test_advance_goal_blocks_on_background_destructive(tmp_path: Path) -> None:
    autonomy, goals, _, _ = _build(
        tmp_path,
        plan_json='[{"description": "delete it", "tool_name": "file", "tool_args": {"action": "delete", "path": "C:\\\\temp\\\\x.txt"}}]',
    )
    goal = goals.create_goal("remove a file")
    report = autonomy.advance_goal(goal.id, max_tasks=1, consent="agent")
    assert report.verdict == "blocked"
    assert "confirmation" in report.message
    assert goals.get_goal(goal.id).status == GoalStatus.BLOCKED  # type: ignore[union-attr]


def test_pick_and_advance_returns_none_without_goals(tmp_path: Path) -> None:
    autonomy, _, _, _ = _build(tmp_path)
    assert autonomy.pick_and_advance() is None
