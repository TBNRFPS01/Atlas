from __future__ import annotations

import webbrowser
import re
from urllib.parse import urlparse

from tools.base import Tool, ToolMetadata, ToolParameter


class BrowserTool(Tool):
    """Browser tool for opening URLs and websites."""

    name = "browser"
    description = "Open websites and URLs in the default web browser."
    metadata = ToolMetadata(category="web", permission_level="basic", confirmation_required=False, description=description)

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform: open, search",
                required=True,
                enum=["open", "search"],
            ),
            ToolParameter(
                name="url",
                type="string",
                description="URL to open (for open action)",
                required=False,
            ),
            ToolParameter(
                name="query",
                type="string",
                description="Search query (for search action)",
                required=False,
            ),
        ]

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.get("action", "open")
        
        if action == "open":
            url = kwargs.get("url", args[0] if args else "")
            if not url:
                return "URL required for open action"
            
            # Ensure URL has a scheme
            if not urlparse(url).scheme:
                url = "https://" + url
            
            try:
                webbrowser.open(url)
                return f"Opened {url} in browser"
            except Exception as e:
                return f"Failed to open {url}: {e}"
        
        elif action == "search":
            query = kwargs.get("query", args[0] if args else "")
            if not query:
                return "Query required for search action"
            
            # Use DuckDuckGo for search
            search_url = f"https://duckduckgo.com/?q={webbrowser.quote(query)}"
            try:
                webbrowser.open(search_url)
                return f"Searching for: {query}"
            except Exception as e:
                return f"Failed to search: {e}"
        
        else:
            return f"Unknown action: {action}"


# Add quote function to webbrowser if not available (Python 3.7+)
if not hasattr(webbrowser, 'quote'):
    import urllib.parse
    webbrowser.quote = urllib.parse.quote