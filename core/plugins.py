from __future__ import annotations

from services.plugin_manager import Plugin, PluginManager

__all__ = ["Plugin", "PluginLoader", "PluginManager"]


class PluginLoader(PluginManager):
    """Backwards-compatible alias for the legacy plugin loading surface.

    The real implementation now lives in ``services.plugin_manager`` so the
    project has exactly one plugin loading path.
    """

    def load(self) -> list[str]:
        """Discover and load plugins (legacy method name)."""
        return self.discover()