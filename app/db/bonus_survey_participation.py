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
                completed_at,
                source_email,
                source_token,
                source_response_key,
                match_method,
                match_confidence,
                needs_review,
                match_notes
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


def get_participation_by_email(
    *,
    bonus_survey_id: int,
    source_email: str,
) -> dict | None:
    """
    Find an existing participation row by the user's registered email.

    Email fallback only links to a known participant who already belongs to
    the target bonus survey participation set. It does not create users and
    does not loosen recruiting/user-pool membership rules.
    """

    email = (source_email or "").strip().lower()
    if not email:
        return None

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                p.bonus_survey_participation_id,
                p.bonus_survey_id,
                p.user_id,
                p.participation_token,
                p.completed_at,
                p.source_email,
                p.source_token,
                p.source_response_key,
                p.match_method,
                p.match_confidence,
                p.needs_review,
                p.match_notes
            FROM bonus_survey_participation p
            JOIN user_pool u
              ON u.user_id = p.user_id
            WHERE p.bonus_survey_id = %s
              AND LOWER(u.Email) = %s
            LIMIT 1
            """,
            (bonus_survey_id, email),
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
                confirmation_source = 'reset',
                source_email = NULL,
                source_token = NULL,
                source_response_key = NULL,
                match_method = NULL,
                match_confidence = NULL,
                needs_review = 0,
                match_notes = NULL
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


def mark_participation_completed_with_attribution(
    *,
    bonus_survey_participation_id: int,
    confirmation_source: str,
    source_email: str | None,
    source_token: str | None,
    source_response_key: str | None,
    match_method: str,
    match_confidence: str,
    needs_review: int,
    match_notes: str | None,
) -> None:
    """
    Mark an existing participation row complete and persist how the uploaded
    response was attributed.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_survey_participation
            SET completed_at = NOW(),
                confirmation_source = %s,
                source_email = %s,
                source_token = %s,
                source_response_key = %s,
                match_method = %s,
                match_confidence = %s,
                needs_review = %s,
                match_notes = %s
            WHERE bonus_survey_participation_id = %s
            """,
            (
                confirmation_source,
                source_email,
                source_token,
                source_response_key,
                match_method,
                match_confidence,
                int(needs_review),
                match_notes,
                bonus_survey_participation_id,
            ),
        )

        conn.commit()
    finally:
        conn.close()


def get_participation_by_source_response_key(
    *,
    bonus_survey_id: int,
    source_response_key: str,
) -> dict | None:
    if not source_response_key:
        return None

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT *
            FROM bonus_survey_participation
            WHERE bonus_survey_id = %s
              AND source_response_key = %s
            LIMIT 1
            """,
            (bonus_survey_id, source_response_key),
        )

        return cur.fetchone()
    finally:
        conn.close()


def create_upload_only_participation(
    *,
    bonus_survey_id: int,
    source_email: str | None,
    source_token: str | None,
    source_response_key: str,
    match_method: str,
    match_confidence: str,
    needs_review: int,
    match_notes: str | None,
    confirmation_source: str = "bonus_csv_upload",
) -> dict:
    """
    Create a feedback-first participation row for an uploaded response that
    cannot be confidently linked to an existing participant.

    user_id stays NULL by design. The generated participation_token is only an
    internal row token so the existing answer FK model can remain intact.
    """

    if not source_response_key:
        raise ValueError("source_response_key is required")

    token = uuid.uuid4().hex

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            INSERT INTO bonus_survey_participation (
                bonus_survey_id,
                user_id,
                participation_token,
                completed_at,
                confirmation_source,
                created_at,
                source_email,
                source_token,
                source_response_key,
                match_method,
                match_confidence,
                needs_review,
                match_notes
            )
            VALUES (%s, NULL, %s, NOW(), %s, NOW(), %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                completed_at = NOW(),
                confirmation_source = VALUES(confirmation_source),
                source_email = VALUES(source_email),
                source_token = VALUES(source_token),
                match_method = VALUES(match_method),
                match_confidence = VALUES(match_confidence),
                needs_review = VALUES(needs_review),
                match_notes = VALUES(match_notes)
            """,
            (
                bonus_survey_id,
                token,
                confirmation_source,
                source_email,
                source_token,
                source_response_key,
                match_method,
                match_confidence,
                int(needs_review),
                match_notes,
            ),
        )

        conn.commit()

        cur.execute(
            """
            SELECT *
            FROM bonus_survey_participation
            WHERE bonus_survey_id = %s
              AND source_response_key = %s
            LIMIT 1
            """,
            (bonus_survey_id, source_response_key),
        )

        row = cur.fetchone()
        if not row:
            raise RuntimeError("Failed to create upload-only bonus survey participation row")

        return row
    finally:
        conn.close()