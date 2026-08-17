"""Clipboard utilities for ATLAS."""

from __future__ import annotations

try:
    import pyperclip
except Exception:  # pragma: no cover - optional runtime dependency
    pyperclip = None


class Clipboard:
    """Read from and write to the system clipboard."""

    def __init__(self) -> None:
        self._enabled = pyperclip is not None

    def get(self) -> str:
        """Read text from the clipboard."""
        if not self._enabled:
            print("Automation: Warning - pyperclip not available; clipboard disabled.")
            return ""
        try:
            return pyperclip.paste()
        except Exception as exc:
            print(f"Automation: Warning - clipboard read failed: {exc}")
            return ""

    def set(self, text: str) -> None:
        """Write text to the clipboard."""
        if not self._enabled:
            return
        try:
            pyperclip.copy(text)
        except Exception as exc:
            print(f"Automation: Warning - clipboard write failed: {exc}")

    def copy(self, text: str) -> None:
        """Copy text to the clipboard (alias for set)."""
        self.set(text)

    def paste(self) -> str:
        """Paste from clipboard (alias for get)."""
        return self.get()