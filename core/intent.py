"""Fast deterministic intent extraction for common ATLAS commands."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass(frozen=True)
class Intent:
    name: str
    target: str | None = None
    arguments: dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0
    skill: Any | None = None
    requires_llm: bool = False


class IntentExtractor:
    """Extract unambiguous local commands without consulting an LLM.

    Built-in commands remain deterministic. Skill-provided triggers are
    registered at runtime by ``FastIntentRouter``.
    """

    _PATTERNS = (
        ("open_app", re.compile(r"^(?:open|launch|start)\s+(.+)$", re.I)),
        ("close_app", re.compile(r"^(?:close|quit|exit)\s+(.+)$", re.I)),
        ("take_screenshot", re.compile(r"^(?:take|capture)\s+(?:a\s+)?screenshot$", re.I)),
        ("lock_system", re.compile(r"^(?:lock|lock the|lock my)\s+(?:pc|computer|system)$", re.I)),
        ("volume_up", re.compile(r"^(?:volume|turn (?:the )?volume)\s+up$", re.I)),
        ("volume_down", re.compile(r"^(?:volume|turn (?:the )?volume)\s+down$", re.I)),
        ("media_play_pause", re.compile(r"^(?:play|pause|play/pause|toggle music)$", re.I)),
    )

    def extract(self, prompt: str) -> Intent | None:
        text = " ".join(prompt.strip().split())
        for name, pattern in self._PATTERNS:
            match = pattern.fullmatch(text)
            if not match:
                continue
            target = match.group(1).strip() if match.lastindex else None
            return Intent(name=name, target=target)
        return None
