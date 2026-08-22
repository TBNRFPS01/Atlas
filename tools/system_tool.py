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

    @staticmethod
    def _normalized_name(value: str) -> str:
        value = Path(value).stem.lower().strip()
        return "".join(ch for ch in value if ch.isalnum())

    @classmethod
    def _path_matches_name(cls, path: str, requested: str) -> bool:
        stem = cls._normalized_name(Path(path).name)
        target = cls._normalized_name(requested)
        if not stem or not target:
            return False
        # Never accept an unrelated executable merely because a Windows PATH
        # lookup returned it. Exact or prefix matches are required.
        return stem == target or stem.startswith(target) or target.startswith(stem)

    def _find_application(self, name: str) -> str:
        """Find an application using verified executable identity and Windows metadata."""
        name = name.strip()
        if not name:
            return "Application name required"
        name_lower = name.lower()
        results: list[str] = []

        path_result = shutil.which(name)
        if path_result and self._path_matches_name(path_result, name):
            results.append(f"Found in PATH: {path_result}")

        if platform.system() == "Windows":
            self._find_windows_registry(name_lower, results)
            self._find_windows_common_locations(name_lower, results)

        elif platform.system() == "Linux":
            for base_dir in ["/usr/bin", "/usr/local/bin", "/opt", "/snap/bin", "/var/lib/flatpak/exports/bin"]:
                if os.path.exists(base_dir):
                    self._collect_executables(base_dir, name_lower, results, limit=5, executable_only=True, max_depth=3)
        elif platform.system() == "Darwin":
            for base_dir in ["/Applications", "/Applications/Utilities", "/usr/local/bin", "/opt/homebrew/bin"]:
                if os.path.exists(base_dir):
                    self._collect_executables(base_dir, name_lower, results, limit=5, max_depth=3)

        unique: list[str] = []
        seen: set[str] = set()
        for result in results:
            if result not in seen:
                seen.add(result)
                unique.append(result)
        return "\n".join(unique[:10]) if unique else f"Application '{name}' not found"

    def _find_windows_registry(self, name_lower: str, results: list[str]) -> None:
        try:
            import winreg
        except ImportError:
            return
        registry_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]
        for reg_path in registry_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                    count = winreg.QueryInfoKey(key)[0]
                    for i in range(count):
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
                                    self._collect_executables(install_location, name_lower, results, limit=5, max_depth=3)
                                # DisplayIcon is often the most precise executable
                                # location for desktop applications.
                                try:
                                    display_icon = str(winreg.QueryValueEx(subkey, "DisplayIcon")[0] or "")
                                    icon_path = display_icon.split(",", 1)[0].strip().strip('"')
                                    if os.path.isfile(icon_path) and self._path_matches_name(icon_path, name_lower):
                                        results.append(f"Found in registry: {icon_path}")
                                except OSError:
                                    pass
                        except (FileNotFoundError, OSError):
                            continue
            except (FileNotFoundError, OSError):
                continue

    def _find_windows_common_locations(self, name_lower: str, results: list[str]) -> None:
        local = os.environ.get("LOCALAPPDATA", "")
        roaming = os.environ.get("APPDATA", "")
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        common = [
            program_files,
            program_files_x86,
            local,
            os.path.join(local, "Programs"),
            roaming,
        ]
        for base_dir in common:
            if base_dir and os.path.isdir(base_dir):
                self._collect_executables(base_dir, name_lower, results, limit=5, max_depth=3)
                if len(results) >= 5:
                    return

    @classmethod
    def _collect_executables(
        cls,
        base_dir: str,
        needle: str,
        results: list[str],
        limit: int = 5,
        executable_only: bool = False,
        max_depth: int = 3,
    ) -> None:
        if len(results) >= limit:
            return
        target = cls._normalized_name(needle)
        root_base = Path(base_dir)
        try:
            for root, dirs, files in os.walk(base_dir):
                try:
                    depth = len(Path(root).relative_to(root_base).parts)
                except ValueError:
                    depth = max_depth + 1
                if depth >= max_depth:
                    dirs[:] = []
                dirs[:] = [d for d in dirs if d.lower() not in {"node_modules", ".git", "cache", "caches", "temp", "tmp"}]
                for file in files:
                    full_path = os.path.join(root, file)
                    if platform.system() == "Windows" and not file.lower().endswith(".exe"):
                        continue
                    if executable_only and not os.access(full_path, os.X_OK):
                        continue
                    if not cls._path_matches_name(full_path, target):
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
            if line.lower().startswith("found ") and ": " in line:
                path = line.split(": ", 1)[1].strip().strip('"')
                if self._path_matches_name(path, name):
                    return self._launch_application_path(name, path, arguments)
        return f"Could not determine a verified executable path for '{name}'"

    def _launch_application_path(self, name: str, path: str, arguments: str = "") -> str:
        if not path:
            return f"Application path required for '{name}'"
        path_obj = Path(path).expanduser()
        if not path_obj.is_file():
            return f"Cached application path is no longer valid: {path_obj}"
        if not self._path_matches_name(str(path_obj), name):
            return f"Refused to launch unrelated executable '{path_obj}' for '{name}'"
        try:
            cmd = [str(path_obj)] + arguments.split() if arguments else [str(path_obj)]
            subprocess.Popen(cmd, start_new_session=True)
            return f"Launched '{name}' ({path_obj})"
        except Exception as exc:
            return f"Failed to launch '{name}': {exc}"
