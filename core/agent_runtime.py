"""Composable runtime for advanced ATLAS agent capabilities.

This module provides a small, dependency-light orchestration layer that can be
used by the existing Router/Planner without replacing them. It adds durable
execution traces, context budgeting and compaction, human-in-the-loop
approvals, subagent delegation, bounded retries/recovery, pluggable model
routing, safe sandbox execution hooks, and resumable task state.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol


@dataclass(slots=True)
class TraceEvent:
    id: str
    kind: str
    name: str
    timestamp: float
    status: str = "ok"
    data: dict[str, Any] = field(default_factory=dict)


class TraceSink(Protocol):
    def emit(self, event: TraceEvent) -> None: ...


class JsonlTrace:
    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path or (Path.home() / ".atlas" / "traces.jsonl"))
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: TraceEvent) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=False, default=str) + "\n")

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-max(1, limit):]
        return [json.loads(line) for line in lines if line.strip()]


class TraceRecorder:
    def __init__(self, sinks: Iterable[TraceSink] = ()) -> None:
        self.sinks = list(sinks)
        self.events: list[TraceEvent] = []

    def record(self, kind: str, name: str, status: str = "ok", **data: Any) -> TraceEvent:
        event = TraceEvent(str(uuid.uuid4()), kind, name, time.time(), status, data)
        self.events.append(event)
        for sink in self.sinks:
            sink.emit(event)
        return event


@dataclass(slots=True)
class ContextItem:
    role: str
    content: str
    priority: int = 0
    timestamp: float = field(default_factory=time.time)


class ContextManager:
    """Keep useful context inside a configurable character budget."""

    def __init__(self, max_chars: int = 48_000) -> None:
        self.max_chars = max(1, max_chars)
        self.items: list[ContextItem] = []

    def add(self, role: str, content: str, priority: int = 0) -> None:
        self.items.append(ContextItem(role, content, priority))
        self.compact()

    @staticmethod
    def _render_item(item: ContextItem) -> str:
        return f"[{item.role}] {item.content}"

    def compact(self) -> None:
        ordered = sorted(self.items, key=lambda i: (i.priority, i.timestamp), reverse=True)
        kept: list[ContextItem] = []
        used = 0
        for item in ordered:
            rendered_len = len(self._render_item(item))
            separator = 2 if kept else 0
            if used + separator + rendered_len <= self.max_chars:
                kept.append(item)
                used += separator + rendered_len
        self.items = sorted(kept, key=lambda i: i.timestamp)

    def render(self) -> str:
        # Re-compact at render time as a final invariant. This also protects
        # callers that mutate ContextItem instances after insertion.
        self.compact()
        rendered = "\n\n".join(self._render_item(i) for i in self.items)
        return rendered[:self.max_chars]


@dataclass(slots=True)
class ApprovalRequest:
    id: str
    action: str
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    status: str = "pending"


class ApprovalGate:
    def __init__(self) -> None:
        self.pending: dict[str, ApprovalRequest] = {}

    def request(self, action: str, reason: str, payload: dict[str, Any] | None = None) -> ApprovalRequest:
        req = ApprovalRequest(str(uuid.uuid4()), action, reason, payload or {})
        self.pending[req.id] = req
        return req

    def approve(self, request_id: str) -> bool:
        req = self.pending.get(request_id)
        if req is None or req.status != "pending":
            return False
        req.status = "approved"
        return True

    def deny(self, request_id: str) -> bool:
        req = self.pending.get(request_id)
        if req is None or req.status != "pending":
            return False
        req.status = "denied"
        return True

    def is_approved(self, request_id: str) -> bool:
        req = self.pending.get(request_id)
        return req is not None and req.status == "approved"


@dataclass(slots=True)
class SubagentSpec:
    name: str
    purpose: str
    max_steps: int = 8
    system_prompt: str = ""


@dataclass(slots=True)
class SubagentResult:
    name: str
    success: bool
    output: str
    steps: int = 0
    error: str = ""


class Subagent(Protocol):
    def run(self, task: str, spec: SubagentSpec) -> SubagentResult: ...


class FunctionSubagent:
    def __init__(self, fn: Callable[[str, SubagentSpec], str]) -> None:
        self.fn = fn

    def run(self, task: str, spec: SubagentSpec) -> SubagentResult:
        try:
            return SubagentResult(spec.name, True, str(self.fn(task, spec)), 1)
        except Exception as exc:
            return SubagentResult(spec.name, False, "", 1, str(exc))


class AgentTeam:
    def __init__(self, trace: TraceRecorder | None = None) -> None:
        self.agents: dict[str, tuple[SubagentSpec, Subagent]] = {}
        self.trace = trace

    def register(self, spec: SubagentSpec, agent: Subagent) -> None:
        self.agents[spec.name] = (spec, agent)

    def delegate(self, name: str, task: str) -> SubagentResult:
        if name not in self.agents:
            raise KeyError(f"Unknown subagent: {name}")
        spec, agent = self.agents[name]
        if self.trace:
            self.trace.record("agent", "delegate", agent=name, task=task)
        result = agent.run(task, spec)
        if self.trace:
            self.trace.record("agent", "result", "ok" if result.success else "error", agent=name, output=result.output, error=result.error)
        return result


@dataclass(slots=True)
class SandboxPolicy:
    timeout: float = 20.0
    max_output: int = 32_000
    allow_network: bool = False
    read_only: bool = False


class Sandbox:
    def __init__(self, policy: SandboxPolicy | None = None, root: str | os.PathLike[str] | None = None) -> None:
        self.policy = policy or SandboxPolicy()
        self.root = Path(root) if root else Path(tempfile.mkdtemp(prefix="atlas-sandbox-"))
        self.root.mkdir(parents=True, exist_ok=True)

    def run(self, command: list[str], timeout: float | None = None) -> dict[str, Any]:
        if not command:
            raise ValueError("Sandbox command cannot be empty")
        started = time.monotonic()
        try:
            proc = subprocess.run(command, cwd=self.root, capture_output=True, text=True,
                                  timeout=timeout or self.policy.timeout, check=False, shell=False,
                                  env={"PATH": os.environ.get("PATH", "")})
            return {"returncode": proc.returncode, "stdout": proc.stdout[-self.policy.max_output:],
                    "stderr": proc.stderr[-self.policy.max_output:], "duration": time.monotonic() - started}
        except subprocess.TimeoutExpired as exc:
            return {"returncode": None, "stdout": str(exc.stdout or "")[-self.policy.max_output:],
                    "stderr": "sandbox timeout", "duration": time.monotonic() - started, "timeout": True}


@dataclass(slots=True)
class ModelCandidate:
    name: str
    provider: str
    capabilities: set[str] = field(default_factory=set)
    priority: int = 0


class ModelRouter:
    def __init__(self, models: Iterable[ModelCandidate] = ()) -> None:
        self.models = list(models)

    def choose(self, capability: str = "general") -> ModelCandidate | None:
        matches = [m for m in self.models if capability in m.capabilities or "general" in m.capabilities]
        return max(matches, key=lambda m: m.priority, default=None)

    def add(self, model: ModelCandidate) -> None:
        self.models.append(model)


@dataclass(slots=True)
class RecoveryPolicy:
    max_attempts: int = 3
    backoff_seconds: float = 0.5


class RecoveryController:
    def __init__(self, policy: RecoveryPolicy | None = None, trace: TraceRecorder | None = None) -> None:
        self.policy = policy or RecoveryPolicy()
        self.trace = trace

    def run(self, operation: Callable[[], Any]) -> tuple[bool, Any, int]:
        last_error: Exception | None = None
        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                result = operation()
                if self.trace:
                    self.trace.record("recovery", "attempt", attempt=attempt, status="success")
                return True, result, attempt
            except Exception as exc:
                last_error = exc
                if self.trace:
                    self.trace.record("recovery", "attempt", "error", attempt=attempt, error=str(exc))
                if attempt < self.policy.max_attempts:
                    time.sleep(self.policy.backoff_seconds * attempt)
        return False, last_error, self.policy.max_attempts


class AgentRuntime:
    def __init__(self, trace_path: str | None = None) -> None:
        self.trace = TraceRecorder([JsonlTrace(trace_path)])
        self.context = ContextManager()
        self.approvals = ApprovalGate()
        self.team = AgentTeam(self.trace)
        self.recovery = RecoveryController(trace=self.trace)
        self.models = ModelRouter()
        self.sandbox = Sandbox()

    def checkpoint(self) -> dict[str, Any]:
        return {"context": [asdict(i) for i in self.context.items],
                "pending_approvals": [asdict(i) for i in self.approvals.pending.values() if i.status == "pending"],
                "models": [asdict(m) | {"capabilities": sorted(m.capabilities)} for m in self.models.models]}

    def save_checkpoint(self, path: str | os.PathLike[str]) -> None:
        Path(path).write_text(json.dumps(self.checkpoint(), indent=2, default=str), encoding="utf-8")

    def load_checkpoint(self, path: str | os.PathLike[str]) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.context.items = [ContextItem(**item) for item in data.get("context", [])]
        for item in data.get("pending_approvals", []):
            req = ApprovalRequest(**item)
            self.approvals.pending[req.id] = req
        for item in data.get("models", []):
            item["capabilities"] = set(item.get("capabilities", []))
            self.models.add(ModelCandidate(**item))
