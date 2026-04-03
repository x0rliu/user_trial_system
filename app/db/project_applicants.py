import mysql.connector
from app.config.config import DB_CONFIG
from app.db.project_participants import user_is_currently_in_trial


def apply_for_trial(*, user_id: str, round_id: int, motivation: str | None = None):

    # -------------------------------------------
    # Prevent applying while already in a trial
    # -------------------------------------------

    if user_is_currently_in_trial(user_id=user_id):
        return

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO project_applicants
            (RoundID, user_id, MotivationText, AppliedAt)
            VALUES (%s, %s, %s, NOW())
            """,
            (round_id, user_id, motivation)
        )

        conn.commit()

    except mysql.connector.IntegrityError:
        # user already applied → update motivation
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE project_applicants
            SET MotivationText = %s
            WHERE RoundID = %s
            AND user_id = %s
            """,
            (motivation, round_id, user_id)
        )

        conn.commit()

    finally:
        conn.close()

def has_applied(user_id: str, round_id: int):

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT 1
            FROM project_applicants
            WHERE user_id = %s
            AND RoundID = %s
            LIMIT 1
            """,
            (user_id, round_id)
        )

        return cur.fetchone() is not None

    finally:
        conn.close()

def withdraw_application(*, user_id: str, round_id: int):

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM project_applicants
            WHERE RoundID = %s
            AND user_id = %s
            """,
            (round_id, user_id)
        )

        conn.commit()

    finally:
        conn.close()