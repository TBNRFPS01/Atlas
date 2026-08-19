"""Lightweight transactional checkpoints for ATLAS stateful tasks."""
from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any


@dataclass
class Checkpoint:
    id: str
    label: str
    created_at: float = field(default_factory=time)
    metadata: dict[str, Any] = field(default_factory=dict)


class CheckpointStore:
    """Records bounded checkpoints that higher-level tools can attach undo actions to."""

    def __init__(self, max_checkpoints: int = 100) -> None:
        self.max_checkpoints = max(1, max_checkpoints)
        self._items: list[Checkpoint] = []

    def create(self, checkpoint_id: str, label: str, **metadata: Any) -> Checkpoint:
        checkpoint = Checkpoint(checkpoint_id, label, metadata=metadata)
        self._items.append(checkpoint)
        if len(self._items) > self.max_checkpoints:
            self._items = self._items[-self.max_checkpoints :]
        return checkpoint

    def latest(self) -> Checkpoint | None:
        return self._items[-1] if self._items else None

    def get(self, checkpoint_id: str) -> Checkpoint | None:
        return next((item for item in reversed(self._items) if item.id == checkpoint_id), None)

    def list(self) -> list[Checkpoint]:
        return list(self._items)
