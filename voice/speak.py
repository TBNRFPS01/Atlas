"""Compatibility wrapper for the legacy voice.speak module.

This keeps older call sites working while the main assistant now uses the
threaded Speaker class directly.
"""

from __future__ import annotations

from voice.speaker import Speaker


def speak(text: str) -> str:
    """Speak the supplied text through the threaded speaker implementation."""
    speaker = Speaker()
    speaker.speak(text)
    return text
