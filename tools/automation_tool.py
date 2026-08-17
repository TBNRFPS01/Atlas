"""Automation tool exposing full computer control to ATLAS.

Wraps the automation package (keyboard, mouse, clipboard, windows,
processes, and desktop context) behind the standard Tool interface so the
planner and the router can drive real actions on the machine.
"""

from __future__ import annotations

from tools.base import Tool, ToolMetadata, ToolParameter

_ACTIONS = (
    "keyboard_type", "keyboard_press", "hotkey",
    "mouse_move", "mouse_click", "mouse_scroll", "mouse_position",
    "clipboard_get", "clipboard_set",
    "windows_list", "windows_activate", "windows_close", "windows_minimize",
    "windows_maximize", "windows_launch",
    "process_list", "process_running", "process_kill", "process_start",
    "context_window", "context_apps", "context_screen", "context_summary",
)


class AutomationTool(Tool):
    """Drive keyboard, mouse, clipboard, windows, processes, and context."""

    name = "automation"
    description = (
        "Control the computer: type text, press keys, move/click the mouse, "
        "manage the clipboard, open/close/activate windows, start/stop processes, "
        "and retrieve desktop context."
    )
    metadata = ToolMetadata(
        category="automation",
        permission_level="elevated",
        confirmation_required=True,
        description=description,
    )

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="action", type="string", description=f"Automation action: {', '.join(_ACTIONS)}", required=True, enum=list(_ACTIONS)),
            ToolParameter(name="text", type="string", description="Text to type or copy", required=False),
            ToolParameter(name="key", type="string", description="Single key name to press", required=False),
            ToolParameter(name="keys", type="string", description="Comma-separated keys for a hotkey", required=False),
            ToolParameter(name="title", type="string", description="Window title to act on", required=False),
            ToolParameter(name="name", type="string", description="Process name", required=False),
            ToolParameter(name="path", type="string", description="File, app, or command to launch", required=False),
            ToolParameter(name="command", type="string", description="Command line for process_start", required=False),
            ToolParameter(name="x", type="integer", description="X screen coordinate", required=False),
            ToolParameter(name="y", type="integer", description="Y screen coordinate", required=False),
            ToolParameter(name="button", type="string", description="Mouse button: left, right, middle", required=False),
            ToolParameter(name="clicks", type="integer", description="Scroll wheel clicks", required=False),
        ]

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.get("action") or (args[0] if args else "")
        params = dict(kwargs)
        params["action"] = action
        try:
            return self._dispatch(**params)
        except Exception as exc:  # pragma: no cover - defensive guard
            return f"Automation action '{action}' failed: {exc}"

    def _dispatch(self, action: str, **kwargs) -> str:
        if action == "keyboard_type":
            return self._keyboard_type(kwargs.get("text", ""))
        if action == "keyboard_press":
            return self._keyboard_press(kwargs.get("key", ""))
        if action == "hotkey":
            keys = [k.strip() for k in (kwargs.get("keys") or "").split(",") if k.strip()]
            return self._hotkey(keys)

        if action == "mouse_move":
            return self._mouse_move(kwargs.get("x"), kwargs.get("y"))
        if action == "mouse_click":
            return self._mouse_click(
                kwargs.get("button") or "left",
                kwargs.get("x"),
                kwargs.get("y"),
            )
        if action == "mouse_scroll":
            return self._mouse_scroll(kwargs.get("clicks") or 0)
        if action == "mouse_position":
            return self._mouse_position()

        if action == "clipboard_get":
            return self._clipboard_get()
        if action == "clipboard_set":
            return self._clipboard_set(kwargs.get("text", ""))

        if action == "windows_list":
            return self._windows_list()
        if action == "windows_activate":
            return self._windows_activate(kwargs.get("title", ""))
        if action == "windows_close":
            return self._windows_close(kwargs.get("title", ""))
        if action == "windows_minimize":
            return self._windows_minimize(kwargs.get("title", ""))
        if action == "windows_maximize":
            return self._windows_maximize(kwargs.get("title", ""))
        if action == "windows_launch":
            return self._windows_launch(kwargs.get("path", kwargs.get("command", "")))

        if action == "process_list":
            return self._process_list()
        if action == "process_running":
            return self._process_running(kwargs.get("name", ""))
        if action == "process_kill":
            return self._process_kill(kwargs.get("name", ""))
        if action == "process_start":
            return self._process_start(kwargs.get("command", kwargs.get("path", "")))

        if action == "context_window":
            return self._context_window()
        if action == "context_apps":
            return self._context_apps()
        if action == "context_screen":
            return self._context_screen()
        if action == "context_summary":
            return self._context_summary()

        return f"Unknown automation action: {action}"

    # -- Keyboard ---------------------------------------------------------

    def _keyboard_type(self, text: str) -> str:
        from automation.keyboard import Keyboard

        kb = Keyboard()
        if not kb._enabled:
            return "Keyboard input unavailable (pyautogui not installed)."
        if not text:
            return "No text provided to type."
        kb.type(text)
        return f"Typed: {text}"

    def _keyboard_press(self, key: str) -> str:
        from automation.keyboard import Keyboard

        kb = Keyboard()
        if not kb._enabled:
            return "Keyboard input unavailable (pyautogui not installed)."
        if not key:
            return "No key provided to press."
        kb.press(key)
        return f"Pressed: {key}"

    def _hotkey(self, keys: list[str]) -> str:
        from automation.keyboard import Keyboard

        kb = Keyboard()
        if not kb._enabled:
            return "Keyboard input unavailable (pyautogui not installed)."
        if not keys:
            return "No keys provided for the hotkey."
        kb.press_hotkey(*keys)
        return f"Pressed hotkey: {'+'.join(keys)}"

    # -- Mouse ------------------------------------------------------------

    def _mouse_move(self, x, y) -> str:
        from automation.mouse import Mouse

        mouse = Mouse()
        if not mouse._enabled:
            return "Mouse control unavailable (pyautogui not installed)."
        if x is None or y is None:
            return "Mouse move requires x and y coordinates."
        mouse.move(int(x), int(y))
        return f"Moved mouse to ({x}, {y})"

    def _mouse_click(self, button: str, x, y) -> str:
        from automation.mouse import Mouse

        mouse = Mouse()
        if not mouse._enabled:
            return "Mouse control unavailable (pyautogui not installed)."
        mouse.click(button=button, x=int(x) if x is not None else None, y=int(y) if y is not None else None)
        target = f" at ({x}, {y})" if x is not None and y is not None else ""
        return f"Clicked {button} button{target}"

    def _mouse_scroll(self, clicks: int) -> str:
        from automation.mouse import Mouse

        mouse = Mouse()
        if not mouse._enabled:
            return "Mouse control unavailable (pyautogui not installed)."
        mouse.scroll(int(clicks))
        return f"Scrolled {clicks} clicks"

    def _mouse_position(self) -> str:
        from automation.mouse import Mouse

        mouse = Mouse()
        if not mouse._enabled:
            return "Mouse control unavailable (pyautogui not installed)."
        pos = mouse.position()
        return f"Mouse position: {pos}" if pos else "Unable to read mouse position."

    # -- Clipboard --------------------------------------------------------

    def _clipboard_get(self) -> str:
        from automation.clipboard import Clipboard

        cb = Clipboard()
        if not cb._enabled:
            return "Clipboard unavailable (pyautogui not installed)."
        return f"Clipboard: {cb.get()}" if cb.get() else "Clipboard is empty."

    def _clipboard_set(self, text: str) -> str:
        from automation.clipboard import Clipboard

        cb = Clipboard()
        if not cb._enabled:
            return "Clipboard unavailable (pyautogui not installed)."
        if not text:
            return "No text provided to copy."
        cb.set(text)
        return f"Copied to clipboard: {text}"

    # -- Windows ----------------------------------------------------------

    def _windows_list(self) -> str:
        from automation.windows import Windows

        wins = Windows().list_windows()
        return "\n".join(wins) if wins else "No open windows detected."

    def _windows_activate(self, title: str) -> str:
        from automation.windows import Windows

        if not title:
            return "No window title provided."
        return f"Window activated: {title}" if Windows().activate(title) else f"Window not found: {title}"

    def _windows_close(self, title: str) -> str:
        from automation.windows import Windows

        if not title:
            return "No window title provided."
        return f"Window closed: {title}" if Windows().close(title) else f"Window not found: {title}"

    def _windows_minimize(self, title: str) -> str:
        from automation.windows import Windows

        if not title:
            return "No window title provided."
        return f"Window minimized: {title}" if Windows().minimize(title) else f"Window not found: {title}"

    def _windows_maximize(self, title: str) -> str:
        from automation.windows import Windows

        if not title:
            return "No window title provided."
        return f"Window maximized: {title}" if Windows().maximize(title) else f"Window not found: {title}"

    def _windows_launch(self, path: str) -> str:
        from automation.windows import Windows

        if not path:
            return "No application or path provided to launch."
        return f"Launched: {path}" if Windows().launch(path) else f"Failed to launch: {path}"

    # -- Processes --------------------------------------------------------

    def _process_list(self) -> str:
        from automation.process import Process

        procs = Process().list_running()
        if not procs:
            return "No processes listed (psutil may be unavailable)."
        lines = [f"{p['name']} (pid {p['pid']}) cpu {p['cpu']:.1f}% mem {p['memory']:.1f}%" for p in procs[:30]]
        return "\n".join(lines)

    def _process_running(self, name: str) -> str:
        from automation.process import Process

        if not name:
            return "No process name provided."
        return f"Process '{name}' is running." if Process().is_running(name) else f"Process '{name}' is not running."

    def _process_kill(self, name: str) -> str:
        from automation.process import Process

        if not name:
            return "No process name provided."
        return f"Process '{name}' terminated." if Process().kill_by_name(name) else f"Process '{name}' not found or failed to terminate."

    def _process_start(self, command: str) -> str:
        from automation.process import Process

        if not command:
            return "No command provided to start."
        proc = Process().start(command)
        return f"Started process: {command}" if proc is not None else f"Failed to start: {command}"

    # -- Context ----------------------------------------------------------

    def _context_window(self) -> str:
        from automation.context import ContextAwareness

        win = ContextAwareness().get_active_window()
        return f"Active window: {win['app']} - {win['title']}" if win.get("title") else "No active window detected."

    def _context_apps(self) -> str:
        from automation.context import ContextAwareness

        apps = ContextAwareness().get_running_apps()
        return ", ".join(apps) if apps else "No running apps detected."

    def _context_screen(self) -> str:
        from automation.context import ContextAwareness

        text = ContextAwareness().get_screen_text()
        return f"Screen text: {text}" if text else "No screen text detected (OCR may be unavailable)."

    def _context_summary(self) -> str:
        from automation.context import ContextAwareness

        return ContextAwareness().get_context_summary()