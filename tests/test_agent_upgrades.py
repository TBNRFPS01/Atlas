from agents.subagents import AgentSpec, SubagentRegistry
from agents.council import AgentCouncil
from core.browser_session import BrowserSession
from core.candidates import Candidate, CandidatePipeline
from core.context_refs import ContextResolver, parse
from core.handoff import SessionHandoff
from core.hooks import HookRegistry


def test_subagents_have_explicit_capabilities():
    registry = SubagentRegistry()
    registry.register(AgentSpec("security", "security reviewer", frozenset({"read"}), max_turns=5))
    assert registry.get("security").role == "security reviewer"
    assert registry.get("security").max_turns == 5


def test_hooks_run_in_registration_order():
    hooks = HookRegistry()
    seen = []
    hooks.register("after_task", lambda **_: seen.append(1))
    hooks.register("after_task", lambda **_: seen.append(2))
    hooks.emit("after_task")
    assert seen == [1, 2]


def test_handoff_round_trip():
    handoff = SessionHandoff.create("finish project", completed=["tests"], pending=["docs"])
    restored = SessionHandoff.from_json(handoff.to_json())
    assert restored.goal == "finish project"
    assert restored.pending == ["docs"]


def test_context_refs_resolve():
    assert parse("inspect @file:core/router.py and @mission:42")
    resolver = ContextResolver()
    resolver.register("mission", lambda value: f"mission-{value}")
    assert resolver.resolve("@mission:42") == {"mission:42": "mission-42"}


def test_candidate_pipeline_judges_and_repairs():
    pipeline = CandidatePipeline(
        judge=lambda c: Candidate(c.value, 1.0, "judged"),
        repair=lambda c: Candidate(f"{c.value}-fixed", c.score, c.reason),
    )
    result = pipeline.choose([Candidate("a", 0.2), Candidate("b", 0.9)])
    assert result.value == "b-fixed"


def test_council_collects_independent_results():
    registry = SubagentRegistry()
    registry.register(AgentSpec("security", "security"))
    registry.register(AgentSpec("reviewer", "review"))
    council = AgentCouncil(registry)
    result = council.deliberate(
        ["security", "reviewer"],
        "check",
        lambda votes, task: ("approved", 0.9),
    )
    assert result.decision == "approved"
    assert len(result.votes) == 2


def test_browser_session_tracks_pages():
    session = BrowserSession()
    session.observe("tab1", "https://example.test", "Example")
    assert session.get().url == "https://example.test"
    session.close("tab1")
    assert session.get() is None
