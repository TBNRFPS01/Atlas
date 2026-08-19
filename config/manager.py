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
    # Autonomous goal management (background loop)
    autonomy_enabled: bool = False
    autonomy_interval_seconds: float = 600.0
    autonomy_max_tasks_per_cycle: int = 2
    learning_enabled: bool = True
    # Gateway provider configuration
    gateway_enabled: bool = False
    gateway_api_key: str = ""
    gateway_model: str = "VerseMonster-Opus"
    gateway_models: str = ""  # Comma-separated list of models (new)
    gateway_base_url: str = "https://freemodelsforall.hopto.org/v1"
    gateway_model_discovery: bool = True  # Auto-discover models from /v1/models
    gateway_model_cache_ttl: int = 300  # Cache TTL in seconds
    # Provider selection
    primary_provider: str = "local"  # "local" or "gateway"
    fallback_provider: str = "gateway"  # "local" or "gateway" or "none"
    # STT/TTS configuration
    stt_enabled: bool = False
    stt_model: str = "small"
    stt_language: str = "en"
    stt_device: str = "auto"
    stt_compute_type: str = "auto"
    tts_enabled: bool = False
    tts_engine: str = "piper"
    tts_voice: str = "en_US-lessac-medium"
    tts_rate: int = 180
    tts_volume: float = 1.0
    # Email configuration
    email_enabled: bool = False
    email_provider: str = "smtp"
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = ""
    email_from: str = ""
    email_use_tls: bool = True


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
            # Autonomous goal management
            "ATLAS_AUTONOMY_ENABLED": "autonomy_enabled",
            "ATLAS_AUTONOMY_INTERVAL": "autonomy_interval_seconds",
            "ATLAS_AUTONOMY_MAX_TASKS": "autonomy_max_tasks_per_cycle",
            "ATLAS_LEARNING_ENABLED": "learning_enabled",
            # Gateway provider
            "ATLAS_GATEWAY_API_KEY": "gateway_api_key",
            "ATLAS_GATEWAY_MODEL": "gateway_model",
            "ATLAS_GATEWAY_MODELS": "gateway_models",
            "ATLAS_GATEWAY_BASE_URL": "gateway_base_url",
            "ATLAS_GATEWAY_ENABLED": "gateway_enabled",
            "ATLAS_GATEWAY_MODEL_DISCOVERY": "gateway_model_discovery",
            "ATLAS_GATEWAY_MODEL_CACHE_TTL": "gateway_model_cache_ttl",
            "ATLAS_PRIMARY_PROVIDER": "primary_provider",
            "ATLAS_FALLBACK_PROVIDER": "fallback_provider",
            # STT configuration
            "ATLAS_STT_ENABLED": "stt_enabled",
            "ATLAS_STT_MODEL": "stt_model",
            "ATLAS_STT_LANGUAGE": "stt_language",
            "ATLAS_STT_DEVICE": "stt_device",
            "ATLAS_STT_COMPUTE_TYPE": "stt_compute_type",
            # TTS configuration
            "ATLAS_TTS_ENABLED": "tts_enabled",
            "ATLAS_TTS_ENGINE": "tts_engine",
            "ATLAS_TTS_VOICE": "tts_voice",
            "ATLAS_TTS_RATE": "tts_rate",
            "ATLAS_TTS_VOLUME": "tts_volume",
            # Email configuration
            "ATLAS_EMAIL_ENABLED": "email_enabled",
            "ATLAS_EMAIL_PROVIDER": "email_provider",
            "ATLAS_EMAIL_SMTP_HOST": "email_smtp_host",
            "ATLAS_EMAIL_SMTP_PORT": "email_smtp_port",
            "ATLAS_EMAIL_USERNAME": "email_username",
            "ATLAS_EMAIL_PASSWORD": "email_password",
            "ATLAS_EMAIL_FROM": "email_from",
            "ATLAS_EMAIL_USE_TLS": "email_use_tls",
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

    def get_gateway_models(self) -> list[str]:
        """Get the ordered list of gateway models to try.

        Priority:
        1. ATLAS_GATEWAY_MODELS (comma-separated)
        2. ATLAS_GATEWAY_MODEL (single model, backwards compatibility)
        3. Default model
        """
        models_str = self.get("gateway_models", "")
        if models_str:
            return [m.strip() for m in models_str.split(",") if m.strip()]

        # Backwards compatibility
        single_model = self.get("gateway_model", "")
        if single_model:
            return [single_model]

        # Default fallback
        return ["VerseMonster-Opus"]

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

        # Validate gateway config if enabled
        if self.get("gateway_enabled"):
            if not self.get("gateway_api_key"):
                issues.append("gateway_api_key is required when gateway_enabled is true")
            # A model list (or single legacy model) is only required when the
            # provider has no valid configured default. get_gateway_models()
            # always falls back to the "VerseMonster-Opus" default, so this
            # only fires if that default itself is emptied.
            if not self.get_gateway_models():
                issues.append("gateway_models or gateway_model is required when gateway_enabled is true")

        primary = self.get("primary_provider")
        if primary not in ("local", "gateway"):
            issues.append("primary_provider must be 'local' or 'gateway'")

        fallback = self.get("fallback_provider")
        if fallback not in ("local", "gateway", "none"):
            issues.append("fallback_provider must be 'local', 'gateway', or 'none'")

        # Validate STT config
        if self.get("stt_enabled"):
            if not self.get("stt_model"):
                issues.append("stt_model is required when stt_enabled is true")

        # Validate TTS config
        if self.get("tts_enabled"):
            if not self.get("tts_engine"):
                issues.append("tts_engine is required when tts_enabled is true")
            if not self.get("tts_voice"):
                issues.append("tts_voice is required when tts_enabled is true")

        # Validate email config
        if self.get("email_enabled"):
            if not self.get("email_smtp_host"):
                issues.append("email_smtp_host is required when email_enabled is true")
            if not self.get("email_username"):
                issues.append("email_username is required when email_enabled is true")
            if not self.get("email_password"):
                issues.append("email_password is required when email_enabled is true")
            if not self.get("email_from"):
                issues.append("email_from is required when email_enabled is true")

        return issues


# Global singleton instance
_manager: ConfigManager | None = None


def get_config() -> ConfigManager:
    """Return the global configuration manager instance."""
    global _manager
    if _manager is None:
        _manager = ConfigManager()
    return _manager