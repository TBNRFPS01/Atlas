from tools.media_tool import MediaTool


def test_send_media_key_unknown_action_returns_false() -> None:
    tool = MediaTool()
    assert tool._send_media_key("nonsense") is False


def test_send_media_key_non_windows_no_backend(monkeypatch) -> None:
    tool = MediaTool()
    monkeypatch.setattr("platform.system", lambda: "Linux")
    import shutil

    monkeypatch.setattr(shutil, "which", lambda cmd: False)
    assert tool._send_media_key("next") is False
