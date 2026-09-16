"""Minimal HTTP fetch utility used as a fallback when WebTool is unavailable."""

from __future__ import annotations

import html
import re
from urllib.error import URLError
from urllib.request import Request, urlopen

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ATLAS-Assistant/1.0"
_TIMEOUT = 15


def _strip_tags(raw: str) -> str:
    raw = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.IGNORECASE | re.DOTALL)
    raw = re.sub(r"<style[^>]*>.*?</style>", " ", raw, flags=re.IGNORECASE | re.DOTALL)
    raw = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(raw)
    return re.sub(r"\s+", " ", text).strip()


def fetch_url(url: str, *, max_chars: int = 2000) -> str:
    """Fetch *url* and return plain text, capped at *max_chars*.

    Returns a human-readable error string on failure rather than raising.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        req = Request(url, headers={"User-Agent": _USER_AGENT})
        with urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        text = _strip_tags(raw)
        return text[:max_chars] if text else "No readable text found on the page."
    except URLError as exc:
        return f"Web fetch failed (network error): {exc.reason}"
    except TimeoutError:
        return f"Web fetch timed out after {_TIMEOUT}s: {url}"
    except Exception as exc:
        return f"Web fetch failed: {exc}"
