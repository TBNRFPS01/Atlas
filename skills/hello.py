"""Example ATLAS skill.

Drop-in capability: replies whenever the prompt contains "say hi atlas".
See ``core/skills.py`` for the contract.
"""

from __future__ import annotations

from typing import Any


def _run(router: Any, prompt: str) -> str:
    return "Hello from the example skill! Skills let you extend ATLAS without touching core code."


SKILL = {
    "name": "hello",
    "description": "Replies with a friendly greeting when triggered.",
    "trigger": "say hi atlas",
    "run": _run,
}
