from core.router import Router
from core.skills import load_skills


def test_load_skills_finds_hello() -> None:
    skills = load_skills()
    names = [s["name"] for s in skills]
    assert "hello" in names


def test_skill_run_invoked() -> None:
    router = Router()
    result = router.route("say hi atlas please")
    assert "example skill" in result


def test_skills_command_lists() -> None:
    router = Router()
    out = router.route("/skills")
    assert "hello" in out


def test_skill_not_triggered_by_unrelated() -> None:
    router = Router()
    result = router.route("what is the weather")
    # Should not be the skill reply; falls through to brain/LLM.
    assert "example skill" not in result
