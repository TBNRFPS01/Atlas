from voice.hardware import check_voice_hardware, summarize_voice_hardware


def test_check_returns_expected_keys() -> None:
    hw = check_voice_hardware()
    assert set(hw) == {"microphone", "transcription", "speaker", "details"}
    assert isinstance(hw["details"], dict)


def test_summarize_returns_string() -> None:
    assert isinstance(summarize_voice_hardware(), str)
