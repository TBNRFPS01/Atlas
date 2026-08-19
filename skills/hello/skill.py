"""Example ATLAS skill packaged as a declarative folder.

Triggered by the phrase "say hi atlas". See ``skill.json`` for the manifest.
"""

from __future__ import annotations

from typing import Any


def run(router: Any, prompt: str) -> str:
    return "Hello from the example skill! Skills let you extend ATLAS without touching core code."
