from __future__ import annotations

import re
from collections.abc import Iterator
from types import MethodType
from typing import Any

from core.application_registry import ApplicationRegistry


class NaturalCapabilityRouter:
    """Deterministic natural-language front door for executable capabilities."""

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

        action = str(kwargs.get("action", "execute"))
        metadata = getattr(tool, "metadata", None)
        permission_level = getattr(metadata, "permission_level", "basic")
        confirmation_required = bool(getattr(metadata, "confirmation_required", False))
        path = str(kwargs.get("path") or kwargs.get("application_path") or kwargs.get("title") or "")

        authorize = getattr(router, "_authorize", None)
        execute_action = getattr(router, "execute_action", None)
        # Older Router implementations retain their legacy gate. The current
        # Router owns policy inside execute_action so it can emit a full record
        # for denials as well as successful actions.
        if execute_action is None and authorize is not None:
            blocked = authorize(
                tool_name,
                action,
                permission_level=permission_level,
                confirmation_required=confirmation_required,
                prompt=kwargs.get("_prompt", ""),
                path=path,
            )
            if blocked:
                return blocked

        intent = str(kwargs.pop("_prompt", "") or f"{tool_name}.{action}")
        if execute_action is not None:
            return execute_action(intent=intent, tool_name=tool_name, action=action,
                fn=lambda: tool.execute(**kwargs), prompt=intent, path=path,
                permission_level=permission_level, confirmation_required=confirmation_required)
        try:
            return tool.execute(**kwargs)
        except Exception as exc:
            return f"{tool_name} tool error: {exc}"

    @staticmethod
    def _clean_application_candidate(candidate: str) -> str:
        value = candidate.strip().strip(" .!?\"'")
        # Strip only semantic suffixes, not words that may legitimately be
        # part of an application name such as "Windows Terminal".
        value = re.sub(r"\s+(?:app|application|program)\b", "", value, flags=re.I).strip()
        value = re.sub(
            r"\s+(?:on|in|from)\s+(?:my|the)\s+(?:laptop|computer|pc|desktop)\b.*$",
            "",
            value,
            flags=re.I,
        ).strip()
        return value.strip(" .!?\"'")

    def _resolve_application_name(self, router: Any, candidate: str) -> str:
        candidate = self._clean_application_candidate(candidate)
        if not candidate:
            return candidate
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
            answer = self._clean_application_candidate(answer.splitlines()[0].strip().strip("`\"'"))
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
            # Extract the last Windows absolute path on the line.
            # The label emitted by SystemTool ("Found in C:\...: C:\...") also
            # contains drive-letter colons, so we can't rely on splitting at the
            # first colon.  Instead find every occurrence of a drive-letter path
            # and take the last one, which is always the actual executable path.
            matches = re.findall(r"[A-Za-z]:[\\/][^\s\"']+", line)
            if matches:
                return matches[-1].strip().strip('"')
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
            result = self._execute(router, "system", action="launch_application_path", application_name=requested, application_path=cached)
            if result is not None and "no longer valid" not in result.lower():
                return result

        app_name = self._resolve_application_name(router, requested)
        discovered = self._execute(router, "system", action="find_application", application_name=app_name)
        path = self._first_verified_path(discovered)
        if path:
            self.apps.remember(app_name, path, source="system-discovery")
            if action == "launch":
                return self._execute(router, "system", action="launch_application_path", application_name=app_name, application_path=path)
            return f"Found '{app_name}' at {path}"
        return discovered

    @staticmethod
    def _match(prompt: str) -> str | None:
        """Route only unambiguous capabilities before the normal LLM path."""
        text = prompt.lower().strip()

        for prefix in (
            "search the web for ", "search the web ", "search web for ",
            "search online for ", "look up ", "google ", "find information about ",
        ):
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

        # Match application launch/find requests, but exclude common non-app
        # verb phrases that happen to start with the same trigger words.
        # The negative lookahead blocks things like "open a new tab",
        # "run the test suite", "start a timer", "launch into details", etc.
        _NON_APP_PATTERN = re.compile(
            r"^(?:open|launch|start|run|find|locate|where is)\s+"
            r"(?:a\s+|an\s+|the\s+)?"
            r"(?:new\s+|my\s+)?"
            r"(?:tab|window|file|folder|terminal|command|cmd|shell|browser|"
            r"test|tests|suite|timer|task|tasks|meeting|note|notes|search|"
            r"url|link|connection|session|server|service|process|script|"
            r"dialog|menu|settings|preferences|prompt|instance)\b",
            re.IGNORECASE,
        )
        app_match = re.match(r"^(find|locate|where is|open|launch|start|run)\s+(?:the\s+)?(.+?)\s*[.!?]*$", text)
        if app_match:
            verb, raw_name = app_match.groups()
            # "Where is <place/person/topic>?" is normally a knowledge
            # question, not an application lookup. Keep that route opt-in by
            # requiring an explicit application qualifier for this otherwise
            # ambiguous phrasing; "find" and "locate" remain concise app
            # discovery commands.
            if verb == "where is" and not re.search(
                r"\b(?:app|application|program)\b", raw_name, re.IGNORECASE
            ):
                return None
            name = NaturalCapabilityRouter._clean_application_candidate(raw_name)
            # Reject if the full original text looks like a non-app command
            if name and not _NON_APP_PATTERN.match(text):
                action = "find" if verb in {"find", "locate", "where is"} else "launch"
                return f"application:{action}:{name}"
        return None

    def _dispatch(self, router: Any, prompt: str, match: str) -> str | None:
        parts = match.split(":", 2)
        if parts[0] == "web":
            if parts[1] == "missing":
                return "Usage: search the web for <query>"
            return self._execute(router, "web", action="search", query=parts[2], _prompt=prompt)
        if parts[0] == "system" and parts[1] == "info":
            return self._execute(router, "system", action="info", _prompt=prompt)
        if parts[0] == "context":
            return self._execute(router, "context", action=parts[1], _prompt=prompt)
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
