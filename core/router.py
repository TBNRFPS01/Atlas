from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from core.autonomy import AutonomyController
from core.brain import Brain
from core.personality import ATLASPersonality
from core.permissions import Decision, PermissionManager
from core.safety import HardSafety, SafetyViolation
from core.skill_manager import SkillManager
from core.undo import UndoStack
from memory.experience import ExperienceStore
from memory.facts import FactStore
from memory.goals import GoalManager
from memory.state import AgentStateStore
from planner.evaluator import SelfEvaluator
from planner.strategies import StrategySelector


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
        state_store: AgentStateStore | None = None,
        goals: GoalManager | None = None,
        experiences: ExperienceStore | None = None,
        autonomy: AutonomyController | None = None,
    ) -> None:
        # Optional voice controller attached at runtime by main; annotate
        # here so Pylance knows the attribute exists.
        self._voice_controller: Any | None = None
        self._planner_inst: Any | None = None
        self._permissions = PermissionManager()
        self._safety = HardSafety()
        self._undo = UndoStack()
        self._trace: list[str] = []
        self._call_log: list[dict[str, Any]] = []
        if registry is None:
            from tools.registry import ToolRegistry

            registry = ToolRegistry()
            registry.discover()
        self._registry = registry
        self.brain = brain or Brain()
        self.personality = personality or ATLASPersonality()
        self.memory = memory or FactStore()
        # Skill system: discover + validate + load declarative skill packages.
        # Skills integrate with the existing permission/safety layers rather
        # than introducing a second policy system.
        self._skill_manager = SkillManager(
            skills_dir="skills",
            permission_manager=self._permissions,
            safety=self._safety,
            registry=self._registry,
        )
        self._skill_manager.load_all()
        self._skills = self._skill_manager.list()
        self._config = config

        # Persistent agent state, goals, and learned experience. These share
        # the same SQLite file as the fact store so everything survives restarts.
        self._state = state_store or AgentStateStore()
        self._goals = goals or GoalManager(memory=self.memory)
        self._experiences = experiences or ExperienceStore(memory=self.memory)
        self._strategy_selector = StrategySelector()
        self._self_evaluator = SelfEvaluator(experiences=self._experiences, brain=self.brain)
        self._autonomy = autonomy or AutonomyController(
            router=self,
            state_store=self._state,
            goals=self._goals,
            experiences=self._experiences,
            selector=self._strategy_selector,
            evaluator=self._self_evaluator,
        )

    def route(self, prompt: str) -> str:
        lowered = prompt.lower().strip()

        if lowered.startswith("/auto"):
            goal = prompt[5:].strip()
            if not goal:
                return self.personality.respond("Usage: /auto <goal>  e.g. /auto open VS Code and take a screenshot")
            return self.personality.respond(self._run_autonomous_mission(goal))

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

        if any(phrase in lowered for phrase in self._TASK_TRIGGER_PHRASES):
            return self.personality.respond(self._run_task(prompt))

        if self._skills:
            for skill in self._skills:
                if skill.enabled and skill.valid and skill.matches(lowered):
                    ok, reason = self._skill_manager.can_run(skill)
                    if not ok:
                        self._record_trace("skill", skill.name, "blocked")
                        return self.personality.respond(f"Skill '{skill.name}' blocked: {reason}")
                    return self.personality.respond(skill.run(self, prompt))

        # Direct Spotify commands (fallback if the spotify skill is unavailable)
        if lowered.startswith("spotify "):
            tool = self._registry.get("spotify")
            if tool is None:
                return self.personality.respond("Spotify tool not loaded.")
            return self.personality.respond(self._spotify_request(prompt))

        if self._looks_like_tool_request(prompt, lowered):
            return self.personality.respond(self._dispatch_tool(lowered))

        return self.personality.respond(self.brain.ask(prompt))

    def stream(self, prompt: str) -> Iterator[str]:
        lowered = prompt.lower().strip()

        if lowered.startswith("/auto"):
            goal = prompt[5:].strip()
            yield self._run_autonomous_mission(goal) if goal else "Usage: /auto <goal>"
            return

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

        if any(phrase in lowered for phrase in self._TASK_TRIGGER_PHRASES):
            yield self._run_task(prompt)
            return

        if self._skills:
            for skill in self._skills:
                if skill.enabled and skill.valid and skill.matches(lowered):
                    ok, reason = self._skill_manager.can_run(skill)
                    if not ok:
                        yield f"Skill '{skill.name}' blocked: {reason}"
                        return
                    yield skill.run(self, prompt)
                    return

        if self._looks_like_tool_request(prompt, lowered):
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

    # Multi-word phrases that are unambiguous tool commands, matched
    # anywhere in the message.
    _TOOL_TRIGGER_PHRASES = (
        "system info", "system information", "computer info", "hardware info",
        "cpu info", "memory info", "read file", "write file", "open file",
        "delete file", "append to file", "list folder", "list directory",
        "search the web", "search web for", "look up", "browse to",
        "open website", "open url", "fetch url", "minecraft status",
        "open browser", "browse to", "click on", "type into", "fill form",
        "navigate to", "browser navigate", "browser click", "browser type",
        "browser screenshot", "browser status", "read the page", "read page",
        "take a screenshot", "take screenshot", "capture screen",
        "run ocr", "read the screen", "open camera", "take a photo",
        "open app", "launch app", "open application", "launch application",
        "open program", "start app", "run app", "run program",
        "close window", "minimize window", "maximize window", "list windows",
        "focus window", "switch to window", "activate window",
        "kill process", "stop process", "list processes", "start process",
        "copy to clipboard", "set clipboard", "paste clipboard",
        "what is on my clipboard", "read clipboard",
        "move mouse", "click at", "double click", "right click",
        "mouse position", "scroll down", "scroll up",
        "what is on my screen", "what's on my screen", "active window",
        "current window", "running apps", "desktop context",
        "type the following", "press enter", "press tab", "press esc",
        "press ctrl", "press alt", "press shift", "press space",
    )

    # Phrases that hand a whole goal to the autonomous planner.
    _TASK_TRIGGER_PHRASES = (
        "complete the task", "complete this task", "auto complete",
        "do the task", "run the task", "execute this task",
        "automate this", "handle this task",
    )

    # Action verbs that, when they open the message, make a bare tool-name
    # mention (e.g. "system", "file", "web") a likely command rather than
    # a normal sentence that happens to contain the word.
    _ACTION_VERBS = {
        "open", "read", "write", "append", "delete", "remove", "list",
        "check", "find", "search", "look", "take", "capture", "launch",
        "start", "run", "fetch", "browse", "screenshot", "show", "get",
        "send", "email", "play", "stop", "pause", "ping",
    }

    def _looks_like_tool_request(self, prompt: str, lowered: str) -> bool:
        # A literal file path or URL in the message is an unambiguous signal
        # regardless of wording ("read C:\notes.txt", "open example.com").
        if self._extract_path(lowered) or self._extract_url(lowered):
            return True

        if any(phrase in lowered for phrase in self._TOOL_TRIGGER_PHRASES):
            return True

        # Direct computer-control prefixes (type/press/click/scroll) and
        # automation phrases are unambiguous commands.
        if self._looks_like_automation_command(lowered):
            return True

        words = re.findall(r"[a-z0-9']+", lowered)
        if not words:
            return False

        tool_name_hit = any(
            re.search(rf"\b{re.escape(name)}\b", lowered)
            for name in self._registry.list()
        )
        if not tool_name_hit:
            return False

        # Only treat a bare tool-name mention as a command if the message
        # also opens with an action verb - otherwise it's almost certainly
        # ordinary conversation that happens to mention the word (e.g.
        # "what's a good system for learning guitar").
        return bool(set(words[:3]) & self._ACTION_VERBS)

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

    def _confirmed(self, prompt: str) -> bool:
        """Whether the user explicitly approved a destructive action."""
        return bool(re.search(r"\b(?:yes|confirm|go ahead|do it|sure|proceed)\b", prompt.lower()))

    def _authorize(self, tool_name: str, action: str, *, permission_level: str = "basic",
                   confirmation_required: bool = False, prompt: str = "", path: str | None = None) -> str | None:
        """Gate a tool action behind safety boundaries and the permission manager.

        Returns ``None`` when the action may proceed, otherwise a
        confirmation/denial message to show the user. Hard safety boundaries
        always win, even over an ``allow`` permission rule.
        """
        if not self._safety.is_safe(tool_name, action, path):
            self._record_trace(tool_name, action, "hard-safety-denied")
            return "Blocked by hard safety boundary: this action is forbidden."

        decision = self._permissions.decide(
            tool_name,
            action,
            permission_level=permission_level,
            confirmation_required=confirmation_required,
            confirmed=self._confirmed(prompt),
        )
        if decision == Decision.DENY:
            self._record_trace(tool_name, action, "denied")
            return "Permission denied for this action."
        if decision == Decision.ASK:
            self._record_trace(tool_name, action, "awaiting confirmation")
            return self._permissions.confirmation_prompt(tool_name, action)
        return None

    def _timed_tool_call(self, tool_name: str, action: str, fn) -> str:
        """Execute ``fn`` while recording duration, success, and errors for /debug."""
        import time

        start = time.perf_counter()
        try:
            result = fn()
            ok, error = True, ""
        except Exception as exc:
            result = f"{tool_name} error: {exc}"
            ok, error = False, str(exc)
        duration = time.perf_counter() - start
        self._call_log.append(
            {"tool": tool_name, "action": action, "ok": ok, "duration": duration, "error": error}
        )
        if len(self._call_log) > 200:
            self._call_log = self._call_log[-200:]
        self._record_trace(tool_name, action, "ok" if ok else "error")
        return result

    def _record_trace(self, tool_name: str, action: str, outcome: str) -> None:
        """Append a compact dispatch record for the /debug observability view."""
        from datetime import datetime

        entry = f"{datetime.now().strftime('%H:%M:%S')} {tool_name}.{action} -> {outcome}"
        self._trace.append(entry)
        if len(self._trace) > 100:
            self._trace = self._trace[-100:]

    def _describe_screen(self) -> str:
        """Capture and describe the screen using vision + context + optional OCR."""
        try:
            from vision.understand import describe_screen

            result = describe_screen(brain=self.brain)
            self._record_trace("vision", "describe_screen", "ok" if result else "empty")
            return result or "Screen captured but nothing could be described."
        except Exception as exc:
            return f"Screen description failed: {exc}"

    def _file_request(self, prompt: str) -> str:
        """Handle read/write/append/delete/list requests against the file tool."""
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

        if action == "delete":
            gate = self._authorize("file", "delete", permission_level="destructive",
                                   confirmation_required=True, prompt=prompt, path=path)
            if gate:
                return gate
            # Destructive but reversible: move to trash instead of permanent delete.
            return self._trash_file(path)

        content = ""
        if action == "write":
            marker_match = re.search(r"\b(?:that says|with the content|containing|:)\s+(.+)", prompt, re.IGNORECASE)
            if marker_match:
                content = marker_match.group(1).strip().strip("'\"")

        tool = self._registry.get("file")
        if tool is None:
            from tools.file_tool import FileTool

            tool = FileTool()

        return self._timed_tool_call(
            "file", action,
            lambda: tool.execute(action=action, path=path, content=content),
        )

    def _trash_file(self, path: str) -> str:
        """Move a file to the ATLAS trash folder and record an undo entry."""
        import shutil

        from pathlib import Path

        src = Path(path)
        if not src.exists():
            return f"No such file: {path}"

        trash_dir = Path.home() / ".atlas" / "trash"
        trash_dir.mkdir(parents=True, exist_ok=True)
        stamp = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        dest = trash_dir / f"{stamp}_{src.name}"

        try:
            shutil.move(str(src), str(dest))
        except Exception as exc:
            return f"Failed to move {path} to trash: {exc}"

        self._undo.record(
            f"delete {src.name}",
            lambda d=str(dest), s=str(src): shutil.move(d, s),
        )
        return (
            f"Moved to trash (reversible): {dest}\n"
            f"Say '/undo' to restore it to {src}."
        )

    def _take_screenshot(self) -> str:
        """Capture the screen, save it to disk, and report a verifiable path."""
        from datetime import datetime
        from pathlib import Path

        from vision.screenshot import Screenshot

        try:
            img = Screenshot().capture()
        except Exception as exc:
            return f"Failed to capture screenshot: {exc}"
        if img is None:
            return "Failed to capture screenshot."

        folder = Path.home() / ".atlas" / "screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"screenshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        try:
            from PIL import Image
            from io import BytesIO

            arr = Image.fromarray(img)
            arr.save(path)
            try:
                buf = BytesIO()
                arr.save(buf, format="PNG")
                description = self.brain.analyze_image(buf.getvalue(), "Describe this screenshot briefly.")
                if description and all(b not in description.lower() for b in ("request failed", "connection failed", "error")):
                    self._record_trace("vision", "analyze", "ok")
                    return f"Screenshot saved to {path}\nVision: {description}"
            except Exception:
                pass
            return f"Screenshot saved to {path}"
        except Exception as exc:
            return f"Screenshot captured but could not be saved: {exc}"

    def _extract_minecraft_server(self, text: str) -> str:
        """Pull a hostname, localhost, or IP (optionally with port) from a prompt."""
        pattern = re.compile(
            r"\b(?:[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+\.[a-zA-Z]{2,}(?::\d{1,5})?|localhost(?::\d{1,5})?|(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?)\b"
        )
        match = pattern.search(text)
        return match.group(0) if match else ""

    def _minecraft_status(self, _prompt: str) -> str:
        """Deprecated alias; use :meth:`_minecraft_request`."""
        return self._minecraft_request(_prompt)

    def _minecraft_request(self, prompt: str) -> str:
        """Report Minecraft status, querying a server when one is mentioned."""
        tool = self._registry.get("minecraft")
        if tool is not None:
            return self._timed_tool_call(
                "minecraft", "status",
                lambda: tool.execute(action="status", server=self._extract_minecraft_server(prompt)),
            )
        from tools.minecraft import minecraft_status

        return minecraft_status()

    def _spotify_request(self, prompt: str) -> str:
        """Dispatch a Spotify command using the loaded SpotifyTool."""
        tool = self._registry.get("spotify")
        if tool is None:
            return "Spotify tool not loaded."
        return self._timed_tool_call(
            "spotify", "dispatch",
            lambda: tool.execute(**self._parse_spotify_args(prompt)),
        )

    def _browser_request(self, prompt: str) -> str:
        """Handle browser automation requests with natural-language parsing."""
        lowered = prompt.lower().strip()
        tool = self._registry.get("browser")
        if tool is None:
            return "Browser tool not loaded."

        action, args = self._build_browser_args(prompt, lowered)

        # Browser actions are gated by hard-safety boundaries and deny rules,
        # but are otherwise allowed by default so the agent can operate sites
        # autonomously. (An explicit deny rule still blocks them.)
        gate = self._authorize("browser", action, permission_level="basic",
                               confirmation_required=False, prompt=prompt)
        if gate:
            return gate

        return self._timed_tool_call(
            "browser", action,
            lambda: tool.execute(**args),
        )

    def _build_browser_args(self, prompt: str, lowered: str) -> tuple[str, dict[str, Any]]:
        """Parse a natural-language browser command into BrowserTool args."""

        def _strip_to(target: str) -> str:
            target = target.strip().strip("\"'")
            if target.lower().startswith("to "):
                target = target[3:].strip()
            return target

        # Direct navigation.
        for prefix in ("browser navigate ", "browser open ", "open browser ", "browse to ", "navigate to ", "open url ", "open website "):
            if lowered.startswith(prefix):
                target = _strip_to(prompt[len(prefix):])
                return "navigate", {"action": "navigate", "url": target}

        if "browser click" in lowered or "click on" in lowered or ("click " in lowered and "browser" in lowered):
            sel = self._after_phrase(prompt, "click on") or self._after_phrase(prompt, "click")
            return "click", {"action": "click", "selector": sel}

        if "browser type" in lowered or "type into" in lowered or ("type " in lowered and "browser" in lowered):
            if "type into" in lowered:
                head = self._after_phrase(prompt, "type into")
            else:
                head = self._after_phrase(prompt, "browser type")
            selector = head
            text = ""
            if " with " in lowered:
                selector, _, text = head.partition(" with ")
                text = text.strip().strip("\"'")
            return "type", {"action": "type", "selector": selector.strip(), "text": text}

        if "fill" in lowered or "fill form" in lowered:
            sel = self._after_phrase(prompt, "fill")
            text = ""
            if " with " in lowered:
                sel, _, text = sel.partition(" with ")
                text = text.strip().strip("\"'")
            return "fill", {"action": "fill", "selector": sel.strip(), "text": text}

        if "browser scroll" in lowered or "scroll down" in lowered or "scroll up" in lowered:
            direction = "up" if "scroll up" in lowered else "down"
            amount = 300
            m = re.search(r"-?\d+", lowered)
            if m:
                amount = int(m.group())
            return "scroll", {"action": "scroll", "direction": direction, "amount": amount}

        if "browser screenshot" in lowered or lowered.startswith("screenshot "):
            return "screenshot", {"action": "screenshot"}

        if "browser status" in lowered or "browser state" in lowered:
            return "status", {"action": "status"}

        if "read the page" in lowered or "read page" in lowered or "page text" in lowered:
            return "get_text", {"action": "get_text"}

        if "close browser" in lowered or "quit browser" in lowered:
            return "close", {"action": "close"}

        # Default: treat the whole message as a navigation target.
        url = self._extract_url(lowered)
        if url:
            return "navigate", {"action": "navigate", "url": url}
        return "status", {"action": "status"}

    def _planner(self):
        """Lazily build the task planner bound to this router."""
        if self._planner_inst is None:
            from planner.planner import Planner

            self._planner_inst = Planner(router=self)
        return self._planner_inst

    def _extract_goal(self, prompt: str) -> str:
        """Pull a goal out of a natural-language task request."""
        lowered = prompt.lower().strip()
        for phrase in sorted(self._TASK_TRIGGER_PHRASES, key=len, reverse=True):
            idx = lowered.find(phrase)
            if idx != -1:
                remainder = prompt[idx + len(phrase):].strip(":,. -")
                if remainder:
                    return remainder
        return prompt.strip()

    def _run_task(self, goal: str) -> str:
        """Decompose a goal and execute it end to end, reporting each step."""
        selection = self._strategy_selector.select(goal, experiences=self._experiences)
        plan = self._planner().run_plan(goal, strategy_hint=selection.hint)
        lines = [f"Goal: {plan['goal']}", f"Success: {plan['success']}"]
        for task in plan["tasks"]:
            lines.append(f"- [{task['status']}] {task['description']}")
            if task["result"]:
                lines.append(f"    -> {task['result'][:200]}")
            if task["error"]:
                lines.append(f"    ! {task['error']}")
        return "\n".join(lines)

    def _run_autonomous_mission(self, goal: str) -> str:
        """Run ``/auto``: a persistent, adaptive, self-evaluated mission."""
        try:
            report = self._autonomy.run_auto(goal)
            text = report.to_text()
        except Exception as exc:
            text = f"Autonomous mission failed to start: {exc}"
        return text

    # -- persistent goals / learning -----------------------------------
    def _goals_command(self, command: str) -> str:
        """Handle ``/goals`` and its subcommands."""
        lowered = command.strip().lower()

        if lowered == "/goals":
            goals = self._goals.list_goals(limit=20)
            if not goals:
                return (
                    "No goals yet. Create one with '/goals add <title>' or run "
                    "'/auto <goal>' which saves a tracked goal automatically."
                )
            lines = ["Goals (status / priority / progress):"]
            for g in goals:
                marker = {"active": "►", "paused": "‖", "blocked": "●", "done": "✓", "abandoned": "✕"}.get(g.status, "?")
                lines.append(f"#{g.id} {marker} {g.title} [{g.status}, p{g.priority:.0f}, {g.progress*100:.0f}%]")
                if g.meta.get("block_reason"):
                    lines.append(f"     blocked: {g.meta['block_reason']}")
            return "\n".join(lines)

        parts = lowered.split(maxsplit=2)

        if len(parts) < 2:
            return (
                "Usage: /goals add <title> | done <id> | pause <id> | resume <id> | "
                "abandon <id> | priority <id> <value> | next"
            )

        _, sub = parts[0], parts[1]

        if sub == "add":
            title = command.split(maxsplit=2)[2].strip() if len(parts) > 2 else ""
            if not title:
                return "Usage: /goals add <title>"
            goal = self._goals.create_goal(title, source="user")
            return f"Goal #{goal.id} created: {goal.title}"

        if sub == "next":
            goal = self._goals.pick_next()
            if goal is None:
                return "No active goals to advance. Add one with '/goals add <title>'."
            report = self._autonomy.advance_goal(goal.id, max_tasks=1, consent="user")
            return report.to_text()

        goal_id = self._parse_goal_id(parts[2]) if len(parts) > 2 else None
        if goal_id is None:
            return "A numeric goal id is required."

        if sub == "done":
            updated = self._goals.complete_goal(goal_id)
            return f"Goal #{goal_id} marked done." if updated else f"No goal #{goal_id}."
        if sub == "pause":
            updated = self._goals.pause_goal(goal_id)
            return f"Goal #{goal_id} paused." if updated else f"No goal #{goal_id}."
        if sub == "resume":
            updated = self._goals.resume_goal(goal_id)
            return f"Goal #{goal_id} resumed (active again)." if updated else f"No goal #{goal_id}."
        if sub == "abandon":
            updated = self._goals.abandon_goal(goal_id)
            return f"Goal #{goal_id} abandoned." if updated else f"No goal #{goal_id}."
        if sub == "priority":
            rest = parts[2].split()
            if len(rest) < 2:
                return "Usage: /goals priority <id> <value>"
            try:
                value = float(rest[1])
            except ValueError:
                return "Priority must be a number."
            updated = self._goals.update_goal(goal_id, priority=value)
            return f"Goal #{goal_id} priority set to {value}." if updated else f"No goal #{goal_id}."

        return f"Unknown subcommand '{sub}'. Run /help for the goals syntax."

    @staticmethod
    def _parse_goal_id(part: str) -> int | None:
        import re as _re

        match = _re.search(r"\d+", part)
        if not match:
            return None
        try:
            return int(match.group())
        except ValueError:
            return None

    def _lessons_report(self) -> str:
        """Show what ATLAS has learned so far (experience + lessons)."""
        lines = ["Learned strategies (task type -> approach, success rate, runs):"]
        strategies = self._experiences.all_strategies(limit=8)
        if not strategies:
            lines.append("  (no recorded attempts yet - run /auto or complete goals to build experience)")
        else:
            for s in strategies:
                lines.append(
                    f"  {s['task_type']} -> {s['strategy_key']} "
                    f"({s['avg_success']:.0%} across {s['run_count']} run(s))"
                )
        lessons = self._experiences.recent_lessons(limit=5)
        if lessons:
            lines.append("Recent lessons:")
            for lesson in lessons:
                lines.append(f"  - {lesson[:200]}")
        return "\n".join(lines)

    def _state_report(self) -> str:
        """Show the persistent agent state snapshot (non-sensitive)."""
        state = self._state.all()
        goals = self._goals.active_goals(limit=5)
        lines = [
            "Persistent agent state:",
            f"  State keys: {self._state.count()}",
            f"  Active goals: {len(goals)}",
            f"  Strategy pairs recorded: {self._experiences.count()}",
        ]
        for key in sorted(state)[:8]:
            value = state[key]
            preview = str(value)[:80]
            lines.append(f"    {key} = {preview}")
        return "\n".join(lines)

    # Automation keywords handled without a full planner plan.
    _AUTOMATION_PHRASES = (
        "open app", "launch app", "open application", "launch application",
        "open program", "start app", "run app", "run program",
        "close window", "minimize window", "maximize window", "list windows",
        "focus window", "switch to window", "activate window",
        "kill process", "stop process", "list processes", "start process",
        "clipboard", "mouse position", "move mouse", "copy to clipboard",
        "active window", "current window", "running apps",
        "read the screen", "what is on my screen", "what's on my screen",
        "desktop context",
    )

    def _looks_like_automation_command(self, lowered: str) -> bool:
        if lowered.startswith(("type ", "press ", "click ", "scroll ")):
            return True
        return any(phrase in lowered for phrase in self._AUTOMATION_PHRASES)

    def _automation_dispatch(self, prompt: str) -> str:
        """Translate a natural-language automation request into tool args."""
        lowered = prompt.lower().strip()
        tool = self._registry.get("automation")
        if tool is None:
            return "Automation tool not loaded."

        # Gate destructive automation actions behind explicit confirmation.
        destructive = None
        if "kill process" in lowered or "stop process" in lowered:
            destructive = ("automation", "process_kill",
                          self._build_automation_args(prompt, lowered).get("name", ""))
        elif "close window" in lowered:
            destructive = ("automation", "windows_close",
                          self._build_automation_args(prompt, lowered).get("title", ""))

        if destructive is not None:
            tool_name, action, detail = destructive
            gate = self._authorize(tool_name, action, permission_level="destructive",
                                   confirmation_required=True, prompt=prompt)
            if gate:
                return gate

        args = self._build_automation_args(prompt, lowered)

        # Make clipboard writes reversible by recording the previous value.
        if args.get("action") == "clipboard_set":
            previous = self._capture_clipboard()
            def _write_and_record(prev=previous, new=args.get("text", "")):
                result = tool.execute(**args)
                if prev is not None:
                    self._undo.record(
                        f"clipboard set to '{new[:20]}'",
                        lambda p=prev: self._restore_clipboard(p),
                    )
                return result
            return self._timed_tool_call("automation", "clipboard_set", _write_and_record)

        return self._timed_tool_call("automation", args.get("action", "action"),
                                     lambda: tool.execute(**args))

    def _capture_clipboard(self) -> str | None:
        try:
            import pyperclip

            return pyperclip.paste()
        except Exception:
            return None

    def _restore_clipboard(self, value: str) -> None:
        import pyperclip

        pyperclip.copy(value)

    def _build_automation_args(self, prompt: str, lowered: str) -> dict[str, Any]:
        """Parse a natural-language automation command into tool arguments."""
        if lowered.startswith("type "):
            return {"action": "keyboard_type", "text": prompt[len("type "):].strip().strip("\"'")}

        if lowered.startswith("press "):
            keys = [k for k in lowered[len("press "):].split() if k]
            if len(keys) > 1:
                return {"action": "hotkey", "keys": ",".join(keys)}
            return {"action": "keyboard_press", "key": keys[0] if keys else ""}

        if lowered.startswith("scroll") or "scroll" in lowered:
            match = re.search(r"-?\d+", lowered)
            return {"action": "mouse_scroll", "clicks": int(match.group()) if match else 3}

        if "mouse position" in lowered or "where is my mouse" in lowered or "cursor position" in lowered:
            return {"action": "mouse_position"}

        if "move mouse" in lowered or lowered.startswith("move "):
            nums = re.findall(r"\d+", lowered)
            if len(nums) >= 2:
                return {"action": "mouse_move", "x": int(nums[0]), "y": int(nums[1])}
            return {"action": "mouse_position"}

        if lowered.startswith("click") or "click " in lowered or "click at" in lowered:
            nums = re.findall(r"\d+", lowered)
            button = "right" if "right click" in lowered else "middle" if "middle click" in lowered else "left"
            if len(nums) >= 2:
                return {"action": "mouse_click", "button": button, "x": int(nums[0]), "y": int(nums[1])}
            return {"action": "mouse_click", "button": button}

        if "clipboard" in lowered:
            if any(verb in lowered for verb in ("set", "copy", "write", "put")):
                text = ""
                if "clipboard to" in lowered:
                    text = prompt.split("clipboard to", 1)[1].strip().strip("\"'")
                elif "to clipboard" in lowered:
                    # Handle both "copy X to clipboard" and "copy to clipboard X"
                    # First try to get text after "to clipboard"
                    parts = prompt.split("to clipboard", 1)
                    if len(parts) > 1 and parts[1].strip():
                        text = parts[1].strip().strip("\"'")
                    else:
                        # Try "copy X to clipboard" pattern - text is between "copy" and "to clipboard"
                        copy_parts = prompt.split("copy", 1)
                        if len(copy_parts) > 1:
                            text = copy_parts[1].split("to clipboard", 1)[0].strip().strip("\"'")
                return {"action": "clipboard_set", "text": text}
            return {"action": "clipboard_get"}

        if lowered.startswith(("open app ", "open application ", "launch app ", "launch application ")):
            app = prompt.split(" ", 2)[2].strip().strip("\"'")
            return {"action": "windows_launch", "path": app}
        if lowered.startswith(("start app ", "run app ", "open program ", "run program ")):
            app = prompt.split(" ", 2)[2].strip().strip("\"'")
            return {"action": "windows_launch", "path": app}

        if "close window" in lowered:
            return {"action": "windows_close", "title": self._after_phrase(prompt, "close window")}
        if "minimize window" in lowered:
            return {"action": "windows_minimize", "title": self._after_phrase(prompt, "minimize window")}
        if "maximize window" in lowered:
            return {"action": "windows_maximize", "title": self._after_phrase(prompt, "maximize window")}
        if "list windows" in lowered:
            return {"action": "windows_list"}
        if any(phrase in lowered for phrase in ("focus window", "switch to window", "activate window", "focus", "switch to")):
            if "focus" in lowered:
                return {"action": "windows_activate", "title": self._after_phrase(prompt, "focus")}
            if "switch to" in lowered:
                return {"action": "windows_activate", "title": self._after_phrase(prompt, "switch to")}
            return {"action": "windows_activate", "title": self._after_phrase(prompt, "activate window")}

        if "list processes" in lowered:
            return {"action": "process_list"}
        if "kill process" in lowered or "stop process" in lowered:
            name = self._after_phrase(prompt, "kill process") or self._after_phrase(prompt, "stop process")
            return {"action": "process_kill", "name": name}
        if "start process" in lowered or "run program" in lowered:
            return {"action": "process_start", "command": self._after_phrase(prompt, "start process")}

        if "active window" in lowered or "current window" in lowered:
            return {"action": "context_window"}
        if "running apps" in lowered or ("apps" in lowered and "running" in lowered):
            return {"action": "context_apps"}
        if "read the screen" in lowered or "on my screen" in lowered:
            return {"action": "context_screen"}
        if "desktop context" in lowered:
            return {"action": "context_summary"}

        return {"action": "context_summary"}

    @staticmethod
    def _after_phrase(prompt: str, phrase: str) -> str:
        """Return the text following a phrase, stripped of punctuation."""
        lowered = prompt.lower()
        idx = lowered.find(phrase)
        if idx == -1:
            return ""
        return prompt[idx + len(phrase):].strip().strip(".,;!?\"'")

    def _email_request(self, prompt: str) -> dict[str, Any]:
        """Parse a natural-language email request into EmailTool args.

        Recognised forms (case-insensitive):
          - "send email to alice@example.com subject Hello body Hi there"
          - "email bob@example.com about lunch: can you make it?"
        """
        text = prompt.strip()
        lowered = text.lower()

        # Recipient: first email-shaped token.
        m = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        to = m.group(0) if m else ""

        subject = ""
        body = ""
        subject_match = re.search(r"\bsubject\s+(.+?)(?:\s+body\s+.*)?$", text, re.IGNORECASE)
        body_match = re.search(r"\bbody\s+(.+)$", text, re.IGNORECASE)
        about_match = re.search(r"\babout\s+(.+?)(?:\s+body\s+.*)?$", text, re.IGNORECASE)

        if subject_match:
            subject = subject_match.group(1).strip().strip("\"':")
        elif about_match:
            chunk = about_match.group(1).strip().strip("\"':")
            if ":" in chunk:
                subject, _, body = chunk.partition(":")
                subject = subject.strip()
                body = body.strip()
            else:
                subject = chunk

        if body_match:
            body = " ".join(body_match.group(1).strip().strip("\"':").split())

        return {"action": "send", "to": to, "subject": subject, "body": body}

    def _parse_spotify_args(self, prompt: str) -> dict[str, Any]:
        """Parse a natural-language Spotify request into SpotifyTool args.

        Recognised forms (case-insensitive):
          - "spotify play"
          - "spotify pause"
          - "spotify next"
          - "spotify previous"
          - "spotify current"
          - "spotify search <query>"
          - "spotify play <track/playlist/album uri>"
          - "spotify volume <0-100>"
          - "spotify devices"
          - "spotify auth"
        """
        text = prompt.strip()
        lowered = text.lower()

        # Remove "spotify" prefix
        if lowered.startswith("spotify "):
            remainder = text[len("spotify "):].strip()
        else:
            remainder = text

        if not remainder:
            return {"action": "current"}

        parts = remainder.split(maxsplit=1)
        action = parts[0].lower()
        query = parts[1] if len(parts) > 1 else ""

        # Map natural language to Spotify actions
        action_map = {
            "play": "play",
            "pause": "pause",
            "next": "next",
            "previous": "previous",
            "prev": "previous",
            "current": "current",
            "now": "current",
            "search": "search",
            "find": "search",
            "volume": "volume",
            "vol": "volume",
            "devices": "devices",
            "device": "devices",
            "auth": "auth",
            "authorize": "auth",
        }

        mapped_action = action_map.get(action, action)

        # Handle volume with number - Spotify tool expects 'volume' param
        if mapped_action == "volume" and query:
            vol_match = re.search(r"\d+", query)
            if vol_match:
                return {"action": "volume", "volume": int(vol_match.group(0))}

        return {"action": mapped_action, "query": query}

    def _debug_report(self) -> str:
        """Build an observability snapshot for the /debug command."""
        lines = [
            "=== ATLAS Debug Report ===",
            f"Brain provider: {getattr(self.brain, 'provider_name', 'unknown')}",
            f"Gateway enabled: {getattr(self.brain, 'gateway_enabled', False)}",
            f"Loaded tools ({len(self._registry.list())}): {', '.join(self._registry.list())}",
            f"Loaded skills ({len(self._skills)}): {', '.join(f'{s.name} v{s.version}' for s in self._skills) or 'none'}",
            f"Undo available: {self._undo.can_undo()}",
        ]
        try:
            lines.append(f"Memory entries: {len(self.memory.search(''))}")
        except Exception:
            lines.append("Memory entries: unavailable")

        lines.append(
            f"Autonomy: {len(self._goals.active_goals())} active goals · "
            f"{self._experiences.count()} strategy pairs · "
            f"{self._state.count()} state keys"
        )

        lines.append("Permission rules:")
        if self._permissions._rules:
            for key, decision in self._permissions._rules.items():
                lines.append(f"  {key}: {decision}")
            for key in self._permissions._authorized:
                lines.append(f"  {key}: authorized")
        else:
            lines.append("  (none configured - defaults in effect)")

        lines.append(f"Tool call log ({len(self._call_log)} entries):")
        if self._call_log:
            failures = [c for c in self._call_log if not c["ok"]]
            for c in self._call_log[-10:]:
                status = "ok" if c["ok"] else f"ERROR: {c['error']}"
                lines.append(f"  {c['tool']}.{c['action']} [{c['duration']*1000:.1f}ms] {status}")
            if failures:
                lines.append(f"  ({len(failures)} failed call(s) this session)")
        else:
            lines.append("  (no tool calls recorded this session)")

        lines.append(f"Recent trace ({len(self._trace)} entries):")
        if self._trace:
            lines.extend(f"  {entry}" for entry in self._trace[-15:])
        else:
            lines.append("  (no actions recorded this session)")
        return "\n".join(lines)

    def _dispatch_tool(self, prompt: str) -> str:
        lowered = prompt.lower().strip()
        self._record_trace("router", "dispatch", lowered[:40])

        if "screenshot" in lowered:
            return self._take_screenshot()

        if "minecraft" in lowered:
            return self._minecraft_request(prompt)

        if any(k in lowered for k in ("browser", "browse", "click on", "type into", "fill form", "navigate to", "open website", "open url")):
            return self._browser_request(prompt)

        if "email" in lowered or "send mail" in lowered or "send email" in lowered:
            tool = self._registry.get("email")
            if tool is None:
                return "Email tool not loaded."
            gate = self._authorize("email", "send", permission_level="elevated",
                                   confirmation_required=True, prompt=prompt)
            if gate:
                return gate
            return self._timed_tool_call(
                "email", "send",
                lambda: tool.execute(**self._email_request(prompt)),
            )

        # Computer-control commands take priority so "read the screen" or
        # "read clipboard" are not swallowed by the file branch below.
        if self._looks_like_automation_command(lowered):
            return self._automation_dispatch(prompt)

        if any(k in lowered for k in ("file", "read", "write", "append", "delete", "folder", "directory")) or self._extract_path(prompt):
            return self._file_request(prompt)

        if any(k in lowered for k in ("system", "computer", "hardware")):
            tool = self._registry.get("system")
            if tool is not None:
                return self._timed_tool_call("system", "info", lambda: tool.execute())
            from tools.system import get_system_info

            return self._timed_tool_call("system", "info", get_system_info)

        if any(k in lowered for k in ("web", "internet", "browser", "url", "search web", "look up")):
            tool = self._registry.get("web")
            if tool is not None:
                def _web():
                    url = self._extract_url(lowered)
                    if url:
                        return tool.execute(action="fetch", url=url)
                    query = prompt
                    for word in ("web", "internet", "browser", "search", "look up", "find", "what is", "what's"):
                        query = re.sub(rf"\b{word}\b", "", query, flags=re.IGNORECASE)
                    return tool.execute(action="search", query=query.strip())
                return self._timed_tool_call("web", "search", _web)
            from tools.web import fetch_url

            url = self._extract_url(lowered)
            if url:
                return self._timed_tool_call("web", "fetch", lambda: fetch_url(url))
            return "Web tool is ready. Try: web search <query>"

        return "No matching tool found. I can help with system info, file operations, web lookups, and screenshots."

    def _handle_command(self, command: str) -> str:
        command = command.lower()

        if command == "/help":
            return (
                "Commands: /help, /status, /tools, /memory, /debug, /undo, /skills, "
                "/screen, /browser, /clear, /config, /reload, /exit, /vision\n"
                "Autonomy: /auto <goal>, /goals, /goals add <title>, /goals done <id>, "
                "/goals pause <id>, /goals resume <id>, /goals priority <id> <value>, /goals next\n"
                "Learning: /lessons, /state"
            )

        if command == "/browser":
            return (
                "Browser commands (ATLAS operates real websites):\n"
                "  browser navigate to <url>\n"
                "  browser click <selector or text>\n"
                "  browser type <selector> with <text>\n"
                "  browser fill <selector> with <text>\n"
                "  browser scroll <up|down> [amount]\n"
                "  browser screenshot\n"
                "  browser status\n"
                "  read the page\n"
                "  close browser\n"
                "Sessions (cookies/login) are persisted between runs."
            )

        if command.startswith("/browser "):
            return self._browser_request(prompt[len("/browser "):].strip())

        if command == "/vision":
            return self._take_screenshot()

        if command == "/screen":
            return self._describe_screen()

        if command == "/undo":
            return self._undo.undo()

        if command == "/skills":
            status = self._skill_manager.status()
            if not status["skills"]:
                return "No skills loaded. Drop a skill package into the skills/ folder."
            lines = ["Loaded skills:"]
            for s in status["skills"]:
                trust = "trusted" if s["trusted"] else "untrusted"
                state = "ready" if (s["valid"] and s["enabled"]) else f"blocked: {s['error']}"
                lines.append(f"- {s['name']} v{s['version']} [{trust}] ({state})")
                lines.append(f"    {s['description']}")
                if s["permissions"]:
                    lines.append(f"    permissions: {', '.join(s['permissions'])}")
                if s["triggers"]:
                    lines.append(f"    triggers: {', '.join(s['triggers'])}")
            if status["rejected"]:
                lines.append("Rejected skills:")
                for r in status["rejected"]:
                    lines.append(f"- {r['name']} v{r['version']}: {r['error']}")
            return "\n".join(lines)

        if command == "/debug":
            return self._debug_report()
        if command == "/status":
            return (
                f"ATLAS status: brain online, memory connected, router ready.\n"
                f"Loaded tools: {len(self._registry.list())} · Memories: {len(self.memory.search(''))} · "
                f"Active goals: {len(self._goals.active_goals())}"
            )
        if command == "/goals" or command.startswith("/goals "):
            return self._goals_command(command)
        if command == "/lessons":
            return self._lessons_report()
        if command == "/state":
            return self._state_report()
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
            from voice.hardware import summarize_voice_hardware

            report = summarize_voice_hardware()
            if hasattr(self, '_voice_controller') and self._voice_controller:
                self._voice_controller.speaker.speak("This is a voice test.")
                return f"Voice test triggered.\n{report}"
            return f"Voice controller not available.\n{report}"
        if command == "/voice status":
            if hasattr(self, '_voice_controller') and self._voice_controller:
                status = "enabled" if self._voice_controller.enabled else "disabled"
                return f"Voice is {status}. PTT key: {self._voice_controller._push_to_talk_key}"
            return "Voice controller not available."
        return "Unknown command. Use /help."
