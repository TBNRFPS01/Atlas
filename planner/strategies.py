"""Adaptive strategy selection for ATLAS planning.

ATLAS classifies the kind of work a goal belongs to, chooses a proven
strategy for it (using experience when available), and produces a plain-text
hint the planner injects so the LLM favours approaches that have worked
before.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class StrategySelection:
    """Outcome of :meth:`StrategySelector.select`."""

    task_type: str
    strategy_key: str
    strategy: str
    hint: str

    def to_dict(self) -> dict[str, str]:
        return {
            "task_type": self.task_type,
            "strategy_key": self.strategy_key,
            "strategy": self.strategy,
            "hint": self.hint,
        }


class StrategySelector:
    """Classify goals and pick an approach, preferring proven strategies.

    ``experiences`` is an optional :class:`memory.experience.ExperienceStore`.
    When present and a strategy for the task type has enough successful runs,
    the selector biases toward it instead of the built-in default.
    """

    TASK_TYPES = (
        "email", "minecraft", "media", "system", "vision", "browser",
        "file", "web", "automation", "general",
    )

    # (strategy_key, human description)
    DEFAULTS: dict[str, tuple[str, str]] = {
        "email": ("email", "Use the email tool with validation: recipient, subject, and body."),
        "minecraft": ("minecraft", "Check Minecraft server status with the minecraft tool."),
        "media": ("spotify", "Control media/Spotify playback with the spotify tool."),
        "system": ("system", "Query system/hardware info with the system tool."),
        "vision": ("vision", "Capture and inspect the screen with screenshots and the vision tool."),
        "browser": ("browser", "Operate real websites with the browser tool (navigate, click, type, fill)."),
        "file": ("file", "Work with files and folders via the file tool (read/write/append/list)."),
        "web": ("web", "Research with web search/fetch; use the web tool first."),
        "automation": ("automation", "Drive the computer itself with the automation tool (windows, keyboard, mouse)."),
        "general": ("llm", "Use the LLM directly; decompose into the smallest safe actions."),
    }

    def _classify(self, goal: str) -> str:
        lowered = goal.lower()

        if "email" in lowered or "send mail" in lowered or "send an email" in lowered:
            return "email"
        if "minecraft" in lowered:
            return "minecraft"
        if "spotify" in lowered or "media" in lowered:
            return "media"
        if any(k in lowered for k in ("system info", "hardware", "computer info", "cpu", "ping")):
            return "system"
        if any(k in lowered for k in ("screenshot", "screen", "ocr", "camera", "vision", "take a photo")):
            return "vision"
        if any(k in lowered for k in (
            "browser", "navigate to", "browse to", "click on", "type into",
            "fill form", "open website", "open url", "fetch url for site",
        )):
            return "browser"
        if any(k in lowered for k in ("read file", "write file", "append", "delete file",
                                      "list folder", "list directory", "create file", "folder", "directory")):
            return "file"
        if any(k in lowered for k in ("search the web", "web search", "look up", "research",
                                      "what is", "find", "fetch url", "google")):
            return "web"
        if any(k in lowered for k in ("open ", "launch ", "start ", "type ", "press ", "click ",
                                      "window", "process", "keyboard", "mouse", "clipboard", "the screen")):
            return "automation"
        return "general"

    def classify(self, goal: str) -> str:
        return self._classify(goal or "")

    def select(
        self,
        goal: str,
        experiences: Any | None = None,
        min_runs: int = 2,
        success_threshold: float = 0.5,
    ) -> StrategySelection:
        """Choose the strategy for ``goal``.

        A stored strategy is preferred only when it has enough runs AND
        performs at or above ``success_threshold``; otherwise the built-in
        default for the task type is used.
        """
        task_type = self.classify(goal)
        default_key, default_strategy = self.DEFAULTS.get(task_type, self.DEFAULTS["general"])

        chosen_key, chosen_strategy = default_key, default_strategy
        if experiences is not None:
            known = experiences.best_strategy(task_type, min_runs=min_runs)
            if known and known.get("avg_success", 0.0) >= success_threshold:
                chosen_key = known.get("strategy_key") or default_key
                chosen_strategy = known.get("strategy") or default_strategy

        hint = (
            f"Strategy hint: this is a '{task_type}' task. Proven approach: "
            f"{chosen_strategy}"
        )
        return StrategySelection(
            task_type=task_type,
            strategy_key=chosen_key,
            strategy=chosen_strategy,
            hint=hint,
        )