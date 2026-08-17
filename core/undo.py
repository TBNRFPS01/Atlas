"""Reversible-action support for ATLAS.

Destructive or state-changing operations record an *inverse* here so the user
(or the autonomous planner) can roll them back with ``/undo``. Reversibility is
a core Level-10 property: computer control must be observable *and* undoable.
"""

from __future__ import annotations

from typing import Callable


class UndoStack:
    """LIFO stack of reversible operations with their inverses."""

    def __init__(self, limit: int = 50) -> None:
        self._stack: list[tuple[str, Callable[[], None]]] = []
        self._limit = limit

    def record(self, label: str, inverse: Callable[[], None]) -> None:
        """Store an undoable operation and its inverse callable."""
        self._stack.append((label, inverse))
        if len(self._stack) > self._limit:
            self._stack.pop(0)

    def undo(self) -> str:
        """Pop and apply the most recent reversible operation's inverse."""
        if not self._stack:
            return "Nothing to undo."
        label, inverse = self._stack.pop()
        try:
            inverse()
            return f"Undid: {label}"
        except Exception as exc:  # pragma: no cover - inverse failures are rare
            return f"Undo of '{label}' failed: {exc}"

    def can_undo(self) -> bool:
        return bool(self._stack)

    def clear(self) -> None:
        self._stack.clear()
