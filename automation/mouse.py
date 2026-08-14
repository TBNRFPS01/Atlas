"""Mouse automation utilities for ATLAS."""

from __future__ import annotations

from typing import Any

# pyautogui is an optional runtime dependency — declare as `Any` so that
# static analysis (Pylance) doesn't warn about attribute access when the
# module is present at runtime. It will be assigned in the try block.
pyautogui: Any = None
try:
    import pyautogui  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    pyautogui = None


class Mouse:
    """Control mouse movement, clicks, and scrolling."""

    def __init__(self) -> None:
        self._enabled = pyautogui is not None

    def move(self, x: int, y: int, duration: float = 0.0) -> None:
        """Move the mouse cursor to absolute screen coordinates."""
        if not self._enabled:
            print("Automation: Warning - pyautogui not available; mouse disabled.")
            return
        try:
            pyautogui.moveTo(x, y, duration=duration)
        except Exception as exc:
            print(f"Automation: Warning - mouse move failed: {exc}")

    def move_relative(self, dx: int, dy: int, duration: float = 0.0) -> None:
        """Move the mouse cursor relative to its current position."""
        if not self._enabled:
            return
        try:
            pyautogui.moveRel(dx, dy, duration=duration)
        except Exception as exc:
            print(f"Automation: Warning - relative mouse move failed: {exc}")

    def click(self, button: str = "left", x: int | None = None, y: int | None = None, confirm: bool = False) -> None:
        """Click at the current position or at specified coordinates."""
        if not self._enabled:
            return
        if confirm:
            pos = self.position()
            if pos:
                print(f"Automation: Confirm click at ({pos[0]}, {pos[1]})? (y/N): ", end="")
                resp = input().strip().lower()
                if resp != "y":
                    print("Automation: Click cancelled.")
                    return
        try:
            if x is not None and y is not None:
                pyautogui.click(x, y, button=button)
            else:
                pyautogui.click(button=button)
        except Exception as exc:
            print(f"Automation: Warning - mouse click failed: {exc}")

    def double_click(self, button: str = "left") -> None:
        """Double-click at the current position."""
        if not self._enabled:
            return
        try:
            pyautogui.doubleClick(button=button)
        except Exception as exc:
            print(f"Automation: Warning - double click failed: {exc}")

    def right_click(self) -> None:
        """Right-click at the current position."""
        self.click(button="right")

    def scroll(self, clicks: int, x: int | None = None, y: int | None = None) -> None:
        """Scroll the mouse wheel."""
        if not self._enabled:
            return
        try:
            if x is not None and y is not None:
                pyautogui.scroll(clicks, x=x, y=y)
            else:
                pyautogui.scroll(clicks)
        except Exception as exc:
            print(f"Automation: Warning - mouse scroll failed: {exc}")

    def position(self) -> tuple[int, int] | None:
        """Return the current mouse cursor position."""
        if not self._enabled:
            return None
        try:
            return pyautogui.position()
        except Exception:
            return None