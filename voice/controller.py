"""Coordinator for ATLAS offline voice input and output.

The controller owns the microphone, listener, speaker, queue, and worker
thread. It is designed to remain optional and resilient: if the microphone,
Whisper, or speaker backend fails, the assistant keeps running in CLI mode.
"""

from __future__ import annotations

import queue
import threading
import time

from core.router import Router
from voice.config import PUSH_TO_TALK_KEY, RECORD_SECONDS, SAMPLE_RATE, TTS_ENGINE, TTS_VOICE, VOICE_ENABLED, VOICE_LANGUAGE, VOICE_RATE, VOICE_VOLUME, WHISPER_MODEL
from voice.listener import Listener
from voice.microphone import Microphone
from voice.speaker import Speaker

try:
    import ctypes
except Exception:  # pragma: no cover - Windows-only helper
    ctypes = None


class VoiceController:
    """Manage offline voice recognition and spoken responses for ATLAS."""

    def __init__(
        self,
        router: Router,
        speaker: Speaker | None = None,
        listener: Listener | None = None,
        microphone: Microphone | None = None,
        enabled: bool = False,
        whisper_model: str = WHISPER_MODEL,
        tts_engine: str = TTS_ENGINE,
        tts_voice: str = TTS_VOICE,
        device: str = "auto",
        compute_type: str = "auto",
    ) -> None:
        self.router = router
        self.enabled = enabled
        self.speaker = speaker or Speaker(rate=VOICE_RATE, volume=VOICE_VOLUME, engine=tts_engine, voice=tts_voice)
        self.listener = listener or Listener(model_name=whisper_model, language=VOICE_LANGUAGE, device=device, compute_type=compute_type)
        self.microphone = microphone or Microphone(sample_rate=SAMPLE_RATE, record_seconds=RECORD_SECONDS)
        self.queue: queue.Queue[str] = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False
        self._push_to_talk_key = (PUSH_TO_TALK_KEY or "F8").upper()

    def start(self) -> None:
        """Start the background voice worker and log readiness."""
        if not self.enabled:
            return

        self._running = True
        self.listener.load_model()
        self.speaker._ensure_engine()
        print("Voice: ✓ Microphone Ready")
        print("Voice: ✓ Whisper Loaded")
        print("Voice: ✓ Speaker Ready")
        print("Voice: Running")

        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable voice at runtime."""
        self.enabled = enabled
        if enabled and not self._running:
            self.start()
        elif not enabled and self._running:
            self.stop()

    def stop(self) -> None:
        """Stop the background controller and the attached speaker."""
        self._running = False
        self._stop_event.set()
        self.speaker.stop()

    def listen_once(self) -> str:
        """Record one utterance and convert it to text using the listener."""
        audio = self.microphone.record()
        if audio is None:
            return ""
        return self.listener.transcribe(audio)

    def process_text(self, text: str) -> None:
        """Send recognized text to the router and speak the resulting reply."""
        cleaned = text.strip()
        if not cleaned:
            return

        try:
            reply = self.router.route(cleaned)
        except Exception as exc:
            print(f"Voice: Warning - router failed while processing speech: {exc}")
            return

        if reply:
            self.speaker.speak(reply)

    def run_background(self) -> None:
        """Run the push-to-talk voice loop in the background.

        The controller watches for the configured hotkey, records audio while it
        is held, and then routes transcription to the router for a spoken reply.
        """
        while self._running and not self._stop_event.is_set():
            if self._is_push_to_talk_down():
                text = self.listen_once()
                if text:
                    self.queue.put(text)
            time.sleep(0.05)

    def _worker_loop(self) -> None:
        """Dispatch transcribed speech into the router and speaker pipeline."""
        while self._running and not self._stop_event.is_set():
            try:
                text = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue

            self.process_text(text)
            self.queue.task_done()

    def _is_push_to_talk_down(self) -> bool:
        """Check whether the configured push-to-talk hotkey is currently held."""
        if ctypes is None:
            return False
        if not hasattr(ctypes, 'windll'):
            return False  # Not Windows

        key_code = self._get_virtual_key_code(self._push_to_talk_key)
        if key_code is None:
            return False

        try:
            return bool(ctypes.windll.user32.GetAsyncKeyState(key_code) & 0x8000)
        except Exception:
            return False

    def _get_virtual_key_code(self, key_name: str) -> int | None:
        """Map a named hotkey to its Windows virtual-key code."""
        mapping = {
            "F1": 0x70,
            "F2": 0x71,
            "F3": 0x72,
            "F4": 0x73,
            "F5": 0x74,
            "F6": 0x75,
            "F7": 0x76,
            "F8": 0x77,
            "F9": 0x78,
            "F10": 0x79,
            "F11": 0x7A,
            "F12": 0x7B,
        }
        return mapping.get(key_name)
