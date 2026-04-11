import os
from dotenv import load_dotenv
import tomllib  # Python 3.11+

#-------------------------
# Database Configuration    
#-------------------------

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

DEBUG = os.getenv("DEBUG", "false").lower() == "true"
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"

assert DB_CONFIG["host"] not in (".", "", None), f"Invalid DB host: {DB_CONFIG['host']}"

#-------------------------
# Email Configuration
#------------------------

EMAIL_BACKEND = "ses"  # "ses" | "logitech"

SES_SMTP_CONFIG = {
    "host": "email-smtp.us-east-1.amazonaws.com",
    "port": 587,
    "username": "SES_SMTP_USERNAME",
    "password": "SES_SMTP_PASSWORD",
    "from_email": "no-reply@yourdomain.com",
}

# Placeholder for future
LOGITECH_SMTP_CONFIG = {
    # same shape as SES_SMTP_CONFIG
}


#-------------------------
# Debug JSON File Cache Backup
#------------------------

USE_TRIAL_FILE_FALLBACK = True  # DEV ONLY

# ----------------------------------------
# Load secrets.toml ONCE
# ----------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SECRETS_PATH = os.path.join(BASE_DIR, ".secret", "secrets.toml")

with open(SECRETS_PATH, "rb") as f:
    _secrets = tomllib.load(f)


# ----------------------------------------
# AI CONFIG
# ----------------------------------------
AI_CLIENT_ID = _secrets["ai"]["client_id"]
AI_CLIENT_SECRET = _secrets["ai"]["client_secret"]
AI_TOKEN_URL = _secrets["ai"]["token_url"]
AI_API_URL = _secrets["ai"]["api_url"]
AI_BASE_URL = _secrets["ai"].get("base_url")  # optional