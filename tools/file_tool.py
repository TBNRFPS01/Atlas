from __future__ import annotations

from pathlib import Path

from tools.base import Tool, ToolMetadata


class FileTool(Tool):
    """Basic ATLAS file tool placeholder."""

    name = "file"
    description = "Read, write, and organize files."
    metadata = ToolMetadata(category="files", permission_level="basic", confirmation_required=False, description=description)

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.get("action", "read")
        path = kwargs.get("path", args[0] if args else "")
        content = kwargs.get("content", "")

        if not path:
            return "No path provided. Usage: file action=read path=... or action=write path=... content=..."

        p = Path(path)

        if action == "read":
            if not p.exists():
                return f"File not found: {path}"
            if p.is_dir():
                return f"Path is a directory: {path}"
            try:
                return p.read_text(encoding="utf-8")
            except Exception as exc:
                return f"Error reading file: {exc}"

        elif action == "write":
            if not content:
                return "No content provided for write operation."
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
                return f"Successfully wrote to {path}"
            except Exception as exc:
                return f"Error writing file: {exc}"

        elif action == "append":
            if not content:
                return "No content provided for append operation."
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "a", encoding="utf-8") as f:
                    f.write(content)
                return f"Successfully appended to {path}"
            except Exception as exc:
                return f"Error appending to file: {exc}"

        elif action == "delete":
            if not p.exists():
                return f"File not found: {path}"
            try:
                p.unlink()
                return f"Successfully deleted {path}"
            except Exception as exc:
                return f"Error deleting file: {exc}"

        elif action == "exists":
            return str(p.exists())

        elif action == "list":
            if not p.exists() or not p.is_dir():
                return f"Directory not found: {path}"
            try:
                items = [
                    f"{'DIR ' if item.is_dir() else 'FILE'} {item.name}"
                    for item in p.iterdir()
                ]
                return "\n".join(items) if items else "Directory is empty."
            except Exception as exc:
                return f"Error listing directory: {exc}"

        return f"Unknown action: {action}. Supported: read, write, append, delete, exists, list"
