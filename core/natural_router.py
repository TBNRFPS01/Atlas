from __future__ import annotations

import re
from collections.abc import Iterator
from types import MethodType
from typing import Any

from core.application_registry import ApplicationRegistry


class NaturalCapabilityRouter:
    """Deterministic natural-language front door for executable capabilities.

    The router recognizes intent and entities without requiring the LLM. For
    applications, the first-use discovery path may use the LLM only to resolve
    an ambiguous human description; actual filesystem discovery and launching
    remain deterministic and verified.
    """

    def __init__(self, router: Any) -> None:
        self.router = router
        self._original_route = router.route
        self._original_stream = router.stream
        self.apps = ApplicationRegistry()

    def install(self) -> Any:
        router = self.router
        router.route = MethodType(self._route, router)
        router.stream = MethodType(self._stream, router)
        return router

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
        except Exception as exc:
            return f"{tool_name} tool error: {exc}"

    @staticmethod
    def _clean_application_candidate(candidate: str) -> str:
        value = candidate.strip().strip(" .!?\"'")
        value = re.sub(r"\b(?:app|application|program)\b", "", value, flags=re.I).strip()
        # Natural suffixes that are instructions/context, not the app name.
        value = re.sub(
            r"\s+(?:on|in|from)\s+(?:my|the)\s+(?:laptop|computer|pc|desktop)\b.*$",
            "",
            value,
            flags=re.I,
        ).strip()
        value = re.sub(r"\s+(?:on|in)\s+(?:my|the)\b.*$", "", value, flags=re.I).strip()
        return value.strip(" .!?\"'")

    def _resolve_application_name(self, router: Any, candidate: str) -> str:
        candidate = self._clean_application_candidate(candidate)
        if not candidate:
            return candidate

        # A simple application name is already an excellent search key. Do not
        # send it through the LLM, because an unavailable or confused model can
        # hallucinate an unrelated executable (e.g. Atlas.exe for Spotify).
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._+&'()-]{0,79}", candidate):
            return candidate

        prompt = (
            "Extract the desktop application name from this request. "
            "Return ONLY the application name, with no explanation. "
            f"Request: {candidate}"
        )
        try:
            answer = router.brain.ask(prompt).strip()
            if answer.startswith("LM Studio connection failed") or answer.startswith("LLM request failed"):
                return candidate
            answer = re.sub(r"^(?:app(?:lication)?[_ ]?name)\s*:\s*", "", answer, flags=re.I)
            answer = answer.splitlines()[0].strip().strip("`\"'")
            answer = self._clean_application_candidate(answer)
            if 0 < len(answer) <= 80:
                return answer
        except Exception:
            pass
        return candidate

    @staticmethod
    def _first_verified_path(result: str | None) -> str | None:
        if not result:
            return None
        for line in result.splitlines():
            match = re.search(r"(?:Found[^:]*:\s*)([A-Za-z]:[\\/].+)$", line)
            if match:
                path = match.group(1).strip().strip('"')
                if path:
                    return path
            if re.fullmatch(r"[A-Za-z]:[\\/].+", line.strip()):
                return line.strip()
        return None

    def _application_action(self, router: Any, action: str, candidate: str) -> str | None:
        requested = self._clean_application_candidate(candidate)
        if not requested:
            return "Tell me which application you mean."

        key = self.apps.normalize(requested)
        cached = self.apps.get(key)
        if cached:
            if action == "find":
                return f"Found '{requested}' at {cached}"
            result = self._execute(
                router,
                "system",
                action="launch_application_path",
                application_name=requested,
                application_path=cached,
            )
            if result is not None and "no longer valid" not in result.lower():
                return result

        app_name = self._resolve_application_name(router, requested)
        discovered = self._execute(router, "system", action="find_application", application_name=app_name)
        path = self._first_verified_path(discovered)
        if path:
            self.apps.remember(app_name, path, source="system-discovery")
            if action == "launch":
                return self._execute(
                    router,
                    "system",
                    action="launch_application_path",
                    application_name=app_name,
                    application_path=path,
                )
            return f"Found '{app_name}' at {path}"
        return discovered

    @staticmethod
    def _match(prompt: str) -> str | None:
        """Return a deterministic capability route without requiring an instance."""
        text = prompt.lower().strip()

        web_prefixes = (
            "search the web for ", "search the web ", "search web for ",
            "search online for ", "look up ", "google ", "find information about ",
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

        # Keep the app suffix outside the captured entity, and strip common
        # computer-location context so "find Spotify app on my laptop" becomes
        # exactly application:find:spotify.
        app_match = re.match(
            r"^(find|locate|where is|open|launch|start|run)\s+(?:the\s+)?(.+?)(?:\s+(?:app|application|program))?\s*[.!?]*$",
            text,
        )
        if app_match:
            verb, name = app_match.groups()
            name = NaturalCapabilityRouter._clean_application_candidate(name)
            action = "find" if verb in {"find", "locate", "where is"} else "launch"
            if name:
                return f"application:{action}:{name}"

        return None

    def _dispatch(self, router: Any, prompt: str, match: str) -> str | None:
        parts = match.split(":", 2)
        if parts[0] == "web":
            if parts[1] == "missing":
                return "Usage: search the web for <query>"
            return self._execute(router, "web", action="search", query=parts[2])

        if parts[0] == "system" and parts[1] == "info":
            return self._execute(router, "system", action="info")

        if parts[0] == "context":
            return self._execute(router, "context", action=parts[1])

        if parts[0] == "application":
            return self._application_action(router, parts[1], parts[2])

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
    return NaturalCapabilityRouter(router).install()
