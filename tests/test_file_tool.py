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


def test_exists_reports_present_and_missing_paths(tmp_path) -> None:
    p = tmp_path / "present.txt"
    p.write_text("data", encoding="utf-8")
    tool = FileTool()

    assert tool.execute(action="exists", path=str(p)) == "True"
    assert tool.execute(action="exists", path=str(tmp_path / "missing.txt")) == "False"


def test_search_matches_files_without_leaving_temp_directory(tmp_path) -> None:
    (tmp_path / "alpha.txt").write_text("a", encoding="utf-8")
    (tmp_path / "beta.log").write_text("b", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "gamma.txt").write_text("c", encoding="utf-8")
    tool = FileTool()

    shallow = tool.execute(action="search", path=str(tmp_path), pattern="*.txt")
    assert "FILE alpha.txt" in shallow
    assert "gamma.txt" not in shallow

    recursive = tool.execute(action="search", path=str(tmp_path), pattern="*.txt", recursive=True)
    assert "FILE alpha.txt" in recursive
    assert "FILE nested/gamma.txt" in recursive


def test_search_rejects_missing_pattern_and_directory(tmp_path) -> None:
    tool = FileTool()
    assert "pattern required" in tool.execute(action="search", path=str(tmp_path)).lower()
    missing = tool.execute(action="search", path=str(tmp_path / "missing"), pattern="*.txt")
    assert "directory not found" in missing.lower()


def test_list_empty_directory(tmp_path) -> None:
    out = FileTool().execute(action="list", path=str(tmp_path))
    assert "empty" in out.lower()


def test_append_creates_parent_directory(tmp_path) -> None:
    p = tmp_path / "nested" / "a.txt"
    out = FileTool().execute(action="append", path=str(p), content="hello")
    assert "appended" in out.lower()
    assert p.read_text(encoding="utf-8") == "hello"


def test_search_non_recursive_does_not_escape_temp_directory(tmp_path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "secret.txt").write_text("secret", encoding="utf-8")
    out = FileTool().execute(action="search", path=str(tmp_path), pattern="*.txt")
    assert "secret.txt" not in out
