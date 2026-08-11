from __future__ import annotations

import importlib.util
from pathlib import Path


class PluginLoader:
    """Auto-discovers future ATLAS plugin modules from the plugins folder."""

    def __init__(self, folder: str = "plugins") -> None:
        self.folder = Path(folder)

    def load(self) -> list[str]:
        loaded: list[str] = []
        if not self.folder.exists():
            return loaded

        for path in sorted(self.folder.glob("*.py")):
            if path.name.startswith("__"):
                continue
            spec = importlib.util.spec_from_file_location(path.stem, path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            loaded.append(path.stem)
        return loaded
