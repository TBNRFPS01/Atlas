"""ATLAS plugins package.

This package provides plugin loading and discovery for ATLAS.
PluginLoader is re-exported from core.plugins for backward compatibility.
"""

from core.plugins import PluginLoader

__all__ = ["PluginLoader"]
