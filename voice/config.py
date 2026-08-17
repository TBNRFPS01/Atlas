"""Runtime voice configuration for the ATLAS offline voice subsystem.

All values are sourced from the central ``ConfigManager`` (JSON + env) so
there is exactly one source of truth. Plain defaults are returned when the
config manager is unavailable (for example during early import or tests
that avoid touching the filesystem).
"""

from __future__ import annotations

from typing import Any


def _read(key: str, default: Any) -> Any:
    try:
        from config.manager import get_config

        return get_config().get(key, default)
    except Exception:
        return default


VOICE_ENABLED: bool = bool(_read("voice_enabled", False))
VOICE_RATE: int = int(_read("voice_rate", 180))
VOICE_VOLUME: float = float(_read("voice_volume", 1.0))
VOICE_LANGUAGE: str = str(_read("voice_language", "en"))
WHISPER_MODEL: str = str(_read("whisper_model", "small"))
TTS_ENGINE: str = str(_read("tts_engine", "piper"))
TTS_VOICE: str = str(_read("tts_voice", "en_US-lessac-medium"))
SAMPLE_RATE: int = int(_read("sample_rate", 16000))
RECORD_SECONDS: int = int(_read("record_seconds", 4))
PUSH_TO_TALK_KEY: str = str(_read("push_to_talk_key", "F8"))