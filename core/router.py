from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from core.brain import Brain
from core.personality import ATLASPersonality
from memory.facts import FactStore


class Router:
    """Intelligent request router for ATLAS.

    The router decides whether a prompt should stay with the LLM, use
    memory, or dispatch to a registered tool. Tools are looked up through a
    single cached ``ToolRegistry`` so new tools can be added without editing
    the router.
    """

    def __init__(
        self,
        brain: Brain | None = None,
        personality: ATLASPersonality | None = None,
        memory: FactStore | None = None,
        registry=None,
        config=None,
    ) -> None:
        self.brain = brain or Brain()
        self.personality = personality or ATLASPersonality()
        self.memory = memory or FactStore()
        if registry is None:
            from tools.registry import ToolRegistry

            registry = ToolRegistry()
            registry.discover()
        self._registry = registry
        self._config = config

    def route(self, prompt: str) -> str:
        lowered = prompt.lower().strip()

        if lowered.startswith("/"):
            return self.personality.respond(self._handle_command(lowered))

        if lowered.startswith("remember "):
            return self.personality.respond(self._remember_memory(prompt))

        if lowered.startswith("forget "):
            return self.personality.respond(self._forget(prompt))

        if lowered.startswith("recall "):
            return self.personality.respond(self._recall(prompt))

        if lowered.startswith("search "):
            return self.personality.respond(self._search(prompt))

        if self._looks_like_tool_request(lowered):
            return self.personality.respond(self._dispatch_tool(lowered))

        return self.personality.respond(self.brain.ask(prompt))

    def stream(self, prompt: str) -> Iterator[str]:
        lowered = prompt.lower().strip()

        if lowered.startswith("/"):
            yield self._handle_command(lowered)
            return

        if lowered.startswith("remember "):
            yield self._remember_memory(prompt)
            return

        if lowered.startswith("forget "):
            yield self._forget(prompt)
            return

        if lowered.startswith("recall "):
            yield self._recall(prompt)
            return

        if lowered.startswith("search "):
            yield self._search(prompt)
            return

        if self._looks_like_tool_request(lowered):
            yield self._dispatch_tool(lowered)
            return

        if self.brain.stream:
            yield from self.brain.ask_stream(prompt)
            return

        yield self.brain.ask(prompt)

    def _remember_memory(self, prompt: str) -> str:
        remainder = prompt.split(maxsplit=1)[1].strip() if " " in prompt else ""
        if not remainder:
            return "Usage: remember <key> <value>  or  remember <key> <value> --category=<category>"

        # Parse category
        category = "fact"
        parts = remainder.split()
        if "--category=" in remainder:
            for i, part in enumerate(parts):
                if part.startswith("--category="):
                    category = part.split("=", 1)[1]
                    parts.pop(i)
                    break
            remainder = " ".join(parts)

        key, _, value = remainder.partition(" ")
        key = key.strip()
        value = value.strip()
        if not key or not value:
            return "Usage: remember <key> <value>"

        # Use the appropriate category method
        if category == "preference":
            self.memory.remember_preference(key, value)
        elif category == "task":
            self.memory.remember_task(key, value)
        elif category == "event":
            self.memory.remember_event(key, value)
        elif category == "project":
            self.memory.remember_project(key, value)
        elif category == "goal":
            self.memory.remember_goal(key, value)
        else:
            self.memory.remember(key, value, category=category)
        return f"Memory updated in category '{category}'."

    def _forget(self, prompt: str) -> str:
        key = prompt.split(maxsplit=1)[1].strip() if " " in prompt else ""
        if not key:
            return "Usage: forget <key>"

        deleted = self.memory.forget(key)
        return f"Memory removed for '{key}'." if deleted else f"No memory found for '{key}'."

    def _recall(self, prompt: str) -> str:
        key = prompt.split(maxsplit=1)[1].strip() if " " in prompt else ""
        if not key:
            return "Usage: recall <key>"

        value = self.memory.recall(key)
        return value if value is not None else f"No memory found for '{key}'."

    def _search(self, prompt: str) -> str:
        term = prompt.split(maxsplit=1)[1].strip() if " " in prompt else ""
        if not term:
            return "Usage: search <term>"

        results = self.memory.search(term)
        if not results:
            return f"No results for '{term}'."

        normalized = [result.split("=", 1)[-1] if "=" in result else result for result in results]
        return " | ".join(normalized)

    def _looks_like_tool_request(self, lowered: str) -> bool:
        for tool_name in self._registry.list():
            if tool_name in lowered:
                return True

        return any(
            phrase in lowered
            for phrase in (
                "system",
                "computer",
                "hardware",
                "file",
                "read",
                "write",
                "folder",
                "web",
                "internet",
                "browser",
                "url",
                "search web",
                "look up",
                "minecraft",
                "screenshot",
                "ocr",
                "camera",
            )
        )

    def _extract_path(self, text: str) -> str:
        """Pull a plausible filesystem path out of a natural-language prompt."""
        patterns = (
            re.compile(r"['\"]([^'\"]+)['\"]"),
            re.compile(r"[A-Za-z]:[\\/][^\s,;]+"),
            re.compile(r"[\w.\\/ -]+\.(?:txt|md|py|json|csv|log|ini|yaml|yml|js|ts|html|css|png|jpg)[\s,;.?!]?"),
        )
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                candidate = match.group(1) if match.lastindex else match.group(0)
                return candidate.strip().strip(".,;?!")
        return ""

    def _extract_url(self, text: str) -> str:
        match = re.search(r"(https?://[^\s]+)", text, re.IGNORECASE)
        return match.group(1).rstrip(".,;?!") if match else ""

    def _file_request(self, prompt: str) -> str:
        """Handle read/write/append/delete/list requests against the file tool."""
        from tools.file_tool import FileTool

        lowered = prompt.lower().strip()
        if "append" in lowered:
            action = "append"
        elif "delete" in lowered or "remove" in lowered:
            action = "delete"
        elif "write" in lowered or "create" in lowered or "save" in lowered:
            action = "write"
        elif "list" in lowered or "folder" in lowered or "directory" in lowered:
            action = "list"
        else:
            action = "read"

        path = self._extract_path(prompt)
        if not path:
            if action in {"read", "write", "append", "delete"}:
                return "Please include a file path. Example: read C:\\Users\\you\\notes.txt"
            return "Please include a directory path. Example: list C:\\Users\\you"

        content = ""
        if action == "write":
            marker_match = re.search(r"\b(?:that says|with the content|containing|:)\s+(.+)", prompt, re.IGNORECASE)
            if marker_match:
                content = marker_match.group(1).strip().strip("'\"")

        try:
            return FileTool().execute(action=action, path=path, content=content)
        except Exception as exc:
            return f"File operation failed: {exc}"

    def _dispatch_tool(self, prompt: str) -> str:
        lowered = prompt.lower().strip()

        if "screenshot" in lowered:
            from vision.screenshot import Screenshot

            img = Screenshot().capture()
            return "Screenshot captured successfully." if img is not None else "Failed to capture screenshot."

        if "minecraft" in lowered:
            return "Minecraft tool stub is ready for integration."

        if any(k in lowered for k in ("file", "read", "write", "append", "delete", "folder", "directory")) or self._extract_path(prompt):
            return self._file_request(prompt)

        if any(k in lowered for k in ("system", "computer", "hardware")):
            tool = self._registry.get("system")
            if tool is not None:
                try:
                    return tool.execute()
                except Exception as exc:
                    return f"System tool failed: {exc}"
            from tools.system import get_system_info

            return get_system_info()

        if any(k in lowered for k in ("web", "internet", "browser", "url", "search web", "look up")):
            tool = self._registry.get("web")
            if tool is not None:
                try:
                    url = self._extract_url(lowered)
                    if url:
                        return tool.execute(action="fetch", url=url)
                    query = prompt
                    for word in ("web", "internet", "browser", "search", "look up", "find", "what is", "what's"):
                        query = re.sub(rf"\b{word}\b", "", query, flags=re.IGNORECASE)
                    return tool.execute(action="search", query=query.strip())
                except Exception as exc:
                    return f"Web tool failed: {exc}"
            from tools.web import fetch_url

            url = self._extract_url(lowered)
            if url:
                try:
                    return fetch_url(url)
                except Exception as exc:
                    return f"Web fetch failed: {exc}"
            return "Web tool is ready. Try: web search <query>"

        return "No matching tool found. I can help with system info, file operations, web lookups, and screenshots."

    def _handle_command(self, command: str) -> str:
        command = command.lower()

        if command == "/help":
            return "Commands: /help, /status, /tools, /memory, /clear, /config, /reload, /exit"
        if command == "/status":
            return (
                f"ATLAS status: brain online, memory connected, router ready.\n"
                f"Loaded tools: {len(self._registry.list())} · Memories: {len(self.memory.search(''))}"
            )
        if command == "/tools":
            return f"Loaded tools: {', '.join(self._registry.list())}"
        if command == "/memory":
            memories = self.memory.search("")
            return f"Memory count: {len(memories)} entries"
        if command == "/memory categories":
            categories = {"fact", "preference", "task", "event", "goal", "project", "short_term", "long_term"}
            return f"Available categories: {', '.join(sorted(categories))}"
        if command.startswith("/memory ") and not command.startswith("/memory categories"):
            # /memory fact or /memory preference etc.
            parts = command.split(maxsplit=2)
            if len(parts) >= 3 and parts[1] in ["fact", "preference", "task", "event", "goal", "project"]:
                cat = parts[1]
                term = parts[2]
                results = self.memory.db.search(term, limit=10)
                if not results:
                    return f"No memories found in category '{cat}' for '{term}'."
                items = [f"{r.content}" for r in results if r.category == cat]
                if items:
                    return f"Category '{cat}':\n" + "\n".join(items[:10])
                return f"No memories found in category '{cat}' for '{term}'."
            return "Usage: /memory [category] [term]  or /memory categories"
        if command == "/clear":
            self.brain.clear_history()
            return "Conversation history cleared."
        if command == "/config":
            return "Configuration is available in config.json."
        if command == "/reload":
            history = self.brain.history
            self.brain = Brain(config_manager=self._config) if self._config is not None else Brain()
            self.brain.history = history
            return "ATLAS components reloaded."
        if command == "/exit":
            return "Goodbye."
        if command == "/voice":
            return "Voice commands: /voice on, /voice off, /voice test, /voice status"
        if command == "/voice on":
            if hasattr(self, '_voice_controller') and self._voice_controller:
                self._voice_controller.set_enabled(True)
                self._voice_controller.start()
                return "Voice enabled. Press F8 to speak."
            return "Voice controller not available."
        if command == "/voice off":
            if hasattr(self, '_voice_controller') and self._voice_controller:
                self._voice_controller.set_enabled(False)
                return "Voice disabled."
            return "Voice controller not available."
        if command == "/voice test":
            if hasattr(self, '_voice_controller') and self._voice_controller:
                self._voice_controller.speaker.speak("This is a voice test.")
                return "Voice test triggered."
            return "Voice controller not available."
        if command == "/voice status":
            if hasattr(self, '_voice_controller') and self._voice_controller:
                status = "enabled" if self._voice_controller.enabled else "disabled"
                return f"Voice is {status}. PTT key: {self._voice_controller._push_to_talk_key}"
            return "Voice controller not available."
        return "Unknown command. Use /help."
