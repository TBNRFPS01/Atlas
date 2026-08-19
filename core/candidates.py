"""Candidate generation, judging, and repair primitives."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass
class Candidate:
    value: Any
    score: float = 0.0
    reason: str = ""


class CandidatePipeline:
    def __init__(self, judge: Callable[[Candidate], Candidate], repair: Callable[[Candidate], Candidate] | None = None):
        self.judge = judge
        self.repair = repair

    def choose(self, candidates: Iterable[Candidate]) -> Candidate:
        items = list(candidates)
        if not items:
            raise ValueError("at least one candidate is required")
        best = self.judge(max(items, key=lambda c: c.score))
        return self.repair(best) if self.repair is not None else best
