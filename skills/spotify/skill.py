"""Spotify skill -- packaged wrapper around the SpotifyTool.

Delegates to the router's existing ``_spotify_request`` so authentication, the
argument parser, and the call-log stay consistent with the rest of ATLAS.
"""

from __future__ import annotations

from typing import Any


def run(router: Any, prompt: str) -> str:
    return router._spotify_request(prompt)
