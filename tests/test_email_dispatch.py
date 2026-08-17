from core.router import Router


def test_email_request_parsing() -> None:
    router = Router()
    args = router._email_request(
        "send email to alice@example.com subject Hello body Hi there"
    )
    assert args["action"] == "send"
    assert args["to"] == "alice@example.com"
    assert args["subject"] == "Hello"
    assert args["body"] == "Hi there"


def test_email_request_about_form() -> None:
    router = Router()
    args = router._email_request(
        "email bob@example.com about lunch: can you make it?"
    )
    assert args["to"] == "bob@example.com"
    assert args["subject"] == "lunch"
    assert "can you make it" in args["body"]


def test_email_dispatch_requires_confirmation() -> None:
    router = Router()
    result = router.route("send email to alice@example.com subject Hi body Hello")
    assert "Confirm" in result
    assert "send email" in result
