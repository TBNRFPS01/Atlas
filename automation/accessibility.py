"""Optional Windows UI Automation bridge inspired by open-source desktop agents.

This is an ATLAS-native implementation. It deliberately keeps UI Automation
optional so ATLAS still starts on machines without pywinauto/UIA support.
"""

from __future__ import annotations

from typing import Any

try:
    from pywinauto import Desktop
except Exception:  # pragma: no cover - Windows-only optional dependency
    Desktop = None


class Accessibility:
    """Query and invoke accessible Windows UI elements by role/title."""

    def __init__(self) -> None:
        self.available = Desktop is not None

    def _desktop(self) -> Any | None:
        if not self.available:
            return None
        try:
            return Desktop(backend="uia")
        except Exception:
            return None

    def windows(self) -> list[str]:
        desktop = self._desktop()
        if desktop is None:
            return []
        try:
            return [w.window_text() for w in desktop.windows() if w.window_text()]
        except Exception:
            return []

    def find(self, title: str, control_type: str | None = None) -> list[dict[str, Any]]:
        desktop = self._desktop()
        if desktop is None:
            return []
        results: list[dict[str, Any]] = []
        try:
            for window in desktop.windows():
                root = window
                candidates = root.descendants()
                for element in candidates:
                    name = element.window_text().strip()
                    if not name or title.casefold() not in name.casefold():
                        continue
                    info = element.element_info
                    kind = getattr(info, "control_type", None)
                    if control_type and str(kind).casefold() != control_type.casefold():
                        continue
                    results.append({
                        "name": name,
                        "control_type": kind,
                        "window": window.window_text(),
                    })
        except Exception:
            return results
        return results

    def invoke(self, title: str, control_type: str | None = None) -> bool:
        desktop = self._desktop()
        if desktop is None:
            return False
        try:
            for window in desktop.windows():
                for element in window.descendants():
                    name = element.window_text().strip()
                    if not name or title.casefold() not in name.casefold():
                        continue
                    kind = getattr(element.element_info, "control_type", None)
                    if control_type and str(kind).casefold() != control_type.casefold():
                        continue
                    try:
                        element.invoke()
                    except Exception:
                        element.click_input()
                    return True
        except Exception:
            return False
        return False
