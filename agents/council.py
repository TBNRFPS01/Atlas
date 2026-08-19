"""Independent multi-agent review for high-stakes ATLAS decisions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .subagents import AgentResult, AgentSpec, SubagentRegistry


@dataclass
class CouncilDecision:
    decision: Any
    votes: list[AgentResult]
    confidence: float


class AgentCouncil:
    def __init__(self, registry: SubagentRegistry | None = None) -> None:
        self.registry = registry or SubagentRegistry()

    def deliberate(self, names: list[str], task: Any, judge: Callable[[list[AgentResult], Any], tuple[Any, float]]) -> CouncilDecision:
        votes: list[AgentResult] = []
        for name in names:
            votes.append(self.registry.run_isolated(name, lambda spec: {"role": spec.role, "task": task}))
        decision, confidence = judge(votes, task)
        return CouncilDecision(decision, votes, confidence)
