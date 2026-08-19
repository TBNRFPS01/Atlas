"""Versioned skill registry and lightweight dependency metadata."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SkillMetadata:
    name: str
    version: str = "0.1.0"
    description: str = ""
    entrypoint: str = "skill.py"
    dependencies: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)


class SkillRegistry:
    """Discover, validate and index versioned skills without installing them."""

    def __init__(self, root: str | Path = "skills") -> None:
        self.root = Path(root)
        self.skills: dict[str, SkillMetadata] = {}

    def discover(self) -> list[SkillMetadata]:
        self.skills.clear()
        if not self.root.exists():
            return []
        for manifest in self.root.glob("*/skill.json"):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                name = str(data.get("name") or manifest.parent.name)
                metadata = SkillMetadata(
                    name=name,
                    version=str(data.get("version", "0.1.0")),
                    description=str(data.get("description", "")),
                    entrypoint=str(data.get("entrypoint", "skill.py")),
                    dependencies=list(data.get("dependencies", [])),
                    capabilities=list(data.get("capabilities", [])),
                )
                if self.validate(metadata):
                    self.skills[name] = metadata
            except (OSError, ValueError, TypeError):
                continue
        return list(self.skills.values())

    def validate(self, metadata: SkillMetadata) -> bool:
        skill_dir = self.root / metadata.name
        entrypoint = skill_dir / metadata.entrypoint
        return bool(metadata.name and metadata.version and entrypoint.exists())

    def get(self, name: str) -> SkillMetadata | None:
        return self.skills.get(name)

    def capability_index(self) -> dict[str, list[str]]:
        index: dict[str, list[str]] = {}
        for skill in self.skills.values():
            for capability in skill.capabilities:
                index.setdefault(capability, []).append(skill.name)
        return index

    def export(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps([metadata.__dict__ for metadata in self.skills.values()], indent=2),
            encoding="utf-8",
        )
