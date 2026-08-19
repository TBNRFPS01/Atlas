from types import SimpleNamespace

from core.permissions import PermissionManager
from core.safety import HardSafety
from planner.planner import Planner
from planner.task import TaskStatus


def _fake_router():
    return SimpleNamespace(
        brain=SimpleNamespace(ask=lambda p: "not a plan"),
        route=lambda text: "done",
        _permissions=PermissionManager(),
        _safety=HardSafety(),
    )


def test_user_consent_allows_destructive_by_default() -> None:
    planner = Planner(router=_fake_router())
    decision = planner._permission_decision("file", {"action": "delete", "path": "C:\\temp\\x.txt"})
    assert decision == "allow"


def test_agent_consent_blocks_destructive_by_default() -> None:
    planner = Planner(router=_fake_router())
    decision = planner._permission_decision(
        "file", {"action": "delete", "path": "C:\\temp\\x.txt"}, consent="agent"
    )
    assert decision == "ask"


def test_deny_rule_wins_over_everything() -> None:
    router = _fake_router()
    router._permissions.set_rule("file.delete", "deny")
    planner = Planner(router=router)
    assert planner._permission_decision("file", {"action": "delete"}) == "deny"
    assert planner._permission_decision("file", {"action": "delete"}, consent="agent") == "deny"


def test_agent_consent_allows_when_rule_permits() -> None:
    router = _fake_router()
    router._permissions.set_rule("file.delete", "allow")
    planner = Planner(router=router)
    decision = planner._permission_decision(
        "file", {"action": "delete", "path": "C:\\temp\\x.txt"}, consent="agent"
    )
    assert decision == "allow"


def test_safety_denies_forbidden_action_for_both_consents() -> None:
    planner = Planner(router=_fake_router())
    assert planner._permission_decision("automation", {"action": "shutdown"}, consent="user") == "deny"
    assert planner._permission_decision("automation", {"action": "shutdown"}, consent="agent") == "deny"


def test_permission_error_does_not_retry() -> None:
    planner = Planner(router=_fake_router())
    planner.create_plan("open notepad")
    task = planner.get_task("task_0")
    assert task is not None
    task.tool_name = "file"
    task.tool_args = {"action": "delete", "path": "C:\\temp\\x.txt"}

    result = planner.execute("task_0", consent="agent")
    assert result.status == TaskStatus.FAILED
    assert result.retry_count == 0
    assert "confirmation" in result.error


def test_create_plan_from_steps_rebuilds_tasks() -> None:
    planner = Planner(router=_fake_router())
    steps = [
        {"description": "one", "tool_name": None, "tool_args": {}},
        {"description": "two", "tool_name": "system", "tool_args": {}},
    ]
    tasks = planner.create_plan_from_steps("goal", steps)
    assert [t.id for t in tasks] == ["task_0", "task_1"]
    assert planner.get_task("task_1").tool_name == "system"  # type: ignore[union-attr]


def test_strategy_hint_is_passed_to_decompose() -> None:
    seen: list[str] = []

    def fake_ask(prompt: str) -> str:
        seen.append(prompt)
        return "[]"

    router = SimpleNamespace(brain=SimpleNamespace(ask=fake_ask), route=lambda t: "done")
    planner = Planner(router=router)
    planner.create_plan("search the web for atlantis", strategy_hint="Strategy hint: use web tool")
    assert any("Strategy hint: use web tool" in p for p in seen)
