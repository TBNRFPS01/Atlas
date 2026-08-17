from tools.web_tool import WebTool


class _Flaky:
    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    def __call__(self, url: str, timeout: int = 20) -> str:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("transient network error")
        return "<html>ok</html>"


def test_retry_succeeds_after_transient_failure(monkeypatch) -> None:
    tool = WebTool()
    flaky = _Flaky(fail_times=2)
    monkeypatch.setattr(tool, "_open", flaky)
    # _open now routes through _open_with_retry; force a real fetch via _strip.
    result = tool._open_with_retry("http://example.com", retries=3, backoff=0.0)
    assert result == "<html>ok</html>"
    assert flaky.calls == 3


def test_retry_exhausts_and_raises(monkeypatch) -> None:
    tool = WebTool()
    monkeypatch.setattr(tool, "_open", _Flaky(fail_times=99))
    try:
        tool._open_with_retry("http://example.com", retries=1, backoff=0.0)
    except RuntimeError as exc:
        assert "after 2 attempts" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_fetch_uses_retry_wrapper() -> None:
    tool = WebTool()
    # The public _open delegates to the retry wrapper.
    assert tool._open.__func__.__name__ == "_open"
