from pathlib import Path

from memory.experience import ExperienceStore
from memory.facts import FactStore


def _store(path: Path) -> ExperienceStore:
    return ExperienceStore(str(path / "atlas_memory.db"), memory=FactStore(str(path / "atlas_memory.db")))


def test_record_attempt_updates_average(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_attempt("web", "web_tool", True, notes="search ok")
    store.record_attempt("web", "web_tool", True)
    store.record_attempt("web", "web_tool", False)
    best = store.best_strategy("web", min_runs=1)
    assert best is not None
    assert best["strategy_key"] == "web_tool"
    assert best["run_count"] == 3
    assert round(best["avg_success"], 2) == round(2 / 3, 2)


def test_best_strategy_requires_min_runs(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_attempt("file", "file_tool", True)
    assert store.best_strategy("file") is None  # min_runs default 2
    store.record_attempt("file", "file_tool", True)
    assert store.best_strategy("file") is not None


def test_best_strategy_prefers_higher_success(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for _ in range(3):
        store.record_attempt("browser", "browser_tool", True)
        store.record_attempt("browser", "slow_tool", False)
    best = store.best_strategy("browser", min_runs=1)
    assert best["strategy_key"] == "browser_tool"  # type: ignore[index]


def test_strategy_stats(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_attempt("automation", "automation", True)
    store.record_attempt("automation", "automation", False)
    stats = store.strategy_stats("automation")
    assert stats["n"] == 1
    assert stats["runs"] == 2
    assert round(stats["success_rate"], 2) == 0.5


def test_lessons_recorded_and_recent(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_lesson("lesson:0", "Browser navigation worked well", importance=1.0)
    store.record_lesson("lesson:1", "Avoid blind clicks", importance=1.3)
    lessons = store.recent_lessons(limit=5)
    assert any("Browser navigation" in lesson for lesson in lessons)
    assert any("Avoid blind clicks" in lesson for lesson in lessons)


def test_count_and_all(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_attempt("web", "web_tool", True)
    store.record_attempt("file", "file_tool", False)
    assert store.count() == 2
    assert len(store.all_strategies()) == 2
    assert len(store.strategies_for("web")) == 1
