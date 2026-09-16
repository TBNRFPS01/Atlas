"""Plugin manager for ATLAS hot-loading plugins."""

from __future__ import annotations

import importlib.util
import threading
from pathlib import Path
from typing import Any


class Plugin:
    """Base class for ATLAS plugins.

    Subclass this and place your file in the ``plugins/`` directory.  ATLAS
    will discover it automatically on startup.

    Minimal implementation::

        class MyPlugin(Plugin):
            name = "my_plugin"
            commands = ["my command"]

            def handle(self, prompt: str, router: Any) -> str | None:
                if "my command" in prompt.lower():
                    return "Plugin handled it!"
                return None  # pass through to the brain
    """

    name: str = "plugin"
    version: str = "1.0.0"
    # Natural-language phrases that should route to this plugin's handle().
    commands: list[str] = []
    # Tool names this plugin provides (informational only).
    tools: list[str] = []

    def startup(self) -> None:
        """Called once when the plugin is loaded."""

    def shutdown(self) -> None:
        """Called once when the plugin is unloaded."""

    def handle(self, prompt: str, router: Any) -> str | None:  # noqa: ARG002
        """Process a user prompt.

        Return a response string if this plugin handled the request, or
        ``None`` to pass the prompt on to the next handler.  The default
        implementation returns ``None`` for every input.
        """
        return None


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

    def dispatch(self, prompt: str, router: Any) -> str | None:
        """Try each loaded plugin in registration order.

        Returns the first non-``None`` response, or ``None`` if no plugin
        handled the prompt.
        """
        lowered = prompt.lower()
        with self._lock:
            plugins = list(self._plugins.values())
        for plugin in plugins:
            # Fast-path: skip plugins whose command list doesn't overlap at all
            if plugin.commands and not any(cmd in lowered for cmd in plugin.commands):
                continue
            try:
                result = plugin.handle(prompt, router)
            except Exception:
                result = None
            if result is not None:
                return result
        return None