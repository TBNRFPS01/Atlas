"""Evidence-based post-action verification for ATLAS."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNVERIFIED = "unverified"


@dataclass
class VerificationResult:
    status: VerificationStatus
    evidence: list[str] = field(default_factory=list)
    details: str = ""


class VerificationEngine:
    """Runs lightweight, explicit checks after an action.

    Verifiers are supplied by the caller so the engine never invents evidence.
    A verifier may return bool, ``(bool, evidence)``, or ``VerificationResult``.
    """

    def verify(self, verifier: Callable[[], Any] | None, *, action_succeeded: bool, blocked: bool = False) -> VerificationResult:
        if blocked:
            return VerificationResult(VerificationStatus.BLOCKED, ["Action was blocked by policy or permissions."])
        if not action_succeeded:
            return VerificationResult(VerificationStatus.FAILED, ["Action execution reported failure."])
        if verifier is None:
            return VerificationResult(VerificationStatus.UNVERIFIED, ["Action succeeded, but no independent verifier was available."])
        try:
            value = verifier()
            if isinstance(value, VerificationResult):
                return value
            if isinstance(value, tuple):
                ok, evidence = value
                evidence_list = [str(x) for x in (evidence if isinstance(evidence, (list, tuple)) else [evidence])]
                return VerificationResult(VerificationStatus.VERIFIED if ok else VerificationStatus.FAILED, evidence_list)
            return VerificationResult(VerificationStatus.VERIFIED if bool(value) else VerificationStatus.FAILED)
        except Exception as exc:
            return VerificationResult(VerificationStatus.UNVERIFIED, [f"Verifier error: {exc}"])
