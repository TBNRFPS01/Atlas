"""Centralized configuration manager for ATLAS v2.

Supports JSON files, environment variables, and hot reload.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ConfigDefaults:
    """Default configuration values for ATLAS."""

    model: str = "local-model"
    temperature: float = 0.7
    max_tokens: int = 512
    history_size: int = 60
    stream: bool = True
    voice_enabled: bool = False
    memory_enabled: bool = True
    debug_mode: bool = False
    theme: str = "dark"
    voice_rate: int = 180
    voice_volume: float = 1.0
    voice_language: str = "en"
    whisper_model: str = "small"
    tts_engine: str = "piper"
    tts_voice: str = "en_US-lessac-medium"
    sample_rate: int = 16000
    record_seconds: int = 4
    push_to_talk_key: str = "F8"
    vision_enabled: bool = False
    ocr_enabled: bool = False
    planner_enabled: bool = True
    event_log_level: str = "INFO"


@dataclass
class ConfigManager:
    """Manage ATLAS configuration from JSON, environment, and defaults."""

    config_path: Path = field(default_factory=lambda: Path("config.json"))
    _data: dict[str, Any] = field(default_factory=lambda: {})
    _defaults: ConfigDefaults = field(default_factory=ConfigDefaults)

    def __post_init__(self) -> None:
        self._load_json()
        self._apply_env_overrides()

    def _load_json(self) -> None:
        """Load configuration from the JSON file if it exists."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as handle:
                    self._data = json.load(handle)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides on top of JSON config."""
        env_mappings = {
            "LM_STUDIO_BASE_URL": "endpoint",
            "LM_STUDIO_MODEL": "model",
            "LM_STUDIO_TEMPERATURE": "temperature",
            "LM_STUDIO_MAX_TOKENS": "max_tokens",
            "LM_STUDIO_HISTORY_SIZE": "history_size",
            "LM_STUDIO_STREAM": "stream",
            "VOICE_ENABLED": "voice_enabled",
            "MEMORY_ENABLED": "memory_enabled",
            "DEBUG_MODE": "debug_mode",
            "THEME": "theme",
            "VOICE_RATE": "voice_rate",
            "VOICE_VOLUME": "voice_volume",
            "VOICE_LANGUAGE": "voice_language",
            "WHISPER_MODEL": "whisper_model",
            "TTS_ENGINE": "tts_engine",
            "TTS_VOICE": "tts_voice",
            "SAMPLE_RATE": "sample_rate",
            "RECORD_SECONDS": "record_seconds",
            "PUSH_TO_TALK_KEY": "push_to_talk_key",
            "VISION_ENABLED": "vision_enabled",
            "OCR_ENABLED": "ocr_enabled",
            "PLANNER_ENABLED": "planner_enabled",
            "EVENT_LOG_LEVEL": "event_log_level",
        }

        for env_key, config_key in env_mappings.items():
            value = os.getenv(env_key)
            if value is not None:
                self._data[config_key] = self._coerce_type(config_key, value)

    def _coerce_type(self, key: str, value: str) -> Any:
        """Convert a string environment value to the appropriate Python type."""
        defaults = self._defaults
        if hasattr(defaults, key):
            default_val = getattr(defaults, key)
            if isinstance(default_val, bool):
                return value.lower() in ("true", "1", "yes", "on")
            if isinstance(default_val, int):
                return int(value)
            if isinstance(default_val, float):
                return float(value)
        return value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value, falling back to defaults."""
        if key in self._data:
            return self._data[key]
        if hasattr(self._defaults, key):
            return getattr(self._defaults, key)
        return default

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self._data[key] = value

    def reload(self) -> None:
        """Reload configuration from JSON file and re-apply env overrides."""
        self._load_json()
        self._apply_env_overrides()

    def validate(self) -> list[str]:
        """Validate configuration and return a list of any issues found."""
        issues: list[str] = []

        if self.get("model") is None or not self.get("model"):
            issues.append("model is required")

        if not isinstance(self.get("temperature"), (int, float)):
            issues.append("temperature must be a number")

        if not isinstance(self.get("voice_rate"), int):
            issues.append("voice_rate must be an integer")

        if not isinstance(self.get("voice_volume"), (int, float)):
            issues.append("voice_volume must be a number between 0 and 1")

        volume = self.get("voice_volume")
        if volume is not None and not (0 <= volume <= 1):
            issues.append("voice_volume must be between 0 and 1")

        return issues


# Global singleton instance
_manager: ConfigManager | None = None


def get_config() -> ConfigManager:
    """Return the global configuration manager instance."""
    global _manager
    if _manager is None:
        _manager = ConfigManager()
    return _manager