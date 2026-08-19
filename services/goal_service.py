"""Background autonomous goal service for ATLAS.

Periodically picks the next active goal and advances it a bounded number of
steps. This is the "autonomous" part of ATLAS that runs *without* a user
prompt, so it is deliberately gated:

  * only runs when explicitly enabled (``autonomy_enabled`` in config),
  * advances at most ``max_tasks`` steps per cycle,
  * runs with ``consent="agent"`` so destructive/elevated steps are parked
    for user confirmation instead of auto-approved,
  * respects hard safety boundaries (which can never be bypassed).
"""

from __future__ import annotations

import threading
import time
from typing import Any


class AutonomousGoalService:
    """Threaded background loop that advances active goals safely."""

    def __init__(
        self,
        autonomy: Any | None = None,
        interval_seconds: float = 600.0,
        max_tasks: int = 2,
        enabled: bool = True,
        console: Any | None = None,
    ) -> None:
        self.autonomy = autonomy
        self.interval_seconds = interval_seconds
        self.max_tasks = max(max_tasks, 1)
        self.enabled = enabled
        self.console = console
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _loop(self) -> None:
        while self._running:
            try:
                if self.enabled:
                    self.run_once()
            except Exception:
                pass
            time.sleep(self.interval_seconds)

    def run_once(self) -> Any:
        """Run a single advancement cycle; returns the report or ``None``."""
        if not self.enabled or self.autonomy is None:
            return None
        try:
            report = self.autonomy.pick_and_advance(self.max_tasks, consent="agent")
        except Exception:
            return None
        if report is not None and report.goal_id is not None:
            self._report(report)
        return report

    def _report(self, report: Any) -> None:
        line = (
            f"Autonomy: advanced goal #{report.goal_id} '{report.goal}' -> "
            f"{report.verdict} (score {report.score:.2f})"
        )
        if self.console is not None:
            self.console(line)
        else:
            print(line)