from __future__ import annotations

from pathlib import Path

from core.permissions import Decision, PermissionManager
from core.safety import HardSafety, SafetyViolation
from core.sandbox import SandboxPolicy, SandboxViolation
from tools.base import Tool, ToolMetadata, ToolParameter


class FileTool(Tool):
    """File operations with a mandatory safety/permission boundary."""

    name = "file"
    description = "Read, write, and organize files."
    metadata = ToolMetadata(category="files", permission_level="basic", confirmation_required=False, description=description)

    def __init__(self, permissions: PermissionManager | None = None, safety: HardSafety | None = None, sandbox: SandboxPolicy | None = None) -> None:
        self.permissions = permissions or PermissionManager()
        self.safety = safety or HardSafety()
        self.sandbox = sandbox

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="action", type="string", description="File operation: read, write, append, delete, exists, list, search", required=True, enum=["read", "write", "append", "delete", "exists", "list", "search"]),
            ToolParameter(name="path", type="string", description="File or directory path", required=True),
            ToolParameter(name="content", type="string", description="Content for write or append operations", required=False),
            ToolParameter(name="pattern", type="string", description="Search pattern (glob or regex) for search action", required=False),
            ToolParameter(name="recursive", type="boolean", description="Search recursively in subdirectories", required=False),
            ToolParameter(name="confirmation_token", type="string", description="Explicit ATLAS confirmation token for a pending destructive action", required=False),
        ]

    def _authorize(self, action: str, path: str, token: str | None) -> Path:
        try:
            self.safety.check_action(self.name, action)
            self.safety.check_path(path)
            target = self.sandbox.check_path(path) if self.sandbox else Path(path).expanduser()
        except (SafetyViolation, SandboxViolation) as exc:
            raise PermissionError(str(exc)) from exc

        if action in {"write", "append", "delete"}:
            if token and self.permissions.confirm(token, self.name, action):
                return target
            decision = self.permissions.decide(self.name, action, permission_level=self.metadata.permission_level)
            if decision == Decision.DENY:
                raise PermissionError(f"Permission denied for {self.name}.{action}")
            if decision == Decision.ASK:
                confirmation = self.permissions.request_confirmation(self.name, action)
                raise PermissionError(
                    f"Confirmation required. token={confirmation.token}"
                )
        return target

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.get("action", "read")
        path = kwargs.get("path", args[0] if args else "")
        content = kwargs.get("content", "")
        pattern = kwargs.get("pattern", "")
        recursive = kwargs.get("recursive", False)
        token = kwargs.get("confirmation_token")

        if not path:
            return "No path provided."

        try:
            p = self._authorize(action, path, token)
        except PermissionError as exc:
            return f"Permission denied: {exc}"

        if action == "read":
            if not p.exists(): return f"File not found: {path}"
            if p.is_dir(): return f"Path is a directory: {path}"
            try: return p.read_text(encoding="utf-8")
            except Exception as exc: return f"Error reading file: {exc}"

        if action == "write":
            if not content: return "No content provided for write operation."
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
                return f"Successfully wrote to {p}"
            except Exception as exc: return f"Error writing file: {exc}"

        if action == "append":
            if not content: return "No content provided for append operation."
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "a", encoding="utf-8") as f: f.write(content)
                return f"Successfully appended to {p}"
            except Exception as exc: return f"Error appending to file: {exc}"

        if action == "delete":
            if not p.exists(): return f"File not found: {path}"
            try:
                if p.is_dir(): return "Directory deletion is not supported by the file tool."
                p.unlink()
                return f"Successfully deleted {p}"
            except Exception as exc: return f"Error deleting file: {exc}"

        if action == "exists": return str(p.exists())
        if action == "list":
            if not p.exists() or not p.is_dir(): return f"Directory not found: {path}"
            try:
                items = [f"{'DIR ' if item.is_dir() else 'FILE'} {item.name}" for item in p.iterdir()]
                return "\n".join(items) if items else "Directory is empty."
            except Exception as exc: return f"Error listing directory: {exc}"

        if action == "search":
            if not pattern: return "Search pattern required for search action"
            if not p.exists() or not p.is_dir(): return f"Directory not found: {path}"
            try:
                iterator = p.rglob(pattern) if recursive else p.glob(pattern)
                results = [f"{'FILE' if item.is_file() else 'DIR '} {item.relative_to(p)}" for item in iterator]
                return "\n".join(results) if results else f"No matches for pattern '{pattern}'"
            except Exception as exc: return f"Error searching: {exc}"

        return f"Unknown action: {action}. Supported: read, write, append, delete, exists, list, search"
