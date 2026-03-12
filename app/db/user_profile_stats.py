import mysql.connector
from app.config.config import DB_CONFIG


def get_trial_application_count(user_id: str) -> int:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM project_applicants
            WHERE user_id = %s
            """,
            (user_id,)
        )

        row = cur.fetchone()
        return row[0] if row else 0

    finally:
        conn.close()


def get_trial_completion_count(user_id: str) -> int:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM project_participants
            WHERE user_id = %s
            AND ParticipantStatus = 'Completed'
            """,
            (user_id,)
        )

        row = cur.fetchone()
        return row[0] if row else 0

    finally:
        conn.close()