from pathlib import Path

from memory.experience import ExperienceStore
from planner.strategies import StrategySelector


def test_classify_web() -> None:
    assert StrategySelector().classify("search the web for climate data") == "web"


def test_classify_browser() -> None:
    assert StrategySelector().classify("navigate to example.com and click submit") == "browser"


def test_classify_file() -> None:
    assert StrategySelector().classify("read file C:\\notes.txt") == "file"


def test_classify_automation() -> None:
    assert StrategySelector().classify("open notepad and type hello") == "automation"


def test_classify_system() -> None:
    assert StrategySelector().classify("show system info") == "system"


def test_classify_general() -> None:
    assert StrategySelector().classify("explain quantum computing") == "general"


def test_select_returns_default_without_experience() -> None:
    selection = StrategySelector().select("research the history of rome")
    assert selection.task_type == "web"
    assert selection.strategy_key == "web"
    assert "Strategy hint" in selection.hint


def test_select_biases_toward_proven_strategy(tmp_path: Path) -> None:
    experiences = ExperienceStore(str(tmp_path / "atlas_memory.db"))
    # A proven non-default strategy for 'web' tasks.
    for _ in range(4):
        experiences.record_attempt("web", "browser_tool", True, strategy="Use browser directly")
    selection = StrategySelector().select("search the web for atlantis", experiences=experiences)
    assert selection.strategy_key == "browser_tool"
    assert "browser" in selection.strategy.lower()


def test_select_ignores_weak_strategies(tmp_path: Path) -> None:
    experiences = ExperienceStore(str(tmp_path / "atlas_memory.db"))
    for _ in range(4):
        experiences.record_attempt("web", "browser_tool", False, strategy="Use browser directly")
    selection = StrategySelector().select("search the web for atlantis", experiences=experiences)
    # Weak strategy stays below threshold -> default is used.
    assert selection.strategy_key == "web"
