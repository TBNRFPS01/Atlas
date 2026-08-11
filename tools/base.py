from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ToolMetadata:
    """Metadata container for ATLAS tool registration."""

    category: str = "general"
    permission_level: str = "basic"
    confirmation_required: bool = False
    description: str = ""


@dataclass(slots=True)
class ToolParameter:
    """OpenAI-compatible function parameter schema."""

    name: str
    type: str  # "string", "number", "integer", "boolean", "array", "object"
    description: str
    required: bool = False
    enum: list[str] | None = None


class Tool(ABC):
    """Common interface for all ATLAS tools.

    Every tool should inherit from this class and expose a stable
    description plus a single execute entrypoint.
    """

    name: str = "tool"
    description: str = "Generic tool"
    metadata = ToolMetadata(description="Generic tool")

    def get_parameters(self) -> list[ToolParameter]:
        """Return OpenAI-compatible function parameters schema.
        Override in subclasses to define tool parameters.
        """
        return []

    def to_openai_function(self) -> dict[str, Any]:
        """Convert tool to OpenAI function calling format."""
        properties = {}
        required = []
        for param in self.get_parameters():
            prop = {"type": param.type, "description": param.description}
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    @abstractmethod
    def execute(self, *args, **kwargs) -> str:
        """Run the tool and return a plain-text result."""

    def describe(self) -> str:
        return f"{self.name}: {self.description}"
