from core.personality import ATLASPersonality


def test_respond_returns_string() -> None:
    p = ATLASPersonality()
    assert isinstance(p.respond("hello"), str)


def test_respond_passes_through() -> None:
    p = ATLASPersonality()
    assert "status report" in p.respond("status report")


def test_personality_has_prompt() -> None:
    p = ATLASPersonality()
    assert isinstance(p, ATLASPersonality)
    assert isinstance(p.system_prompt(), str)
    assert len(p.system_prompt()) > 0


def test_respond_with_empty() -> None:
    p = ATLASPersonality()
    assert isinstance(p.respond(""), str)
