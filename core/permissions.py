"""Central permission and confirmation gate for ATLAS tool execution."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any


class Decision:
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class Confirmation:
    token: str
    tool: str
    action: str


class PermissionManager:
    """Deterministic permission gate. Model/web text never counts as approval."""

    DESTRUCTIVE: set[tuple[str, str]] = {
        ("file", "write"), ("file", "append"), ("file", "delete"),
        ("automation", "process_kill"), ("automation", "windows_close"),
        ("automation", "windows_kill"), ("email", "send"),
    }

    def __init__(self, rules: dict[str, str] | None = None) -> None:
        self._rules = dict(rules or {})
        self._authorized: set[str] = set()
        self._pending: dict[str, Confirmation] = {}

    def set_rule(self, key: str, decision: str) -> None:
        if decision not in {Decision.ALLOW, Decision.ASK, Decision.DENY}:
            raise ValueError(f"Unknown permission decision: {decision}")
        self._rules[key] = decision

    def authorize(self, key: str) -> None:
        self._authorized.add(key)

    def revoke(self, key: str) -> None:
        self._authorized.discard(key)

    def is_authorized(self, key: str) -> bool:
        return key in self._authorized

    def decide(self, tool_name: str, action: str, *, permission_level: str = "basic", confirmation_required: bool = False, confirmed: bool = False) -> str:
        key = f"{tool_name}.{action}"
        if self._rules.get(key) == Decision.DENY or self._rules.get(tool_name) == Decision.DENY:
            return Decision.DENY
        if self._rules.get(key) == Decision.ALLOW or self._rules.get(tool_name) == Decision.ALLOW or self.is_authorized(key):
            return Decision.ALLOW
        needs_confirmation = ((tool_name, action) in self.DESTRUCTIVE or permission_level in {"elevated", "destructive"} or confirmation_required)
        if needs_confirmation:
            return Decision.ALLOW if confirmed else Decision.ASK
        return Decision.ALLOW

    def request_confirmation(self, tool_name: str, action: str) -> Confirmation:
        token = secrets.token_urlsafe(24)
        confirmation = Confirmation(token, tool_name, action)
        self._pending[token] = confirmation
        return confirmation

    def confirm(self, token: str, tool_name: str, action: str) -> bool:
        pending = self._pending.pop(token, None)
        return bool(pending and pending.tool == tool_name and pending.action == action)

    def confirmation_prompt(self, tool_name: str, action: str, detail: str = "") -> str:
        verb = {
            ("file", "write"): "write file", ("file", "append"): "append to file",
            ("file", "delete"): "delete file", ("automation", "process_kill"): "terminate process",
            ("automation", "windows_close"): "close window", ("automation", "windows_kill"): "kill window",
            ("email", "send"): "send email",
        }.get((tool_name, action), action.replace("_", " "))
        suffix = f" {detail}" if detail else ""
        return f"Confirmation required: {verb}{suffix}. Approve this action explicitly."
