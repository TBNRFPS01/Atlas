from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.base import Tool, ToolMetadata, ToolParameter


class BrowserTool(Tool):
    """Operate real websites: open pages, click, type, navigate, inspect, verify.

    This is the browser automation layer that turns ATLAS from a "research the
    web" agent into an "operate websites" agent. State (cookies, localStorage,
    session storage) is persisted to disk so login sessions survive restarts.
    """

    name = "browser"
    description = "Operate websites: open pages, click, type, navigate, read content, and verify."
    metadata = ToolMetadata(
        category="web",
        permission_level="elevated",
        confirmation_required=False,
        description=description,
    )

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._state_dir = Path.home() / ".atlas" / "browser"
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._storage_path = self._state_dir / "storage.json"
        self._headless = True

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description=(
                    "Browser operation: navigate, click, type, scroll, back, forward, "
                    "reload, get_text, get_html, get_links, eval_js, screenshot, "
                    "wait_for, fill, close, status"
                ),
                required=True,
                enum=[
                    "navigate", "click", "type", "scroll", "back", "forward",
                    "reload", "get_text", "get_html", "get_links", "eval_js",
                    "screenshot", "wait_for", "fill", "close", "status",
                ],
            ),
            ToolParameter(name="url", type="string",
                          description="URL for navigate/open", required=False),
            ToolParameter(name="selector", type="string",
                          description="CSS or text selector for click/fill/type/wait", required=False),
            ToolParameter(name="text", type="string",
                          description="Text to type/fill or JS expression to eval", required=False),
            ToolParameter(name="direction", type="string",
                          description="Scroll direction: up/down", required=False, enum=["up", "down"]),
            ToolParameter(name="amount", type="integer",
                          description="Scroll amount in pixels (default 300)", required=False),
            ToolParameter(name="timeout", type="integer",
                          description="Wait timeout in ms (default 5000)", required=False),
        ]

    # -- lifecycle -------------------------------------------------------
    def _ensure_browser(self) -> None:
        """Lazily launch Chromium and restore persisted session state."""
        if self._browser is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright is not installed. Run: pip install playwright && playwright install chromium"
            )

        self._playwright = sync_playwright().start()

        launch_args = {
            "headless": self._headless,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        try:
            self._browser = self._playwright.chromium.launch(**launch_args)
        except Exception as exc:
            # Headless shell may be unavailable; retry headed as a last resort.
            raise RuntimeError(f"Failed to launch Chromium: {exc}") from exc

        # Restore persisted cookies/localStorage if present.
        storage_state = None
        if self._storage_path.exists():
            try:
                storage_state = str(self._storage_path)
            except Exception:
                storage_state = None

        self._context = self._browser.new_context(
            storage_state=storage_state,
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
        )
        self._page = self._context.new_page()
        self._page.set_default_timeout(5000)

    def _persist_state(self) -> None:
        """Save cookies and storage so sessions survive restarts."""
        if self._context is None:
            return
        try:
            self._context.storage_state(path=str(self._storage_path))
        except Exception:
            pass

    def _close(self) -> None:
        self._persist_state()
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._page = None

    # -- helpers ---------------------------------------------------------
    def _resolve_selector(self, page, selector: str):
        """Resolve a selector that may be plain text, CSS, or XPath-like."""
        if not selector:
            return None
        # Try CSS first; if it doesn't match, fall back to text search.
        try:
            count = page.locator(selector).count()
            if count > 0:
                return selector
        except Exception:
            pass
        # Text-based fallback: clickable with visible text.
        return f"text={selector}"

    def _screenshot(self) -> str | None:
        """Capture a screenshot and return its path (or None on failure)."""
        if self._page is None:
            return None
        folder = self._state_dir / "screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        from datetime import datetime

        path = folder / f"browser-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        try:
            self._page.screenshot(path=str(path))
            return str(path)
        except Exception:
            return None

    # -- actions ---------------------------------------------------------
    def _do_navigate(self, url: str) -> dict[str, Any]:
        if not url:
            return {"success": False, "error": "navigate requires a url"}
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self._ensure_browser()
        self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
        self._page.wait_for_load_state("networkidle", timeout=5000)
        self._persist_state()
        return {
            "success": True,
            "data": {
                "url": self._page.url,
                "title": self._page.title(),
            },
            "screenshot_path": self._screenshot(),
        }

    def _do_click(self, selector: str) -> dict[str, Any]:
        if not selector:
            return {"success": False, "error": "click requires a selector or text"}
        self._ensure_browser()
        resolved = self._resolve_selector(self._page, selector)
        locator = self._page.locator(resolved).first
        locator.wait_for(state="visible", timeout=5000)
        locator.click()
        self._page.wait_for_load_state("networkidle", timeout=5000)
        self._persist_state()
        return {
            "success": True,
            "data": {"url": self._page.url, "title": self._page.title()},
            "screenshot_path": self._screenshot(),
        }

    def _do_type(self, selector: str, text: str) -> dict[str, Any]:
        if not selector:
            return {"success": False, "error": "type requires a selector or text target"}
        if not text:
            return {"success": False, "error": "type requires text"}
        self._ensure_browser()
        resolved = self._resolve_selector(self._page, selector)
        locator = self._page.locator(resolved).first
        locator.wait_for(state="visible", timeout=5000)
        locator.click()
        locator.type(text, delay=20)
        return {
            "success": True,
            "data": {"typed": text, "url": self._page.url},
            "screenshot_path": self._screenshot(),
        }

    def _do_fill(self, selector: str, text: str) -> dict[str, Any]:
        if not selector:
            return {"success": False, "error": "fill requires a selector"}
        if not text:
            return {"success": False, "error": "fill requires text"}
        self._ensure_browser()
        resolved = self._resolve_selector(self._page, selector)
        locator = self._page.locator(resolved).first
        locator.wait_for(state="visible", timeout=5000)
        locator.fill(text)
        return {
            "success": True,
            "data": {"filled": text, "url": self._page.url},
            "screenshot_path": self._screenshot(),
        }

    def _do_scroll(self, direction: str, amount: int) -> dict[str, Any]:
        self._ensure_browser()
        delta = amount if direction != "up" else -amount
        self._page.mouse.wheel(0, delta)
        return {
            "success": True,
            "data": {"scrolled": delta, "url": self._page.url},
            "screenshot_path": self._screenshot(),
        }

    def _do_back(self) -> dict[str, Any]:
        self._ensure_browser()
        self._page.go_back()
        return {"success": True, "data": {"url": self._page.url}, "screenshot_path": self._screenshot()}

    def _do_forward(self) -> dict[str, Any]:
        self._ensure_browser()
        self._page.go_forward()
        return {"success": True, "data": {"url": self._page.url}, "screenshot_path": self._screenshot()}

    def _do_reload(self) -> dict[str, Any]:
        self._ensure_browser()
        self._page.reload()
        return {"success": True, "data": {"url": self._page.url}, "screenshot_path": self._screenshot()}

    def _do_get_text(self) -> dict[str, Any]:
        self._ensure_browser()
        text = self._page.inner_text("body")
        return {"success": True, "data": {"text": text[:5000]}}

    def _do_get_html(self) -> dict[str, Any]:
        self._ensure_browser()
        html = self._page.content()
        return {"success": True, "data": {"html": html[:20000]}}

    def _do_get_links(self) -> dict[str, Any]:
        self._ensure_browser()
        links = self._page.eval_on_selector_all(
            "a[href]", "els => els.map(e => ({text: e.innerText, href: e.href}))"
        )
        return {"success": True, "data": {"links": links[:50]}}

    def _do_eval_js(self, expression: str) -> dict[str, Any]:
        if not expression:
            return {"success": False, "error": "eval_js requires a JS expression"}
        self._ensure_browser()
        result = self._page.evaluate(expression)
        return {"success": True, "data": {"result": str(result)[:2000]}}

    def _do_screenshot(self) -> dict[str, Any]:
        self._ensure_browser()
        path = self._screenshot()
        return {"success": path is not None, "data": {"path": path},
                "error": None if path else "screenshot failed"}

    def _do_wait_for(self, selector: str, timeout: int) -> dict[str, Any]:
        if not selector:
            return {"success": False, "error": "wait_for requires a selector"}
        self._ensure_browser()
        resolved = self._resolve_selector(self._page, selector)
        locator = self._page.locator(resolved).first
        locator.wait_for(state="visible", timeout=timeout)
        return {"success": True, "data": {"waited_for": selector, "url": self._page.url},
                "screenshot_path": self._screenshot()}

    def _do_status(self) -> dict[str, Any]:
        if self._page is None:
            return {"success": True, "data": {"state": "no active session"}}
        return {"success": True, "data": {"url": self._page.url, "title": self._page.title()}}

    # -- main entry ------------------------------------------------------
    def execute(self, *args, **kwargs) -> str:
        action = (kwargs.get("action") or "").lower()
        url = kwargs.get("url", "")
        selector = kwargs.get("selector", "")
        text = kwargs.get("text", "")
        direction = (kwargs.get("direction") or "down").lower()
        amount = int(kwargs.get("amount") or 300)
        timeout = int(kwargs.get("timeout") or 5000)

        handlers = {
            "navigate": lambda: self._do_navigate(url),
            "click": lambda: self._do_click(selector),
            "type": lambda: self._do_type(selector, text),
            "fill": lambda: self._do_fill(selector, text),
            "scroll": lambda: self._do_scroll(direction, amount),
            "back": self._do_back,
            "forward": self._do_forward,
            "reload": self._do_reload,
            "get_text": self._do_get_text,
            "get_html": self._do_get_html,
            "get_links": self._do_get_links,
            "eval_js": lambda: self._do_eval_js(text),
            "screenshot": self._do_screenshot,
            "wait_for": lambda: self._do_wait_for(selector, timeout),
            "close": lambda: (self._close(), {"success": True, "data": {"closed": True}}) [1],
            "status": self._do_status,
        }

        handler = handlers.get(action)
        if handler is None:
            return f"Unknown browser action: {action}. Available: {', '.join(handlers)}"

        try:
            result = handler()
        except Exception as exc:
            return f"Browser error: {exc}"

        return self._format(result)

    @staticmethod
    def _format(result: dict[str, Any]) -> str:
        """Render a structured browser result as compact, readable text."""
        if not result.get("success"):
            return f"Browser failed: {result.get('error', 'unknown error')}"
        data = result.get("data", {})
        lines = []
        if "url" in data:
            lines.append(f"URL: {data['url']}")
        if "title" in data:
            lines.append(f"Title: {data['title']}")
        for key in ("text", "html", "result", "links", "typed", "filled", "waited_for", "scrolled", "path", "state", "closed"):
            if key in data and data[key] is not None:
                value = data[key]
                if isinstance(value, (list, dict)):
                    value = json.dumps(value, ensure_ascii=False)[:2000]
                lines.append(f"{key}: {value}")
        if result.get("screenshot_path"):
            lines.append(f"screenshot: {result['screenshot_path']}")
        return "\n".join(lines) if lines else "Browser action completed."
