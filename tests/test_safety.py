from core.router import Router


def test_file_delete_requires_confirmation(tmp_path) -> None:
    router = Router()
    target = tmp_path / "notes.txt"
    target.write_text("secret", encoding="utf-8")

    denied = router._file_request(f"delete {target}")
    assert "Confirm" in denied
    assert "delete file" in denied
    assert target.exists()

    approved = router._file_request(f"yes, delete {target}")
    assert "Moved to trash" in approved
    assert not target.exists()
    # The operation is reversible via /undo.
    assert "undo" in approved.lower()
    undo_result = router.route("/undo")
    assert target.exists()
    assert "Undid" in undo_result


def test_file_delete_confirmed_via_registry(tmp_path) -> None:
    router = Router()
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")
    result = router._file_request(f"yes, delete {target}")
    assert "Moved to trash" in result
    assert not target.exists()


def test_kill_process_requires_confirmation() -> None:
    router = Router()
    result = router.route("kill process notepad")
    assert "Confirm" in result
    assert "terminated" not in result


def test_close_window_requires_confirmation() -> None:
    router = Router()
    result = router.route("close window Untitled - Notepad")
    assert "Confirm" in result


def test_voice_config_is_typed() -> None:
    import voice.config as vc

    assert isinstance(vc.VOICE_ENABLED, bool)
    assert isinstance(vc.WHISPER_MODEL, str) and vc.WHISPER_MODEL


def test_logging_delegates_to_single_implementation() -> None:
    from core.logging_utils import setup_logger
    from utils.logger import get_logger

    assert setup_logger("ATLAS") is get_logger("ATLAS")