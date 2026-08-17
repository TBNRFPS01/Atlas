from types import SimpleNamespace

import numpy as np

from core.brain import Brain
from vision.analyzer import VisionAnalyzer


def _ok_response(content: str = "a dog") -> SimpleNamespace:
    choice = SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=None))
    return SimpleNamespace(choices=[choice])


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls = []

    def create(self, *args, **kwargs):
        self.calls.append(kwargs)
        return _ok_response()


class _FakeChat:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()


class _FakeBrain:
    def __init__(self) -> None:
        self.chat = _FakeChat()
        self.captured: list[tuple[bytes, str]] = []

    def analyze_image(self, image_bytes: bytes, prompt: str) -> str:
        self.captured.append((image_bytes, prompt))
        return "a dog"


def _rgb_image() -> np.ndarray:
    return np.zeros((8, 8, 3), dtype=np.uint8)


def test_analyzer_requires_brain() -> None:
    result = VisionAnalyzer().analyze(_rgb_image())
    assert "requires a brain" in result


def test_analyzer_no_image() -> None:
    result = VisionAnalyzer(_FakeBrain()).analyze(None)
    assert "No image" in result


def test_analyzer_invokes_brain_analyze_image() -> None:
    brain = _FakeBrain()
    result = VisionAnalyzer(brain=brain).describe(_rgb_image())
    assert result == "a dog"
    image_bytes, prompt = brain.captured[-1]
    assert isinstance(image_bytes, bytes)
    assert prompt == "Describe this image in detail."


def test_brain_analyze_image_sends_vision_payload() -> None:
    brain = Brain()
    brain.model = "vision-model"
    fake_chat = _FakeChat()
    brain.client = SimpleNamespace(chat=fake_chat)

    result = brain.analyze_image(b"\x89PNG\r\n\x1a\n", "What is in this image?")
    assert result == "a dog"

    kwargs = fake_chat.completions.calls[-1]
    assert kwargs["model"] == "vision-model"
    content = kwargs["messages"][1]["content"]
    assert content[0] == {"type": "text", "text": "What is in this image?"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")