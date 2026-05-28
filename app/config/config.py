import os
from dotenv import load_dotenv
import tomllib  # Python 3.11+

#-------------------------
# Database Configuration    
#-------------------------

load_dotenv()


def _env_required(name: str) -> str:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return str(value).strip()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        raise RuntimeError(f"Invalid integer environment variable: {name}")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default

    return str(value).strip().lower() in {"1", "true", "yes", "on"}


DB_CONFIG = {
    "host": _env_required("DB_HOST"),
    "port": _env_int("DB_PORT", 3306),
    "database": _env_required("DB_NAME"),
    "user": _env_required("DB_USER"),
    "password": _env_required("DB_PASSWORD"),
}

DEBUG = _env_bool("DEBUG", False)
APP_ENV = (
    os.getenv("APP_ENV")
    or os.getenv("UTS_ENV")
    or os.getenv("ENVIRONMENT")
    or "development"
).strip().lower()
IS_PRODUCTION = APP_ENV in {"prod", "production"}
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", IS_PRODUCTION)
MAX_POST_BODY_BYTES = _env_int("MAX_POST_BODY_BYTES", 12 * 1024 * 1024)

if IS_PRODUCTION and not SESSION_COOKIE_SECURE:
    raise RuntimeError("SESSION_COOKIE_SECURE must be true in production")

if DB_CONFIG["host"] in {".", "localhost.", ""}:
    raise RuntimeError("Invalid DB_HOST configuration")

#-------------------------
# Email Configuration
#------------------------

EMAIL_BACKEND = "ses"  # "ses" | "logitech"

SES_SMTP_CONFIG = {
    "host": os.getenv("SES_SMTP_HOST", "email-smtp.us-east-1.amazonaws.com"),
    "port": _env_int("SES_SMTP_PORT", 587),
    "username": os.getenv("SES_SMTP_USERNAME", ""),
    "password": os.getenv("SES_SMTP_PASSWORD", ""),
    "from_email": os.getenv("SES_FROM_EMAIL", "no-reply@yourdomain.com"),
}

# Placeholder for future
LOGITECH_SMTP_CONFIG = {
    # same shape as SES_SMTP_CONFIG
}


#-------------------------
# Debug JSON File Cache Backup
#------------------------

# Local/dev fallback only. Production must use DB-backed trial data.
USE_TRIAL_FILE_FALLBACK = _env_bool(
    "USE_TRIAL_FILE_FALLBACK",
    default=not IS_PRODUCTION,
)

if IS_PRODUCTION and USE_TRIAL_FILE_FALLBACK:
    raise RuntimeError("USE_TRIAL_FILE_FALLBACK must be false in production")

# ----------------------------------------
# Load secrets.toml ONCE
# ----------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SECRETS_PATH = os.path.join(BASE_DIR, ".secret", "secrets.toml")

def _load_secrets() -> dict:
    if not os.path.exists(SECRETS_PATH):
        raise RuntimeError("Missing secrets configuration file")

    with open(SECRETS_PATH, "rb") as f:
        return tomllib.load(f)


def _required_secret(section: str, key: str) -> str:
    try:
        value = _secrets[section][key]
    except KeyError:
        raise RuntimeError(f"Missing required secret: {section}.{key}")

    if value is None or not str(value).strip():
        raise RuntimeError(f"Missing required secret: {section}.{key}")

    return str(value).strip()


_secrets = _load_secrets()


OKTA_SSO_CONFIG = {
    "enabled": bool(_secrets.get("okta_sso", {}).get("enabled", False)),
    "issuer": str(_secrets.get("okta_sso", {}).get("issuer", "")).strip(),
    "client_id": str(_secrets.get("okta_sso", {}).get("client_id", "")).strip(),
    "redirect_uri": str(_secrets.get("okta_sso", {}).get("redirect_uri", "")).strip(),
}


# ----------------------------------------
# UPS TRACKING CONFIG
# ----------------------------------------
_ups_tracking = _secrets.get("ups_tracking", {})
_ups_environment = str(_ups_tracking.get("environment", "production")).strip().lower()
_ups_is_sandbox = _ups_environment in {"sandbox", "test", "testing", "cie"}

UPS_TRACKING_CONFIG = {
    "enabled": bool(_ups_tracking.get("enabled", False)),
    "environment": "sandbox" if _ups_is_sandbox else "production",
    "client_id": str(_ups_tracking.get("client_id", "")).strip(),
    "client_secret": str(_ups_tracking.get("client_secret", "")).strip(),
    "merchant_id": str(_ups_tracking.get("merchant_id", _ups_tracking.get("client_id", ""))).strip(),
    "token_url": str(
        _ups_tracking.get(
            "token_url",
            "https://wwwcie.ups.com/security/v1/oauth/token"
            if _ups_is_sandbox
            else "https://onlinetools.ups.com/security/v1/oauth/token",
        )
    ).strip(),
    "base_url": str(
        _ups_tracking.get(
            "base_url",
            "https://wwwcie.ups.com"
            if _ups_is_sandbox
            else "https://onlinetools.ups.com",
        )
    ).strip().rstrip("/"),
}


# ----------------------------------------
# AI CONFIG
# ----------------------------------------
AI_CLIENT_ID = _required_secret("profile_ai", "client_id")
AI_CLIENT_SECRET = _required_secret("profile_ai", "client_secret")
AI_TOKEN_URL = _required_secret("profile_ai", "token_url")
AI_API_BASE_URL = _required_secret("profile_ai", "api_url").rstrip("/")
AI_API_URL = AI_API_BASE_URL + "/chat/completions"
AI_BASE_URL = _secrets["profile_ai"].get("base_url")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

TOKEN_CACHE_FILE = os.path.join(
    BASE_DIR,
    ".secret",
    "logiq_token_cache.json"
)