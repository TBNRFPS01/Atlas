from core.natural_router import NaturalCapabilityRouter


def test_knowledge_question_is_not_application_lookup() -> None:
    assert NaturalCapabilityRouter._match("Where is Pakistan?") is None


def test_explicit_web_search_is_web() -> None:
    assert NaturalCapabilityRouter._match("Search the web for Pakistan") == "web:search:Pakistan"


def test_app_discovery_still_works() -> None:
    assert NaturalCapabilityRouter._match("Find Spotify") == "application:find:spotify"
