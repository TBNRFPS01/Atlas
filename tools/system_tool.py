from __future__ import annotations

import platform
import socket
import time
import subprocess
import os
import shutil
import winreg
from datetime import datetime
from pathlib import Path

from tools.base import Tool, ToolMetadata, ToolParameter


class SystemTool(Tool):
    """System information tool for ATLAS."""

    name = "system"
    description = "Collect hardware and system information, get time/date, find and launch applications."
    metadata = ToolMetadata(category="system", permission_level="basic", confirmation_required=False, description=description)

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform: info, get_time, get_date, find_application, launch_application",
                required=True,
                enum=["info", "get_time", "get_date", "find_application", "launch_application"],
            ),
            ToolParameter(
                name="application_name",
                type="string",
                description="Name of the application to find or launch",
                required=False,
            ),
            ToolParameter(
                name="arguments",
                type="string",
                description="Command line arguments for launching application",
                required=False,
            ),
        ]

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.get("action", "info")
        
        if action == "info":
            return self._get_system_info()
        elif action == "get_time":
            return self._get_time()
        elif action == "get_date":
            return self._get_date()
        elif action == "find_application":
            app_name = kwargs.get("application_name", "")
            if not app_name:
                return "Application name required for find_application"
            return self._find_application(app_name)
        elif action == "launch_application":
            app_name = kwargs.get("application_name", "")
            if not app_name:
                return "Application name required for launch_application"
            arguments = kwargs.get("arguments", "")
            return self._launch_application(app_name, arguments)
        else:
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
        now = datetime.now()
        return now.strftime("%H:%M:%S")

    def _get_date(self) -> str:
        now = datetime.now()
        return now.strftime("%Y-%m-%d (%A)")

    def _find_application(self, name: str) -> str:
        """Find an application by name using various platform-specific methods."""
        name_lower = name.lower()
        results = []
        
        # Method 1: Check PATH
        path_result = shutil.which(name)
        if path_result:
            results.append(f"Found in PATH: {path_result}")
        
        # Method 2: Check common Windows locations
        if platform.system() == "Windows":
            # Check registry for installed applications
            try:
                registry_paths = [
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                ]
                for reg_path in registry_paths:
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                            for i in range(winreg.QueryInfoKey(key)[0]):
                                subkey_name = winreg.EnumKey(key, i)
                                with winreg.OpenKey(key, subkey_name) as subkey:
                                    try:
                                        display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                        if name_lower in display_name.lower():
                                            install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0] if "InstallLocation" in [winreg.EnumValue(subkey, j)[0] for j in range(winreg.QueryInfoKey(subkey)[1])] else ""
                                            if install_location:
                                                # Look for executable in install location
                                                for ext in [".exe", ""]:
                                                    for root, dirs, files in os.walk(install_location):
                                                        for file in files:
                                                            if name_lower in file.lower() and file.endswith(".exe"):
                                                                full_path = os.path.join(root, file)
                                                                results.append(f"Found in registry: {full_path}")
                                                                break
                                    except (FileNotFoundError, OSError):
                                        continue
                    except (FileNotFoundError, OSError):
                        continue
            except Exception:
                pass
            
            # Common installation directories
            common_dirs = [
                os.environ.get("ProgramFiles", "C:\\Program Files"),
                os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
                os.environ.get("LOCALAPPDATA", ""),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
            ]
            for base_dir in common_dirs:
                if base_dir and os.path.exists(base_dir):
                    for root, dirs, files in os.walk(base_dir):
                        for file in files:
                            if name_lower in file.lower() and file.endswith(".exe"):
                                full_path = os.path.join(root, file)
                                results.append(f"Found in {base_dir}: {full_path}")
        
        # Method 3: Check Linux common locations
        elif platform.system() == "Linux":
            common_dirs = ["/usr/bin", "/usr/local/bin", "/opt", "/snap/bin", "/var/lib/flatpak/exports/bin"]
            for base_dir in common_dirs:
                if os.path.exists(base_dir):
                    for root, dirs, files in os.walk(base_dir):
                        for file in files:
                            if name_lower in file.lower():
                                full_path = os.path.join(root, file)
                                if os.access(full_path, os.X_OK):
                                    results.append(f"Found in {base_dir}: {full_path}")
        
        # Method 4: Check macOS
        elif platform.system() == "Darwin":
            common_dirs = ["/Applications", "/Applications/Utilities", "/usr/local/bin", "/opt/homebrew/bin"]
            for base_dir in common_dirs:
                if os.path.exists(base_dir):
                    for root, dirs, files in os.walk(base_dir):
                        for file in files:
                            if name_lower in file.lower():
                                full_path = os.path.join(root, file)
                                results.append(f"Found in {base_dir}: {full_path}")
        
        if results:
            # Remove duplicates while preserving order
            seen = set()
            unique_results = []
            for r in results:
                if r not in seen:
                    seen.add(r)
                    unique_results.append(r)
            return "\n".join(unique_results[:10])  # Limit to 10 results
        else:
            return f"Application '{name}' not found"

    def _launch_application(self, name: str, arguments: str = "") -> str:
        """Launch an application by name."""
        # First find the application
        find_result = self._find_application(name)
        if "not found" in find_result.lower():
            return f"Cannot launch: {find_result}"
        
        # Extract the first path found
        lines = find_result.split("\n")
        app_path = None
        for line in lines:
            if ":" in line:
                # Get the path after the last colon
                app_path = line.split(":")[-1].strip()
                break
        
        if not app_path:
            return f"Could not determine path for '{name}'"
        
        try:
            if arguments:
                cmd = [app_path] + arguments.split()
            else:
                cmd = [app_path]
            
            # Use subprocess.Popen to launch without waiting
            subprocess.Popen(cmd, start_new_session=True)
            return f"Launched '{name}' ({app_path})"
        except Exception as e:
            return f"Failed to launch '{name}': {e}"
