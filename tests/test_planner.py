from types import SimpleNamespace

from planner.planner import Planner
from planner.task import TaskStatus


def test_fallback_open_app_maps_to_automation() -> None:
    steps = Planner()._fallback_decompose("open notepad")
    assert steps[0]["tool_name"] == "automation"
    assert steps[0]["tool_args"]["action"] == "windows_launch"
    assert steps[0]["tool_args"]["path"] == "notepad"


def test_fallback_type_maps_to_keyboard() -> None:
    steps = Planner()._fallback_decompose("type hello world")
    assert steps[0]["tool_args"]["action"] == "keyboard_type"
    assert steps[0]["tool_args"]["text"] == "hello world"


def test_fallback_screenshot() -> None:
    steps = Planner()._fallback_decompose("take a screenshot")
    assert steps[0]["tool_name"] == "screenshot"


def test_fallback_search() -> None:
    steps = Planner()._fallback_decompose("search the web for atlantis")
    assert steps[0]["tool_name"] == "web"


def test_failing_task_retries_then_fails() -> None:
    router = SimpleNamespace(brain=SimpleNamespace(ask=lambda p: (_ for _ in ()).throw(RuntimeError("llm down"))))
    planner = Planner(router=router)
    planner.create_plan("open notepad")
    task = planner.get_task("task_0")
    assert task is not None
    task.tool_name = "does_not_exist"

    result = planner.execute("task_0")
    assert result.status == TaskStatus.FAILED
    assert result.retry_count == result.max_retries
    assert result.error