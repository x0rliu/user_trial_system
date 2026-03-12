# app/db/user_blacklist.py
import mysql.connector
from app.config.config import DB_CONFIG


def get_connection():
    return mysql.connector.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
    )


def is_blacklisted_email_or_domain(email: str) -> bool:
    email = email.lower().strip()
    domain = email.split("@")[-1]

    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT 1
            FROM user_blacklist
            WHERE IsActive = 1
              AND (ExpiresAt IS NULL OR ExpiresAt > NOW())
              AND (
                    (BlacklistType = 'email'  AND LOWER(Email)  = %s)
                 OR (BlacklistType = 'domain' AND LOWER(Domain) = %s)
              )
            LIMIT 1
            """,
            (email, domain),
        )

        return cur.fetchone() is not None

    finally:
        conn.close()
