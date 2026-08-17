from core.router import Router


def test_debug_includes_skills_and_call_log() -> None:
    router = Router()
    router.route("system info")
    report = router._debug_report()
    assert "Loaded skills" in report
    assert "Tool call log" in report
    assert "Undo available" in report


def test_call_log_records_duration() -> None:
    router = Router()
    router.route("system info")
    assert router._call_log
    last = router._call_log[-1]
    assert last["tool"] == "system"
    assert "duration" in last
    assert isinstance(last["ok"], bool)


def test_undo_command_restores_trashed_file(tmp_path) -> None:
    router = Router()
    target = tmp_path / "x.txt"
    target.write_text("data", encoding="utf-8")
    router._file_request(f"yes, delete {target}")
    assert not target.exists()
    out = router.route("/undo")
    assert target.exists()
    assert "Undid" in out


def test_screen_command_returns_string() -> None:
    router = Router()
    result = router.route("/screen")
    assert isinstance(result, str)


def test_trace_records_dispatch() -> None:
    router = Router()
    router._dispatch_tool("system info")
    assert any("system.info" in e for e in router._trace)
