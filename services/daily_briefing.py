"""Daily briefing service for ATLAS."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any

from core.router import Router
from memory.facts import FactStore


class DailyBriefingService:
    """Generate and deliver a daily briefing at startup or scheduled time."""

    def __init__(
        self,
        router: Router | None = None,
        memory: FactStore | None = None,
        run_at_startup: bool = True,
        briefing_hour: int = 9,
    ) -> None:
        self.router = router or Router()
        self.memory = memory or FactStore()
        self.run_at_startup = run_at_startup
        self.briefing_hour = briefing_hour
        self._running = False
        self._thread: threading.Thread | None = None
        self._delivered_today = False

    def start(self) -> None:
        """Start the briefing scheduler."""
        if self._running:
            return
        self._running = True
        if self.run_at_startup:
            threading.Thread(target=self._deliver_briefing, daemon=True).start()
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _scheduler_loop(self) -> None:
        """Check daily if briefing should be delivered."""
        while self._running:
            now = datetime.now()
            if now.hour == self.briefing_hour and not self._delivered_today:
                self._deliver_briefing()
                self._delivered_today = True
            elif now.hour != self.briefing_hour:
                self._delivered_today = False
            time.sleep(60)

    def _deliver_briefing(self) -> None:
        """Generate and speak the daily briefing."""
        try:
            self.memory.db.consolidate_memories()

            recent = self.memory.recent(limit=20)
            facts = [m.content for m in recent if m.category == "fact"]
            tasks = [m.content for m in recent if m.category == "task"]
            events = [m.content for m in recent if m.category == "event"]
            goals = [m.content for m in recent if m.category == "goal"]

            context = self._build_context(facts, tasks, events, goals)
            prompt = (
                "Generate a concise, friendly daily briefing for the user. "
                "Include: key facts they've shared, pending tasks, upcoming events, and goals. "
                "Keep it under 3 sentences. Be natural and conversational.\n\n"
                f"Context:\n{context}"
            )

            briefing = self.router.brain.ask(prompt)
            if briefing and not briefing.startswith("LM Studio"):
                print(f"\nATLAS (daily briefing): {briefing}\n")
                voice = getattr(self.router, "_voice_controller", None)
                if voice is not None and getattr(voice, "enabled", False):
                    try:
                        voice.speaker.speak(briefing)
                    except Exception:
                        pass
        except Exception:
            pass

    def _build_context(
        self, facts: list[str], tasks: list[str], events: list[str], goals: list[str]
    ) -> str:
        parts = []
        if facts:
            parts.append("Facts: " + "; ".join(facts[:5]))
        if tasks:
            parts.append("Tasks: " + "; ".join(tasks[:5]))
        if events:
            parts.append("Events: " + "; ".join(events[:5]))
        if goals:
            parts.append("Goals: " + "; ".join(goals[:5]))
        return "\n".join(parts) if parts else "No recent memories."

    def trigger_now(self) -> None:
        """Manually trigger a briefing delivery."""
        self._deliver_briefing()