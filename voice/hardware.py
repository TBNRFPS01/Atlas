"""Voice hardware diagnostics for ATLAS.

Provides a lightweight capability probe so users can verify that the
microphone, transcription model, and speaker backends are available before
relying on voice input. All checks are best-effort and never raise.
"""

from __future__ import annotations

from typing import Any


def check_voice_hardware() -> dict[str, Any]:
    """Probe the local voice hardware/software stack.

    Returns a dict with boolean capability flags and a ``details`` map that
    records the reason for any missing capability.
    """
    result: dict[str, Any] = {
        "microphone": False,
        "transcription": False,
        "speaker": False,
        "details": {},
    }

    # Microphone input backend (sounddevice / pyaudio).
    for mod in ("sounddevice", "pyaudio"):
        try:
            __import__(mod)
            result["microphone"] = True
            break
        except Exception as exc:  # pragma: no cover - depends on host
            result["details"]["microphone"] = f"missing {mod}: {exc}"

    # Transcription model (faster-whisper + soundfile to write samples).
    try:
        import soundfile  # noqa: F401
        from faster_whisper import WhisperModel  # noqa: F401

        result["transcription"] = True
    except Exception as exc:  # pragma: no cover - depends on host
        result["details"]["transcription"] = f"{exc}"

    # Speaker / TTS backend (pyttsx3 or edge-tts).
    for mod in ("pyttsx3", "edge_tts"):
        try:
            __import__(mod)
            result["speaker"] = True
            break
        except Exception as exc:  # pragma: no cover - depends on host
            result["details"]["speaker"] = f"missing {mod}: {exc}"

    return result


def summarize_voice_hardware() -> str:
    """Return a human-readable voice hardware report."""
    hw = check_voice_hardware()
    lines = ["Voice hardware check:"]
    lines.append(f"  Microphone:   {'OK' if hw['microphone'] else 'UNAVAILABLE'}")
    lines.append(f"  Transcription:{'OK' if hw['transcription'] else 'UNAVAILABLE'}")
    lines.append(f"  Speaker:      {'OK' if hw['speaker'] else 'UNAVAILABLE'}")
    if hw["details"]:
        lines.append("Details:")
        for key, value in hw["details"].items():
            lines.append(f"  - {key}: {value}")
    return "\n".join(lines)
