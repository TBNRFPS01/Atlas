import numpy as np

from core.router import Router
from voice.controller import VoiceController


def _make(monkeypatch):
    router = Router()
    vc = VoiceController(router)
    vc.enabled = False
    monkeypatch.setattr(vc.microphone, "record", lambda: np.zeros(16000, dtype=np.int16))
    monkeypatch.setattr(vc.listener, "transcribe", lambda audio: "hello world")
    return vc, router


def test_listen_once_returns_transcription(monkeypatch) -> None:
    vc, _ = _make(monkeypatch)
    assert vc.listen_once() == "hello world"


def test_process_text_empty_is_noop(monkeypatch) -> None:
    vc, _ = _make(monkeypatch)
    spoken = []
    monkeypatch.setattr(vc.speaker, "speak", lambda t: spoken.append(t))
    vc.process_text("   ")
    assert spoken == []


def test_process_text_routes_and_speaks(monkeypatch) -> None:
    vc, _ = _make(monkeypatch)
    spoken = []
    monkeypatch.setattr(vc.speaker, "speak", lambda t: spoken.append(t))
    vc.process_text("system info")
    assert spoken  # router produced a reply that was spoken


def test_set_enabled_toggles(monkeypatch) -> None:
    vc, _ = _make(monkeypatch)
    vc.set_enabled(True)
    assert vc.enabled is True
    vc.set_enabled(False)
    assert vc.enabled is False
