"""Hard safety boundaries for ATLAS.

Unlike the permission manager (which can be relaxed via ``allow`` rules or
runtime authorization), these boundaries are *immutable*. ATLAS will never
perform actions that could destroy the host operating system, tamper with its
own installation/memory, or overwrite critical system data -- no matter how
permissions are configured. Safety checks are consulted before every
destructive tool step, in both the router and the autonomous planner.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


# Directories that must never be deleted or overwritten, on any platform.
PROTECTED_DIRS = (
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "/",
    "/System",
    "/usr",
    "/bin",
    "/sbin",
    "/etc",
    "/boot",
    "/private/var",
    str(Path.home() / ".atlas"),  # never self-destruct the assistant
)

# (tool, action) combinations that are categorically forbidden.
FORBIDDEN_ACTIONS = {
    ("automation", "format_disk"),
    ("automation", "shutdown"),
    ("automation", "reboot"),
    ("file", "format"),
}

# Path fragments that indicate a protected / system-critical target.
PROTECTED_PATH_FRAGMENTS = (
    "windows\\system32",
    "windows\\systemapps",
    "/system/",
    "/private/var",
    "atlas_memory.db",  # never let a plan wipe long-term memory
)


class SafetyViolation(Exception):
    """Raised when an action would cross a hard safety boundary."""


class HardSafety:
    """Immutable guardrails consulted before any destructive tool action."""

    def __init__(
        self,
        protected_dirs: Iterable[str] | None = None,
        forbidden_actions: Iterable[tuple[str, str]] | None = None,
    ) -> None:
        self._protected_dirs = tuple(protected_dirs or PROTECTED_DIRS)
        self._forbidden = set(forbidden_actions or FORBIDDEN_ACTIONS)

    def check_action(self, tool_name: str, action: str) -> None:
        if (tool_name, action) in self._forbidden:
            raise SafetyViolation(f"Hard safety: '{tool_name}.{action}' is forbidden.")

    def check_path(self, path: str) -> None:
        if not path:
            return
        low = str(path).lower().replace("\\", "/")
        for fragment in PROTECTED_PATH_FRAGMENTS:
            if fragment in low:
                raise SafetyViolation(
                    f"Hard safety: path '{path}' contains protected fragment '{fragment}'."
                )

        try:
            target = Path(path).resolve()
        except Exception:
            return

        for directory in self._protected_dirs:
            try:
                protected = Path(directory)
            except Exception:
                continue
            if not protected.exists():
                continue
            try:
                target.relative_to(protected)
                raise SafetyViolation(
                    f"Hard safety: path '{path}' is inside protected directory '{directory}'."
                )
            except SafetyViolation:
                raise
            except Exception:
                continue

    def is_safe(self, tool_name: str, action: str, path: str | None = None) -> bool:
        try:
            self.check_action(tool_name, action)
            if path:
                self.check_path(path)
            return True
        except SafetyViolation:
            return False
