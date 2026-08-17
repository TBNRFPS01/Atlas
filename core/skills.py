"""Drop-in skills for ATLAS.

A skill is a small Python module placed in the ``skills/`` folder that exposes
a module-level ``SKILL`` dict::

    SKILL = {
        "name": "hello",
        "description": "Friendly greeting skill.",
        "trigger": "say hi atlas",     # phrase that activates the skill
        "run": lambda router, prompt: "Hello from the hello skill!",
    }

The router loads every skill at startup, lists them via ``/skills``, and
invokes a skill's ``run`` whenever its trigger phrase appears in a prompt.
This is the lightweight, dependency-free way to add capabilities without
editing the core router.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def load_skills(folder: str = "skills") -> list[dict[str, Any]]:
    """Discover and load all valid ``SKILL`` modules in ``folder``."""
    skills: list[dict[str, Any]] = []
    base = Path(folder)
    if not base.exists():
        return skills

    for path in sorted(base.glob("*.py")):
        if path.name.startswith("__"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(path.stem, path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            skill = getattr(module, "SKILL", None)
            if (
                isinstance(skill, dict)
                and skill.get("name")
                and skill.get("trigger")
                and callable(skill.get("run"))
            ):
                skills.append(skill)
        except Exception:
            # A broken skill must never break ATLAS startup.
            continue
    return skills
