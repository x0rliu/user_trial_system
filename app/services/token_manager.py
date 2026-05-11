# token_manager.py
import os, json, time, requests, threading, random
from app.config.config import TOKEN_CACHE_FILE

lock = threading.Lock()

# Refresh preemptively this many seconds before the server-side expiry
EXPIRY_MARGIN = 120  # 2 minutes
JITTER_LOW, JITTER_HIGH = 5, 25  # random jitter to avoid thundering herd

def _read_cache():
    if os.path.exists(TOKEN_CACHE_FILE):
        try:
            with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}
    return {}

def _write_cache(access_token: str, expires_in: int):
    # Store an adjusted "expires_at" (now + server expiry - margin - jitter)
    jitter = random.randint(JITTER_LOW, JITTER_HIGH)
    exp_at = time.time() + max(60, int(expires_in)) - EXPIRY_MARGIN - jitter
    os.makedirs(os.path.dirname(TOKEN_CACHE_FILE), exist_ok=True)

    tmp_path = f"{TOKEN_CACHE_FILE}.tmp"

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"access_token": access_token, "expires_at": exp_at}, f)

    try:
        os.chmod(tmp_path, 0o600)
    except OSError:
        pass

    os.replace(tmp_path, TOKEN_CACHE_FILE)

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
            last_err = RuntimeError(f"Failed to get token: HTTP {resp.status_code}")
        except requests.RequestException as e_err:
            last_err = RuntimeError(f"Failed to get token request: {type(e_err).__name__}")
        except (KeyError, ValueError, TypeError):
            last_err = RuntimeError("Failed to parse token response")
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
