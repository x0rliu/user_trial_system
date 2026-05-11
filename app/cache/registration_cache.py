# app/cache/registration_cache.py

import os
import uuid
import time
from typing import Dict, Optional

REGISTRATION_TOKEN_TTL_SECONDS = int(
    os.getenv("REGISTRATION_TOKEN_TTL_SECONDS", "3600")
)

# token -> payload
_REGISTRATION_CACHE: Dict[str, dict] = {}


def create_registration_entry(data: dict) -> str:
    """
    Store pending registration data and return verification token.
    """
    token = str(uuid.uuid4())
    _REGISTRATION_CACHE[token] = {
        "data": data,
        "created_at": time.time(),
    }
    return token


def get_registration_entry(token: str) -> Optional[dict]:
    entry = _REGISTRATION_CACHE.get(token)
    if not entry:
        return None

    created_at = float(entry.get("created_at") or 0)
    if time.time() - created_at > REGISTRATION_TOKEN_TTL_SECONDS:
        delete_registration_entry(token)
        return None

    return entry["data"]


def delete_registration_entry(token: str):
    _REGISTRATION_CACHE.pop(token, None)

def clear_registration_cache():
    _REGISTRATION_CACHE.clear()