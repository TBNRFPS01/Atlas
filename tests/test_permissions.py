from core.permissions import Decision, PermissionManager


def test_default_basic_action_is_allowed() -> None:
    pm = PermissionManager()
    assert pm.decide("system", "info") == Decision.ALLOW


def test_destructive_requires_confirmation() -> None:
    pm = PermissionManager()
    assert pm.decide("file", "delete", confirmed=False) == Decision.ASK
    assert pm.decide("file", "delete", confirmed=True) == Decision.ALLOW


def test_deny_rule_overrides_confirmation() -> None:
    pm = PermissionManager({"file.delete": Decision.DENY})
    assert pm.decide("file", "delete", confirmed=True) == Decision.DENY


def test_allow_rule_overrides_prompt() -> None:
    pm = PermissionManager({"automation.process_kill": Decision.ALLOW})
    assert pm.decide("automation", "process_kill", confirmed=False) == Decision.ALLOW


def test_authorize_short_circuits_prompt() -> None:
    pm = PermissionManager()
    pm.authorize("email.send")
    assert pm.decide("email", "send", permission_level="elevated", confirmed=False) == Decision.ALLOW


def test_elevated_without_confirm_prompts() -> None:
    pm = PermissionManager()
    assert pm.decide("email", "send", permission_level="elevated", confirmed=False) == Decision.ASK


def test_confirmation_prompt_formatting() -> None:
    pm = PermissionManager()
    prompt = pm.confirmation_prompt("file", "delete", "C:\\a.txt")
    assert "delete file" in prompt
    assert "C:\\a.txt" in prompt
    assert "yes," in prompt
