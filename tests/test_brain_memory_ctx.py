from core.brain import Brain


class _FakeMemory:
    def __init__(self, records) -> None:
        self._records = records

    def retrieve(self, query, limit=5):
        return self._records[:limit]


class _Rec:
    def __init__(self, content) -> None:
        self.content = content


def test_memory_context_joins_retrieved() -> None:
    brain = Brain()
    brain.memory_store = _FakeMemory([_Rec("user_name=Alice"), _Rec("city=Paris")])
    ctx = brain._memory_context("who is the user")
    assert "user_name=Alice" in ctx
    assert "city=Paris" in ctx


def test_memory_context_empty_when_no_store() -> None:
    brain = Brain()
    brain.memory_store = None
    assert brain._memory_context("anything") == ""


def test_brain_responds_to_unknown_without_crash() -> None:
    # No LM Studio; ask should return a graceful error string, not raise.
    brain = Brain()
    out = brain.ask("hello there")
    assert isinstance(out, str)
