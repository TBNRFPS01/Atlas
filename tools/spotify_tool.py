"""Spotify control tool for ATLAS.

Provides playback control, search, and current track info via the Spotify Web API.
Requires OAuth authentication (handled by SpotifyAuth).
"""

from __future__ import annotations

import json
from typing import Any

import requests

from core.spotify_auth import SpotifyAuth, SpotifyConfig
from tools.base import Tool, ToolMetadata, ToolParameter


class SpotifyTool(Tool):
    """Control Spotify playback and query track info."""

    name = "spotify"
    description = "Control Spotify playback, search, and get current track info."
    metadata = ToolMetadata(
        category="media",
        permission_level="basic",
        confirmation_required=False,
        description=description,
    )

    API_BASE = "https://api.spotify.com/v1"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._config = config or {}
        self._spotify_config = SpotifyConfig.from_config(self._config)
        self._auth = SpotifyAuth(self._spotify_config)
        self._auth.load_token()

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description=(
                    "Action: play, pause, next, previous, current, search, "
                    "play_track, play_playlist, devices, volume, auth, auth_code"
                ),
                required=True,
                enum=[
                    "play",
                    "pause",
                    "next",
                    "previous",
                    "current",
                    "search",
                    "play_track",
                    "play_playlist",
                    "devices",
                    "volume",
                    "auth",
                    "auth_code",
                ],
            ),
            ToolParameter(
                name="query",
                type="string",
                description="Search query (track, artist, album) or track/playlist URI",
                required=False,
            ),
            ToolParameter(
                name="device_id",
                type="string",
                description="Target device ID (optional)",
                required=False,
            ),
            ToolParameter(
                name="volume",
                type="integer",
                description="Volume 0-100",
                required=False,
            ),
            ToolParameter(
                name="code",
                type="string",
                description="Authorization code from OAuth callback",
                required=False,
            ),
        ]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._auth.get_valid_access_token()}",
            "Content-Type": "application/json",
        }

    def _request(
        self, method: str, endpoint: str, **kwargs
    ) -> requests.Response:
        url = f"{self.API_BASE}{endpoint}"
        return requests.request(
            method, url, headers=self._headers(), timeout=10, **kwargs
        )

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.get("action") or (args[0] if args else "")
        try:
            if action == "auth":
                return self._handle_auth()
            if action == "auth_code":
                code = kwargs.get("code") or (args[1] if len(args) > 1 else "")
                return self._handle_auth_code(code)
            if action == "current":
                return self._current_track()
            if action == "play":
                return self._play(kwargs)
            if action == "pause":
                return self._pause()
            if action == "next":
                return self._next()
            if action == "previous":
                return self._previous()
            if action == "search":
                query = kwargs.get("query") or " ".join(args[1:])
                return self._search(query)
            if action == "play_track":
                uri = kwargs.get("query") or (args[1] if len(args) > 1 else "")
                return self._play_uri(uri, "track")
            if action == "play_playlist":
                uri = kwargs.get("query") or (args[1] if len(args) > 1 else "")
                return self._play_uri(uri, "context")
            if action == "devices":
                return self._devices()
            if action == "volume":
                vol = kwargs.get("volume")
                if vol is None:
                    return "Volume level (0-100) required."
                return self._set_volume(int(vol))
            return f"Unknown action: {action}"
        except requests.HTTPError as exc:
            return f"Spotify API error: {exc.response.status_code} {exc.response.text}"
        except Exception as exc:
            return f"Spotify error: {exc}"

    def _handle_auth(self) -> str:
        if not self._spotify_config.client_id or not self._spotify_config.client_secret:
            return (
                "Spotify not configured. Set spotify_client_id and "
                "spotify_client_secret in config.json."
            )
        url = self._auth.get_auth_url()
        return (
            "Open this URL in a browser to authorize ATLAS:\n"
            f"{url}\n\n"
            "After authorizing, you will be redirected to a localhost URL. "
            "Copy the 'code' query parameter and run:\n"
            "  /spotify auth_code <code>"
        )

    def _handle_auth_code(self, code: str) -> str:
        if not code:
            return "Usage: /spotify auth_code <code>"
        token = self._auth.exchange_code(code)
        return f"Authenticated! Token expires in ~1 hour. Refresh token saved."

    def _current_track(self) -> str:
        resp = self._request("GET", "/me/player/currently-playing")
        if resp.status_code == 204 or not resp.json():
            return "Nothing playing."
        data = resp.json()
        item = data.get("item", {})
        name = item.get("name", "Unknown")
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        album = item.get("album", {}).get("name", "")
        progress = data.get("progress_ms", 0) // 1000
        duration = item.get("duration_ms", 0) // 1000
        return (
            f"Now playing: {name} — {artists}\n"
            f"Album: {album}\n"
            f"Progress: {progress}s / {duration}s"
        )

    def _play(self, kwargs: dict) -> str:
        uri = kwargs.get("query") or ""
        device_id = kwargs.get("device_id")
        body = {}
        if uri:
            if uri.startswith("spotify:track:"):
                body["uris"] = [uri]
            elif uri.startswith("spotify:playlist:") or uri.startswith("spotify:album:"):
                body["context_uri"] = uri
            else:
                return "Provide a valid Spotify track, playlist, or album URI."
        if device_id:
            body["device_id"] = device_id
        resp = self._request("PUT", "/me/player/play", json=body or None)
        if resp.status_code in (200, 204):
            return "Playback started." + (f" ({uri})" if uri else "")
        return f"Play failed: {resp.status_code} {resp.text}"

    def _pause(self) -> str:
        resp = self._request("PUT", "/me/player/pause")
        return "Paused." if resp.status_code in (200, 204) else f"Pause failed: {resp.status_code}"

    def _next(self) -> str:
        resp = self._request("POST", "/me/player/next")
        return "Skipped to next." if resp.status_code in (200, 204) else f"Next failed: {resp.status_code}"

    def _previous(self) -> str:
        resp = self._request("POST", "/me/player/previous")
        return "Skipped to previous." if resp.status_code in (200, 204) else f"Previous failed: {resp.status_code}"

    def _search(self, query: str) -> str:
        if not query:
            return "Search query required."
        resp = self._request(
            "GET",
            "/search",
            params={"q": query, "type": "track,artist,album,playlist", "limit": 10},
        )
        data = resp.json()
        lines = []
        for track in data.get("tracks", {}).get("items", [])[:5]:
            name = track["name"]
            artists = ", ".join(a["name"] for a in track["artists"])
            uri = track["uri"]
            lines.append(f"  {name} — {artists}  ({uri})")
        for artist in data.get("artists", {}).get("items", [])[:3]:
            lines.append(f"  Artist: {artist['name']}  ({artist['uri']})")
        for album in data.get("albums", {}).get("items", [])[:3]:
            lines.append(f"  Album: {album['name']} — {', '.join(a['name'] for a in album['artists'])}  ({album['uri']})")
        for pl in data.get("playlists", {}).get("items", [])[:3]:
            lines.append(f"  Playlist: {pl['name']}  ({pl['uri']})")
        return "Search results:\n" + "\n".join(lines) if lines else "No results."

    def _play_uri(self, uri: str, type_: str) -> str:
        if not uri:
            return "URI required."
        body = {"uris": [uri]} if type_ == "track" else {"context_uri": uri}
        resp = self._request("PUT", "/me/player/play", json=body)
        return "Playing." if resp.status_code in (200, 204) else f"Play failed: {resp.status_code}"

    def _devices(self) -> str:
        resp = self._request("GET", "/me/player/devices")
        devices = resp.json().get("devices", [])
        if not devices:
            return "No active devices."
        lines = []
        for d in devices:
            status = "ACTIVE" if d.get("is_active") else "idle"
            lines.append(f"  {d['name']} ({d['type']}) — {status}  [{d['id']}]")
        return "Available devices:\n" + "\n".join(lines)

    def _set_volume(self, volume: int) -> str:
        if not 0 <= volume <= 100:
            return "Volume must be 0-100."
        resp = self._request("PUT", f"/me/player/volume?volume_percent={volume}")
        return f"Volume set to {volume}%." if resp.status_code in (200, 204) else f"Volume failed: {resp.status_code}"