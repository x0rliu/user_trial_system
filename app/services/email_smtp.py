# app/services/email_smtp.py

import os
import smtplib
import ssl
from email.message import EmailMessage


def _env(name: str, default: str | None = None) -> str:
    val = os.getenv(name, default)
    if val is None or val == "":
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def send_email(*, to_email: str, subject: str, text_body: str, reply_to: str | None = None) -> None:
    provider = os.getenv("SMTP_PROVIDER", "ses").lower()
    if provider not in ("ses", "smtp"):
        raise RuntimeError(f"Unsupported SMTP_PROVIDER: {provider}")

    host = _env("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = _env("SMTP_USERNAME")
    password = _env("SMTP_PASSWORD")

    from_email = _env("SMTP_FROM")
    default_reply_to = os.getenv("SMTP_REPLY_TO", "")

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    rt = reply_to or default_reply_to
    if rt:
        msg["Reply-To"] = rt

    msg.set_content(text_body)

    context = ssl.create_default_context()

    # SES SMTP supports STARTTLS on 587
    with smtplib.SMTP(host, port, timeout=20) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(username, password)
        server.send_message(msg)

# --------------------------------------------------
# USER EVENTS
# --------------------------------------------------

from datetime import datetime


def send_new_user_alert(*, email: str, user_id: str) -> None:
    """
    Sends alert when a REAL user is created (post-verification).
    """

    subject = "✅ New User Created"

    body = f"""
New user successfully created:

UserID: {user_id}
Email: {email}
Time: {datetime.utcnow().isoformat()} UTC
"""

    # Send to yourself (admin)
    send_email(
        to_email=_env("ALERT_EMAIL"),  # <-- add this env var
        subject=subject,
        text_body=body,
    )