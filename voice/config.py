"""Runtime voice configuration for the ATLAS offline voice subsystem.

This module centralizes the speech-related defaults so the controller can
remain small and keep a single place for tuning.
"""

from __future__ import annotations

VOICE_ENABLED: bool = False
VOICE_RATE: int = 180
VOICE_VOLUME: float = 1.0
VOICE_LANGUAGE: str = "en"
WHISPER_MODEL: str = "small"
TTS_ENGINE: str = "piper"
TTS_VOICE: str = "en_US-lessac-medium"
SAMPLE_RATE: int = 16000
RECORD_SECONDS: int = 4
PUSH_TO_TALK_KEY: str = "F8"
