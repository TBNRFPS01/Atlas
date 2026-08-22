from core.fast_router import FastIntentRouter


class FakeSkill:
    def __init__(self, name, triggers, *, requires_llm=False):
        self.name = name
        self.triggers = triggers
        self.requires_llm = requires_llm
        self.enabled = True
        self.valid = True


def test_builtin_intents_still_take_fast_path():
    router = FastIntentRouter()

    intent = router.route("open Spotify")

    assert intent is not None
    assert intent.name == "open_app"
    assert intent.target == "Spotify"
    assert router.to_dispatch(intent) == "open Spotify"


def test_skill_trigger_can_fast_route_without_llm():
    skill = FakeSkill("spotify", ["^spotify "])
    router = FastIntentRouter(skills=[skill])

    intent = router.route("spotify play my playlist")

    assert intent is not None
    assert intent.name == "skill"
    assert intent.target == "spotify"
    assert intent.skill is skill
    assert intent.arguments["prompt"] == "spotify play my playlist"


def test_llm_required_skill_is_not_fast_routed():
    skill = FakeSkill("research", ["research ", "find sources"], requires_llm=True)
    router = FastIntentRouter(skills=[skill])

    assert router.route("research this topic") is None


def test_ambiguous_skill_triggers_fall_back():
    first = FakeSkill("first", ["do this"])
    second = FakeSkill("second", ["do this"])
    router = FastIntentRouter(skills=[first, second])

    assert router.route("please do this") is None
