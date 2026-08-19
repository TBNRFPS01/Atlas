from pathlib import Path

from memory.state import AgentStateStore


def test_state_set_get_roundtrip(tmp_path: Path) -> None:
    store = AgentStateStore(str(tmp_path / "atlas_memory.db"))
    store.set("mission.counter", 3)
    assert store.get("mission.counter") == 3


def test_state_persists_across_instances(tmp_path: Path) -> None:
    path = str(tmp_path / "atlas_memory.db")
    AgentStateStore(path).set("goals.last_id", 7)
    fresh = AgentStateStore(path)
    assert fresh.get("goals.last_id") == 7


def test_state_serializes_complex_objects(tmp_path: Path) -> None:
    store = AgentStateStore(str(tmp_path / "atlas_memory.db"))
    payload = {"steps": [{"tool": "web", "ok": True}], "index": 1, "active": False}
    store.set("mission.plan:1", payload)
    loaded = store.get("mission.plan:1")
    assert loaded == payload


def test_state_default_when_missing(tmp_path: Path) -> None:
    store = AgentStateStore(str(tmp_path / "atlas_memory.db"))
    assert store.get("missing.key", "fallback") == "fallback"
    assert store.has("missing.key") is False


def test_state_delete_and_increment(tmp_path: Path) -> None:
    store = AgentStateStore(str(tmp_path / "atlas_memory.db"))
    store.set("calls", 1)
    assert store.increment("calls") == 2
    assert store.counter("calls") == 2
    assert store.delete("calls") is True
    assert store.has("calls") is False
    assert store.delete("calls") is False


def test_state_all_and_count(tmp_path: Path) -> None:
    store = AgentStateStore(str(tmp_path / "atlas_memory.db"))
    store.set("a", 1)
    store.set("b", "x")
    assert store.count() == 2
    assert set(store.keys()) == {"a", "b"}
    assert store.all() == {"a": 1, "b": "x"}
