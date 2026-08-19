"""Declarative capability sets for tools and plugins."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CapabilitySet:
    """The permissions a tool declares it needs."""
    filesystem: frozenset[str] = frozenset()
    network: frozenset[str] = frozenset()
    processes: frozenset[str] = frozenset()
    ui: frozenset[str] = frozenset()
    sensitive: frozenset[str] = frozenset()

    def allows(self, category: str, capability: str) -> bool:
        values = getattr(self, category, frozenset())
        return capability in values or "*" in values


@dataclass
class CapabilityRegistry:
    _items: dict[str, CapabilitySet] = field(default_factory=dict)

    def register(self, tool: str, capabilities: CapabilitySet) -> None:
        self._items[tool] = capabilities

    def get(self, tool: str) -> CapabilitySet:
        return self._items.get(tool, CapabilitySet())

    def check(self, tool: str, category: str, capability: str) -> bool:
        return self.get(tool).allows(category, capability)
