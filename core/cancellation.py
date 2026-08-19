"""Cooperative cancellation primitives for long-running ATLAS work."""
from __future__ import annotations


class CancellationToken:
    def __init__(self) -> None:
        self._cancelled = False
        self.reason = ""

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self, reason: str = "cancelled") -> None:
        self._cancelled = True
        self.reason = reason

    def raise_if_cancelled(self) -> None:
        if self._cancelled:
            raise RuntimeError(f"Task cancelled: {self.reason}")
