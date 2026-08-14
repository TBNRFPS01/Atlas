from __future__ import annotations

import html
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from tools.base import Tool, ToolMetadata, ToolParameter


class WebTool(Tool):
    """Search and fetch web content for ATLAS."""

    name = "web"
    description = "Search the web and fetch page text."
    metadata = ToolMetadata(category="web", permission_level="basic", confirmation_required=False, description=description)

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Web operation: search or fetch",
                required=True,
                enum=["search", "fetch"],
            ),
            ToolParameter(
                name="query",
                type="string",
                description="Search query (for search action)",
                required=False,
            ),
            ToolParameter(
                name="url",
                type="string",
                description="URL to fetch (for fetch action)",
                required=False,
            ),
        ]

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ATLAS-Assistant/1.0"

    def _open(self, url: str, timeout: int = 20) -> str:
        request = Request(url, headers={"User-Agent": self.USER_AGENT})
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="ignore")

    def _strip_tags(self, raw: str) -> str:
        raw = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.IGNORECASE | re.DOTALL)
        raw = re.sub(r"<style[^>]*>.*?</style>", " ", raw, flags=re.IGNORECASE | re.DOTALL)
        raw = re.sub(r"<[^>]+>", " ", raw)
        text = html.unescape(raw)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _fetch(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        raw = self._open(url)
        text = self._strip_tags(raw)
        return text[:2000] if text else "No readable text found on the page."

    def _search(self, query: str) -> str:
        target = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
        raw = self._open(target)
        anchors = re.findall(
            r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            raw,
            re.IGNORECASE | re.DOTALL,
        )
        results: list[tuple[str, str]] = []
        skip = {"more at wikipedia"}
        for href, title in anchors:
            title_text = self._strip_tags(title)
            if not title_text or title_text.lower() in skip:
                continue
            if href.startswith("//duckduckgo.com/l/"):
                href = self._decode_uddg(href)
            results.append((title_text, href))
            if len(results) >= 10:
                break

        if not results:
            return "No search results found."
        return "\n".join(f"- {title}\n  {href}" for title, href in results)

    @staticmethod
    def _decode_uddg(href: str) -> str:
        """Decode DuckDuckGo redirect-wrapped result URLs."""
        from urllib.parse import parse_qs, urlparse

        query = parse_qs(urlparse("https:" + href).query)
        uddg = query.get("uddg", [""])[0]
        return uddg or href

    def _clean(self, piece: str) -> str:
        piece = re.sub(r"<[^>]+>", " ", piece)
        piece = html.unescape(piece)
        return re.sub(r"\s+", " ", piece).strip()

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.get("action") or "search"
        url = kwargs.get("url", "")
        query = kwargs.get("query", "")

        if action == "fetch" or (action == "search" and url):
            return self._fetch(url or query)
        return self._search(query or " ".join(str(a) for a in args))