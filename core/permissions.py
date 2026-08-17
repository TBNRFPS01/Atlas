"""Granular permission management for ATLAS tool execution.

The :class:`PermissionManager` centralises the decision of whether a tool
action may run. Rules map either a specific ``"tool.action"`` or a whole
``"tool"`` to ``allow``, ``ask`` or ``deny``. Destructive actions are always
``ask`` unless an explicit allow/deny rule exists or the action has been
pre-authorized via :meth:`PermissionManager.authorize`.
"""

from __future__ import annotations

from typing import Any


class Decision:
    """Possible outcomes of a permission decision."""

    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class PermissionManager:
    """Decide whether a tool/action may execute.

    Levels returned by a tool's metadata are honoured:
      * ``basic``        -> always allowed unless a deny rule exists.
      * ``elevated``     -> ask the user unless an allow rule/authorization exists.
      * ``destructive``  -> always ask unless an allow rule/authorization exists.

    A confirmation is satisfied by passing ``confirmed=True`` (the user replied
    with an explicit yes) or by pre-authorizing via :meth:`authorize`.
    """

    # (tool, action) tuples that must always be confirmed by default.
    DESTRUCTIVE: set[tuple[str, str]] = {
        ("file", "delete"),
        ("automation", "process_kill"),
        ("automation", "windows_close"),
        ("automation", "windows_kill"),
    }

    def __init__(self, rules: dict[str, str] | None = None) -> None:
        self._rules: dict[str, str] = dict(rules or {})
        self._authorized: set[str] = set()

    # -- configuration --------------------------------------------------
    def set_rule(self, key: str, decision: str) -> None:
        """Add or replace a rule (``key`` is ``"tool"`` or ``"tool.action"``)."""
        self._rules[key] = decision

    def authorize(self, key: str) -> None:
        """Pre-authorize a specific ``tool.action`` so it no longer prompts."""
        self._authorized.add(key)

    def revoke(self, key: str) -> None:
        """Remove a prior authorization."""
        self._authorized.discard(key)

    def is_authorized(self, key: str) -> bool:
        return key in self._authorized

    # -- decisions ------------------------------------------------------
    def decide(
        self,
        tool_name: str,
        action: str,
        *,
        permission_level: str = "basic",
        confirmation_required: bool = False,
        confirmed: bool = False,
    ) -> str:
        """Return one of :attr:`Decision.ALLOW`, ``ASK`` or ``DENY``.

        ``confirmed`` should be ``True`` only when the user has explicitly
        approved the action in the same prompt (e.g. replied "yes, delete X").
        """
        key = f"{tool_name}.{action}"

        if self._rules.get(key) == Decision.DENY or self._rules.get(tool_name) == Decision.DENY:
            return Decision.DENY

        if (
            self._rules.get(key) == Decision.ALLOW
            or self._rules.get(tool_name) == Decision.ALLOW
            or self.is_authorized(key)
        ):
            return Decision.ALLOW

        requires_prompt = (
            (tool_name, action) in self.DESTRUCTIVE
            or permission_level == "elevated"
            or permission_level == "destructive"
            or confirmation_required
        )
        if requires_prompt:
            return Decision.ALLOW if confirmed else Decision.ASK
        return Decision.ALLOW

    # -- helpers --------------------------------------------------------
    def confirmation_prompt(self, tool_name: str, action: str, detail: str = "") -> str:
        """Build a human-readable confirmation request for an action."""
        verb = {
            ("file", "delete"): "delete file",
            ("automation", "process_kill"): "terminate process",
            ("automation", "windows_close"): "close window",
            ("automation", "windows_kill"): "kill window",
            ("email", "send"): "send email",
        }.get((tool_name, action), action.replace("_", " "))
        suffix = f" {detail}" if detail else ""
        return (
            f"Confirm: {verb}{suffix}? "
            f"Reply with 'yes, {verb}{suffix}' to proceed."
        )
