from __future__ import annotations

"""Unified execution guard for ATLAS tool actions.

Keeps execution concerns in one place: dry-run, loop detection, retries,
verification, checkpoints, and a compact audit trail. The router remains the
policy owner and passes already-authorized actions here.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable


@dataclass
class ExecutionResult:
    ok: bool
    result: Any = ""
    attempts: int = 1
    verified: bool = False
    error: str = ""
    dry_run: bool = False
    observation: Any = None
    verification: str = "unavailable"


class ExecutionPipeline:
    """Run approved actions consistently and detect obvious non-progress."""

    def __init__(self, *, max_retries: int = 1, dry_run: bool = False, history_limit: int = 100) -> None:
        self.max_retries = max(0, int(max_retries))
        self.dry_run = bool(dry_run)
        self.history_limit = max(10, int(history_limit))
        self.history: list[dict[str, Any]] = []
        self.checkpoints: list[dict[str, Any]] = []

    def set_dry_run(self, enabled: bool) -> None:
        self.dry_run = bool(enabled)

    def is_looping(self, signature: str, window: int = 4) -> bool:
        recent = [x.get("signature") for x in self.history[-window:]]
        return recent.count(signature) >= max(2, window - 1)

    def checkpoint(self, label: str, state: Any = None) -> None:
        self.checkpoints.append({
            "label": label,
            "state": state,
            "time": datetime.now().isoformat(timespec="seconds"),
        })
        if len(self.checkpoints) > self.history_limit:
            del self.checkpoints[:-self.history_limit]

    def run(
        self,
        tool: str,
        action: str,
        fn: Callable[[], Any],
        *,
        verify: Callable[[Any], bool] | None = None,
        observe: Callable[[Any], Any] | None = None,
        signature: str | None = None,
        description: str | None = None,
        intent: str = "",
        permission_decision: str = "allow",
        safety_decision: str = "allow",
    ) -> ExecutionResult:
        signature = signature or f"{tool}:{action}:{description or ''}".strip(":")
        if self.is_looping(signature):
            message = f"Execution stopped: repeated action detected ({tool}.{action})."
            self._record(tool, action, signature, False, message, 0, intent=intent,
                         permission_decision=permission_decision, safety_decision=safety_decision,
                         verification="unavailable")
            return ExecutionResult(False, message, attempts=0, error=message)

        if self.dry_run:
            message = f"DRY RUN: would execute {tool}.{action}"
            self._record(tool, action, signature, True, message, 0, dry_run=True, intent=intent,
                         permission_decision=permission_decision, safety_decision=safety_decision,
                         verification="unavailable")
            return ExecutionResult(True, message, attempts=0, verified=False, dry_run=True)

        self.checkpoint(f"before:{tool}.{action}")
        last_error = ""
        attempts = 0
        for attempts in range(1, self.max_retries + 2):
            try:
                result = fn()
                observation = observe(result) if observe is not None else None
                verification = "unavailable" if verify is None else "failed"
                verified = False if verify is None else bool(verify(observation if observe is not None else result))
                if verified:
                    verification = "verified"
                if verified:
                    self._record(tool, action, signature, True, result, attempts, intent=intent,
                                 permission_decision=permission_decision, safety_decision=safety_decision,
                                 observation=observation, verification=verification)
                    self.checkpoint(f"after:{tool}.{action}", {"result": str(result)[:500]})
                    return ExecutionResult(True, result, attempts=attempts, verified=True,
                                           observation=observation, verification=verification)
                if verify is None:
                    self._record(tool, action, signature, True, result, attempts, intent=intent,
                                 permission_decision=permission_decision, safety_decision=safety_decision,
                                 observation=observation, verification=verification)
                    self.checkpoint(f"after:{tool}.{action}", {"result": str(result)[:500]})
                    return ExecutionResult(True, result, attempts=attempts, verified=False,
                                           observation=observation, verification=verification)
                last_error = "Verification failed"
            except Exception as exc:  # tool failures are contained at the boundary
                last_error = str(exc)

        message = f"{tool}.{action} failed after {attempts} attempt(s): {last_error}"
        self._record(tool, action, signature, False, message, attempts, intent=intent,
                     permission_decision=permission_decision, safety_decision=safety_decision,
                     verification="failed")
        return ExecutionResult(False, message, attempts=attempts, verified=False, error=last_error,
                               verification="failed")

    def record_denial(self, tool: str, action: str, *, intent: str, permission_decision: str,
                      safety_decision: str, result: str) -> ExecutionResult:
        self._record(tool, action, f"{tool}:{action}", False, result, 0, intent=intent,
                     permission_decision=permission_decision, safety_decision=safety_decision,
                     verification="unavailable")
        return ExecutionResult(False, result, attempts=0, error=result, verification="unavailable")

    def _record(self, tool: str, action: str, signature: str, ok: bool, result: Any, attempts: int, *, dry_run: bool = False,
                intent: str = "", permission_decision: str = "allow", safety_decision: str = "allow",
                observation: Any = None, verification: str = "unavailable") -> None:
        self.history.append({
            "time": datetime.now().isoformat(timespec="seconds"),
            "tool": tool,
            "action": action,
            "signature": signature,
            "ok": ok,
            "attempts": attempts,
            "result": str(result)[:1000],
            "dry_run": dry_run,
            "intent": intent,
            "permissions": permission_decision,
            "safety": safety_decision,
            "execution_result": str(result)[:1000],
            "observation": observation,
            "verification": verification,
            "recovery": {"attempts": attempts, "retried": attempts > 1},
        })
        if len(self.history) > self.history_limit:
            del self.history[:-self.history_limit]

    def report(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "history": list(self.history[-20:]),
            "checkpoints": list(self.checkpoints[-20:]),
        }
