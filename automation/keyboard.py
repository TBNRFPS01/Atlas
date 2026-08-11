"""Keyboard automation utilities for ATLAS."""

from __future__ import annotations

from typing import Any

try:
    import pyautogui
except Exception:  # pragma: no cover - optional runtime dependency
    pyautogui = None


class Keyboard:
    """Simulate keyboard input and manage hotkeys."""

    def __init__(self) -> None:
        self._enabled = pyautogui is not None

    def type(self, text: str, interval: float = 0.0) -> None:
        """Type text as if typed by a human."""
        if not self._enabled:
            print("Automation: Warning - pyautogui not available; keyboard disabled.")
            return
        try:
            pyautogui.write(text, interval=interval)
        except Exception as exc:
            print(f"Automation: Warning - keyboard type failed: {exc}")

    def press(self, key: str) -> None:
        """Press and release a single key."""
        if not self._enabled:
            return
        try:
            pyautogui.keyDown(key)
            pyautogui.keyUp(key)
        except Exception as exc:
            print(f"Automation: Warning - key press failed: {exc}")

    def press_hotkey(self, *keys: str, confirm: bool = False) -> None:
        """Press a combination of keys as a hotkey (e.g., ctrl+c)."""
        if not self._enabled:
            return
        if confirm:
            print(f"Automation: Confirm hotkey {'+'.join(keys)}? (y/N): ", end="")
            resp = input().strip().lower()
            if resp != "y":
                print("Automation: Hotkey cancelled.")
                return
        try:
            pyautogui.hotkey(*keys)
        except Exception as exc:
            print(f"Automation: Warning - hotkey failed: {exc}")

    def tap(self, key: str) -> None:
        """Tap a single key (alias for press)."""
        self.press(key)

    def press_and_hold(self, key: str) -> None:
        """Hold down a key until release() is called."""
        if not self._enabled:
            return
        try:
            pyautogui.keyDown(key)
        except Exception as exc:
            print(f"Automation: Warning - key hold failed: {exc}")

    def release(self, key: str) -> None:
        """Release a held key."""
        if not self._enabled:
            return
        try:
            pyautogui.keyUp(key)
        except Exception as exc:
            print(f"Automation: Warning - key release failed: {exc}")

    def is_pressed(self, key: str) -> bool:
        """Check if a key is currently held down."""
        if not self._enabled:
            return False
        try:
            return pyautogui.isPressed(key)
        except Exception:
            return False