# app/services/email_smtp.py

import os
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage


def _safe_header(value: str) -> str:
    value = str(value or "").strip()
    if "\n" in value or "\r" in value:
        raise ValueError("Invalid header value")
    return value


def _env_required(name: str) -> str:
    val = os.getenv(name)
    if val is None or not str(val).strip():
        raise RuntimeError(f"Missing required env var: {name}")
    return str(val).strip()


def _env_optional(name: str, default: str = "") -> str:
    val = os.getenv(name, default)
    return str(val or "").strip()


def _env_first_required(*names: str) -> str:
    for name in names:
        val = os.getenv(name)
        if val is not None and str(val).strip():
            return str(val).strip()

    raise RuntimeError(f"Missing required env var: {' or '.join(names)}")


def _env_int_first(*names: str, default: int) -> int:
    for name in names:
        val = os.getenv(name)
        if val is None or not str(val).strip():
            continue
        try:
            return int(val)
        except (TypeError, ValueError):
            raise RuntimeError(f"Invalid integer env var: {name}")

    return default


def send_email(*, to_email: str, subject: str, text_body: str, reply_to: str | None = None) -> None:
    provider = _env_optional("SMTP_PROVIDER", "ses").lower()
    if provider not in {"ses", "smtp"}:
        raise RuntimeError("Unsupported SMTP provider")

    host = os.getenv("SMTP_HOST") or os.getenv("SES_SMTP_HOST") or "email-smtp.us-east-1.amazonaws.com"
    host = str(host).strip()
    if not host:
        raise RuntimeError("Missing required env var: SMTP_HOST or SES_SMTP_HOST")

    port = _env_int_first("SMTP_PORT", "SES_SMTP_PORT", default=587)
    username = _env_first_required("SMTP_USERNAME", "SES_SMTP_USERNAME")
    password = _env_first_required("SMTP_PASSWORD", "SES_SMTP_PASSWORD")

    from_email = os.getenv("SMTP_FROM") or os.getenv("SES_FROM_EMAIL")
    if not from_email or not str(from_email).strip():
        raise RuntimeError("Missing required env var: SMTP_FROM or SES_FROM_EMAIL")

    default_reply_to = _env_optional("SMTP_REPLY_TO")

    msg = EmailMessage()
    msg["From"] = _safe_header(from_email)
    msg["To"] = _safe_header(to_email)
    msg["Subject"] = _safe_header(subject)

    rt = reply_to or default_reply_to
    if rt:
        msg["Reply-To"] = _safe_header(rt)

    msg.set_content(text_body)

    context = ssl.create_default_context()

    with smtplib.SMTP(host, port, timeout=20) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(username, password)
        server.send_message(msg)


# --------------------------------------------------
# USER EVENTS
# --------------------------------------------------

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

    send_email(
        to_email=_env_required("ALERT_EMAIL"),
        subject=subject,
        text_body=body,
    )