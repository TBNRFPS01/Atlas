from pathlib import Path

from core.permissions import PermissionManager
from core.sandbox import SandboxPolicy
from tools.file_tool import FileTool


def test_write_requires_structured_confirmation(tmp_path: Path):
    tool = FileTool(sandbox=SandboxPolicy(workspace=tmp_path))
    target = tmp_path / "safe.txt"

    first = tool.execute(action="write", path=str(target), content="hello")
    assert "Confirmation required" in first
    assert not target.exists()


def test_confirmation_token_is_single_use(tmp_path: Path):
    permissions = PermissionManager()
    tool = FileTool(permissions=permissions, sandbox=SandboxPolicy(workspace=tmp_path))
    target = tmp_path / "safe.txt"

    result = tool.execute(action="write", path=str(target), content="hello")
    token = result.split("token=", 1)[1]
    assert "token=" in result

    assert tool.execute(action="write", path=str(target), content="hello", confirmation_token=token).startswith("Successfully")
    assert tool.execute(action="write", path=str(target), content="again", confirmation_token=token).startswith("Permission denied")


def test_sandbox_blocks_path_escape(tmp_path: Path):
    tool = FileTool(sandbox=SandboxPolicy(workspace=tmp_path))
    outside = tmp_path.parent / "atlas-escape-test.txt"
    result = tool.execute(action="write", path=str(outside), content="blocked")
    assert "Permission denied" in result
    assert not outside.exists()


def test_append_is_protected_like_write(tmp_path: Path):
    tool = FileTool(sandbox=SandboxPolicy(workspace=tmp_path))
    target = tmp_path / "safe.txt"
    target.write_text("base", encoding="utf-8")
    result = tool.execute(action="append", path=str(target), content="-blocked")
    assert "Confirmation required" in result
    assert target.read_text(encoding="utf-8") == "base"
