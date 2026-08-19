from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tools.browser_tool import BrowserTool


class _FakeLocator:
    def __init__(self, text: str = "element") -> None:
        self._text = text
        self.typed = ""
        self.filled = ""

    def count(self) -> int:
        return 1

    @property
    def first(self) -> "_FakeLocator":
        return self

    def wait_for(self, state: str = "visible", timeout: int = 5000) -> None:
        return None

    def click(self) -> None:
        return None

    def type(self, text: str, delay: int = 0) -> None:
        self.typed = text

    def fill(self, text: str) -> None:
        self.filled = text

    def inner_text(self) -> str:
        return self._text


class _FakePage:
    def __init__(self, url: str = "https://example.com", title: str = "Example") -> None:
        self.url = url
        self._title = title
        self._text = "Hello world"
        self._html = "<html><body>Hello world</body></html>"
        self._links = [{"text": "Home", "href": "https://example.com/"}]
        self._scroll = 0
        self._navigated = None
        self._clicked = None
        self.mouse = MagicMock()
        self.mouse.wheel.side_effect = lambda x, y: setattr(self, "_scroll", y)

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator()

    def goto(self, url: str, wait_until: str = "load", timeout: int = 30000) -> None:
        self._navigated = url
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.url = url

    def wait_for_load_state(self, state: str = "load", timeout: int = 30000) -> None:
        return None

    def go_back(self) -> None:
        self.url = "https://example.com/previous"

    def go_forward(self) -> None:
        self.url = "https://example.com/next"

    def reload(self) -> None:
        return None

    def inner_text(self, selector: str) -> str:
        return self._text

    def content(self) -> str:
        return self._html

    def title(self) -> str:
        return self._title

    def eval_on_selector_all(self, selector: str, expr: str) -> list[dict]:
        return self._links

    def evaluate(self, expr: str) -> str:
        return "42"

    def screenshot(self, path: str | None = None) -> bytes:
        return b"fakepng"


class _FakeContext:
    def __init__(self) -> None:
        self._page = _FakePage()

    def new_page(self) -> _FakePage:
        return self._page

    def storage_state(self, path: str | None = None) -> dict:
        return {"cookies": [], "origins": []}

    def close(self) -> None:
        return None


class _FakeBrowser:
    def __init__(self) -> None:
        self._context = _FakeContext()

    def new_context(self, **kwargs) -> _FakeContext:
        return self._context

    def close(self) -> None:
        return None


class _FakePlaywright:
    def __init__(self) -> None:
        self._browser = _FakeBrowser()

    @property
    def chromium(self) -> _FakeBrowser:
        return self._browser

    def stop(self) -> None:
        return None


@pytest.fixture
def browser(monkeypatch) -> BrowserTool:
    """A BrowserTool with Playwright fully mocked."""
    tool = BrowserTool()
    pw = _FakePlaywright()

    def _fake_ensure(self) -> None:
        import types
        self._playwright = pw
        self._browser = pw.chromium
        self._context = pw.chromium.new_context()
        self._page = self._context.new_page()
        self._page.set_default_timeout = lambda *a, **k: None  # type: ignore[attr-defined]

    monkeypatch.setattr(BrowserTool, "_ensure_browser", _fake_ensure)
    monkeypatch.setattr(tool, "_screenshot", lambda: "/tmp/shot.png")
    return tool


def test_navigate_success(browser: BrowserTool) -> None:
    result = browser.execute(action="navigate", url="example.com")
    assert "URL: https://example.com" in result
    assert "Title: Example" in result
    assert "screenshot: /tmp/shot.png" in result


def test_navigate_requires_url(browser: BrowserTool) -> None:
    result = browser.execute(action="navigate")
    assert "requires a url" in result


def test_click_success(browser: BrowserTool) -> None:
    result = browser.execute(action="click", selector="button.submit")
    assert "URL: https://example.com" in result


def test_click_requires_selector(browser: BrowserTool) -> None:
    result = browser.execute(action="click")
    assert "requires a selector" in result


def test_type_success(browser: BrowserTool) -> None:
    result = browser.execute(action="type", selector="input#q", text="hello")
    assert "typed: hello" in result


def test_type_requires_text(browser: BrowserTool) -> None:
    result = browser.execute(action="type", selector="input#q")
    assert "requires text" in result


def test_fill_success(browser: BrowserTool) -> None:
    result = browser.execute(action="fill", selector="input#q", text="world")
    assert "filled: world" in result


def test_scroll_down(browser: BrowserTool) -> None:
    result = browser.execute(action="scroll", direction="down", amount=400)
    assert "scrolled: 400" in result


def test_scroll_up_negates_amount(browser: BrowserTool) -> None:
    result = browser.execute(action="scroll", direction="up", amount=400)
    assert "scrolled: -400" in result


def test_back_forward(browser: BrowserTool) -> None:
    back = browser.execute(action="back")
    assert "URL: https://example.com/previous" in back
    forward = browser.execute(action="forward")
    assert "URL: https://example.com/next" in forward


def test_get_text(browser: BrowserTool) -> None:
    result = browser.execute(action="get_text")
    assert "Hello world" in result


def test_get_html(browser: BrowserTool) -> None:
    result = browser.execute(action="get_html")
    assert "<html>" in result


def test_get_links(browser: BrowserTool) -> None:
    result = browser.execute(action="get_links")
    assert "Home" in result
    assert "https://example.com/" in result


def test_eval_js(browser: BrowserTool) -> None:
    result = browser.execute(action="eval_js", text="1+1")
    assert "42" in result


def test_eval_js_requires_expression(browser: BrowserTool) -> None:
    result = browser.execute(action="eval_js")
    assert "requires a JS expression" in result


def test_screenshot(browser: BrowserTool) -> None:
    result = browser.execute(action="screenshot")
    assert "path: /tmp/shot.png" in result


def test_status_no_session(monkeypatch) -> None:
    tool = BrowserTool()
    monkeypatch.setattr(tool, "_page", None)
    result = tool.execute(action="status")
    assert "no active session" in result


def test_unknown_action(browser: BrowserTool) -> None:
    result = browser.execute(action="frobnicate")
    assert "Unknown browser action" in result


def test_error_is_caught(browser: BrowserTool, monkeypatch) -> None:
    def _boom(self, url):
        raise RuntimeError("boom")
    monkeypatch.setattr(BrowserTool, "_do_navigate", _boom)
    result = browser.execute(action="navigate", url="example.com")
    assert "Browser error: boom" in result
