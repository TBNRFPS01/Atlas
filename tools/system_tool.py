from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

from tools.base import Tool, ToolMetadata, ToolParameter


class SystemTool(Tool):
    """System information and verified application discovery/launch tool."""

    name = "system"
    description = "Collect hardware and system information, get time/date, find and launch applications."
    metadata = ToolMetadata(category="system", permission_level="basic", confirmation_required=False, description=description)

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="action", type="string", description="Action to perform", required=True,
                          enum=["info", "get_time", "get_date", "find_application", "launch_application", "launch_application_path"]),
            ToolParameter(name="application_name", type="string", description="Name of application", required=False),
            ToolParameter(name="application_path", type="string", description="Verified executable path", required=False),
            ToolParameter(name="arguments", type="string", description="Command line arguments", required=False),
        ]

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.get("action", "info")
        if action == "info":
            return self._get_system_info()
        if action == "get_time":
            return self._get_time()
        if action == "get_date":
            return self._get_date()
        if action == "find_application":
            name = kwargs.get("application_name", "")
            return self._find_application(name) if name else "Application name required for find_application"
        if action == "launch_application":
            name = kwargs.get("application_name", "")
            return self._launch_application(name, kwargs.get("arguments", "")) if name else "Application name required for launch_application"
        if action == "launch_application_path":
            return self._launch_application_path(
                kwargs.get("application_name", "application"),
                kwargs.get("application_path", ""),
                kwargs.get("arguments", ""),
            )
        return f"Unknown action: {action}"

    def _get_system_info(self) -> str:
        return (
            f"Platform: {platform.platform()}\n"
            f"System: {platform.system()}\n"
            f"Release: {platform.release()}\n"
            f"Hostname: {socket.gethostname()}\n"
            f"Python: {platform.python_version()}\n"
            f"Uptime: {time.time():.0f}"
        )

    def _get_time(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _get_date(self) -> str:
        return datetime.now().strftime("%Y-%m-%d (%A)")

    def _find_application(self, name: str) -> str:
        """Find an application using PATH, installed-app metadata, and common locations."""
        name_lower = name.lower().strip()
        if not name_lower:
            return "Application name required"
        results: list[str] = []

        path_result = shutil.which(name)
        if path_result:
            results.append(f"Found in PATH: {path_result}")

        if platform.system() == "Windows":
            try:
                import winreg
            except ImportError:
                winreg = None
            if winreg is not None:
                registry_paths = [
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                ]
                for reg_path in registry_paths:
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                            for i in range(winreg.QueryInfoKey(key)[0]):
                                try:
                                    subkey_name = winreg.EnumKey(key, i)
                                    with winreg.OpenKey(key, subkey_name) as subkey:
                                        display_name = str(winreg.QueryValueEx(subkey, "DisplayName")[0])
                                        if name_lower not in display_name.lower():
                                            continue
                                        try:
                                            install_location = str(winreg.QueryValueEx(subkey, "InstallLocation")[0] or "")
                                        except OSError:
                                            install_location = ""
                                        if install_location and os.path.isdir(install_location):
                                            self._collect_executables(install_location, name_lower, results, limit=5)
                                except (FileNotFoundError, OSError):
                                    continue
                    except (FileNotFoundError, OSError):
                        continue

            common_dirs = [
                os.environ.get("ProgramFiles", r"C:\Program Files"),
                os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                os.environ.get("LOCALAPPDATA", ""),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
            ]
            for base_dir in common_dirs:
                if base_dir and os.path.exists(base_dir):
                    self._collect_executables(base_dir, name_lower, results, limit=5)

        elif platform.system() == "Linux":
            for base_dir in ["/usr/bin", "/usr/local/bin", "/opt", "/snap/bin", "/var/lib/flatpak/exports/bin"]:
                if os.path.exists(base_dir):
                    self._collect_executables(base_dir, name_lower, results, limit=5, executable_only=True)
        elif platform.system() == "Darwin":
            for base_dir in ["/Applications", "/Applications/Utilities", "/usr/local/bin", "/opt/homebrew/bin"]:
                if os.path.exists(base_dir):
                    self._collect_executables(base_dir, name_lower, results, limit=5)

        unique: list[str] = []
        seen: set[str] = set()
        for result in results:
            if result not in seen:
                seen.add(result)
                unique.append(result)
        return "\n".join(unique[:10]) if unique else f"Application '{name}' not found"

    @staticmethod
    def _collect_executables(base_dir: str, needle: str, results: list[str], limit: int = 5, executable_only: bool = False) -> None:
        if len(results) >= limit:
            return
        try:
            for root, dirs, files in os.walk(base_dir):
                dirs[:] = [d for d in dirs if d.lower() not in {"node_modules", ".git", "cache", "caches"}]
                for file in files:
                    if needle not in file.lower():
                        continue
                    full_path = os.path.join(root, file)
                    if platform.system() == "Windows" and not file.lower().endswith(".exe"):
                        continue
                    if executable_only and not os.access(full_path, os.X_OK):
                        continue
                    results.append(f"Found in {base_dir}: {full_path}")
                    if len(results) >= limit:
                        return
        except (OSError, PermissionError):
            return

    def _launch_application(self, name: str, arguments: str = "") -> str:
        find_result = self._find_application(name)
        if "not found" in find_result.lower():
            return f"Cannot launch: {find_result}"
        for line in find_result.splitlines():
            if line.lower().startswith("found "):
                # Everything after the first ": " separator is the path;
                # preserve the drive colon in C:\... paths.
                marker = ": "
                if marker in line:
                    path = line.split(marker, 1)[1].strip()
                    return self._launch_application_path(name, path, arguments)
        return f"Could not determine path for '{name}'"

    def _launch_application_path(self, name: str, path: str, arguments: str = "") -> str:
        if not path:
            return f"Application path required for '{name}'"
        path_obj = Path(path).expanduser()
        if not path_obj.is_file():
            return f"Cached application path is no longer valid: {path_obj}"
        try:
            cmd = [str(path_obj)] + arguments.split() if arguments else [str(path_obj)]
            subprocess.Popen(cmd, start_new_session=True)
            return f"Launched '{name}' ({path_obj})"
        except Exception as exc:
            return f"Failed to launch '{name}': {exc}"
