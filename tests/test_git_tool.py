from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from core.permissions import Decision, PermissionManager
from core.router import Router
from core.safety import HardSafety
from tools.git_tool import GitTool, parse_request

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "atlas@test.local")
    _git(repo, "config", "user.name", "ATLAS Test")
    return repo


def test_parse_git_status() -> None:
    assert parse_request("git status") == {"action": "status"}
    assert parse_request("what's the git status") == {"action": "status"}
    assert parse_request("run git status") == {"action": "status"}


def test_parse_does_not_capture_git_questions() -> None:
    assert parse_request("what is git") is None
    assert parse_request("tell me how git works") is None


def test_parse_commit_message() -> None:
    parsed = parse_request("git commit with message Fix the parser")
    assert parsed == {"action": "commit", "message": "Fix the parser"}


def test_parse_force_push_is_forbidden_action() -> None:
    assert parse_request("git push --force") == {"action": "force_push"}
    assert parse_request("force push this branch") == {"action": "force_push"}


def test_status_observes_real_repo(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "notes.txt").write_text("hello", encoding="utf-8")
    tool = GitTool()
    result = tool.execute(action="status", path=str(repo))
    assert "OK git.status" in result
    assert "notes.txt" in result
    observation = tool.observe("status", result, path=str(repo))
    assert observation["is_repo"] is True
    assert observation["porcelain"]
    assert tool.verify("status", observation, path=str(repo)) is True


def test_add_and_commit_are_verified(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "app.py").write_text("print('hi')\n", encoding="utf-8")
    tool = GitTool()
    added = tool.execute(action="add", path=str(repo), files="app.py")
    assert "OK git.add" in added
    add_obs = tool.observe("add", added, path=str(repo), files="app.py")
    assert tool.verify("add", add_obs, path=str(repo), files="app.py") is True

    committed = tool.execute(action="commit", path=str(repo), message="Add app.py")
    assert "OK git.commit" in committed
    after = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert after
    observation = tool.observe("commit", committed, path=str(repo), message="Add app.py")
    assert observation["latest_message"] == "Add app.py"
    assert tool.verify("commit", observation, path=str(repo), message="Add app.py") is True


def test_commit_verification_fails_when_nothing_committed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    tool = GitTool()
    result = tool.execute(action="commit", path=str(repo), message="Empty")
    observation = tool.observe("commit", result, path=str(repo), message="Empty")
    assert tool.verify("commit", observation, path=str(repo), message="Empty") is False


def test_create_and_checkout_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "seed.txt").write_text("x", encoding="utf-8")
    tool = GitTool()
    tool.execute(action="add", path=str(repo), files=".")
    tool.execute(action="commit", path=str(repo), message="seed")
    created = tool.execute(action="create_branch", path=str(repo), branch="feature-x")
    assert "OK git.create_branch" in created
    observation = tool.observe("create_branch", created, path=str(repo), branch="feature-x")
    assert observation["branch"] == "feature-x"
    assert tool.verify("create_branch", observation, path=str(repo), branch="feature-x") is True


def test_tool_refuses_force_push(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    tool = GitTool()
    result = tool.execute(action="force_push", path=str(repo))
    assert "forbidden" in result.lower()
    result = tool.execute(action="push", path=str(repo), remote="origin --force")
    assert "refused" in result.lower()


def test_permissions_and_safety_for_git() -> None:
    pm = PermissionManager()
    assert pm.decide("git", "status") == Decision.ALLOW
    assert pm.decide("git", "commit", confirmed=False) == Decision.ASK
    assert pm.decide("git", "push", confirmed=False) == Decision.ASK
    assert pm.decide("git", "push", confirmed=True) == Decision.ALLOW
    safety = HardSafety()
    assert safety.is_safe("git", "force_push") is False
    assert safety.is_safe("git", "reset_hard") is False
    assert safety.is_safe("git", "status") is True


def test_router_blocks_force_push_before_execution() -> None:
    router = Router()
    called = {"ran": False}

    def fn():
        called["ran"] = True
        return "should not run"

    result = router.execute_action(
        intent="git push --force",
        tool_name="git",
        action="force_push",
        fn=fn,
        prompt="yes, force push",
    )
    assert "hard safety" in result.lower()
    assert called["ran"] is False
    assert router._execution.history[-1]["safety"] == "deny"


def test_natural_router_status_uses_execution_boundary(tmp_path: Path) -> None:
    from core.natural_router import install

    repo = _repo(tmp_path)
    (repo / "tracked.txt").write_text("n", encoding="utf-8")
    router = install(Router())
    result = router.route(f"git status {repo}")
    assert "OK git.status" in result
    record = router._execution.history[-1]
    assert record["tool"] == "git"
    assert record["action"] == "status"
    assert record["permissions"] == "allow"
    assert record["verification"] == "verified"


def test_router_commit_requires_confirmation(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "a.txt").write_text("a", encoding="utf-8")
    router = Router()
    tool = router._registry.get("git")
    assert tool is not None
    denied = router.execute_action(
        intent="git commit",
        tool_name="git",
        action="commit",
        fn=lambda: tool.execute(action="commit", path=str(repo), message="x"),
        prompt="git commit with message x",
        path=str(repo),
    )
    assert "Confirm" in denied
    assert "create git commit" in denied.lower()
