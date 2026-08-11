import sqlite3
from pathlib import Path

from memory.database import MemoryDatabase


def test_memory_database_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "atlas_memory.db"
    db = MemoryDatabase(str(db_path))

    with sqlite3.connect(db_path) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
        ).fetchall()

    assert tables
    assert db.get_fact("missing") is None


def test_memory_set_and_get_fact(tmp_path: Path) -> None:
    db_path = tmp_path / "atlas_memory.db"
    db = MemoryDatabase(str(db_path))

    db.set_fact("name", "ATLAS")
    assert db.get_fact("name") == "ATLAS"
