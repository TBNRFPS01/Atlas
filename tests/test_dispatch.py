from core.router import Router
from tools.media_tool import MediaTool


def test_extract_minecraft_server_from_prompt() -> None:
    router = Router()
    assert router._extract_minecraft_server("check my minecraft server play.example.com") == "play.example.com"
    assert router._extract_minecraft_server("minecraft status") == ""


def test_minecraft_dispatch_reports_status() -> None:
    result = Router().route("minecraft status")
    assert "Minecraft" in result
    assert "stub" not in result


def test_media_transport_actions_no_longer_stub() -> None:
    tool = MediaTool()
    for action in ("next", "previous", "pause"):
        result = tool.execute(action=action)
        assert "not implemented" not in result
        assert result.strip()


def test_automation_type_args() -> None:
    router = Router()
    assert router._build_automation_args("type hello world", "type hello world") == {
        "action": "keyboard_type",
        "text": "hello world",
    }


def test_automation_open_app_args() -> None:
    router = Router()
    assert router._build_automation_args("open app notepad", "open app notepad") == {
        "action": "windows_launch",
        "path": "notepad",
    }


def test_looks_like_automation_command() -> None:
    router = Router()
    assert router._looks_like_automation_command("type hello") is True
    assert router._looks_like_automation_command("open app notepad") is True
    assert router._looks_like_automation_command("what is the weather like") is False