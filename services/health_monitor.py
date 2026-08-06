"""Health monitoring service for ATLAS."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable


class HealthMonitor:
    """Monitor the health of ATLAS components and report issues."""

    def __init__(self, check_interval: float = 30.0) -> None:
        self.check_interval = check_interval
        self._running = False
        self._thread: threading.Thread | None = None
        self._checks: dict[str, Callable[[], bool]] = {}
        self._status: dict[str, bool] = {}

    def register_check(self, name: str, check_fn: Callable[[], bool]) -> None:
        """Register a health check function for a component."""
        self._checks[name] = check_fn
        self._status[name] = True

    def start(self) -> None:
        """Start the health monitoring loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the health monitoring loop."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _monitor_loop(self) -> None:
        """Run health checks at regular intervals."""
        while self._running:
            for name, check_fn in self._checks.items():
                try:
                    healthy = check_fn()
                    self._status[name] = healthy
                except Exception:
                    self._status[name] = False
            time.sleep(self.check_interval)

    def is_healthy(self, name: str) -> bool:
        """Check if a specific component is healthy."""
        return self._status.get(name, False)

    def all_healthy(self) -> bool:
        """Check if all registered components are healthy."""
        return all(self._status.values())

    def get_status(self) -> dict[str, bool]:
        """Return the current health status of all components."""
        return dict(self._status)