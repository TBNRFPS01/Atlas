"""Text-to-speech speaker for ATLAS.

By default the speaker uses edge-tts, which provides high-quality neural
voices (Microsoft Edge). If edge-tts is unavailable (e.g. offline mode) it
falls back to the local pyttsx3 engine, and if neither is available it
degrades silently. Speech is queued in a background worker thread so it never
blocks the main assistant loop.
"""

from __future__ import annotations

import queue
import threading
from typing import Any

from voice.config import TTS_ENGINE, TTS_VOICE, VOICE_RATE, VOICE_VOLUME

try:
    import numpy as np
except Exception:  # pragma: no cover - optional runtime dependency
    np = None

try:
    import edge_tts
except Exception:  # pragma: no cover - optional runtime dependency
    edge_tts = None

try:
    import miniaudio
except Exception:  # pragma: no cover - optional runtime dependency
    miniaudio = None

try:
    import sounddevice
except Exception:  # pragma: no cover - optional runtime dependency
    sounddevice = None

try:
    import pyttsx3
except Exception:  # pragma: no cover - optional runtime dependency
    pyttsx3 = None

try:
    from piper import PiperVoice
except Exception:  # pragma: no cover - optional runtime dependency
    PiperVoice = None


class Speaker:
    """Queue speech requests and speak them from a background worker thread."""

    def __init__(
        self,
        rate: int = VOICE_RATE,
        volume: float = VOICE_VOLUME,
        engine: str = TTS_ENGINE,
        voice: str = TTS_VOICE,
    ) -> None:
        self.rate = rate
        self.volume = max(0.0, min(1.0, volume))
        self.engine = engine
        self.voice = voice
        self._queue: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()
        self._engine: Any | None = None
        self._piper_voice: Any | None = None
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def _speak_edge(self, text: str) -> bool:
        """Synthesize with edge-tts neural voices and play the result."""
        if edge_tts is None or miniaudio is None or sounddevice is None or np is None:
            return False

        rate_pct = max(-100, min(100, int((self.rate - 180) / 2)))
        volume_pct = max(0, min(100, int((self.volume - 1.0) * 100)))

        import asyncio
        import os
        import tempfile

        path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as handle:
                path = handle.name

            async def _generate() -> None:
                communicate = edge_tts.Communicate(
                    text,
                    voice=self.voice,
                    rate=f"{rate_pct:+d}%",
                    volume=f"{volume_pct:+d}%",
                )
                await communicate.save(path)

            asyncio.run(_generate())

            decoded = miniaudio.decode_file(
                path,
                output_format=miniaudio.SampleFormat.FLOAT32,
            )
            samples = np.reshape(
                decoded.samples, (decoded.nchannels, -1), order="F"
            )
            sounddevice.play(samples, samplerate=decoded.sample_rate)
            sounddevice.wait()
            return True
        except Exception as exc:
            print(f"Voice: Warning - edge-tts speech failed ({exc}); falling back.")
            return False
        finally:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def _speak_piper(self, text: str) -> bool:
        """Synthesize with Piper offline neural TTS and play the result."""
        if PiperVoice is None or sounddevice is None or np is None:
            return False

        import os
        import tempfile

        path: str | None = None
        try:
            if self._piper_voice is None:
                # Voice format: "en_US-lessac-medium" or path to .onnx file
                self._piper_voice = PiperVoice.load(self.voice)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                path = handle.name

            self._piper_voice.synthesize(text, path)
            decoded = miniaudio.decode_file(
                path,
                output_format=miniaudio.SampleFormat.FLOAT32,
            )
            samples = np.reshape(
                decoded.samples, (decoded.nchannels, -1), order="F"
            )
            sounddevice.play(samples, samplerate=decoded.sample_rate)
            sounddevice.wait()
            return True
        except Exception as exc:
            print(f"Voice: Warning - Piper speech failed ({exc}); falling back.")
            return False
        finally:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def _ensure_engine(self) -> Any | None:
        """Create the pyttsx3 engine lazily on first use (fallback backend)."""
        if pyttsx3 is None:
            print("Voice: Warning - no TTS backend available; speech disabled.")
            return None

        if self._engine is None:
            try:
                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", self.rate)
                self._engine.setProperty("volume", self.volume)
            except Exception as exc:
                print(f"Voice: Warning - speaker initialization failed: {exc}")
                self._engine = None
        return self._engine

    def _worker_loop(self) -> None:
        """Consume queued speech requests in a background thread."""
        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            self._speak_sync(text)
            self._queue.task_done()

    def _speak_sync(self, text: str) -> None:
        """Speak one text payload on the worker thread."""
        if not text.strip():
            return

        # Priority: piper (offline neural) > edge-tts (online neural) > pyttsx3 (local)
        if self.engine == "piper" and self._speak_piper(text):
            return
        if self.engine == "edge" and self._speak_edge(text):
            return
        if self.engine == "pyttsx3":
            engine = self._ensure_engine()
            if engine is not None:
                try:
                    engine.setProperty("rate", self.rate)
                    engine.setProperty("volume", self.volume)
                    engine.say(text)
                    engine.runAndWait()
                except Exception as exc:
                    print(f"Voice: Warning - speech playback failed: {exc}")
            return

        # Fallback chain if requested engine fails
        if self._speak_piper(text):
            return
        if self._speak_edge(text):
            return
        engine = self._ensure_engine()
        if engine is not None:
            try:
                engine.setProperty("rate", self.rate)
                engine.setProperty("volume", self.volume)
                engine.say(text)
                engine.runAndWait()
            except Exception as exc:
                print(f"Voice: Warning - speech playback failed: {exc}")

    def speak(self, text: str) -> None:
        """Queue a response for spoken playback without blocking the caller."""
        if not text.strip():
            return
        self._queue.put(text)

    def stop(self) -> None:
        """Stop the speaker thread and shut down the engine cleanly."""
        self._stop_event.set()
        engine = self._ensure_engine()
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass

    def set_rate(self, rate: int) -> None:
        """Adjust the speech rate used for future utterances."""
        self.rate = rate
        engine = self._ensure_engine()
        if engine is not None:
            try:
                engine.setProperty("rate", self.rate)
            except Exception:
                pass

    def set_volume(self, volume: float) -> None:
        """Adjust the speech volume used for future utterances."""
        self.volume = max(0.0, min(1.0, volume))
        engine = self._ensure_engine()
        if engine is not None:
            try:
                engine.setProperty("volume", self.volume)
            except Exception:
                pass