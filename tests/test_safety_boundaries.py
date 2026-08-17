from core.safety import HardSafety, SafetyViolation


def test_protected_directory_is_blocked() -> None:
    safety = HardSafety()
    assert safety.is_safe("file", "delete", "C:\\Windows\\notepad.exe") is False
    try:
        safety.check_path("C:\\Windows\\system32\\x")
    except SafetyViolation:
        pass
    else:
        raise AssertionError("expected SafetyViolation")


def test_protected_fragment_blocked() -> None:
    safety = HardSafety()
    assert safety.is_safe("file", "delete", "atlas_memory.db") is False
    assert safety.is_safe("file", "write", "C:\\Windows\\system32\\kernel32.dll") is False


def test_forbidden_action_blocked() -> None:
    safety = HardSafety()
    assert safety.is_safe("automation", "shutdown") is False
    assert safety.is_safe("automation", "format_disk") is False


def test_normal_action_allowed() -> None:
    safety = HardSafety()
    assert safety.is_safe("file", "delete", "C:\\Users\\me\\junk.txt") is True
    assert safety.is_safe("automation", "process_kill", "notepad") is True


def test_custom_protected_dir(tmp_path) -> None:
    safety = HardSafety(protected_dirs=[str(tmp_path)])
    target = tmp_path / "data.txt"
    assert safety.is_safe("file", "read", str(target)) is False
    # Files outside the protected dir are still allowed.
    assert safety.is_safe("file", "read", "C:\\other\\data.txt") is True
