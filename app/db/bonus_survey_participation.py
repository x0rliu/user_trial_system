# db/bonus_survey_participation.py

from app.config.config import DB_CONFIG
import mysql.connector
import uuid


def get_or_create_participation(
    *,
    bonus_survey_id: int,
    user_id: str,
) -> dict:
    """
    Ensure a participation row exists.
    Creates token + seen_at on first access.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # Check existing
        cur.execute(
            """
            SELECT *
            FROM bonus_survey_participation
            WHERE bonus_survey_id = %s
              AND user_id = %s
            LIMIT 1
            """,
            (bonus_survey_id, user_id),
        )

        row = cur.fetchone()
        if row:
            return row

        # Create new participation
        token = uuid.uuid4().hex

        cur.execute(
            """
            INSERT INTO bonus_survey_participation (
                bonus_survey_id,
                user_id,
                participation_token,
                confirmation_source,
                created_at
            )
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (bonus_survey_id, user_id, token, "internal_click"),
        )

        conn.commit()

        cur.execute(
            """
            SELECT *
            FROM bonus_survey_participation
            WHERE participation_token = %s
            """,
            (token,),
        )

        return cur.fetchone()

    finally:
        conn.close()


def mark_participation_started(
    *,
    bonus_survey_id: int,
    user_id: str,
):
    """
    Mark survey as started (first form open).
    Idempotent.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_survey_participation
            SET started_at = NOW()
            WHERE bonus_survey_id = %s
              AND user_id = %s
              AND started_at IS NULL
            """,
            (bonus_survey_id, user_id),
        )

        conn.commit()
    finally:
        conn.close()


def mark_participation_completed(
    *,
    participation_token: str,
    confirmation_source: str,
):
    """
    Mark survey as completed (CSV ingestion).
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_survey_participation
            SET completed_at = NOW(),
                confirmation_source = %s
            WHERE participation_token = %s
            AND completed_at IS NULL
            """,
            (confirmation_source, participation_token),
        )

        if cur.rowcount == 0:
            raise RuntimeError(
                f"Participation completion failed: token not found or already completed ({participation_token})"
            )

        conn.commit()

        conn.commit()
    finally:
        conn.close()

def get_participation_by_token(
    *,
    bonus_survey_id: int,
    participation_token: str,
) -> dict | None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                bonus_survey_participation_id,
                bonus_survey_id,
                user_id,
                participation_token,
                completed_at
            FROM bonus_survey_participation
            WHERE bonus_survey_id = %s
              AND participation_token = %s
            LIMIT 1
            """,
            (bonus_survey_id, participation_token),
        )

        return cur.fetchone()
    finally:
        conn.close()


def list_participation_tokens_for_survey(*, bonus_survey_id: int) -> set[str]:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT participation_token
            FROM bonus_survey_participation
            WHERE bonus_survey_id = %s
              AND participation_token IS NOT NULL
            """,
            (bonus_survey_id,),
        )

        return {row[0] for row in cur.fetchall() if row[0]}
    finally:
        conn.close()


def reset_bonus_survey_completion_state(*, bonus_survey_id: int) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_survey_participation
            SET completed_at = NULL,
                confirmation_source = 'reset'
            WHERE bonus_survey_id = %s
            """,
            (bonus_survey_id,),
        )

        conn.commit()
    finally:
        conn.close()


def mark_participation_completed_by_id(
    *,
    bonus_survey_participation_id: int,
    confirmation_source: str,
) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_survey_participation
            SET completed_at = NOW(),
                confirmation_source = %s
            WHERE bonus_survey_participation_id = %s
            """,
            (
                confirmation_source,
                bonus_survey_participation_id,
            ),
        )

        conn.commit()
    finally:
        conn.close()