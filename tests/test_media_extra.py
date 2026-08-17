import os

from tools.media_tool import MediaTool


def test_find_media_files(tmp_path, monkeypatch) -> None:
    (tmp_path / "song.mp3").write_text("x")
    (tmp_path / "clip.mp4").write_text("x")
    (tmp_path / "notes.txt").write_text("x")
    monkeypatch.setenv("ATLAS_MUSIC_DIR", str(tmp_path))
    tool = MediaTool()
    results = tool._find_media_files("song")
    assert any("song.mp3" in r for r in results)


def test_play_missing_file() -> None:
    tool = MediaTool()
    out = tool._play_file("C:\\nonexistent\\file.mp3")
    assert "not found" in out.lower()


def test_volume_validation() -> None:
    tool = MediaTool()
    out = tool.execute(action="volume", volume=250)
    assert "between 0 and 100" in out


def test_send_media_key_unknown_action() -> None:
    tool = MediaTool()
    assert tool._send_media_key("bogus") is False


def test_play_requires_query_or_path() -> None:
    tool = MediaTool()
    out = tool.execute(action="play")
    assert "path or query" in out.lower()
