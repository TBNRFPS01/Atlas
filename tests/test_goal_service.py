from pathlib import Path
from types import SimpleNamespace

from memory.experience import ExperienceStore
from memory.goals import GoalManager, GoalStatus
from memory.state import AgentStateStore
from planner.strategies import StrategySelector
from services.goal_service import AutonomousGoalService
from core.autonomy import AutonomyController
from planner.evaluator import SelfEvaluator


def _make_autonomy(tmp_path: Path):
    class _FakeBrain:
        def ask(self, prompt: str) -> str:
            if "Break the user's goal" in prompt:
                return '[{"description": "a step", "tool_name": null, "tool_args": {}}]'
            return "ok"

    router = SimpleNamespace(
        brain=_FakeBrain(),
        route=lambda t: "done",
    )
    goals = GoalManager(str(tmp_path / "atlas_memory.db"))
    experiences = ExperienceStore(str(tmp_path / "atlas_memory.db"))
    state = AgentStateStore(str(tmp_path / "atlas_memory.db"))
    autonomy = AutonomyController(
        router=router,
        state_store=state,
        goals=goals,
        experiences=experiences,
        selector=StrategySelector(),
        evaluator=SelfEvaluator(experiences=experiences),
    )
    return autonomy, goals


def test_service_returns_none_when_disabled(tmp_path: Path) -> None:
    autonomy, _ = _make_autonomy(tmp_path)
    service = AutonomousGoalService(autonomy=autonomy, enabled=False, interval_seconds=1)
    assert service.run_once() is None


def test_service_advances_next_goal(tmp_path: Path) -> None:
    autonomy, goals = _make_autonomy(tmp_path)
    goals.create_goal("first background goal", priority=3.0)
    service = AutonomousGoalService(autonomy=autonomy, enabled=True, interval_seconds=1, max_tasks=1)
    report = service.run_once()
    assert report is not None
    assert report.goal_id is not None
    # The single-step goal should now be complete.
    goal = goals.get_goal(report.goal_id)
    assert goal is not None
    assert goal.status == GoalStatus.DONE


def test_service_returns_none_when_no_goals(tmp_path: Path) -> None:
    autonomy, _ = _make_autonomy(tmp_path)
    service = AutonomousGoalService(autonomy=autonomy, enabled=True, interval_seconds=1)
    assert service.run_once() is None


def test_service_reports_through_console(tmp_path: Path) -> None:
    autonomy, goals = _make_autonomy(tmp_path)
    goals.create_goal("reported goal")
    seen: list[str] = []
    service = AutonomousGoalService(
        autonomy=autonomy, enabled=True, interval_seconds=1, console=seen.append
    )
    service.run_once()
    assert seen and "Autonomy:" in seen[0]