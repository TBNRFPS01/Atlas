"""Provider monitor for ATLAS LM Studio and OpenRouter endpoints."""

from __future__ import annotations

import threading
import time
from typing import Any


class ProviderMonitor:
    """Monitor and manage LLM provider availability."""

    def __init__(self, check_interval: float = 60.0) -> None:
        self.check_interval = check_interval
        self._running = False
        self._thread: threading.Thread | None = None
        self._providers: dict[str, Any] = {}
        self._status: dict[str, bool] = {}

    def register_provider(self, name: str, provider: Any) -> None:
        """Register a provider for monitoring."""
        self._providers[name] = provider
        self._status[name] = True

    def start(self) -> None:
        """Start the provider monitoring loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _monitor_loop(self) -> None:
        """Check provider health at regular intervals."""
        while self._running:
            for name, provider in self._providers.items():
                try:
                    healthy = self._check_provider(provider)
                    self._status[name] = healthy
                except Exception:
                    self._status[name] = False
            time.sleep(self.check_interval)

    def _check_provider(self, provider: Any) -> bool:
        """Check if a provider is responding."""
        if hasattr(provider, "is_available"):
            return provider.is_available()
        if hasattr(provider, "client"):
            try:
                provider.client.models.list()
                return True
            except Exception:
                return False
        return True

    def is_available(self, name: str) -> bool:
        """Check if a specific provider is available."""
        return self._status.get(name, False)

    def get_available_providers(self) -> list[str]:
        """Return a list of available provider names."""
        return [name for name, available in self._status.items() if available]

    def get_status(self) -> dict[str, bool]:
        """Return the current status of all providers."""
        return dict(self._status)