"""Context awareness tool for ATLAS."""

from __future__ import annotations

from tools.base import Tool, ToolMetadata
from automation.context import ContextAwareness


class ContextTool(Tool):
    """Get desktop context: active window, running apps, screen text."""

    name = "context"
    description = "Get current desktop context (active window, running apps, screen text)."
    metadata = ToolMetadata(
        category="system", permission_level="basic", confirmation_required=False, description=description
    )

    def __init__(self) -> None:
        self._context = ContextAwareness()

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.get("action", "summary")
        if action == "window":
            win = self._context.get_active_window()
            return f"Active window: {win['app']} — {win['title']}"
        if action == "apps":
            apps = self._context.get_running_apps()
            return "Running apps: " + ", ".join(apps)
        if action == "screen":
            text = self._context.get_screen_text()
            return f"Screen text: {text[:500]}" if text else "No text detected on screen."
        return self._context.get_context_summary()