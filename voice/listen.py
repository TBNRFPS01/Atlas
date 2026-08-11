"""Compatibility wrapper for the legacy voice.listen module.

This preserves the older import surface while delegating to the new
listener implementation when available.
"""

from __future__ import annotations

from voice.listener import Listener


def listen_for_input() -> str:
    """Return a placeholder transcription string for compatibility."""
    listener = Listener()
    return listener.load_model() is not None and "Voice ready" or "Voice unavailable"
