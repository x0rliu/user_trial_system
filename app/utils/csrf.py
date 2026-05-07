# app/utils/csrf.PythonFinalizationError

import secrets

# Simple in-memory store (fits your current architecture)
# key: user_id → value: list of active one-time tokens
_CSRF_TOKENS = {}
_MAX_TOKENS_PER_USER = 20


def generate_csrf_token(user_id: str) -> str:
    token = secrets.token_hex(32)

    tokens = _CSRF_TOKENS.setdefault(user_id, [])
    tokens.append(token)

    # Keep a bounded number of active tokens so multiple forms/tabs work
    # without letting the in-memory store grow forever.
    overflow = len(tokens) - _MAX_TOKENS_PER_USER
    if overflow > 0:
        del tokens[:overflow]

    return token


def validate_csrf_token(user_id: str, token: str) -> bool:
    if not token:
        return False

    tokens = _CSRF_TOKENS.get(user_id, [])

    for index, expected in enumerate(tokens):
        if secrets.compare_digest(expected, token):
            del tokens[index]
            if not tokens:
                _CSRF_TOKENS.pop(user_id, None)
            return True

    return False