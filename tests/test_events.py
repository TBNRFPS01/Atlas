from core.events import EventBus


def test_emit_invokes_listeners() -> None:
    bus = EventBus()
    calls = []
    bus.on("greet", lambda name: calls.append(name))
    bus.emit("greet", "world")
    assert calls == ["world"]


def test_emit_ignores_other_events() -> None:
    bus = EventBus()
    calls = []
    bus.on("greet", lambda name: calls.append(name))
    bus.emit("other", "world")
    assert calls == []