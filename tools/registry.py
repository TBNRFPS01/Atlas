from __future__ import annotations

import importlib.util
from pathlib import Path

from tools.base import Tool


class ToolRegistry:
    """Registry for ATLAS tools with automatic discovery support."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self) -> list[str]:
        return sorted(self._tools)

    def discover(self, folder: str = "tools") -> list[str]:
        """Auto-discover Python tool modules and register their default tool classes."""
        root = Path(folder)
        loaded: list[str] = []

        for path in sorted(root.glob("*.py")):
            if path.name.startswith("__"):
                continue
            if path.name in {"base.py", "registry.py"}:
                continue

            spec = importlib.util.spec_from_file_location(path.stem, path)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Tool) and attr is not Tool:
                    instance = attr()
                    existing = self._tools.get(instance.name)
                    if existing is None:
                        self.register(instance)
                        loaded.append(instance.name)

        return loaded
