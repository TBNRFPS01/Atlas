from __future__ import annotations

from pathlib import Path

from core.router import Router
from core.natural_router import NaturalCapabilityRouter
from tools.base import Tool, ToolMetadata
from tools.registry import ToolRegistry


class DemoTool(Tool):
    name = "demo"
    metadata = ToolMetadata()

    def execute(self, **kwargs):
        if kwargs.get("fail"):
            raise RuntimeError("boom")
        return kwargs.get("result", "ok")


def _router() -> Router:
    registry = ToolRegistry()
    registry.register(DemoTool())
    return Router(registry=registry)


def test_execution_record_contains_evidence_for_verified_action() -> None:
    router = _router()
    assert router.execute_action(intent="finish demo", tool_name="demo", action="run",
        fn=lambda: "done", observe=lambda result: {"value": result},
        verify=lambda observation: observation["value"] == "done") == "done"
    record = router._execution.history[-1]
    assert record["intent"] == "finish demo"
    assert record["permissions"] == "allow"
    assert record["safety"] == "allow"
    assert record["observation"] == {"value": "done"}
    assert record["verification"] == "verified"


def test_failed_verification_is_not_success() -> None:
    router = _router()
    response = router.execute_action(intent="finish demo", tool_name="demo", action="run",
        fn=lambda: "wrong", verify=lambda value: value == "done")
    assert "verification failed" in response.lower()
    assert router._execution.history[-1]["verification"] == "failed"


def test_exception_is_recorded() -> None:
    router = _router()
    response = router.execute_action(intent="run demo", tool_name="demo", action="run",
        fn=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert "boom" in response
    assert router._execution.history[-1]["ok"] is False


def test_permission_and_safety_denials_are_recorded() -> None:
    router = _router()
    router._permissions.set_rule("demo.run", "deny")
    assert "denied" in router.execute_action(intent="run demo", tool_name="demo", action="run", fn=lambda: "no").lower()
    assert router._execution.history[-1]["permissions"] == "deny"
    assert router._execution.history[-1]["safety"] == "allow"
    assert "hard safety" in router.execute_action(intent="format", tool_name="automation", action="shutdown", fn=lambda: "no").lower()
    assert router._execution.history[-1]["safety"] == "deny"


def test_unavailable_verification_is_explicit() -> None:
    router = _router()
    assert router.execute_action(intent="run demo", tool_name="demo", action="run", fn=lambda: "ok") == "ok"
    assert router._execution.history[-1]["verification"] == "unavailable"


def test_natural_route_uses_the_same_execution_boundary() -> None:
    router = _router()
    assert NaturalCapabilityRouter._execute(router, "demo", action="run", _prompt="run demo") == "ok"
    assert router._execution.history[-1]["intent"] == "run demo"


def test_file_write_is_observed_and_verified() -> None:
    router = Router()
    target = Path(".atlas-execution-evidence-test.txt").resolve()
    try:
        response = router._file_request(f"confirm write {target} with the content: hello")
        assert "Successfully wrote" in response
        record = router._execution.history[-1]
        assert record["verification"] == "verified"
        assert record["observation"]["content"] == "hello"
    finally:
        target.unlink(missing_ok=True)
