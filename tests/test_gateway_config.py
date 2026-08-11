"""Tests for gateway configuration validation and model list priority."""

import os
from pathlib import Path

from config.manager import ConfigManager


def _build_config(env: dict[str, str]) -> ConfigManager:
    """Clear env, build a ConfigManager from a temp config path with env overrides."""
    for key in list(os.environ):
        if key.startswith("ATLAS_") or key.startswith("LM_STUDIO_"):
            os.environ.pop(key, None)
    for k, v in env.items():
        os.environ[k] = v
    return ConfigManager(config_path=Path("nonexistent_config.json"))


def test_gateway_disabled_requires_no_key() -> None:
    cm = _build_config({})
    assert not cm.get("gateway_enabled")
    assert cm.validate() == []


def test_gateway_enabled_requires_api_key() -> None:
    cm = _build_config({"ATLAS_GATEWAY_ENABLED": "true"})
    issues = cm.validate()
    assert any("gateway_api_key" in i for i in issues)


def test_gateway_enabled_with_key_and_models_valid() -> None:
    cm = _build_config(
        {
            "ATLAS_GATEWAY_ENABLED": "true",
            "ATLAS_GATEWAY_API_KEY": "sk-gtw-test",
            "ATLAS_GATEWAY_MODELS": "gpt-5.6-luna,claude-opus-5,gpt-5.5",
        }
    )
    # Should not require gateway_model independently; should not reject this config.
    issues = cm.validate()
    assert not any("gateway_model" in i or "gateway_models" in i for i in issues)


def test_legacy_single_model_accepted() -> None:
    cm = _build_config(
        {
            "ATLAS_GATEWAY_ENABLED": "true",
            "ATLAS_GATEWAY_API_KEY": "sk-gtw-test",
            "ATLAS_GATEWAY_MODEL": "gpt-5.6-luna",
        }
    )
    assert cm.get_gateway_models() == ["gpt-5.6-luna"]
    issues = cm.validate()
    assert not any("gateway" in i for i in issues)


def test_models_take_priority_over_single_model() -> None:
    cm = _build_config(
        {
            "ATLAS_GATEWAY_MODELS": "gpt-5.6-luna,claude-opus-5,gpt-5.5",
            "ATLAS_GATEWAY_MODEL": "gpt-5.6-luna",
        }
    )
    # ATLAS_GATEWAY_MODELS must take priority.
    assert cm.get_gateway_models() == ["gpt-5.6-luna", "claude-opus-5", "gpt-5.5"]


def test_default_model_when_nothing_configured() -> None:
    cm = _build_config({})
    assert cm.get_gateway_models() == ["VerseMonster-Opus"]