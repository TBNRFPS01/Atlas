from core.router import Router


def test_debug_report_contains_sections() -> None:
    router = Router()
    report = router._debug_report()
    assert "Loaded tools" in report
    assert "Memory entries" in report
    assert "Recent trace" in report


def test_record_trace_caps_size() -> None:
    router = Router()
    for i in range(120):
        router._record_trace("tool", "action", str(i))
    assert len(router._trace) <= 100


def test_dispatch_records_trace() -> None:
    router = Router()
    router._dispatch_tool("system info")
    assert any("router.dispatch" in entry for entry in router._trace)


def test_vision_command_returns_string() -> None:
    router = Router()
    result = router.route("/vision")
    assert isinstance(result, str)
    assert len(result) > 0
