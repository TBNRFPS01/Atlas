from planner.planner import Planner
from planner.task import Task, TaskStatus


def _make_planner() -> Planner:
    return Planner(router=object())  # router only needs _permissions for permission checks


def test_verify_task_succeeds_on_clean_result() -> None:
    planner = _make_planner()
    task = Task(id="t1", description="open app", tool_name="automation", tool_args={"action": "windows_launch"})
    task.complete("Launched: notepad")
    assert planner._verify_task(task) is True


def test_verify_task_fails_on_error_marker() -> None:
    planner = _make_planner()
    task = Task(id="t1", description="open app", tool_name="automation", tool_args={})
    task.complete("Failed to launch application")
    assert planner._verify_task(task) is False


def test_verify_task_fails_when_not_completed() -> None:
    planner = _make_planner()
    task = Task(id="t1", description="x", tool_name="", tool_args={})
    task.fail("boom")
    assert planner._verify_task(task) is False


def test_permission_decision_honors_deny_rule() -> None:
    planner = Planner()
    planner.router._permissions.set_rule("file.delete", "deny")
    assert planner._permission_decision("file", {"action": "delete"}) == "deny"


def test_permission_decision_allows_autonomous_destructive() -> None:
    planner = Planner()
    # Autonomous runs are treated as confirmed, so destructive actions are allowed
    # unless explicitly denied.
    assert planner._permission_decision("automation", {"action": "process_kill"}) == "allow"
