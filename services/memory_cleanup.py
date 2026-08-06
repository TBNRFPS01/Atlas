"""Memory cleanup service for ATLAS."""

from __future__ import annotations

import threading
import time
from typing import Any


class MemoryCleanupService:
    """Periodically clean up old or low-importance memory entries."""

    def __init__(self, interval_seconds: float = 3600.0, max_age_days: int = 30) -> None:
        self.interval_seconds = interval_seconds
        self.max_age_days = max_age_days
        self._running = False
        self._thread: threading.Thread | None = None
        self._db: Any | None = None

    def set_database(self, db: Any) -> None:
        """Set the memory database reference for cleanup operations."""
        self._db = db

    def start(self) -> None:
        """Start the periodic cleanup loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the cleanup loop."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _cleanup_loop(self) -> None:
        """Run cleanup at regular intervals."""
        while self._running:
            try:
                self._perform_cleanup()
            except Exception:
                pass
            time.sleep(self.interval_seconds)

    def _perform_cleanup(self) -> None:
        """Execute the actual memory cleanup logic."""
        if self._db is None:
            return

        try:
            self._db.cleanup_old_memories(self.max_age_days)
        except Exception:
            pass

    def run_once(self) -> int:
        """Run a single cleanup pass and return the number of records removed."""
        if self._db is None:
            return 0
        try:
            return self._db.cleanup_old_memories(self.max_age_days)
        except Exception:
            return 0