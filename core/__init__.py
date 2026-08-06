"""Core package for ATLAS v2.

Provides the Brain, Router, and EventBus for the assistant's core functionality.
"""

from core.brain import Brain
from core.events import EventBus
from core.personality import ATLASPersonality
from core.plugins import PluginLoader
from core.router import Router

__all__ = ["Brain", "EventBus", "ATLASPersonality", "PluginLoader", "Router"]
