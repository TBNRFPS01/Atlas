"""Inspect and operate Git repositories with observation and verification.

Read actions inspect reality. Mutating actions go through ATLAS policy.
Force-push, hard reset, and clean are refused by the tool and by hard safety.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from tools.base import Tool, ToolMetadata, ToolParameter

_READ_ACTIONS = frozenset({"status", "log", "diff", "branch", "show", "remote"})
_MUTATING_ACTIONS = frozenset({
    "add", "commit", "checkout", "create_branch", "pull", "push", "stash",
})
_FORBIDDEN_ACTIONS = frozenset({"force_push", "reset_hard", "clean"})
_DANGEROUS_TOKENS = (
    "--force",
    "--force-with-lease",
    "--hard",
    "--no-verify",
    "filter-branch",
    "update-ref",
    "git-filter-repo",
)
_COMMAND = re.compile(
    r"^(?:please\s+|run\s+|check\s+|show\s+)?"
    r"(?:what(?:'s| is)\s+(?:the\s+)?)?"
    r"git\s+(status|log|diff|branches|branch|remote|add|commit|checkout|switch|push|pull|stash)\b",
    re.IGNORECASE,
)


def parse_request(prompt: str) -> dict[str, Any] | None:
    """Parse an unambiguous git command. Returns kwargs or None."""
    text = prompt.strip()
    if not text:
        return None
    lower = text.lower()

    if re.search(r"\bforce(?:[ -]push)\b", lower) or re.search(
        r"\bgit\s+push\b.*(?:--force\b|--force-with-lease\b|(?<!\w)-f\b)", lower
    ):
        return {"action": "force_push"}
    if re.search(r"\bgit\s+reset\s+--hard\b", lower):
        return {"action": "reset_hard"}
    if re.search(r"\bgit\s+clean\b", lower):
        return {"action": "clean"}

    match = _COMMAND.match(lower)
    if not match:
        return None

    verb = match.group(1).lower()
    action = {
        "status": "status",
        "log": "log",
        "diff": "diff",
        "branch": "branch",
        "branches": "branch",
        "remote": "remote",
        "add": "add",
        "commit": "commit",
        "checkout": "checkout",
        "switch": "checkout",
        "push": "push",
        "pull": "pull",
        "stash": "stash",
    }[verb]
    kwargs: dict[str, Any] = {"action": action}
    rest = text[match.end():].strip()

    if action == "add":
        kwargs["files"] = rest if rest else "."
    elif action == "commit":
        message_match = re.search(
            r"""(?:-m|--message)\s+['"](.+?)['"]|(?:-m|--message)\s+(\S+)|with(?:\s+the)?\s+message\s+['"](.+?)['"]|with(?:\s+the)?\s+message\s+(.+)$""",
            text,
            re.IGNORECASE,
        )
        if message_match:
            kwargs["message"] = next(g for g in message_match.groups() if g)
        else:
            kwargs["message"] = ""
    elif action in {"checkout", "create_branch"}:
        tokens = rest.split()
        if tokens[:1] in (["-b"], ["-c"]) and len(tokens) >= 2:
            kwargs["action"] = "create_branch"
            kwargs["branch"] = tokens[1]
        elif tokens:
            kwargs["branch"] = tokens[0]
    elif action == "show" or action == "log":
        if rest:
            kwargs["ref"] = rest.split()[0]
    elif action == "diff":
        if rest:
            kwargs["ref"] = rest
    path_match = re.search(r"([A-Za-z]:[\\/][^\s]+|~/[^\s]+)", text)
    if path_match:
        kwargs["path"] = path_match.group(1).rstrip(".,;?!")
    return kwargs


class GitTool(Tool):
    name = "git"
    description = (
        "Inspect and operate Git repositories: status, log, diff, branch, add, "
        "commit, checkout, pull, and push. Force-push and hard reset are forbidden."
    )
    metadata = ToolMetadata(
        category="development",
        permission_level="basic",
        confirmation_required=False,
        description=description,
    )

    def __init__(self) -> None:
        self._git = shutil.which("git")
        self._last_repo: str | None = None

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Git operation",
                required=True,
                enum=sorted(_READ_ACTIONS | _MUTATING_ACTIONS),
            ),
            ToolParameter(name="path", type="string",
                          description="Repository path (defaults to current working directory)", required=False),
            ToolParameter(name="files", type="string",
                          description="Paths for add (space-separated). Use . for all.", required=False),
            ToolParameter(name="message", type="string",
                          description="Commit message", required=False),
            ToolParameter(name="branch", type="string",
                          description="Branch name for checkout or create_branch", required=False),
            ToolParameter(name="ref", type="string",
                          description="Optional ref for log/diff/show", required=False),
            ToolParameter(name="remote", type="string",
                          description="Remote name for push/pull (default origin)", required=False),
        ]

    def execute(self, *args, **kwargs) -> str:
        action = str(kwargs.get("action") or (args[0] if args else "") or "").strip()
        if not action:
            return "No git action provided. Try: git status"
        if action in _FORBIDDEN_ACTIONS:
            return f"Refused: git.{action} is forbidden."
        if self._contains_dangerous_tokens({k: v for k, v in kwargs.items() if k != "message"}):
            return "Refused: dangerous git flags are not allowed (force, hard reset, hook bypass)."
        if self._git is None:
            return "Git is not installed or not on PATH."

        repo = self._resolve_repo(str(kwargs.get("path") or ""))
        if repo.startswith("Not a git"):
            return repo
        self._last_repo = repo

        handlers = {
            "status": self._status,
            "log": self._log,
            "diff": self._diff,
            "branch": self._branch,
            "show": self._show,
            "remote": self._remote,
            "add": self._add,
            "commit": self._commit,
            "checkout": self._checkout,
            "create_branch": self._create_branch,
            "pull": self._pull,
            "push": self._push,
            "stash": self._stash,
        }
        handler = handlers.get(action)
        if handler is None:
            supported = ", ".join(sorted(handlers))
            return f"Unknown git action: {action}. Supported: {supported}"
        return handler(repo, **kwargs)

    def observe(self, action: str, result: str, **kwargs: Any) -> dict[str, Any]:
        repo = str(kwargs.get("path") or self._last_repo or "")
        root = self._repo_root(repo) if repo else ""
        observation: dict[str, Any] = {
            "action": action,
            "repo": root or repo,
            "is_repo": bool(root),
            "result_ok": not str(result).lower().startswith(("refused:", "error", "git is not", "not a git", "unknown git")),
        }
        if not root:
            return observation
        observation["head"] = self._stdout(["rev-parse", "HEAD"], root)
        observation["branch"] = self._stdout(["rev-parse", "--abbrev-ref", "HEAD"], root)
        observation["porcelain"] = self._stdout(["status", "--porcelain"], root)
        if action == "commit":
            observation["latest_message"] = self._stdout(["log", "-1", "--format=%s"], root)
            observation["committed"] = "nothing to commit" not in str(result).lower()
        if action == "add":
            observation["staged"] = self._stdout(["diff", "--cached", "--name-only"], root)
        if action in {"checkout", "create_branch"}:
            observation["requested_branch"] = str(kwargs.get("branch") or "")
        if action == "push":
            observation["rejected"] = "rejected" in str(result).lower()
        return observation

    def verify(self, action: str, observation: Any, **kwargs: Any) -> bool | None:
        if not isinstance(observation, dict):
            return None
        if not observation.get("is_repo") or not observation.get("result_ok"):
            return False
        if action in _READ_ACTIONS:
            return bool(observation.get("branch"))
        if action == "add":
            files = str(kwargs.get("files") or ".").strip()
            staged = str(observation.get("staged") or "")
            if files in {".", "-A", "--all"}:
                return True
            name = Path(files.split()[0]).name
            return name in staged or files.replace("\\", "/") in staged.replace("\\", "/")
        if action == "commit":
            message = str(kwargs.get("message") or "").strip()
            return bool(
                observation.get("committed")
                and observation.get("head")
                and (not message or observation.get("latest_message") == message)
            )
        if action in {"checkout", "create_branch"}:
            requested = str(kwargs.get("branch") or observation.get("requested_branch") or "")
            return bool(requested) and observation.get("branch") == requested
        if action == "push":
            return not observation.get("rejected")
        if action in {"pull", "stash"}:
            return True
        return None

    def _status(self, repo: str, **kwargs: Any) -> str:
        short = self._run(["status", "-sb"], repo)
        return self._format("status", repo, short)

    def _log(self, repo: str, **kwargs: Any) -> str:
        ref = str(kwargs.get("ref") or "").strip()
        args = ["log", "-10", "--oneline"]
        if ref:
            args.append(ref)
        return self._format("log", repo, self._run(args, repo))

    def _diff(self, repo: str, **kwargs: Any) -> str:
        ref = str(kwargs.get("ref") or "").strip()
        args = ["diff"]
        if ref:
            args.extend(ref.split())
        return self._format("diff", repo, self._run(args, repo))

    def _branch(self, repo: str, **kwargs: Any) -> str:
        return self._format("branch", repo, self._run(["branch", "-vv"], repo))

    def _show(self, repo: str, **kwargs: Any) -> str:
        ref = str(kwargs.get("ref") or "HEAD").strip()
        return self._format("show", repo, self._run(["show", "--stat", ref], repo))

    def _remote(self, repo: str, **kwargs: Any) -> str:
        return self._format("remote", repo, self._run(["remote", "-v"], repo))

    def _add(self, repo: str, **kwargs: Any) -> str:
        files = str(kwargs.get("files") or ".").strip() or "."
        paths = files.split()
        if files in {".", "-A", "--all"}:
            completed = self._run(["add", "-A"], repo)
        else:
            completed = self._run(["add", "--", *paths], repo)
        return self._format("add", repo, completed)

    def _commit(self, repo: str, **kwargs: Any) -> str:
        message = str(kwargs.get("message") or "").strip()
        if not message:
            return "Commit message required. Example: git commit with message Fix the parser"
        completed = self._run(["commit", "-m", message], repo)
        return self._format("commit", repo, completed)

    def _checkout(self, repo: str, **kwargs: Any) -> str:
        branch = str(kwargs.get("branch") or "").strip()
        if not branch or branch.startswith("-"):
            return "Branch name required for checkout."
        return self._format("checkout", repo, self._run(["checkout", branch], repo))

    def _create_branch(self, repo: str, **kwargs: Any) -> str:
        branch = str(kwargs.get("branch") or "").strip()
        if not branch or branch.startswith("-"):
            return "Branch name required to create a branch."
        return self._format("create_branch", repo, self._run(["checkout", "-b", branch], repo))

    def _pull(self, repo: str, **kwargs: Any) -> str:
        remote = str(kwargs.get("remote") or "origin").strip() or "origin"
        return self._format("pull", repo, self._run(["pull", "--ff-only", remote], repo, timeout=120))

    def _push(self, repo: str, **kwargs: Any) -> str:
        remote = str(kwargs.get("remote") or "origin").strip() or "origin"
        return self._format("push", repo, self._run(["push", remote], repo, timeout=120))

    def _stash(self, repo: str, **kwargs: Any) -> str:
        return self._format("stash", repo, self._run(["stash", "push", "-u", "-m", "atlas-stash"], repo))

    def _resolve_repo(self, path: str) -> str:
        target = Path(path).expanduser() if path else Path.cwd()
        try:
            target = target.resolve()
        except Exception:
            return f"Not a git repository: {path or '.'}"
        if target.is_file():
            target = target.parent
        root = self._repo_root(str(target))
        return root or f"Not a git repository: {target}"

    def _repo_root(self, path: str) -> str:
        if not path or self._git is None:
            return ""
        completed = self._run(["rev-parse", "--show-toplevel"], path)
        if completed.returncode != 0:
            return ""
        return completed.stdout.strip() or ""

    def _stdout(self, args: list[str], repo: str) -> str:
        return self._run(args, repo).stdout.strip()

    def _run(self, args: list[str], repo: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        if self._git is None:
            return subprocess.CompletedProcess(args, 127, "", "git not found")
        if self._contains_dangerous_tokens({"args": " ".join(args)}):
            return subprocess.CompletedProcess(args, 2, "", "dangerous git flags refused")
        try:
            return subprocess.run(
                [self._git, *args],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(args, 124, "", f"git {' '.join(args)} timed out")
        except OSError as exc:
            return subprocess.CompletedProcess(args, 1, "", str(exc))

    def _format(self, action: str, repo: str, completed: subprocess.CompletedProcess[str]) -> str:
        body = (completed.stdout or "").strip()
        err = (completed.stderr or "").strip()
        lines = [
            f"{'OK' if completed.returncode == 0 else 'ERROR'} git.{action}",
            f"repo: {repo}",
        ]
        if body:
            lines.append(body)
        if err and completed.returncode != 0:
            lines.append(err)
        elif err and not body:
            lines.append(err)
        text = "\n".join(lines)
        if len(text) > 20_000:
            return text[:20_000] + "\n[truncated]"
        return text

    @staticmethod
    def _contains_dangerous_tokens(payload: dict[str, Any]) -> bool:
        blob = " ".join(str(value) for value in payload.values()).lower()
        if any(token in blob for token in _DANGEROUS_TOKENS):
            return True
        return bool(re.search(r"(^|\s)-f(\s|$)", blob)) and "push" in blob
