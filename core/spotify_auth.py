"""Spotify OAuth configuration and token management for ATLAS."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class SpotifyConfig:
    """Spotify API configuration loaded from config.json or environment."""

    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8888/callback"
    scopes: tuple[str, ...] = (
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        "user-read-recently-played",
        "playlist-read-private",
        "playlist-read-collaborative",
    )

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "SpotifyConfig":
        return cls(
            client_id=config.get("spotify_client_id", ""),
            client_secret=config.get("spotify_client_secret", ""),
            redirect_uri=config.get("spotify_redirect_uri", "http://localhost:8888/callback"),
        )


@dataclass
class SpotifyToken:
    """OAuth token with expiry tracking."""

    access_token: str = ""
    refresh_token: str = ""
    expires_at: float = 0.0  # Unix timestamp
    token_type: str = "Bearer"
    scope: str = ""

    def is_expired(self, buffer_seconds: int = 30) -> bool:
        return time.time() >= (self.expires_at - buffer_seconds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "token_type": self.token_type,
            "scope": self.scope,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpotifyToken":
        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", ""),
            expires_at=data.get("expires_at", 0.0),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope", ""),
        )


class SpotifyAuth:
    """Manages Spotify OAuth flow and token persistence."""

    TOKEN_FILE = Path.home() / ".atlas" / "spotify_token.json"
    AUTH_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"

    def __init__(self, config: SpotifyConfig) -> None:
        self.config = config
        self._token: Optional[SpotifyToken] = None
        self.TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

    def load_token(self) -> bool:
        """Load saved token from disk."""
        if not self.TOKEN_FILE.exists():
            return False
        try:
            data = json.loads(self.TOKEN_FILE.read_text(encoding="utf-8"))
            self._token = SpotifyToken.from_dict(data)
            return True
        except Exception:
            return False

    def save_token(self) -> None:
        """Persist current token to disk."""
        if self._token:
            self.TOKEN_FILE.write_text(
                json.dumps(self._token.to_dict(), indent=2), encoding="utf-8"
            )

    def get_auth_url(self, state: str = "atlas") -> str:
        """Generate the authorization URL for the user to visit."""
        from urllib.parse import quote_plus

        scopes = " ".join(self.config.scopes)
        params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "redirect_uri": self.config.redirect_uri,
            "scope": scopes,
            "state": state,
        }
        query = "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())
        return f"{self.AUTH_URL}?{query}"

    def exchange_code(self, code: str) -> SpotifyToken:
        """Exchange authorization code for access/refresh tokens."""
        import base64
        import requests

        auth_header = base64.b64encode(
            f"{self.config.client_id}:{self.config.client_secret}".encode()
        ).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
        }
        resp = requests.post(self.TOKEN_URL, headers=headers, data=data, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        token = SpotifyToken(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token", ""),
            expires_at=time.time() + payload.get("expires_in", 3600),
            token_type=payload.get("token_type", "Bearer"),
            scope=payload.get("scope", ""),
        )
        self._token = token
        self.save_token()
        return token

    def refresh_access_token(self) -> SpotifyToken:
        """Refresh the access token using the refresh token."""
        import base64
        import requests

        if not self._token or not self._token.refresh_token:
            raise RuntimeError("No refresh token available; re-authenticate.")

        auth_header = base64.b64encode(
            f"{self.config.client_id}:{self.config.client_secret}".encode()
        ).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._token.refresh_token,
        }
        resp = requests.post(self.TOKEN_URL, headers=headers, data=data, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        self._token.access_token = payload["access_token"]
        self._token.expires_at = time.time() + payload.get("expires_in", 3600)
        if "refresh_token" in payload:
            self._token.refresh_token = payload["refresh_token"]
        self.save_token()
        return self._token

    def get_valid_access_token(self) -> str:
        """Return a valid access token, refreshing if necessary."""
        if not self._token:
            self.load_token()
        if not self._token or not self._token.access_token:
            raise RuntimeError("Not authenticated; run /spotify auth first.")
        if self._token.is_expired():
            self.refresh_access_token()
        return self._token.access_token