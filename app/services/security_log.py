# app/services/security_log.py

from app.config.config import DEBUG


SENSITIVE_METADATA_KEYS = {
    "email",
    "ip",
    "token",
    "csrf_token",
    "session_id",
    "password",
    "secret",
    "answer",
    "payload",
}


def _safe_metadata(metadata: dict | None) -> dict:
    if not isinstance(metadata, dict):
        return {}

    safe = {}
    for key, value in metadata.items():
        safe_key = str(key or "")
        if safe_key.lower() in SENSITIVE_METADATA_KEYS:
            safe[safe_key] = "[redacted]"
        elif isinstance(value, (str, int, float, bool)) or value is None:
            safe[safe_key] = value
        else:
            safe[safe_key] = f"[{type(value).__name__}]"

    return safe


def log_security_event(*, user_id: str, action: str, reason: str, metadata: dict):
    if not DEBUG:
        return

    safe_user = str(user_id or "")[:8]
    safe_action = str(action or "")[:80]
    safe_reason = str(reason or "")[:80]
    safe_metadata = _safe_metadata(metadata)

    print(
        f"[SECURITY] user={safe_user} action={safe_action} "
        f"reason={safe_reason} meta={safe_metadata}"
    )