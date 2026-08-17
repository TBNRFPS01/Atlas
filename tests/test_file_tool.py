from tools.file_tool import FileTool


def test_write_and_read(tmp_path) -> None:
    p = tmp_path / "a.txt"
    tool = FileTool()
    out = tool.execute(action="write", path=str(p), content="hello")
    assert isinstance(out, str)
    assert p.read_text(encoding="utf-8") == "hello"
    out = tool.execute(action="read", path=str(p))
    assert "hello" in out


def test_append(tmp_path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("one", encoding="utf-8")
    FileTool().execute(action="append", path=str(p), content="two")
    assert p.read_text(encoding="utf-8") == "onetwo"


def test_list_directory(tmp_path) -> None:
    (tmp_path / "x.txt").write_text("1")
    (tmp_path / "y.txt").write_text("2")
    out = FileTool().execute(action="list", path=str(tmp_path))
    assert "x.txt" in out and "y.txt" in out


def test_delete_via_tool(tmp_path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("x")
    FileTool().execute(action="delete", path=str(p))
    assert not p.exists()


def test_read_missing_file(tmp_path) -> None:
    out = FileTool().execute(action="read", path=str(tmp_path / "nope.txt"))
    assert "not found" in out.lower() or "does not exist" in out.lower()


def test_write_without_path() -> None:
    out = FileTool().execute(action="write", content="x")
    assert "path" in out.lower()


def test_overwrite_existing(tmp_path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("old")
    FileTool().execute(action="write", path=str(p), content="new")
    assert p.read_text(encoding="utf-8") == "new"
