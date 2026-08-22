"""Deterministic fast path for unambiguous assistant commands."""
from __future__ import annotations

from collections.abc import Iterable

from core.intent import Intent, IntentExtractor


class FastIntentRouter:
    """Route built-in commands and eligible skill triggers without an LLM."""

    def __init__(
        self,
        extractor: IntentExtractor | None = None,
        skills: Iterable[object] | None = None,
    ) -> None:
        self.extractor = extractor or IntentExtractor()
        self._skills: list[object] = []
        self.set_skills(skills or ())

    def set_skills(self, skills: Iterable[object]) -> None:
        """Replace the deterministic skill index with active skill objects."""
        self._skills = [
            skill for skill in skills
            if getattr(skill, "enabled", True) and getattr(skill, "valid", True)
        ]

    def route(self, prompt: str) -> Intent | None:
        """Return a deterministic intent, preferring built-ins over skills."""
        built_in = self.extractor.extract(prompt)
        if built_in is not None:
            return built_in

        text = " ".join(prompt.strip().lower().split())
        matches: list[object] = []
        for skill in self._skills:
            if getattr(skill, "requires_llm", False):
                continue
            if self._matches_skill(skill, text):
                matches.append(skill)

        # A deterministic route must be unambiguous. Multiple matching skills
        # fall through to the normal LLM path instead of guessing.
        if len(matches) != 1:
            return None

        skill = matches[0]
        return Intent(
            name="skill",
            target=str(getattr(skill, "name", "")),
            arguments={"prompt": prompt},
            confidence=1.0,
            skill=skill,
            requires_llm=False,
        )

    @staticmethod
    def _matches_skill(skill: object, text: str) -> bool:
        """Match the same manifest trigger semantics used by Skill.matches()."""
        for raw_trigger in getattr(skill, "triggers", ()):
            trigger = str(raw_trigger).lower()
            if not trigger.strip():
                continue
            if trigger.startswith("^"):
                if text.startswith(trigger[1:]):
                    return True
            elif trigger in text:
                return True
        return False

    @staticmethod
    def to_dispatch(intent: Intent) -> str | None:
        """Translate supported built-in fast intents to existing Router syntax."""
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
