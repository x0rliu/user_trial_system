import secrets

# Simple in-memory store (fits your current architecture)
# key: user_id → value: token
_CSRF_TOKENS = {}


def generate_csrf_token(user_id: str) -> str:
    token = secrets.token_hex(32)
    _CSRF_TOKENS[user_id] = token
    return token


def validate_csrf_token(user_id: str, token: str) -> bool:
    if not token:
        return False

    expected = _CSRF_TOKENS.get(user_id)

    # Optional: one-time use (recommended)
    if expected and secrets.compare_digest(expected, token):
        del _CSRF_TOKENS[user_id]
        return True

    return False