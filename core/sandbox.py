"""Defense-in-depth execution sandbox for ATLAS V1.

This is an application-level boundary, not a substitute for an OS/container
sandbox. It provides deterministic path, network, and resource policy checks
that can be enforced before a tool launches external work.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


class SandboxViolation(PermissionError):
    """Raised when an operation exceeds the configured sandbox policy."""


@dataclass(slots=True)
class SandboxPolicy:
    workspace: Path = field(default_factory=lambda: Path.cwd().resolve())
    allow_network: bool = False
    allowed_hosts: set[str] = field(default_factory=set)
    max_output_bytes: int = 2_000_000
    max_processes: int = 8

    def __post_init__(self) -> None:
        self.workspace = self.workspace.expanduser().resolve()

    def check_path(self, path: str | os.PathLike[str]) -> Path:
        target = Path(path).expanduser()
        # Resolve existing parents where possible and prevent traversal outside
        # the workspace. Non-existent targets are still checked lexically.
        resolved = target.resolve(strict=False)
        try:
            resolved.relative_to(self.workspace)
        except ValueError as exc:
            raise SandboxViolation(
                f"Sandbox denied path outside workspace: {resolved}"
            ) from exc
        return resolved

    def check_network(self, host: str) -> None:
        if not self.allow_network:
            raise SandboxViolation("Sandbox network access is disabled")
        if self.allowed_hosts and host.lower() not in {h.lower() for h in self.allowed_hosts}:
            raise SandboxViolation(f"Sandbox denied network host: {host}")

    def check_output_size(self, size: int) -> None:
        if size > self.max_output_bytes:
            raise SandboxViolation("Sandbox output limit exceeded")
