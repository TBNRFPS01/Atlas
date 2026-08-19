from __future__ import annotations

from pathlib import Path

from core.agent_runtime import (
    AgentRuntime,
    AgentTeam,
    ContextManager,
    FunctionSubagent,
    JsonlTrace,
    MCPTool,
    # imported below conditionally to keep this test file explicit
    ModelCandidate,
    RecoveryController,
    Sandbox,
    SubagentSpec,
    TraceRecorder,
)
from core.mcp import InMemoryMCPTransport, MCPClient


def test_context_manager_compacts_by_priority() -> None:
    context = ContextManager(max_chars=20)
    context.add("user", "low priority context", priority=0)
    context.add("goal", "KEEP", priority=10)
    rendered = context.render()
    assert "KEEP" in rendered
    assert len(rendered) <= 20


def test_approval_gate_never_auto_approves() -> None:
    runtime = AgentRuntime()
    request = runtime.approvals.request("delete", "destructive action")
    assert not runtime.approvals.is_approved(request.id)
    assert runtime.approvals.approve(request.id)
    assert runtime.approvals.is_approved(request.id)


def test_subagent_team_delegates() -> None:
    trace = TraceRecorder()
    team = AgentTeam(trace)
    spec = SubagentSpec("research", "research tasks")
    team.register(spec, FunctionSubagent(lambda task, _: f"done: {task}"))
    result = team.delegate("research", "find docs")
    assert result.success
    assert "find docs" in result.output
    assert any(event.kind == "agent" for event in trace.events)


def test_recovery_retries_and_succeeds() -> None:
    attempts = {"count": 0}

    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError("temporary")
        return "ok"

    success, value, used = RecoveryController().run(flaky)
    assert success
    assert value == "ok"
    assert used == 2


def test_model_router_selects_capability() -> None:
    runtime = AgentRuntime()
    runtime.models.add(ModelCandidate("small", "local", {"general"}, 1))
    runtime.models.add(ModelCandidate("coder", "local", {"coding"}, 5))
    assert runtime.models.choose("coding").name == "coder"


def test_trace_persists_jsonl(tmp_path: Path) -> None:
    sink = JsonlTrace(tmp_path / "trace.jsonl")
    recorder = TraceRecorder([sink])
    recorder.record("tool", "search", query="atlas")
    recent = sink.recent()
    assert recent[0]["name"] == "search"


def test_sandbox_runs_without_shell(tmp_path: Path) -> None:
    result = Sandbox(root=tmp_path).run(["python", "-c", "print('ok')"])
    assert result["returncode"] == 0
    assert result["stdout"].strip() == "ok"


def test_mcp_adapter_discovers_and_calls_tools() -> None:
    transport = InMemoryMCPTransport()
    transport.register(MCPTool("add", "add numbers"), lambda a, b: a + b)
    client = MCPClient(transport)
    assert [tool.name for tool in client.tools()] == ["add"]
    assert client.call("add", a=2, b=3) == 5


def test_runtime_checkpoint_roundtrip(tmp_path: Path) -> None:
    runtime = AgentRuntime(tmp_path / "trace.jsonl")
    runtime.context.add("user", "remember this", priority=5)
    runtime.models.add(ModelCandidate("local", "lmstudio", {"general"}, 1))
    path = tmp_path / "checkpoint.json"
    runtime.save_checkpoint(path)

    restored = AgentRuntime(tmp_path / "trace2.jsonl")
    restored.load_checkpoint(path)
    assert "remember this" in restored.context.render()
    assert restored.models.choose("general").name == "local"
