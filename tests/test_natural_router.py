from __future__ import annotations

from core.natural_router import NaturalCapabilityRouter


class DummyRouter:
    def __init__(self):
        self.personality = type("P", (), {"respond": staticmethod(lambda value: value)})()
        self._registry = type("R", (), {"get": lambda self, name: None})()


def match(prompt: str) -> str | None:
    return NaturalCapabilityRouter._match(prompt)


def test_web_search_is_not_memory_search():
    assert match("search the web for the latest Minecraft version") == "web:search:the latest Minecraft version"


def test_system_status_routes_to_system():
    assert match("what's my current system status?") == "system:info"
    assert match("what is my CPU usage?") == "system:info"


def test_running_apps_routes_to_context():
    assert match("check what's currently open on my computer") == "context:apps"
    assert match("what apps are open?") == "context:apps"


def test_active_window_routes_to_context():
    assert match("what window is active?") == "context:window"


def test_generic_application_requests_are_not_hardcoded():
    assert match("find Spotify app on my laptop") == "application:find:spotify"
    assert match("open Spotify") == "application:launch:spotify"
    assert match("locate Discord application") == "application:find:discord"
    assert match("launch VS Code") == "application:launch:vs code"


def test_normal_conversation_is_not_captured():
    assert match("how are you today?") is None
    assert match("tell me about computer science") is None
