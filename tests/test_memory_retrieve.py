from memory.database import MemoryDatabase


def test_retrieve_ranks_relevant_higher(tmp_path) -> None:
    db = MemoryDatabase(db_path=str(tmp_path / "mem.db"))
    db.remember("fact", "user_name=Alice")
    db.remember("fact", "favorite_color=blue")
    db.remember("fact", "unrelated_metric=42")

    results = db.retrieve("what is the user name", limit=3)
    assert results
    contents = [r.content for r in results]
    assert "user_name=Alice" in contents
    assert results[0].content == "user_name=Alice"


def test_retrieve_excludes_non_matching(tmp_path) -> None:
    db = MemoryDatabase(db_path=str(tmp_path / "mem2.db"))
    db.remember("fact", "project_deadline=Friday")
    results = db.retrieve("completely unrelated query about cats", limit=5)
    assert results == []
