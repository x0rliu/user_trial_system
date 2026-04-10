import secrets
from datetime import datetime, timedelta

import mysql.connector

from app.config.config import DB_CONFIG


def create_session(user_id: str) -> str:
    session_id = secrets.token_hex(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO user_sessions (SessionID, user_id, ExpiresAt)
            VALUES (%s, %s, %s)
            """,
            (session_id, user_id, expires_at),
        )
        conn.commit()
        return session_id
    finally:
        conn.close()


def get_user_from_session(session_id: str) -> str | None:
    if not session_id:
        return None

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT user_id
            FROM user_sessions
            WHERE SessionID = %s
              AND ExpiresAt > UTC_TIMESTAMP()
            LIMIT 1
            """,
            (session_id,),
        )
        row = cur.fetchone()
        return row["user_id"] if row else None
    finally:
        conn.close()


def delete_session(session_id: str) -> None:
    if not session_id:
        return

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM user_sessions
            WHERE SessionID = %s
            """,
            (session_id,),
        )
        conn.commit()
    finally:
        conn.close()
