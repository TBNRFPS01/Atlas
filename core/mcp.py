"""Minimal MCP-style tool adapter for ATLAS.

MCP calls are treated as external capabilities and require an explicit
authorization context before a handler is invoked.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class MCPTool:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    risk: str = "elevated"


class MCPTransport(Protocol):
    def list_tools(self) -> list[MCPTool]: ...
    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


class MCPClient:
    """Transport-neutral MCP client facade with permission gating."""

    def __init__(self, transport: MCPTransport, permission_manager: Any | None = None) -> None:
        self.transport = transport
        self._permissions = permission_manager
        self._tools: dict[str, MCPTool] = {}
        self.refresh()

    def refresh(self) -> list[MCPTool]:
        tools = self.transport.list_tools()
        for tool in tools:
            if tool.risk not in {"safe", "elevated", "destructive"}:
                raise ValueError(f"Invalid MCP risk level for '{tool.name}': {tool.risk}")
        self._tools = {tool.name: tool for tool in tools}
        return tools

    def tools(self) -> list[MCPTool]:
        return list(self._tools.values())

    def call(self, name: str, *, confirmed: bool = False, **arguments: Any) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown MCP tool: {name}")

        action = str(arguments.get("action", "call"))
        if self._permissions is None:
            if not confirmed:
                raise PermissionError(
                    f"MCP tool '{name}' requires an authorization context or explicit confirmation"
                )
        else:
            decision = self._permissions.decide(
                f"mcp.{name}",
                action,
                permission_level=tool.risk,
                confirmed=confirmed,
            )
            if decision == "deny":
                raise PermissionError(f"Permission denied for MCP tool '{name}'")
            if decision == "ask":
                raise PermissionError(f"Confirmation required for MCP tool '{name}'")

        return self.transport.call_tool(name, arguments)


class InMemoryMCPTransport:
    """Useful for tests and local skill bridges."""

    def __init__(self) -> None:
        self.handlers: dict[str, tuple[MCPTool, Any]] = {}

    def register(self, tool: MCPTool, handler: Any) -> None:
        self.handlers[tool.name] = (tool, handler)

    def list_tools(self) -> list[MCPTool]:
        return [tool for tool, _ in self.handlers.values()]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            _, handler = self.handlers[name]
        except KeyError as exc:
            raise KeyError(f"Unknown MCP tool: {name}") from exc
        return handler(**arguments)
