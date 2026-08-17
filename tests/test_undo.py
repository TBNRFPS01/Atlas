from core.undo import UndoStack


def test_record_and_undo() -> None:
    stack = UndoStack()
    state = {"v": 1}
    stack.record("set v", lambda: state.__setitem__("v", 1))
    state["v"] = 99
    msg = stack.undo()
    assert state["v"] == 1
    assert "Undid" in msg


def test_empty_undo() -> None:
    stack = UndoStack()
    assert stack.undo() == "Nothing to undo."
    assert stack.can_undo() is False


def test_undo_failure_reported() -> None:
    stack = UndoStack()
    stack.record("boom", lambda: (_ for _ in ()).throw(RuntimeError("nope")))
    msg = stack.undo()
    assert "failed" in msg


def test_limit_enforced() -> None:
    stack = UndoStack(limit=2)
    for i in range(5):
        stack.record(f"op{i}", lambda: None)
    assert len(stack._stack) == 2
