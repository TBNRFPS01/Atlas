"""Deterministic fast path for unambiguous assistant commands."""
from __future__ import annotations

from core.intent import Intent, IntentExtractor


class FastIntentRouter:
    def __init__(self, extractor: IntentExtractor | None = None) -> None:
        self.extractor = extractor or IntentExtractor()

    def route(self, prompt: str) -> Intent | None:
        return self.extractor.extract(prompt)

    @staticmethod
    def to_dispatch(intent: Intent) -> str | None:
        """Translate supported fast intents to the existing Router tool syntax."""
        if intent.name == "open_app" and intent.target:
            return f"open {intent.target}"
        if intent.name == "close_app" and intent.target:
            return f"close {intent.target}"
        if intent.name == "take_screenshot":
            return "take screenshot"
        if intent.name == "lock_system":
            return "lock computer"
        if intent.name == "volume_up":
            return "volume up"
        if intent.name == "volume_down":
            return "volume down"
        if intent.name == "media_play_pause":
            return "play pause"
        return None
