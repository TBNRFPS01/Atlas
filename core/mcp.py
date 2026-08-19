"""Minimal MCP-style tool adapter for ATLAS.

ATLAS can consume any MCP-like server through a tiny transport-neutral
interface. A real MCP transport can be attached later without changing the
agent's tool registry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class MCPTool:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


class MCPTransport(Protocol):
    def list_tools(self) -> list[MCPTool]: ...
    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


class MCPClient:
    """Transport-neutral MCP client facade."""

    def __init__(self, transport: MCPTransport) -> None:
        self.transport = transport
        self._tools: dict[str, MCPTool] = {}
        self.refresh()

    def refresh(self) -> list[MCPTool]:
        tools = self.transport.list_tools()
        self._tools = {tool.name: tool for tool in tools}
        return tools

    def tools(self) -> list[MCPTool]:
        return list(self._tools.values())

    def call(self, name: str, **arguments: Any) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown MCP tool: {name}")
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
