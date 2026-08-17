"""Compatibility wrapper for the legacy voice.listen module.

This preserves the older import surface while delegating to the new
listener implementation when available.
"""

from __future__ import annotations

from voice.listener import Listener


def listen_for_input(seconds: float | None = None) -> str:
    """Record microphone audio and return a real transcription.

    Falls back to a short human-readable status string when the voice
    hardware or dependencies are unavailable instead of pretending to
    transcribe.
    """
    try:
        from voice.config import RECORD_SECONDS
        from voice.microphone import Microphone

        mic = Microphone(record_seconds=int(seconds or RECORD_SECONDS))
        audio = mic.record()
        if audio is None:
            return "Voice unavailable"
        text = Listener().transcribe(audio)
        return text or "Voice unavailable"
    except Exception as exc:
        print(f"Voice: Warning - listen_for_input failed: {exc}")
        return "Voice unavailable"
