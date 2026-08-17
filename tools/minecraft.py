"""Minecraft tool for ATLAS.

Reports whether the game is running locally and optionally queries a
Minecraft server's status (online state, version, player count) through
the public mcsrvstat.us JSON API.
"""

from __future__ import annotations

import json
import re
import urllib.request
from urllib.error import URLError

from tools.base import Tool, ToolMetadata, ToolParameter

_PROCESS_HINTS = ("minecraft", "javaw.exe", "java.exe")


class MinecraftTool(Tool):
    """Check Minecraft server status and whether the game is running locally."""

    name = "minecraft"
    description = "Check whether Minecraft is running locally and query the status of a Minecraft server."
    metadata = ToolMetadata(category="gaming", permission_level="basic", confirmation_required=False, description=description)

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform: status (process + optional server), process",
                required=False,
                enum=["status", "process"],
            ),
            ToolParameter(
                name="server",
                type="string",
                description="Minecraft server address to query, e.g. play.example.com or host:25565",
                required=False,
            ),
        ]

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.get("action") or "status"
        server = kwargs.get("server") or (args[0] if args else "")
        if action == "process":
            return self.check_process()
        return self.status(server)

    def status(self, server: str = "") -> str:
        """Return local process status, plus server status when an address is given."""
        lines = [self.check_process()]
        server = (server or "").strip().lower()
        if server and re.match(r"^[a-z0-9.-]+(?::\d{1,5})?$", server):
            lines.append(self.query_server(server))
        elif server:
            lines.append(f"Invalid server address: {server}")
        return "\n".join(lines)

    @staticmethod
    def check_process() -> str:
        """Report whether any Minecraft or Java process is currently running."""
        try:
            import psutil
        except Exception:
            return "Minecraft process check unavailable (psutil not installed)."

        try:
            for proc in psutil.process_iter(["name"]):
                name = (proc.info["name"] or "").lower()
                if any(hint in name for hint in _PROCESS_HINTS):
                    return "Minecraft is running locally."
            return "Minecraft is not running locally."
        except Exception as exc:
            return f"Minecraft process check failed: {exc}"

    @staticmethod
    def query_server(address: str) -> str:
        """Query a Minecraft server's status through the mcsrvstat.us API."""
        hostname, _, port = address.partition(":")
        if not hostname:
            return f"Invalid server address: {address}"
        port = port or "25565"
        url = f"https://api.mcsrvstat.us/3/{hostname}:{port}"
        try:
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            return f"Failed to query server '{hostname}:{port}': {exc}"

        if not data.get("online"):
            return f"Server '{hostname}:{port}' is offline."

        players = data.get("players") or {}
        online = players.get("online", 0)
        maximum = players.get("max", 0)
        version = data.get("version") or "unknown"
        motd = " ".join((data.get("motd") or {}).get("clean") or [])

        lines = [f"Server '{hostname}:{port}' is online.", f"  Version: {version}", f"  Players: {online}/{maximum}"]
        if motd:
            lines.append(f"  MotD: {motd}")
        return "\n".join(lines)


def minecraft_status() -> str:
    """Legacy convenience entrypoint returning a plain-text status report."""
    return MinecraftTool().execute(action="status")