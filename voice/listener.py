"""Lazy-loading local speech-to-text support for ATLAS.

The listener uses faster-whisper locally and keeps the transcription model
reused after the first successful load. This allows offline speech input
without any cloud dependency.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any

import numpy as np

from voice.config import VOICE_LANGUAGE, WHISPER_MODEL

try:
    import soundfile
except Exception:  # pragma: no cover - optional runtime dependency
    soundfile = None

try:
    from faster_whisper import WhisperModel
except Exception:  # pragma: no cover - optional runtime dependency
    WhisperModel = None


class Listener:
    """Transcribe microphone audio into plain text using faster-whisper."""

    def __init__(
        self,
        model_name: str = WHISPER_MODEL,
        language: str = VOICE_LANGUAGE,
        device: str = "auto",
        compute_type: str = "auto",
        beam_size: int = 5,
        vad_filter: bool = True,
    ) -> None:
        self.model_name = model_name
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self._model: Any | None = None

    def load_model(self) -> Any | None:
        """Lazily load the Whisper model and reuse it on later calls."""
        if WhisperModel is None:
            print("Voice: Warning - faster-whisper is not installed; voice transcription disabled.")
            return None

        if self._model is None:
            try:
                if self.device == "auto":
                    try:
                        import torch  # type: ignore

                        device = "cuda" if torch.cuda.is_available() else "cpu"
                    except Exception:
                        device = "cpu"
                else:
                    device = self.device

                self._model = WhisperModel(self.model_name, device=device, compute_type=self.compute_type)
                print(f"Voice: ✓ Whisper Loaded ({self.model_name} on {device})")
            except Exception as exc:
                print(f"Voice: Warning - Whisper model failed to load: {exc}")
                self._model = None
        return self._model

    def transcribe(self, audio: np.ndarray | None) -> str:
        """Translate recorded audio into plain user text."""
        if audio is None:
            return ""

        model = self.load_model()
        if model is None or soundfile is None:
            return ""

        path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                path = handle.name
            soundfile.write(path, audio, samplerate=16000)

            segments, _ = model.transcribe(
                path,
                language=self.language,
                beam_size=self.beam_size,
                vad_filter=self.vad_filter,
                condition_on_previous_text=False,
            )
            text = " ".join(segment.text.strip() for segment in segments if segment.text)
            return text.strip()
        except Exception as exc:
            print(f"Voice: Warning - transcription failed: {exc}")
            return ""
        finally:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
