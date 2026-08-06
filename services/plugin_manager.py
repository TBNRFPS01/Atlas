"""Plugin manager for ATLAS hot-loading plugins."""

from __future__ import annotations

import importlib.util
import threading
from pathlib import Path
from typing import Any


class Plugin:
    """Base class for ATLAS plugins."""

    name: str = "plugin"
    version: str = "1.0.0"
    commands: list[str] = []
    tools: list[str] = []

    def startup(self) -> None:
        """Called when the plugin is loaded."""
        pass

    def shutdown(self) -> None:
        """Called when the plugin is unloaded."""
        pass


class PluginManager:
    """Discover, load, and manage ATLAS plugins."""

    def __init__(self, folder: str = "plugins") -> None:
        self.folder = Path(folder)
        self._plugins: dict[str, Plugin] = {}
        self._lock = threading.Lock()

    def discover(self) -> list[str]:
        """Find and load all plugins in the plugins folder."""
        if not self.folder.exists():
            return []

        loaded: list[str] = []
        for path in sorted(self.folder.glob("*.py")):
            if path.name.startswith("__"):
                continue
            plugin = self._load_plugin(path)
            if plugin is not None:
                with self._lock:
                    self._plugins[plugin.name] = plugin
                loaded.append(plugin.name)
                try:
                    plugin.startup()
                except Exception:
                    pass

        return loaded

    def _load_plugin(self, path: Path) -> Plugin | None:
        """Load a plugin from a Python file."""
        try:
            spec = importlib.util.spec_from_file_location(path.stem, path)
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Plugin) and attr is not Plugin:
                    instance = attr()
                    return instance
            return None
        except Exception:
            return None

    def get(self, name: str) -> Plugin | None:
        """Get a loaded plugin by name."""
        with self._lock:
            return self._plugins.get(name)

    def list_plugins(self) -> list[str]:
        """Return the names of all loaded plugins."""
        with self._lock:
            return list(self._plugins.keys())

    def stop_all(self) -> None:
        """Call shutdown on all loaded plugins."""
        with self._lock:
            for plugin in self._plugins.values():
                try:
                    plugin.shutdown()
                except Exception:
                    pass
            self._plugins.clear()

    def reload(self) -> list[str]:
        """Reload all plugins from disk."""
        self.stop_all()
        return self.discover()