"""Provider-neutral browser session state for future real browser adapters."""
from __future__ import annotations

from dataclasses import dataclass, field
from time import time


@dataclass
class BrowserPage:
    url: str
    title: str = ""
    snapshot: str = ""
    updated_at: float = field(default_factory=time)


class BrowserSession:
    def __init__(self) -> None:
        self.pages: dict[str, BrowserPage] = {}
        self.active: str | None = None

    def observe(self, page_id: str, url: str, title: str = "", snapshot: str = "") -> BrowserPage:
        page = BrowserPage(url, title, snapshot)
        self.pages[page_id] = page
        self.active = page_id
        return page

    def get(self, page_id: str | None = None) -> BrowserPage | None:
        return self.pages.get(page_id or self.active) if (page_id or self.active) else None

    def close(self, page_id: str) -> None:
        self.pages.pop(page_id, None)
        if self.active == page_id:
            self.active = next(iter(self.pages), None)
