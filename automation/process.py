"""Process management utilities for ATLAS."""

from __future__ import annotations

import subprocess
from typing import Any

try:
    import psutil
except Exception:  # pragma: no cover - optional runtime dependency
    psutil = None


class Process:
    """Query and manage system processes."""

    def __init__(self) -> None:
        self._enabled = psutil is not None

    def list_running(self) -> list[dict[str, Any]]:
        """Return a list of running processes with basic info."""
        if not self._enabled:
            print("Automation: Warning - psutil not available; process control disabled.")
            return []
        try:
            processes = []
            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    info = proc.info
                    processes.append(
                        {
                            "pid": info["pid"],
                            "name": info["name"],
                            "cpu": info["cpu_percent"],
                            "memory": info["memory_percent"],
                        }
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return processes
        except Exception as exc:
            print(f"Automation: Warning - process list failed: {exc}")
            return []

    def is_running(self, name: str) -> bool:
        """Check if a process with the given name is running."""
        if not self._enabled:
            return False
        try:
            for proc in psutil.process_iter(["name"]):
                if name.lower() in proc.info["name"].lower():
                    return True
            return False
        except Exception:
            return False

    def pid(self, name: str) -> int | None:
        """Return the PID of a process by name, or None if not found."""
        if not self._enabled:
            return None
        try:
            for proc in psutil.process_iter(["pid", "name"]):
                if name.lower() in proc.info["name"].lower():
                    return proc.info["pid"]
            return None
        except Exception:
            return None

    def kill_by_name(self, name: str) -> bool:
        """Terminate a process by name."""
        if not self._enabled:
            return False
        try:
            for proc in psutil.process_iter(["name"]):
                if name.lower() in proc.info["name"].lower():
                    proc.terminate()
                    return True
            return False
        except Exception as exc:
            print(f"Automation: Warning - process kill failed: {exc}")
            return False

    def kill_by_pid(self, pid: int) -> bool:
        """Terminate a process by PID."""
        if not self._enabled:
            return False
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            return True
        except Exception as exc:
            print(f"Automation: Warning - process kill by PID failed: {exc}")
            return False

    def start(self, command: str) -> subprocess.Popen | None:
        """Start a new process with the given command."""
        try:
            return subprocess.Popen(command, shell=True)
        except Exception as exc:
            print(f"Automation: Warning - process start failed: {exc}")
            return None