from __future__ import annotations

import html
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from tools.base import Tool, ToolMetadata, ToolParameter


class WebTool(Tool):
    """Search, research, and fetch web content for ATLAS."""

    name = "web"
    description = "Search the web, research a topic from multiple results, and fetch page text."
    metadata = ToolMetadata(category="web", permission_level="basic", confirmation_required=False, description=description)

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Web operation: search, research, or fetch",
                required=True,
                enum=["search", "research", "fetch"],
            ),
            ToolParameter(
                name="query",
                type="string",
                description="Search/research query",
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
        """Perform a single HTTP fetch (no retries)."""
        request = Request(url, headers={"User-Agent": self.USER_AGENT})
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status and 400 <= int(status) < 600:
                raise RuntimeError(f"HTTP {status} from {url}")
            return response.read().decode("utf-8", errors="ignore")

    def _open_with_retry(self, url: str, timeout: int = 20, retries: int = 2, backoff: float = 0.3) -> str:
        """Fetch a URL with bounded retries and exponential backoff."""
        import time

        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                return self._open(url, timeout=timeout)
            except Exception as exc:  # noqa: BLE001 - normalise to RuntimeError
                last_error = exc
                if attempt < retries:
                    time.sleep(backoff * (2 ** attempt))
                    continue
                break
        raise RuntimeError(f"Failed to fetch {url} after {retries + 1} attempts: {last_error}") from last_error

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
        try:
            raw = self._open_with_retry(url)
        except Exception as exc:
            return f"Web fetch failed: {exc}"
        text = self._strip_tags(raw)
        return text[:2000] if text else "No readable text found on the page."

    def _search(self, query: str) -> str:
        if not query:
            return "Search query required."
        target = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
        try:
            raw = self._open_with_retry(target)
        except Exception as exc:
            return f"Web search failed: {exc}"
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

    def _research(self, query: str) -> str:
        """Build a compact research packet from several search results.

        The LLM can use the returned source titles, URLs, and page text as
        grounded context instead of relying only on its training knowledge.
        """
        if not query:
            return "Research query required."

        search_target = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
        try:
            raw = self._open_with_retry(search_target)
        except Exception as exc:
            return f"Web research failed during search: {exc}"

        anchors = re.findall(
            r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            raw,
            re.IGNORECASE | re.DOTALL,
        )
        results: list[tuple[str, str]] = []
        for href, title in anchors:
            title_text = self._strip_tags(title)
            if not title_text:
                continue
            if href.startswith("//duckduckgo.com/l/"):
                href = self._decode_uddg(href)
            if not href.startswith(("http://", "https://")):
                continue
            if any(existing_url == href for _, existing_url in results):
                continue
            results.append((title_text, href))
            if len(results) >= 5:
                break

        if not results:
            return "No research sources found."

        packets: list[str] = [f"Research results for: {query}"]
        for index, (title, url) in enumerate(results, start=1):
            text = self._fetch(url)
            packets.append(f"\n[{index}] {title}\nURL: {url}\nContent: {text[:1600]}")
        packets.append("\nUse the sources above as current web evidence; distinguish sourced facts from model knowledge.")
        return "\n".join(packets)[:9000]

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

        try:
            if action == "fetch" or (action == "search" and url):
                return self._fetch(url or query)
            if action == "research":
                return self._research(query or " ".join(str(a) for a in args))
            return self._search(query or " ".join(str(a) for a in args))
        except Exception as exc:
            return f"Web tool error: {exc}"
