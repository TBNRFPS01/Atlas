"""Declarative, discoverable, permission-aware skill packages for ATLAS.

A *skill* is a folder under ``skills/`` containing:

    skill.json   -- declarative manifest (metadata + capabilities)
    skill.py     -- optional entry module exposing a ``run(router, prompt)`` callable

``skill.json`` supports:

    {
      "name": "browser",
      "version": "1.0.0",
      "description": "...",
      "dependencies": ["browser"],            # tool names or importable modules
      "permissions": ["browser:navigate"],    # capabilities the skill REQUESTS
      "triggers": ["open browser", "^spotify "],
      "tools": ["browser"],
      "entry": "run"                          # optional, default "run"
    }

Security model
-------------
* A skill only *declares* the capabilities it wants. It never receives them
  automatically. Actual enforcement still flows through the existing
  :class:`~core.permissions.PermissionManager` and :class:`~core.safety.HardSafety`
  -- this module is an integration layer, not a second permission system.
* Built-in skills (a known, shipped set) are *trusted*. Any other skill is
  *untrusted* and is blocked from dangerous capability classes (filesystem
  writes, shell, unrestricted network, browser control, secrets, destructive
  operations). Deny rules continue to override allows.
* Dependencies are validated before loading. Missing/incompatible deps produce
  a clear error and the skill is marked invalid -- nothing is auto-installed.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Callable

from core.permissions import Decision, PermissionManager
from core.safety import HardSafety


# Skills shipped with ATLAS. Trust is *not* self-declared: a skill is trusted
# only if its name is in this set, so a third-party skill cannot escalate by
# writing ``"trusted": true`` into its own manifest.
BUILTIN_SKILLS = frozenset({"hello", "browser", "spotify", "minecraft", "coding"})

# Capabilities an UNTRUSTED skill may never request. Trusted skills are exempt.
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
    """A single loaded skill package.

    Exposes both attribute access (``skill.name``) and dict-style access
    (``skill["name"]``) so legacy router/test code keeps working.
    """

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
        # Legacy single-trigger field used by old router contract.
        self.trigger = self.triggers[0] if self.triggers else ""

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def matches(self, lowered_prompt: str) -> bool:
        """Return True if any trigger matches (``^`` anchors at start-of-prompt)."""
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

    # -- discovery -------------------------------------------------------
    def discover(self) -> list[Path]:
        """Return paths of skill directories that contain a ``skill.json``."""
        if not self._skills_dir.exists():
            return []
        found: list[Path] = []
        for child in sorted(self._skills_dir.iterdir()):
            if child.is_dir() and (child / "skill.json").exists():
                found.append(child)
        return found

    # -- loading ---------------------------------------------------------
    def load_all(self) -> list[Skill]:
        """Discover and load every skill package, resolving duplicates."""
        self._skills.clear()
        self._rejected.clear()

        candidates: list[tuple[Path, dict[str, Any]]] = []
        for skill_dir in self.discover():
            try:
                manifest = self._read_manifest(skill_dir / "skill.json")
            except SkillLoadError as exc:
                rejected = Skill(
                    name=skill_dir.name, version="0.0.0",
                    description="", triggers=[], valid=False, error=str(exc),
                    path=str(skill_dir),
                )
                self._rejected.append(rejected)
                continue
            candidates.append((skill_dir, manifest))

        for skill_dir, manifest in candidates:
            skill = self._build_skill(skill_dir, manifest)
            self._register(skill)
        return self.list()

    def _register(self, skill: Skill) -> None:
        existing = self._skills.get(skill.name)
        if existing is None:
            self._skills[skill.name] = skill
            return
        # Duplicate name: keep the higher version; reject the lower one.
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
        except OSError as exc:
            raise SkillLoadError(f"cannot read manifest: {exc}") from exc
        try:
            manifest = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SkillLoadError(f"malformed skill.json: {exc}") from exc
        if not isinstance(manifest, dict):
            raise SkillLoadError("skill.json must be a JSON object")
        missing = [f for f in REQUIRED_MANIFEST_FIELDS if not manifest.get(f)]
        if missing:
            raise SkillLoadError(f"missing required manifest field(s): {', '.join(missing)}")
        return manifest

    def _build_skill(self, skill_dir: Path, manifest: dict[str, Any]) -> Skill:
        name = str(manifest["name"])
        trusted = name in self._trusted

        # 1. Dependency validation (before anything else).
        missing_deps = self.validate_dependencies(name, manifest.get("dependencies", []))
        if missing_deps:
            return Skill(
                name=name, version=str(manifest.get("version", "0.0.0")),
                description=str(manifest.get("description", "")),
                triggers=list(manifest.get("triggers", [])),
                dependencies=manifest.get("dependencies", []),
                permissions=manifest.get("permissions", []),
                tools=manifest.get("tools", []),
                trusted=trusted, path=str(skill_dir), valid=False,
                error=f"missing dependencies: {', '.join(missing_deps)}",
            )

        # 2. Permission validation for untrusted skills.
        forbidden = [c for c in manifest.get("permissions", []) if _is_forbidden_capability(c)]
        if forbidden and not trusted:
            return Skill(
                name=name, version=str(manifest.get("version", "0.0.0")),
                description=str(manifest.get("description", "")),
                triggers=list(manifest.get("triggers", [])),
                dependencies=manifest.get("dependencies", []),
                permissions=manifest.get("permissions", []),
                tools=manifest.get("tools", []),
                trusted=trusted, path=str(skill_dir), valid=False,
                error=f"untrusted skill requests forbidden capabilities: {', '.join(forbidden)}",
            )

        # 3. Load the entry module.
        entry = str(manifest.get("entry", "run"))
        run_func = self._load_entry(skill_dir, entry)
        if run_func is None:
            return Skill(
                name=name, version=str(manifest.get("version", "0.0.0")),
                description=str(manifest.get("description", "")),
                triggers=list(manifest.get("triggers", [])),
                dependencies=manifest.get("dependencies", []),
                permissions=manifest.get("permissions", []),
                tools=manifest.get("tools", []),
                trusted=trusted, path=str(skill_dir), valid=False,
                error=f"skill entry '{entry}' not found or not callable",
            )

        return Skill(
            name=name, version=str(manifest.get("version", "0.0.0")),
            description=str(manifest.get("description", "")),
            triggers=list(manifest.get("triggers", [])),
            dependencies=manifest.get("dependencies", []),
            permissions=manifest.get("permissions", []),
            tools=manifest.get("tools", []),
            run=run_func, trusted=trusted, path=str(skill_dir), valid=True,
        )

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

    # -- dependency validation ------------------------------------------
    def validate_dependencies(self, name: str, dependencies: list[str]) -> list[str]:
        """Return a list of unmet dependency identifiers (empty if all met)."""
        missing: list[str] = []
        for dep in dependencies or []:
            if self._dependency_met(dep):
                continue
            missing.append(dep)
        return missing

    def _dependency_met(self, dep: str) -> bool:
        # 1. If a registry is available, a tool name counts as a dependency.
        if self._registry is not None:
            try:
                if self._registry.get(dep) is not None:
                    return True
            except Exception:
                pass
        # 2. Otherwise/also, treat as an importable Python module.
        try:
            return importlib.util.find_spec(dep) is not None
        except Exception:
            return False

    # -- runtime permission integration ---------------------------------
    def request_permission(self, name: str, capability: str) -> str:
        """Request a capability for a skill.

        Returns one of :class:`Decision` values. A skill *requests*; it never
        auto-receives. Untrusted skills are denied forbidden capabilities, and
        the hard-safety boundaries plus explicit deny rules still apply.
        """
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
        """Whether a skill may currently be executed by the router."""
        if not skill.valid:
            return False, skill.error or "skill is invalid"
        if not skill.enabled:
            return False, "skill is disabled"
        if not skill.trusted:
            forbidden = [c for c in skill.permissions if _is_forbidden_capability(c)]
            if forbidden:
                return False, f"untrusted skill requests forbidden capabilities: {forbidden}"
        return True, ""

    # -- lifecycle -------------------------------------------------------
    def unload(self, name: str) -> bool:
        """Unload a skill by name. Returns True if it was loaded."""
        skill = self._skills.pop(name, None)
        if skill is None:
            # Also clear from rejected list if present.
            self._rejected = [s for s in self._rejected if s.name != name]
            return False
        skill.enabled = False
        return True

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list(self) -> list[Skill]:
        """Return all currently active (registered) skills."""
        return list(self._skills.values())

    def all_skills(self) -> list[Skill]:
        """Return active skills plus rejected/duplicate ones (for diagnostics)."""
        return list(self._skills.values()) + self._rejected

    def status(self) -> dict[str, Any]:
        """Structured snapshot for debugging/observability."""
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
