"""Coding skill -- create, read, and edit code files via the file tool.

Demonstrates a skill that brings its own lightweight command parsing while
delegating all file I/O to the already-gated file tool (so undo, trash, and
permission checks are reused rather than reimplemented).
"""

from __future__ import annotations

import re
from typing import Any


def run(router: Any, prompt: str) -> str:
    tool = router._registry.get("file")
    if tool is None:
        return "File tool not loaded; coding skill cannot operate."

    path = router._extract_path(prompt)
    lowered = prompt.lower()

    if "read" in lowered and path:
        return tool.execute(action="read", path=path)

    if any(word in lowered for word in ("create", "write", "edit", "append")) and path:
        content = ""
        marker = re.search(r"\b(?:with|containing|:)\s+(.+)", prompt, re.IGNORECASE)
        if marker:
            content = marker.group(1).strip().strip("'\"")
        action = "append" if "append" in lowered else "write"
        return tool.execute(action=action, path=path, content=content or "# (no content supplied)")

    return (
        "Coding skill ready. Try:\n"
        "  create a python script C:\\path\\app.py with print('hi')\n"
        "  read code C:\\path\\app.py\n"
        "  append to code C:\\path\\app.py with # comment"
    )
