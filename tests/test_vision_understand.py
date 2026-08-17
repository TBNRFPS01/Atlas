from vision.understand import describe_screen, save_screenshot


def test_describe_screen_returns_string() -> None:
    # Offline (no display/model) it still returns a string rather than raising.
    result = describe_screen(brain=None)
    assert isinstance(result, str)
    assert len(result) > 0


def test_save_screenshot_returns_string_or_empty() -> None:
    path = save_screenshot()
    assert isinstance(path, str)
