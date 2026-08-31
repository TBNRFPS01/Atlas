"""Task-aware intelligence routing for ATLAS.

Inspired by routing/failover patterns observed in the user's MIRA, OpenAgent,
Hearth, and Web Agent forks. This is an ATLAS-native implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
import time
from typing import Any


class TaskKind(str, Enum):
    CHAT = "chat"
    CODING = "coding"
    REASONING = "reasoning"
    RESEARCH = "research"
    VISION = "vision"
    ACTION = "action"
    CREATIVE = "creative"


@dataclass(slots=True)
class RouteDecision:
    provider: str
    model: str | None
    task: TaskKind
    confidence: float
    reason: str


@dataclass(slots=True)
class ProviderHealth:
    failures: int = 0
    last_failure: float = 0.0
    cooldown_until: float = 0.0
    last_success: float = 0.0

    def available(self) -> bool:
        return time.time() >= self.cooldown_until

    def success(self) -> None:
        self.failures = 0
        self.last_success = time.time()
        self.cooldown_until = 0.0

    def failure(self, cooldown: float = 5.0) -> None:
        self.failures += 1
        self.last_failure = time.time()
        self.cooldown_until = time.time() + min(cooldown * (2 ** max(0, self.failures - 1)), 300.0)


@dataclass
class SmartRouter:
    """Small deterministic router that can sit above any provider abstraction."""

    local_provider: str = "local"
    cloud_provider: str = "openrouter"
    local_model: str | None = None
    fast_model: str | None = None
    reasoning_model: str | None = None
    coding_model: str | None = None
    vision_model: str | None = None
    prefer_local: bool = True
    health: dict[str, ProviderHealth] = field(default_factory=dict)

    _patterns: dict[TaskKind, tuple[str, ...]] = field(default_factory=lambda: {
        TaskKind.CODING: (r"\b(code|coding|python|javascript|typescript|bug|debug|refactor|implement|function|class|repository|repo|git|program)\b",),
        TaskKind.REASONING: (r"\b(why|prove|derive|reason|reasoning|compare|tradeoff|architecture|complex|analy[sz]e|deeply|step[- ]by[- ]step)\b",),
        TaskKind.RESEARCH: (r"\b(search|research|latest|current|look up|find out|sources|cite|documentation|docs|news)\b",),
        TaskKind.VISION: (r"\b(image|screenshot|screen|photo|picture|what do you see|ocr|visual)\b",),
        TaskKind.ACTION: (r"\b(open|close|launch|run|execute|delete|create|move|rename|install|click|type|download|send)\b",),
        TaskKind.CREATIVE: (r"\b(write|story|poem|design|brainstorm|creative|imagine|caption)\b",),
    })

    def classify(self, prompt: str) -> tuple[TaskKind, float]:
        text = prompt.lower()
        scores: dict[TaskKind, int] = {kind: 0 for kind in TaskKind}
        for kind, patterns in self._patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    scores[kind] += 1
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return TaskKind.CHAT, 0.55
        confidence = min(0.95, 0.60 + scores[best] * 0.10)
        return best, confidence

    def _healthy(self, provider: str) -> bool:
        return self.health.setdefault(provider, ProviderHealth()).available()

    def record_success(self, provider: str) -> None:
        self.health.setdefault(provider, ProviderHealth()).success()

    def record_failure(self, provider: str, cooldown: float = 5.0) -> None:
        self.health.setdefault(provider, ProviderHealth()).failure(cooldown)

    def choose(self, prompt: str, available_providers: set[str] | None = None) -> RouteDecision:
        available = available_providers or {self.local_provider, self.cloud_provider}
        task, confidence = self.classify(prompt)

        # Private/local-sensitive requests should stay local whenever possible.
        sensitive = bool(re.search(r"\b(password|secret|private key|api key|personal file|private file)\b", prompt, re.I))
        if sensitive and self.local_provider in available and self._healthy(self.local_provider):
            return RouteDecision(self.local_provider, self.local_model, task, 0.98, "sensitive request prefers local execution")

        if task == TaskKind.VISION and self.cloud_provider in available and self._healthy(self.cloud_provider):
            return RouteDecision(self.cloud_provider, self.vision_model, task, confidence, "vision workload prefers a vision-capable cloud model")

        if task == TaskKind.CODING and self.cloud_provider in available and self._healthy(self.cloud_provider):
            return RouteDecision(self.cloud_provider, self.coding_model, task, confidence, "coding workload prefers the configured coding model")

        if task in {TaskKind.REASONING, TaskKind.RESEARCH} and self.cloud_provider in available and self._healthy(self.cloud_provider):
            return RouteDecision(self.cloud_provider, self.reasoning_model, task, confidence, "complex workload prefers a stronger cloud model")

        if self.prefer_local and self.local_provider in available and self._healthy(self.local_provider):
            return RouteDecision(self.local_provider, self.local_model, task, confidence, "local-first default")

        if self.cloud_provider in available and self._healthy(self.cloud_provider):
            return RouteDecision(self.cloud_provider, self.fast_model or self.reasoning_model, task, confidence, "local provider unavailable; cloud fallback")

        # Return a deterministic choice even when health says everything is down.
        provider = self.local_provider if self.local_provider in available else self.cloud_provider
        return RouteDecision(provider, self.local_model if provider == self.local_provider else self.fast_model, task, 0.20, "all providers are unhealthy; caller should surface the failure")

    def explain(self, prompt: str, available_providers: set[str] | None = None) -> str:
        decision = self.choose(prompt, available_providers)
        model = decision.model or "configured model"
        return f"{decision.task.value} → {decision.provider}/{model} ({decision.reason})"
