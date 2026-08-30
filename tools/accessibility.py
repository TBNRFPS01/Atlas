from __future__ import annotations

from automation.accessibility import Accessibility
from tools.base import Tool, ToolMetadata, ToolParameter


class AccessibilityTool(Tool):
    """Windows UI Automation tool for accessible desktop controls."""

    name = "accessibility"
    description = "Inspect or invoke accessible Windows UI elements by visible name."
    metadata = ToolMetadata(
        category="desktop",
        permission_level="basic",
        confirmation_required=False,
        description=description,
    )

    def __init__(self) -> None:
        self._accessibility = Accessibility()

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter("action", "string", "Action: windows, find, or invoke", True, ["windows", "find", "invoke"]),
            ToolParameter("title", "string", "Visible UI element title for find/invoke", False),
            ToolParameter("control_type", "string", "Optional UI Automation control type", False),
        ]

    def execute(self, action: str = "windows", title: str = "", control_type: str = "") -> str:
        if not self._accessibility.available:
            return "Windows UI Automation is unavailable. Install pywinauto on Windows."
        if action == "windows":
            values = self._accessibility.windows()
            return "\n".join(values) if values else "No accessible windows found."
        if not title:
            return "A title is required for find/invoke."
        if action == "find":
            matches = self._accessibility.find(title, control_type or None)
            if not matches:
                return f"No accessible UI elements matched '{title}'."
            return "\n".join(
                f"{item['name']} [{item['control_type']}] in {item['window']}"
                for item in matches[:50]
            )
        if action == "invoke":
            return "Invoked." if self._accessibility.invoke(title, control_type or None) else f"Could not invoke '{title}'."
        return "Usage: accessibility(action=windows|find|invoke, title=<name>, control_type=<optional>)."
