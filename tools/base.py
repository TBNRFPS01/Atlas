from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class ToolMetadata:
    """Metadata container for ATLAS tool registration."""

    category: str = "general"
    permission_level: str = "basic"
    confirmation_required: bool = False
    description: str = ""


class Tool(ABC):
    """Common interface for all ATLAS tools.

    Every tool should inherit from this class and expose a stable
    description plus a single execute entrypoint.
    """

    name: str = "tool"
    description: str = "Generic tool"
    metadata = ToolMetadata(description="Generic tool")

    @abstractmethod
    def execute(self, *args, **kwargs) -> str:
        """Run the tool and return a plain-text result."""

    def describe(self) -> str:
        return f"{self.name}: {self.description}"
