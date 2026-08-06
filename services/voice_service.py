"""Voice service for ATLAS background voice processing."""

from __future__ import annotations

import queue
import threading
import time
from typing import Any

from core.router import Router
from voice.config import VOICE_ENABLED, VOICE_RATE, VOICE_VOLUME, WHISPER_MODEL, SAMPLE_RATE, RECORD_SECONDS
from voice.listener import Listener
from voice.microphone import Microphone
from voice.speaker import Speaker


class VoiceService:
    """Background service for continuous voice input and output."""

    def __init__(self, router: Router | None = None) -> None:
        self.router = router or Router()
        self.speaker = Speaker(rate=VOICE_RATE, volume=VOICE_VOLUME)
        self.listener = Listener(model_name=WHISPER_MODEL)
        self.microphone = Microphone(sample_rate=SAMPLE_RATE, record_seconds=RECORD_SECONDS)
        self.queue: queue.Queue[str] = queue.Queue()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the voice service if enabled."""
        if not VOICE_ENABLED:
            return

        self._running = True
        self.listener.load_model()
        self.speaker._ensure_engine()
        print("Voice: ✓ Microphone Ready")
        print("Voice: ✓ Whisper Loaded")
        print("Voice: ✓ Speaker Ready")
        print("Voice: Running")

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the voice service."""
        self._running = False
        self.speaker.stop()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _run_loop(self) -> None:
        """Main voice processing loop."""
        while self._running:
            try:
                text = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue

            self._process_text(text)

    def _process_text(self, text: str) -> None:
        """Route text through the router and speak the response."""
        cleaned = text.strip()
        if not cleaned:
            return

        try:
            reply = self.router.route(cleaned)
            if reply:
                self.speaker.speak(reply)
        except Exception:
            pass

    def enqueue(self, text: str) -> None:
        """Add text to the voice processing queue."""
        self.queue.put(text)

    def listen_once(self) -> str:
        """Record and transcribe a single utterance."""
        audio = self.microphone.record()
        if audio is None:
            return ""
        return self.listener.transcribe(audio)

    def is_running(self) -> bool:
        """Check if the voice service is active."""
        return self._running