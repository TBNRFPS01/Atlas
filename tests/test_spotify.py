"""Tests for Spotify tool integration."""

from core.router import Router


def test_spotify_current_routes_to_tool() -> None:
    router = Router()
    result = router.route("spotify current")
    assert "Spotify error: Not authenticated" in result
    assert "LM Studio connection failed" not in result


def test_spotify_play_routes_to_tool() -> None:
    router = Router()
    result = router.route("spotify play")
    assert "Spotify error: Not authenticated" in result
    assert "LM Studio connection failed" not in result


def test_spotify_search_routes_to_tool() -> None:
    router = Router()
    result = router.route("spotify search hello")
    assert "Spotify error: Not authenticated" in result
    assert "LM Studio connection failed" not in result


def test_spotify_volume_routes_to_tool() -> None:
    router = Router()
    result = router.route("spotify volume 50")
    assert "Spotify error: Not authenticated" in result
    assert "LM Studio connection failed" not in result


def test_spotify_next_routes_to_tool() -> None:
    router = Router()
    result = router.route("spotify next")
    assert "Spotify error: Not authenticated" in result
    assert "LM Studio connection failed" not in result


def test_spotify_pause_routes_to_tool() -> None:
    router = Router()
    result = router.route("spotify pause")
    assert "Spotify error: Not authenticated" in result
    assert "LM Studio connection failed" not in result


def test_spotify_devices_routes_to_tool() -> None:
    router = Router()
    result = router.route("spotify devices")
    assert "Spotify error: Not authenticated" in result
    assert "LM Studio connection failed" not in result