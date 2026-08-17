from tools.email_tool import EmailTool


def test_validate_recipients_filters_invalid() -> None:
    good = EmailTool._validate_recipients(["a@b.com", "bad", "c@d.org"])
    assert good == ["a@b.com", "c@d.org"]


def test_rejects_invalid_recipient_with_config() -> None:
    cfg = {
        "email_smtp_host": "smtp.example.com",
        "email_smtp_port": 587,
        "email_username": "u",
        "email_password": "p",
        "email_from": "u@example.com",
        "email_use_tls": True,
    }
    tool = EmailTool(config=cfg)
    result = tool.execute(action="send", to="not-an-email", subject="s", body="b")
    assert "Invalid recipient" in result


def test_ssl_port_uses_smtp_ssl(monkeypatch) -> None:
    cfg = {
        "email_smtp_host": "smtp.example.com",
        "email_smtp_port": 465,
        "email_username": "u",
        "email_password": "p",
        "email_from": "u@example.com",
        "email_use_tls": True,
    }
    tool = EmailTool(config=cfg)

    captured = {}

    def fake_smtp_ssl(host, port, timeout=0, context=None):
        captured["host"] = host
        captured["port"] = port

        class C:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def login(self_inner, *a):
                raise Exception("stop here")

        return C()

    import smtplib

    monkeypatch.setattr(smtplib, "SMTP_SSL", fake_smtp_ssl)
    tool.execute(action="test")
    assert captured.get("port") == 465
