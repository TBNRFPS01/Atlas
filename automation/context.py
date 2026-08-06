"""Context awareness for ATLAS: active window, screen text, running apps."""

from __future__ import annotations

from typing import Any

try:
    import pygetwindow as gw
except Exception:  # pragma: no cover - optional runtime dependency
    gw = None

try:
    import psutil
except Exception:  # pragma: no cover - optional runtime dependency
    psutil = None

from vision.screenshot import Screenshot
from vision.ocr import OCR


class ContextAwareness:
    """Gather desktop context: active window, visible text, running apps."""

    def __init__(self) -> None:
        self._screenshot = Screenshot()
        self._ocr = OCR()
        self._windows_enabled = gw is not None

    def get_active_window(self) -> dict[str, Any]:
        """Return info about the currently active window."""
        if not self._windows_enabled:
            return {"title": "", "app": "", "pid": None}
        try:
            win = gw.getActiveWindow()
            if win is None:
                return {"title": "", "app": "", "pid": None}
            title = win.title or ""
            app = self._extract_app_name(title)
            pid = getattr(win, "_hWnd", None)
            return {"title": title, "app": app, "pid": pid}
        except Exception:
            return {"title": "", "app": "", "pid": None}

    def _extract_app_name(self, title: str) -> str:
        """Guess application name from window title."""
        title_lower = title.lower()
        apps = {
            "visual studio code": "VS Code",
            "code - ": "VS Code",
            "chrome": "Chrome",
            "firefox": "Firefox",
            "edge": "Edge",
            "terminal": "Terminal",
            "powershell": "PowerShell",
            "cmd": "Command Prompt",
            "explorer": "File Explorer",
            "discord": "Discord",
            "slack": "Slack",
            "spotify": "Spotify",
            "notion": "Notion",
            "obsidian": "Obsidian",
            "vim": "Vim",
            "nvim": "Neovim",
            "pycharm": "PyCharm",
            "intellij": "IntelliJ",
            "postman": "Postman",
            "docker": "Docker Desktop",
        }
        for key, name in apps.items():
            if key in title_lower:
                return name
        return title.split(" - ")[-1] if " - " in title else title[:30]

    def get_running_apps(self, limit: int = 10) -> list[str]:
        """Return list of running application names."""
        if psutil is None:
            return []
        try:
            apps = set()
            for proc in psutil.process_iter(["name"]):
                name = proc.info.get("name")
                if name and name.endswith(".exe"):
                    apps.add(name[:-4])
                elif name:
                    apps.add(name)
            return sorted(apps)[:limit]
        except Exception:
            return []

    def get_screen_text(self, region: tuple[int, int, int, int] | None = None) -> str:
        """Capture screenshot and extract text via OCR."""
        try:
            img = self._screenshot.capture(region)
            if img is None:
                return ""
            return self._ocr.extract_text(img)
        except Exception:
            return ""

    def get_context_summary(self) -> str:
        """Build a concise context string for the LLM."""
        parts = []
        win = self.get_active_window()
        if win["title"]:
            parts.append(f"Active window: {win['app']} — {win['title'][:60]}")
        apps = self.get_running_apps(limit=8)
        if apps:
            parts.append(f"Running apps: {', '.join(apps)}")
        screen_text = self.get_screen_text()
        if screen_text:
            parts.append(f"Screen text (first 200 chars): {screen_text[:200]}")
        return "\n".join(parts) if parts else "No desktop context available."