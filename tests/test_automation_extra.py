from tools.automation_tool import AutomationTool


def test_get_parameters_returns_list() -> None:
    params = AutomationTool().get_parameters()
    assert isinstance(params, list)
    assert all(hasattr(p, "name") for p in params)


def test_invalid_action_returns_string() -> None:
    out = AutomationTool().execute(action="not_a_real_action")
    assert isinstance(out, str)


def test_mouse_position_returns_string() -> None:
    out = AutomationTool().execute(action="mouse_position")
    assert isinstance(out, str)
    assert "position" in out.lower()


def test_windows_list_returns_string() -> None:
    out = AutomationTool().execute(action="windows_list")
    assert isinstance(out, str)


def test_clipboard_get_returns_string() -> None:
    out = AutomationTool().execute(action="clipboard_get")
    assert isinstance(out, str)
