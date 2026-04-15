# token_manager.py
import os, json, time, requests, threading, random
from app.config.config import TOKEN_CACHE_FILE

lock = threading.Lock()
TOKEN_CACHE_FILE = "logiq_token_cache.json"

# Refresh preemptively this many seconds before the server-side expiry
EXPIRY_MARGIN = 120  # 2 minutes
JITTER_LOW, JITTER_HIGH = 5, 25  # random jitter to avoid thundering herd

def _read_cache():
    if os.path.exists(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE, "r") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def _write_cache(access_token: str, expires_in: int):
    # Store an adjusted "expires_at" (now + server expiry - margin - jitter)
    jitter = random.randint(JITTER_LOW, JITTER_HIGH)
    exp_at = time.time() + max(60, int(expires_in)) - EXPIRY_MARGIN - jitter
    os.makedirs(os.path.dirname(TOKEN_CACHE_FILE), exist_ok=True)

    with open(TOKEN_CACHE_FILE, "w") as f:
        json.dump({"access_token": access_token, "expires_at": exp_at}, f)

def invalidate_cache():
    try:
        os.remove(TOKEN_CACHE_FILE)
    except FileNotFoundError:
        pass

def _needs_refresh(cache: dict) -> bool:
    if not cache:
        return True
    return time.time() >= float(cache.get("expires_at", 0))

def fetch_new_token(client_id, client_secret, token_url):
    data = {"grant_type": "client_credentials"}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # light backoff: 0.2s → 0.5s → 1.0s
    delays = (0.2, 0.5, 1.0)
    last_err = None
    for d in delays:
        try:
            resp = requests.post(
                token_url, data=data, auth=(client_id, client_secret),
                headers=headers, timeout=10
            )
            if resp.status_code == 200:
                payload = resp.json()
                token = payload["access_token"]
                expires_in = payload.get("expires_in", 3600)
                _write_cache(token, expires_in)
                return token
            last_err = Exception(f"Failed to get token: {resp.status_code} - {resp.text}")
        except Exception as e_err:
            last_err = e_err
        time.sleep(d)
    raise last_err

def get_access_token(client_id, client_secret, token_url, *, force_refresh: bool=False):
    with lock:
        if force_refresh:
            invalidate_cache()
        cache = _read_cache()
        if _needs_refresh(cache):
            return fetch_new_token(client_id, client_secret, token_url)
        return cache["access_token"]
