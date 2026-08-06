from __future__ import annotations

import platform
import socket
import time

from tools.base import Tool, ToolMetadata


class SystemTool(Tool):
    """System information tool for ATLAS."""

    name = "system"
    description = "Collect hardware and system information."
    metadata = ToolMetadata(category="system", permission_level="basic", confirmation_required=False, description=description)

    def execute(self, *args, **kwargs) -> str:
        return (
            f"Platform: {platform.platform()}\n"
            f"System: {platform.system()}\n"
            f"Release: {platform.release()}\n"
            f"Hostname: {socket.gethostname()}\n"
            f"Python: {platform.python_version()}\n"
            f"Uptime: {time.time():.0f}"
        )
