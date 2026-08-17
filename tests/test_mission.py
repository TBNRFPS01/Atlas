from planner.planner import Planner


class _FakeBrain:
    def __init__(self, plan_json: str = "[]") -> None:
        self.plan_json = plan_json
        self.ask_calls = 0

    def ask(self, prompt: str) -> str:
        self.ask_calls += 1
        # The decompose prompt contains our system instruction text.
        if "Break the user's goal" in prompt:
            return self.plan_json
        return "ok"


class _FakeRouter:
    def __init__(self, brain, route_result: str = "done") -> None:
        self.brain = brain
        self.route_result = route_result

    def route(self, text: str) -> str:
        return self.route_result


def _planner_with(plan_json: str, route_result: str = "done") -> Planner:
    brain = _FakeBrain(plan_json=plan_json)
    planner = Planner(router=_FakeRouter(brain, route_result))
    return planner


def test_run_mission_complete() -> None:
    planner = _planner_with('[{"description": "step one", "tool_name": null, "tool_args": {}}]')
    report = planner.run_mission("do something")
    assert report["success"] is True
    assert report["verdict"] == "MISSION COMPLETE"
    assert report["completed"] == 1
    assert "summary" in report


def test_run_mission_recovers_failed_step() -> None:
    # Route returns a failure marker so the step fails verification, triggering
    # a recovery attempt (a second brain.ask). The loop must complete without
    # crashing and record the failed result.
    planner = _planner_with(
        '[{"description": "risky step", "tool_name": null, "tool_args": {}}]',
        route_result="Failed to complete the risky step",
    )
    report = planner.run_mission("attempt the risky step")
    assert report["tasks"][0]["result"] == "Failed to complete the risky step"
    # decompose + recovery = at least 2 LLM calls.
    assert planner.router.brain.ask_calls >= 2


def test_run_mission_no_crash_on_bad_step() -> None:
    planner = _planner_with("[]")
    report = planner.run_mission("do absolutely nothing useful")
    assert isinstance(report["summary"], str)
    assert "completed" in report and "failed" in report and "recovered" in report
