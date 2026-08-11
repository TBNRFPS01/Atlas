"""Offline microphone recording helpers for ATLAS voice input.

The microphone wrapper keeps the recording logic isolated from the
listener/controller so the voice subsystem remains modular.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from voice.config import RECORD_SECONDS, SAMPLE_RATE

try:
    import sounddevice
except Exception:  # pragma: no cover - optional runtime dependency
    sounddevice = None


class Microphone:
    """Record raw audio from the default input device."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        record_seconds: int = RECORD_SECONDS,
        channels: int = 1,
    ) -> None:
        self.sample_rate = sample_rate
        self.record_seconds = record_seconds
        self.channels = channels

    def record(self) -> np.ndarray | None:
        """Capture microphone audio for a configured duration."""
        if sounddevice is None:
            print("Voice: Warning - sounddevice is not available; microphone input disabled.")
            return None

        try:
            frames = int(self.sample_rate * self.record_seconds)
            recording = sounddevice.rec(
                frames=frames,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
            )
            sounddevice.wait()
            return np.asarray(recording, dtype=np.float32)
        except Exception as exc:  # pragma: no cover - runtime dependency issue
            print(f"Voice: Warning - microphone recording failed: {exc}")
            return None

    def record_raw(self) -> Any | None:
        """Return the raw microphone capture object if available."""
        if sounddevice is None:
            return None

        try:
            frames = int(self.sample_rate * self.record_seconds)
            recording = sounddevice.rec(
                frames=frames,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
            )
            sounddevice.wait()
            return recording
        except Exception as exc:  # pragma: no cover - runtime dependency issue
            print(f"Voice: Warning - microphone recording failed: {exc}")
            return None
