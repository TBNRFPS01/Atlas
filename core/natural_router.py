from __future__ import annotations

import re
from collections.abc import Iterator
from types import MethodType
from typing import Any


class NaturalCapabilityRouter:
    """Small deterministic front-door for common human phrasing.

    This layer intentionally sits in front of the existing Router rather than
    replacing it. It handles requests whose intent is unambiguous, then lets
    the existing router handle skills, memory, planning, permissions, and the
    LLM fallback.
    """

    def __init__(self, router: Any) -> None:
        self.router = router
        self._original_route = router.route
        self._original_stream = router.stream

    def install(self) -> Any:
        self.router.route = MethodType(self._route, self.router)
        self.router.stream = MethodType(self._stream, self.router)
        return self.router

    @staticmethod
    def _tool(router: Any, name: str) -> Any | None:
        return router._registry.get(name)

    @classmethod
    def _execute(cls, router: Any, tool_name: str, **kwargs: Any) -> str | None:
        tool = cls._tool(router, tool_name)
        if tool is None:
            return None
        try:
            return tool.execute(**kwargs)
        except Exception as exc:  # defensive boundary for deterministic routing
            return f"{tool_name} tool error: {exc}"

    @classmethod
    def _match(cls, prompt: str) -> str | None:
        text = prompt.lower().strip()

        # Web search must be checked before the legacy `search <term>` memory
        # shortcut. This prevents "search the web for X" from becoming a
        # memory search for "the web for X".
        web_prefixes = (
            "search the web for ",
            "search the web ",
            "search web for ",
            "search online for ",
            "look up ",
            "google ",
            "find information about ",
        )
        for prefix in web_prefixes:
            if text.startswith(prefix):
                query = prompt[len(prefix):].strip()
                return f"web:search:{query}" if query else "web:missing"

        if re.search(r"\b(?:system|computer|pc)\s+(?:status|info|information)\b", text):
            return "system:info"
        if re.search(r"\b(?:cpu|processor)\s+(?:usage|status|info|information)\b", text):
            return "system:info"
        if re.search(r"\b(?:ram|memory)\s+(?:usage|status|info|information)\b", text):
            return "system:info"
        if re.search(r"\b(?:disk|storage)\s+(?:usage|status|space|info|information)\b", text):
            return "system:info"

        if re.search(r"\b(?:what(?:'s| is)|which|show|list|check)\s+(?:apps?|applications?|programs?|windows?)\s+(?:are\s+)?(?:currently\s+)?(?:open|running)\b", text):
            return "context:apps"
        if any(p in text for p in (
            "what apps are open", "what programs are running", "what applications are open",
            "what windows are open", "what's currently open", "what is currently open",
            "show running apps", "list running apps", "check what's open", "check what is open",
        )):
            return "context:apps"

        if any(p in text for p in (
            "what window is active", "what's my active window", "what is my active window",
            "what window am i on", "current window", "active window",
        )):
            return "context:window"

        # App discovery/launching. Keep this separate from Spotify playback
        # so "find Spotify" means find the desktop application.
        app_match = re.search(
            r"^(?:find|locate|where is|open|launch|start|run)\s+(?:the\s+)?(.+?)(?:\s+app|\s+application|\s+program)?[.!?]*$",
            text,
        )
        if app_match:
            name = app_match.group(1).strip()
            if name in {"spotify", "chrome", "google chrome", "discord", "steam", "notepad", "vscode", "vs code"}:
                action = "find_application" if text.startswith(("find ", "locate ", "where is ")) else "launch_application"
                return f"system:{action}:{name}"

        return None

    def _dispatch(self, router: Any, prompt: str, match: str) -> str | None:
        parts = match.split(":", 2)
        if parts[0] == "web":
            if parts[1] == "missing":
                return "Usage: search the web for <query>"
            return self._execute(router, "web", action="search", query=parts[2])

        if parts[0] == "system":
            action = parts[1]
            if action == "info":
                return self._execute(router, "system", action="info")
            return self._execute(router, "system", action=action, application_name=parts[2])

        if parts[0] == "context":
            return self._execute(router, "context", action=parts[1])

        return None

    def _route(self, router: Any, prompt: str) -> str:
        match = self._match(prompt)
        if match:
            result = self._dispatch(router, prompt, match)
            if result is not None:
                return router.personality.respond(result)
        return self._original_route(prompt)

    def _stream(self, router: Any, prompt: str) -> Iterator[str]:
        match = self._match(prompt)
        if match:
            result = self._dispatch(router, prompt, match)
            if result is not None:
                yield router.personality.respond(result)
                return
        yield from self._original_stream(prompt)


def install(router: Any) -> Any:
    """Install the natural-language capability front-door on a Router."""
    return NaturalCapabilityRouter(router).install()
