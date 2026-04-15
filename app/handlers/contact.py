# app/handlers/contact.py

import os
import time
from app.services.email_smtp import send_email


_RATE = {}


def _rate_limit(key: str, *, max_hits=3, window=60) -> bool:
    now = time.time()
    hits = _RATE.get(key, [])
    hits = [t for t in hits if now - t < window]

    if len(hits) >= max_hits:
        _RATE[key] = hits
        return False

    hits.append(now)
    _RATE[key] = hits
    return True


def handle_contact_post(*, actor_uid: str | None, form: dict, actor_ip: str):
    # honeypot
    if (form.get("company", [""])[0] or "").strip():
        return {"success": True}

    key = actor_uid or actor_ip or "anon"
    if not _rate_limit(key):
        return {
            "error": "Too many messages. Please wait a minute and try again.",
            "status": 429,
        }

    name = (form.get("name", [""])[0] or "").strip()
    email = (form.get("email", [""])[0] or "").strip()
    subject = (form.get("subject", [""])[0] or "").strip()
    message = (form.get("message", [""])[0] or "").strip()

    if not all([name, email, subject, message]):
        return {"error": "All fields are required."}

    if "@" not in email:
        return {"error": "Please enter a valid email address."}

    to_email = os.getenv("SMTP_CONTACT_TO") or os.getenv("SMTP_REPLY_TO")
    if not to_email:
        return {"error": "Contact email not configured."}

    body = (
        "New Contact Us submission\n"
        "-------------------------\n"
        f"From: {name} <{email}>\n"
        f"user_id: {actor_uid or 'guest'}\n"
        f"IP: {actor_ip}\n\n"
        f"{message}"
    )

    try:
        send_email(
            to_email=to_email,
            subject=f"[User Trials] {subject}",
            text_body=body,
            reply_to=email,
        )
    except Exception as e_err:
        print("[ERROR] Contact send failed:", e)
        return {"error": "Unable to send message. Please try again later."}

    return {"success": True}
