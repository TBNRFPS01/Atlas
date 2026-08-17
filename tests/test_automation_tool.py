from tools.automation_tool import AutomationTool
from tools.registry import ToolRegistry


def test_automation_tool_discovered() -> None:
    registry = ToolRegistry()
    registry.discover()
    assert registry.get("automation") is not None


def test_automation_keyboard_type_reports() -> None:
    result = AutomationTool().execute(action="keyboard_type", text="hello world")
    assert "Typed" in result or "unavailable" in result


def test_automation_clipboard_read_reports() -> None:
    result = AutomationTool().execute(action="clipboard_get")
    assert "Clipboard" in result or "unavailable" in result


def test_automation_unknown_action() -> None:
    result = AutomationTool().execute(action="nope")
    assert "Unknown automation action" in result