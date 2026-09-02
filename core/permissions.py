"""Granular permission management for ATLAS tool execution.

Permission decisions are metadata-driven and fail closed for privileged
capabilities. Callers may request stricter policy, but they cannot downgrade a
tool's declared security level.
"""

from __future__ import annotations

from typing import Any


class Decision:
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class PermissionManager:
    """Decide whether a tool/action may execute."""

    DESTRUCTIVE: set[tuple[str, str]] = {
        ("file", "delete"),
        ("automation", "process_kill"),
        ("automation", "windows_close"),
        ("automation", "windows_kill"),
        ("automation", "process_start"),
        ("automation", "windows_launch"),
        ("browser", "eval_js"),
        ("system", "launch_application"),
        ("system", "launch_application_path"),
    }

    ELEVATED_ACTIONS: set[tuple[str, str]] = {
        ("file", "write"),
        ("file", "append"),
        ("automation", "clipboard_get"),
        ("system", "launch_application"),
        ("system", "launch_application_path"),
    }

    LEVELS = {"basic": 0, "elevated": 1, "destructive": 2}

    def __init__(self, rules: dict[str, str] | None = None) -> None:
        self._rules: dict[str, str] = dict(rules or {})
        self._authorized: set[str] = set()
        self._metadata_cache: dict[str, Any | None] = {}

    def set_rule(self, key: str, decision: str) -> None:
        self._rules[key] = decision

    def authorize(self, key: str) -> None:
        self._authorized.add(key)

    def revoke(self, key: str) -> None:
        self._authorized.discard(key)

    def is_authorized(self, key: str) -> bool:
        return key in self._authorized

    def _tool_metadata(self, tool_name: str) -> Any | None:
        """Resolve registered tool metadata lazily for callers that omit it."""
        if tool_name in self._metadata_cache:
            return self._metadata_cache[tool_name]
        try:
            from tools.registry import ToolRegistry

            registry = ToolRegistry()
            registry.discover()
            tool = registry.get(tool_name)
            metadata = getattr(tool, "metadata", None) if tool is not None else None
        except Exception:
            metadata = None
        self._metadata_cache[tool_name] = metadata
        return metadata

    def decide(
        self,
        tool_name: str,
        action: str,
        *,
        permission_level: str | None = None,
        confirmation_required: bool | None = None,
        confirmed: bool = False,
    ) -> str:
        """Return ``allow``, ``ask`` or ``deny``.

        Registered tool metadata supplies the minimum security level. A caller
        can make policy stricter, but cannot downgrade an elevated tool to
        basic. Critical action overrides are enforced even if tool metadata is
        too broad.
        """
        key = f"{tool_name}.{action}"

        if self._rules.get(key) == Decision.DENY or self._rules.get(tool_name) == Decision.DENY:
            return Decision.DENY

        metadata = self._tool_metadata(tool_name)
        declared_level = str(getattr(metadata, "permission_level", "") or "basic")
        declared_confirm = bool(getattr(metadata, "confirmation_required", False))
        requested_level = permission_level or "basic"

        levels = [declared_level, requested_level]
        if (tool_name, action) in self.ELEVATED_ACTIONS:
            levels.append("elevated")
        if (tool_name, action) in self.DESTRUCTIVE:
            levels.append("destructive")
        effective_level = max(levels, key=lambda value: self.LEVELS.get(value, 2))

        effective_confirm = declared_confirm or bool(confirmation_required)

        if (
            self._rules.get(key) == Decision.ALLOW
            or self._rules.get(tool_name) == Decision.ALLOW
            or self.is_authorized(key)
        ):
            return Decision.ALLOW

        if effective_level in {"elevated", "destructive"} or effective_confirm:
            return Decision.ALLOW if confirmed else Decision.ASK
        return Decision.ALLOW

    def confirmation_prompt(self, tool_name: str, action: str, detail: str = "") -> str:
        verb = {
            ("file", "delete"): "delete file",
            ("file", "write"): "write file",
            ("file", "append"): "append to file",
            ("automation", "process_kill"): "terminate process",
            ("automation", "process_start"): "start a process",
            ("automation", "windows_launch"): "launch an application",
            ("automation", "windows_close"): "close window",
            ("automation", "windows_kill"): "kill window",
            ("browser", "eval_js"): "execute JavaScript in the browser",
            ("system", "launch_application"): "launch an application",
            ("system", "launch_application_path"): "launch an application",
            ("email", "send"): "send email",
        }.get((tool_name, action), action.replace("_", " "))
        suffix = f" {detail}" if detail else ""
        return f"Confirm: {verb}{suffix}? Reply with 'yes, {verb}{suffix}' to proceed."
