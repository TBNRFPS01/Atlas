"""Browser skill -- packaged wrapper around the BrowserTool.

This skill is the declarative entry point for browser automation. It does not
reimplement any browser logic; it delegates to the router's existing, gated
``_browser_request`` so all safety/permission checks stay in one place.
"""

from __future__ import annotations

from typing import Any


def run(router: Any, prompt: str) -> str:
    return router._browser_request(prompt)
