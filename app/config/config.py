import os
from dotenv import load_dotenv

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
