# app/cache/registration_cache.py

import uuid
import time
from typing import Dict, Optional

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
    return entry["data"] if entry else None


def delete_registration_entry(token: str):
    _REGISTRATION_CACHE.pop(token, None)

def clear_registration_cache():
    _REGISTRATION_CACHE.clear()