"""Minecraft skill -- packaged wrapper around the MinecraftTool.

Delegates to the router's existing ``_minecraft_request``.
"""

from __future__ import annotations

from typing import Any


def run(router: Any, prompt: str) -> str:
    return router._minecraft_request(prompt)
