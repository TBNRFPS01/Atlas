from core.execution import ExecutionPipeline


def test_dry_run_never_calls_action():
    called = []
    pipeline = ExecutionPipeline(dry_run=True)
    result = pipeline.run("file", "delete", lambda: called.append(True), signature="file:delete")
    assert result.ok
    assert result.dry_run
    assert called == []


def test_retries_then_succeeds():
    attempts = {"count": 0}

    def action():
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError("temporary failure")
        return "ok"

    pipeline = ExecutionPipeline(max_retries=1)
    result = pipeline.run("demo", "run", action, signature="demo:run")
    assert result.ok
    assert result.verified
    assert result.attempts == 2


def test_verification_failure_is_retried():
    attempts = {"count": 0}

    def action():
        attempts["count"] += 1
        return attempts["count"] == 2

    pipeline = ExecutionPipeline(max_retries=1)
    result = pipeline.run("demo", "run", action, verify=lambda value: value is True, signature="demo:verify")
    assert result.ok
    assert result.attempts == 2


def test_repeated_action_is_stopped():
    pipeline = ExecutionPipeline(max_retries=0)
    calls = {"count": 0}

    def action():
        calls["count"] += 1
        return "ok"

    for _ in range(3):
        pipeline.run("demo", "same", action, signature="demo:same")

    result = pipeline.run("demo", "same", action, signature="demo:same")
    assert not result.ok
    assert "repeated action" in str(result.result).lower()
    assert calls["count"] < 4
