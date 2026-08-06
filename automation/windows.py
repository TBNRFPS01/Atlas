"""Windows management utilities for ATLAS."""

from __future__ import annotations

import subprocess
from typing import Any

try:
    import pygetwindow as gw
except Exception:  # pragma: no cover - optional runtime dependency
    gw = None

try:
    import psutil
except Exception:  # pragma: no cover - optional runtime dependency
    psutil = None


class Windows:
    """Manage windows, processes, and applications."""

    def __init__(self) -> None:
        self._enabled = gw is not None

    def list_windows(self) -> list[str]:
        """Return a list of all open window titles."""
        if not self._enabled:
            print("Automation: Warning - pygetwindow not available; window control disabled.")
            return []
        try:
            return [win.title for win in gw.getAllTitles() if win.title]
        except Exception as exc:
            print(f"Automation: Warning - list windows failed: {exc}")
            return []

    def find_window(self, title: str) -> Any | None:
        """Find a window by partial title match."""
        if not self._enabled:
            return None
        try:
            windows = gw.getWindowsWithTitle(title)
            return windows[0] if windows else None
        except Exception:
            return None

    def activate(self, title: str) -> bool:
        """Bring a window to the foreground."""
        if not self._enabled:
            return False
        try:
            win = self.find_window(title)
            if win:
                win.activate()
                return True
            return False
        except Exception as exc:
            print(f"Automation: Warning - window activate failed: {exc}")
            return False

    def close(self, title: str, confirm: bool = False) -> bool:
        """Close a window by title."""
        if not self._enabled:
            return False
        if confirm:
            print(f"Automation: Confirm close window '{title}'? (y/N): ", end="")
            resp = input().strip().lower()
            if resp != "y":
                print("Automation: Window close cancelled.")
                return False
        try:
            win = self.find_window(title)
            if win:
                win.close()
                return True
            return False
        except Exception as exc:
            print(f"Automation: Warning - window close failed: {exc}")
            return False

    def minimize(self, title: str) -> bool:
        """Minimize a window by title."""
        if not self._enabled:
            return False
        try:
            win = self.find_window(title)
            if win:
                win.minimize()
                return True
            return False
        except Exception as exc:
            print(f"Automation: Warning - window minimize failed: {exc}")
            return False

    def maximize(self, title: str) -> bool:
        """Maximize a window by title."""
        if not self._enabled:
            return False
        try:
            win = self.find_window(title)
            if win:
                win.maximize()
                return True
            return False
        except Exception as exc:
            print(f"Automation: Warning - window maximize failed: {exc}")
            return False

    def launch(self, path: str) -> bool:
        """Launch an application by path or executable name."""
        try:
            subprocess.Popen([path], shell=True)
            return True
        except Exception as exc:
            print(f"Automation: Warning - launch failed: {exc}")
            return False

    def kill(self, process_name: str) -> bool:
        """Terminate a process by name."""
        if psutil is None:
            return False
        try:
            for proc in psutil.process_iter(["name"]):
                if proc.info["name"] and process_name.lower() in proc.info["name"].lower():
                    proc.terminate()
                    return True
            return False
        except Exception as exc:
            print(f"Automation: Warning - process kill failed: {exc}")
            return False