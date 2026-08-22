from __future__ import annotations

from pathlib import Path

from core.application_registry import ApplicationRegistry


def test_registry_persists_verified_application(tmp_path: Path):
    executable = tmp_path / "Spotify.exe"
    executable.write_text("stub", encoding="utf-8")
    registry = ApplicationRegistry(tmp_path / "applications.json")

    registry.remember("Spotify", str(executable), source="test")

    reloaded = ApplicationRegistry(tmp_path / "applications.json")
    assert reloaded.get("spotify app") == str(executable)


def test_registry_drops_stale_paths(tmp_path: Path):
    registry = ApplicationRegistry(tmp_path / "applications.json")
    registry.remember("Spotify", str(tmp_path / "missing.exe"), source="test")

    assert registry.get("Spotify") is None
    assert "spotify" not in registry.all()
