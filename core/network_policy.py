from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class NetworkDecision:
    allowed: bool
    reason: str


class NetworkPolicy:
    """Deterministic URL allow/deny policy for tool-side network access."""

    def __init__(self, allowed_hosts: set[str] | None = None, blocked_hosts: set[str] | None = None) -> None:
        self.allowed_hosts = {h.lower().strip() for h in (allowed_hosts or set())}
        self.blocked_hosts = {h.lower().strip() for h in (blocked_hosts or set())}

    def check(self, url: str) -> NetworkDecision:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return NetworkDecision(False, "Only HTTP(S) URLs with a hostname are permitted")
        host = parsed.hostname.lower().rstrip(".")
        if host in self.blocked_hosts:
            return NetworkDecision(False, "Host is blocked by network policy")
        if self.allowed_hosts and host not in self.allowed_hosts:
            return NetworkDecision(False, "Host is not on the network allowlist")
        return NetworkDecision(True, "allowed")
