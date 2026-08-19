"""Legacy compatibility shim for loading ATLAS skills.

Historically a skill was a single ``SKILL``-dict module in the ``skills/``
folder. Skills are now declarative packages (``skill.json`` + ``skill.py``)
managed by :class:`core.skill_manager.SkillManager`. This module keeps the old
``load_skills()`` entry point working (it now returns lightweight dicts) so
existing imports/behaviour are preserved while the real logic lives in one place.
"""

from __future__ import annotations

from typing import Any

from core.skill_manager import SkillManager


def load_skills(folder: str = "skills") -> list[dict[str, Any]]:
    """Discover and load all valid skill packages, returning legacy dicts.

    Each dict exposes ``name``, ``description``, ``trigger``, and ``run`` so
    old callers (and tests) keep working unchanged.
    """
    manager = SkillManager(skills_dir=folder)
    manager.load_all()
    return [skill.to_legacy_dict() for skill in manager.list() if skill.valid]
