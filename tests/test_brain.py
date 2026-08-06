from core.brain import Brain


def test_brain_has_openai_client() -> None:
    brain = Brain()
    assert brain.client is not None
    assert brain.endpoint == "http://localhost:1234/v1"
