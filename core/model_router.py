from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ModelClient(Protocol):
    def ask(self, prompt: str) -> str: ...


@dataclass(frozen=True, slots=True)
class ModelChoice:
    name: str
    reason: str


class ModelRouter:
    """Select a model by task complexity without weakening safety policy.

    The router only chooses a reasoning backend. Tool permissions, sandbox
    policy, and confirmation remain outside the model and are never delegated
    to it.
    """

    def __init__(self, local: ModelClient | None = None, frontier: ModelClient | None = None) -> None:
        self.local = local
        self.frontier = frontier

    @staticmethod
    def complexity(prompt: str) -> int:
        text = prompt.lower()
        score = 0
        score += min(4, len(text) // 180)
        score += 2 if any(x in text for x in ("plan", "analyze", "debug", "architect", "compare")) else 0
        score += 2 if any(x in text for x in ("multiple", "step", "workflow", "automate")) else 0
        score += 2 if any(x in text for x in ("codebase", "repository", "security", "incident")) else 0
        return min(score, 10)

    def choose(self, prompt: str) -> ModelChoice:
        score = self.complexity(prompt)
        if self.frontier is not None and score >= 5:
            return ModelChoice("frontier", f"complexity={score}")
        if self.local is not None:
            return ModelChoice("local", f"complexity={score}")
        if self.frontier is not None:
            return ModelChoice("frontier", "local model unavailable")
        raise RuntimeError("No model backend is configured")

    def ask(self, prompt: str) -> str:
        choice = self.choose(prompt)
        client = self.frontier if choice.name == "frontier" else self.local
        if client is None:
            raise RuntimeError(f"Selected model backend unavailable: {choice.name}")
        return client.ask(prompt)
