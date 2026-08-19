from memory.experience import ExperienceStore
from pathlib import Path

from planner.evaluator import SelfEvaluator


def _plan(success: bool, statuses: list[str]) -> dict:
    return {
        "goal": "test goal",
        "success": success,
        "tasks": [
            {"id": f"task_{i}", "description": f"step {i}", "status": s, "result": "ok" if s == "completed" else "", "error": "" if s == "completed" else "boom"}
            for i, s in enumerate(statuses)
        ],
    }


def test_evaluate_success() -> None:
    ev = SelfEvaluator().evaluate_mission("test", _plan(True, ["completed", "completed"]))
    assert ev.verdict == "success"
    assert ev.score == 1.0
    assert ev.issues == []


def test_evaluate_partial() -> None:
    ev = SelfEvaluator().evaluate_mission("test", _plan(False, ["completed", "failed"]))
    assert ev.verdict == "partial"
    assert round(ev.score, 2) == 0.5
    assert len(ev.issues) == 1


def test_evaluate_failed() -> None:
    ev = SelfEvaluator().evaluate_mission("test", _plan(False, ["failed", "failed"]))
    assert ev.verdict == "failed"
    assert ev.score == 0.0


def test_recommendation_falls_back_without_brain() -> None:
    ev = SelfEvaluator().evaluate_mission("test", _plan(False, ["failed"]), task_type="web", strategy_key="browser")
    assert ev.recommendation  # non-empty fallback


def test_brain_recommendation_is_used() -> None:
    class _FakeBrain:
        def ask(self, prompt: str) -> str:
            return "Use smaller, verifiable steps."

    ev = SelfEvaluator(brain=_FakeBrain()).evaluate_mission("test", _plan(False, ["failed"]))
    assert "smaller" in ev.recommendation


def test_lessons_include_outcome() -> None:
    ev = SelfEvaluator().evaluate_mission("test", _plan(False, ["completed", "failed"]), task_type="web", strategy_key="web_tool")
    assert len(ev.lessons) >= 1
    assert "partial" in ev.lessons[0]


def test_persist_lessons_writes_to_memory(tmp_path: Path) -> None:
    from memory.facts import FactStore

    memory = FactStore(str(tmp_path / "atlas_memory.db"))
    experiences = ExperienceStore(str(tmp_path / "atlas_memory.db"), memory=memory)
    ev = SelfEvaluator(experiences=experiences).evaluate_mission("test", _plan(False, ["failed"]))
    SelfEvaluator(experiences=experiences).persist_lessons(ev)
    lessons = experiences.recent_lessons(limit=5)
    assert lessons
    assert any("failed" in lesson for lesson in lessons)
