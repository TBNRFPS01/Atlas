from __future__ import annotations

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional

from tools.base import Tool, ToolMetadata, ToolParameter


class EmailTool(Tool):
    """Email tool for sending emails via SMTP."""

    name = "email"
    description = "Send emails via SMTP with optional attachments."
    metadata = ToolMetadata(category="communication", permission_level="elevated", confirmation_required=True, description=description)

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform: send, test",
                required=True,
                enum=["send", "test"],
            ),
            ToolParameter(
                name="to",
                type="string",
                description="Recipient email address(es), comma-separated",
                required=False,
            ),
            ToolParameter(
                name="subject",
                type="string",
                description="Email subject",
                required=False,
            ),
            ToolParameter(
                name="body",
                type="string",
                description="Email body (plain text)",
                required=False,
            ),
            ToolParameter(
                name="html_body",
                type="string",
                description="Email body (HTML)",
                required=False,
            ),
            ToolParameter(
                name="attachments",
                type="string",
                description="Comma-separated list of file paths to attach",
                required=False,
            ),
        ]

    def __init__(self, config=None) -> None:
        super().__init__()
        self._config = config

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.get("action", "send")
        
        if action == "test":
            return self._test_connection()
        elif action == "send":
            return self._send_email(kwargs)
        else:
            return f"Unknown action: {action}"

    def _get_smtp_config(self) -> dict:
        """Get SMTP configuration from config or environment."""
        if self._config:
            return {
                "host": self._config.get("email_smtp_host", "smtp.gmail.com"),
                "port": self._config.get("email_smtp_port", 587),
                "username": self._config.get("email_username", ""),
                "password": self._config.get("email_password", ""),
                "from_addr": self._config.get("email_from", ""),
                "use_tls": self._config.get("email_use_tls", True),
            }
        else:
            # Fallback to environment variables
            import os
            return {
                "host": os.getenv("ATLAS_EMAIL_SMTP_HOST", "smtp.gmail.com"),
                "port": int(os.getenv("ATLAS_EMAIL_SMTP_PORT", "587")),
                "username": os.getenv("ATLAS_EMAIL_USERNAME", ""),
                "password": os.getenv("ATLAS_EMAIL_PASSWORD", ""),
                "from_addr": os.getenv("ATLAS_EMAIL_FROM", ""),
                "use_tls": os.getenv("ATLAS_EMAIL_USE_TLS", "true").lower() in ("true", "1", "yes"),
            }

    def _test_connection(self) -> str:
        """Test SMTP connection without sending email."""
        config = self._get_smtp_config()
        
        if not config["username"] or not config["password"]:
            return "Email not configured: username/password required"
        
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(config["host"], config["port"], timeout=10) as server:
                if config["use_tls"]:
                    server.starttls(context=context)
                server.login(config["username"], config["password"])
            return "Email configuration test successful"
        except smtplib.SMTPAuthenticationError:
            return "Authentication failed: check username/password"
        except smtplib.SMTPConnectError:
            return f"Connection failed: cannot reach {config['host']}:{config['port']}"
        except Exception as e:
            return f"Test failed: {e}"

    def _send_email(self, kwargs: dict) -> str:
        """Send an email."""
        config = self._get_smtp_config()
        
        # Validate configuration
        if not config["username"] or not config["password"]:
            return "Email not configured: username/password required"
        if not config["from_addr"]:
            return "Email not configured: from address required"
        
        to = kwargs.get("to", "")
        subject = kwargs.get("subject", "No Subject")
        body = kwargs.get("body", "")
        html_body = kwargs.get("html_body", "")
        attachments_str = kwargs.get("attachments", "")
        
        if not to:
            return "Recipient (to) required"
        if not body and not html_body:
            return "Email body required"
        
        # Parse recipients
        recipients = [addr.strip() for addr in to.split(",") if addr.strip()]
        
        # Create message
        msg = MIMEMultipart("alternative")
        msg["From"] = config["from_addr"]
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        
        # Add plain text body
        if body:
            msg.attach(MIMEText(body, "plain", "utf-8"))
        
        # Add HTML body if provided
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))
        
        # Handle attachments
        if attachments_str:
            attachment_paths = [p.strip() for p in attachments_str.split(",") if p.strip()]
            for path in attachment_paths:
                try:
                    with open(path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={os.path.basename(path)}",
                    )
                    msg.attach(part)
                except Exception as e:
                    return f"Failed to attach {path}: {e}"
        
        # Send email
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(config["host"], config["port"], timeout=30) as server:
                if config["use_tls"]:
                    server.starttls(context=context)
                server.login(config["username"], config["password"])
                server.send_message(msg, from_addr=config["from_addr"], to_addrs=recipients)
            
            return f"Email sent successfully to {', '.join(recipients)}"
        
        except smtplib.SMTPAuthenticationError:
            return "Authentication failed: check username/password"
        except smtplib.SMTPRecipientsRefused:
            return "Recipient address rejected by server"
        except smtplib.SMTPSenderRefused:
            return "Sender address rejected by server"
        except smtplib.SMTPDataError as e:
            return f"Server refused email data: {e}"
        except Exception as e:
            return f"Failed to send email: {e}"


import os