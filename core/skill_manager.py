"""Declarative, discoverable, permission-aware skill packages for ATLAS."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Callable

from core.permissions import Decision, PermissionManager
from core.safety import HardSafety


BUILTIN_SKILLS = frozenset({"hello", "browser", "spotify", "minecraft", "coding"})

_FORBIDDEN_CAP_PREFIXES = (
    "fs:", "file:write", "file:delete", "file:append", "file:format",
    "shell:", "exec:", "subprocess:", "os.system",
    "network:unrestricted", "network:raw",
    "browser:", "browser:control",
    "secrets:", "credentials:", "auth:", "token:", "destructive:",
    "automation:process_kill", "automation:windows_close", "automation:windows_kill",
    "automation:shutdown", "system:shutdown", "system:reboot", "format:",
)
_FORBIDDEN_CAP_EXACT = frozenset(
    {"file:write", "file:delete", "shell", "exec", "destructive", "secrets", "credentials"}
)
REQUIRED_MANIFEST_FIELDS = ("name", "version", "description", "triggers")


class SkillLoadError(Exception):
    """Raised when a skill package cannot be parsed or is fundamentally invalid."""


def _is_forbidden_capability(capability: str) -> bool:
    cap = (capability or "").lower()
    if cap in _FORBIDDEN_CAP_EXACT:
        return True
    return any(cap.startswith(prefix) for prefix in _FORBIDDEN_CAP_PREFIXES)


def _parse_version(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in str(version).split("."):
        num = ""
        for ch in piece:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    return tuple(parts)


class Skill:
    """A loaded skill package."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        triggers: list[str],
        *,
        dependencies: list[str] | None = None,
        permissions: list[str] | None = None,
        tools: list[str] | None = None,
        run: Callable[[Any, str], str] | None = None,
        trusted: bool = False,
        path: str | None = None,
        valid: bool = True,
        error: str = "",
        requires_llm: bool = False,
    ) -> None:
        self.name = name
        self.version = version
        self.description = description
        self.triggers = list(triggers)
        self.dependencies = list(dependencies or [])
        self.permissions = list(permissions or [])
        self.tools = list(tools or [])
        self.run = run
        self.trusted = trusted
        self.path = path
        self.valid = valid
        self.error = error
        self.enabled = valid
        self.requires_llm = requires_llm
        self.trigger = self.triggers[0] if self.triggers else ""

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def matches(self, lowered_prompt: str) -> bool:
        for trigger in self.triggers:
            if not trigger:
                continue
            if trigger.startswith("^"):
                if lowered_prompt.startswith(trigger[1:]):
                    return True
            elif trigger in lowered_prompt:
                return True
        return False

    def to_legacy_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger,
            "triggers": self.triggers,
            "version": self.version,
            "run": self.run,
        }

    def __repr__(self) -> str:
        state = "valid" if self.valid else f"invalid({self.error})"
        trust = "trusted" if self.trusted else "untrusted"
        return f"<Skill {self.name} v{self.version} {trust} {state}>"


class SkillManager:
    """Discovers, validates, loads, and supervises ATLAS skills."""

    def __init__(
        self,
        skills_dir: str = "skills",
        *,
        trusted: set[str] | None = None,
        permission_manager: PermissionManager | None = None,
        safety: HardSafety | None = None,
        registry: Any | None = None,
    ) -> None:
        self._skills_dir = Path(skills_dir)
        self._trusted = set(trusted if trusted is not None else BUILTIN_SKILLS)
        self._permissions = permission_manager
        self._safety = safety
        self._registry = registry
        self._skills: dict[str, Skill] = {}
        self._rejected: list[Skill] = []

    def discover(self) -> list[Path]:
        if not self._skills_dir.exists():
            return []
        return [
            child for child in sorted(self._skills_dir.iterdir())
            if child.is_dir() and (child / "skill.json").exists()
        ]

    def load_all(self) -> list[Skill]:
        self._skills.clear()
        self._rejected.clear()
        candidates: list[tuple[Path, dict[str, Any]]] = []
        for skill_dir in self.discover():
            try:
                manifest = self._read_manifest(skill_dir / "skill.json")
            except SkillLoadError as exc:
                self._rejected.append(Skill(
                    name=skill_dir.name, version="0.0.0", description="", triggers=[],
                    valid=False, error=str(exc), path=str(skill_dir),
                ))
                continue
            candidates.append((skill_dir, manifest))
        for skill_dir, manifest in candidates:
            self._register(self._build_skill(skill_dir, manifest))
        return self.list()

    def _register(self, skill: Skill) -> None:
        existing = self._skills.get(skill.name)
        if existing is None:
            self._skills[skill.name] = skill
            return
        if _parse_version(skill.version) > _parse_version(existing.version):
            self._skills[skill.name] = skill
            existing.enabled = False
            existing.valid = False
            existing.error = (
                f"duplicate skill name '{skill.name}'; "
                f"using v{skill.version} over v{existing.version}"
            )
            self._rejected.append(existing)
        else:
            skill.enabled = False
            skill.valid = False
            skill.error = (
                f"duplicate skill name '{skill.name}'; "
                f"using v{existing.version} over v{skill.version}"
            )
            self._rejected.append(skill)

    def _read_manifest(self, path: Path) -> dict[str, Any]:
        try:
            raw = path.read_text(encoding="utf-8")
            manifest = json.loads(raw)
        except OSError as exc:
            raise SkillLoadError(f"cannot read manifest: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise SkillLoadError(f"malformed skill.json: {exc}") from exc
        if not isinstance(manifest, dict):
            raise SkillLoadError("skill.json must be a JSON object")
        missing = [f for f in REQUIRED_MANIFEST_FIELDS if not manifest.get(f)]
        if missing:
            raise SkillLoadError(f"missing required manifest field(s): {', '.join(missing)}")
        return manifest

    @staticmethod
    def _manifest_requires_llm(manifest: dict[str, Any]) -> bool:
        value = manifest.get("requires_llm", False)
        if isinstance(value, bool):
            return value
        # Invalid/malformed values fail closed to the deterministic path being
        # unavailable. Treating non-booleans as True prevents accidental bypass.
        return True

    def _build_skill(self, skill_dir: Path, manifest: dict[str, Any]) -> Skill:
        name = str(manifest["name"])
        trusted = name in self._trusted
        requires_llm = self._manifest_requires_llm(manifest)
        common = dict(
            name=name,
            version=str(manifest.get("version", "0.0.0")),
            description=str(manifest.get("description", "")),
            triggers=list(manifest.get("triggers", [])),
            dependencies=manifest.get("dependencies", []),
            permissions=manifest.get("permissions", []),
            tools=manifest.get("tools", []),
            trusted=trusted,
            path=str(skill_dir),
            requires_llm=requires_llm,
        )

        missing_deps = self.validate_dependencies(name, manifest.get("dependencies", []))
        if missing_deps:
            return Skill(**common, valid=False, error=f"missing dependencies: {', '.join(missing_deps)}")

        forbidden = [c for c in manifest.get("permissions", []) if _is_forbidden_capability(c)]
        if forbidden and not trusted:
            return Skill(
                **common,
                valid=False,
                error=f"untrusted skill requests forbidden capabilities: {', '.join(forbidden)}",
            )

        entry = str(manifest.get("entry", "run"))
        run_func = self._load_entry(skill_dir, entry)
        if run_func is None:
            return Skill(
                **common,
                valid=False,
                error=f"skill entry '{entry}' not found or not callable",
            )

        return Skill(**common, run=run_func, valid=True)

    def _load_entry(self, skill_dir: Path, entry: str) -> Callable[[Any, str], str] | None:
        module_path = skill_dir / "skill.py"
        if not module_path.exists():
            return None
        try:
            spec = importlib.util.spec_from_file_location(f"_atlas_skill_{skill_dir.name}", module_path)
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            func = getattr(module, entry, None)
            return func if callable(func) else None
        except Exception:
            return None

    def validate_dependencies(self, name: str, dependencies: list[str]) -> list[str]:
        missing: list[str] = []
        for dep in dependencies or []:
            if not self._dependency_met(dep):
                missing.append(dep)
        return missing

    def _dependency_met(self, dep: str) -> bool:
        if self._registry is not None:
            try:
                if self._registry.get(dep) is not None:
                    return True
            except Exception:
                pass
        try:
            return importlib.util.find_spec(dep) is not None
        except Exception:
            return False

    def request_permission(self, name: str, capability: str) -> str:
        skill = self._skills.get(name)
        if skill is None:
            return Decision.DENY
        if not skill.trusted and _is_forbidden_capability(capability):
            return Decision.DENY
        if self._safety is not None:
            tool, _, action = capability.partition(":")
            if not self._safety.is_safe(tool or "skill", action or capability):
                return Decision.DENY
        if self._permissions is not None:
            return self._permissions.decide("skill", capability, permission_level="basic")
        return Decision.ALLOW

    def can_run(self, skill: Skill) -> tuple[bool, str]:
        if not skill.valid:
            return False, skill.error or "skill is invalid"
        if not skill.enabled:
            return False, "skill is disabled"
        if not skill.trusted:
            forbidden = [c for c in skill.permissions if _is_forbidden_capability(c)]
            if forbidden:
                return False, f"untrusted skill requests forbidden capabilities: {forbidden}"
        return True, ""

    def unload(self, name: str) -> bool:
        skill = self._skills.pop(name, None)
        if skill is None:
            self._rejected = [s for s in self._rejected if s.name != name]
            return False
        skill.enabled = False
        return True

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list(self) -> list[Skill]:
        return list(self._skills.values())

    def all_skills(self) -> list[Skill]:
        return list(self._skills.values()) + self._rejected

    def status(self) -> dict[str, Any]:
        active = []
        for skill in self._skills.values():
            active.append({
                "name": skill.name,
                "version": skill.version,
                "description": skill.description,
                "trusted": skill.trusted,
                "enabled": skill.enabled,
                "valid": skill.valid,
                "error": skill.error,
                "requires_llm": skill.requires_llm,
                "permissions": skill.permissions,
                "dependencies": skill.dependencies,
                "triggers": skill.triggers,
                "tools": skill.tools,
            })
        rejected = [
            {"name": s.name, "version": s.version, "error": s.error}
            for s in self._rejected
        ]
        return {"count": len(active), "skills": active, "rejected": rejected}
