from __future__ import annotations

from pathlib import Path

from tools.base import Tool, ToolMetadata, ToolParameter


class FileTool(Tool):
    """Basic ATLAS file tool placeholder."""

    name = "file"
    description = "Read, write, and organize files."
    metadata = ToolMetadata(category="files", permission_level="basic", confirmation_required=False, description=description)

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="File operation: read, write, append, delete, exists, list, search",
                required=True,
                enum=["read", "write", "append", "delete", "exists", "list", "search"],
            ),
            ToolParameter(
                name="path",
                type="string",
                description="File or directory path",
                required=True,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="Content for write or append operations",
                required=False,
            ),
            ToolParameter(
                name="pattern",
                type="string",
                description="Search pattern (glob or regex) for search action",
                required=False,
            ),
            ToolParameter(
                name="recursive",
                type="boolean",
                description="Search recursively in subdirectories",
                required=False,
            ),
        ]

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.get("action", "read")
        path = kwargs.get("path", args[0] if args else "")
        content = kwargs.get("content", "")
        pattern = kwargs.get("pattern", "")
        recursive = kwargs.get("recursive", False)

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

        elif action == "search":
            if not pattern:
                return "Search pattern required for search action"
            if not p.exists() or not p.is_dir():
                return f"Directory not found: {path}"
            try:
                results = []
                if recursive:
                    for item in p.rglob(pattern):
                        if item.is_file():
                            results.append(f"FILE {item.relative_to(p)}")
                        elif item.is_dir():
                            results.append(f"DIR  {item.relative_to(p)}")
                else:
                    for item in p.glob(pattern):
                        if item.is_file():
                            results.append(f"FILE {item.name}")
                        elif item.is_dir():
                            results.append(f"DIR  {item.name}")
                
                return "\n".join(results) if results else f"No matches for pattern '{pattern}'"
            except Exception as exc:
                return f"Error searching: {exc}"

        return f"Unknown action: {action}. Supported: read, write, append, delete, exists, list, search"
