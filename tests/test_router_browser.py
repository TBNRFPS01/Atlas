from __future__ import annotations

from unittest.mock import MagicMock

from core.router import Router


def _make_router() -> Router:
    router = Router()
    # Avoid touching LM Studio / real brain.
    router.brain = MagicMock()
    router.brain.ask.return_value = "ok"
    return router


def test_build_browser_args_navigate() -> None:
    router = _make_router()
    action, args = router._build_browser_args("browser navigate to example.com", "browser navigate to example.com")
    assert action == "navigate"
    assert args["url"] == "example.com"


def test_build_browser_args_click() -> None:
    router = _make_router()
    action, args = router._build_browser_args("click on Submit", "click on submit")
    assert action == "click"
    assert args["selector"] == "Submit"


def test_build_browser_args_type_with_text() -> None:
    router = _make_router()
    action, args = router._build_browser_args(
        "browser type input#q with hello world", "browser type input#q with hello world"
    )
    assert action == "type"
    assert args["selector"] == "input#q"
    assert args["text"] == "hello world"


def test_build_browser_args_scroll() -> None:
    router = _make_router()
    action, args = router._build_browser_args("scroll down 500", "scroll down 500")
    assert action == "scroll"
    assert args["direction"] == "down"
    assert args["amount"] == 500


def test_build_browser_args_status() -> None:
    router = _make_router()
    action, args = router._build_browser_args("browser status", "browser status")
    assert action == "status"


def test_browser_request_dispatches() -> None:
    router = _make_router()
    fake_tool = MagicMock()
    fake_tool.name = "browser"
    fake_tool.execute.return_value = "URL: https://example.com"
    router._registry._tools["browser"] = fake_tool
    result = router._browser_request("browser navigate to example.com")
    assert "URL: https://example.com" in result
    fake_tool.execute.assert_called_once()
    call_args = fake_tool.execute.call_args.kwargs
    assert call_args["action"] == "navigate"
    assert call_args["url"] == "example.com"


def test_browser_request_denied_by_rule() -> None:
    router = _make_router()
    router._permissions.set_rule("browser", "deny")
    fake_tool = MagicMock()
    fake_tool.name = "browser"
    router._registry._tools["browser"] = fake_tool
    result = router._browser_request("browser navigate to example.com")
    assert "Permission denied" in result
    fake_tool.execute.assert_not_called()


def test_browser_request_unloaded_tool() -> None:
    router = _make_router()
    router._registry._tools.pop("browser", None)
    result = router._browser_request("browser navigate to example.com")
    assert "not loaded" in result
