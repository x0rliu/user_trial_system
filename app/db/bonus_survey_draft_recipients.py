# app/db/bonus_survey_draft_recipients.py

import mysql.connector
from app.config.config import DB_CONFIG


def _connect():
    return mysql.connector.connect(**DB_CONFIG)


def get_users_by_normalized_emails(normalized_emails: list[str]) -> dict[str, dict]:
    """
    Return users keyed by lowercase email.

    Input emails must already be normalized/lowercased.
    """

    clean_emails = [
        email.strip().lower()
        for email in normalized_emails
        if isinstance(email, str) and email.strip()
    ]

    if not clean_emails:
        return {}

    placeholders = ", ".join(["%s"] * len(clean_emails))

    query = f"""
        SELECT
            user_id,
            Email,
            FirstName,
            LastName
        FROM user_pool
        WHERE LOWER(Email) IN ({placeholders})
    """

    conn = _connect()

    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, clean_emails)
        rows = cur.fetchall()
        cur.close()

        users_by_email = {}

        for row in rows:
            email = (row.get("Email") or "").strip().lower()
            if not email:
                continue

            users_by_email[email] = row

        return users_by_email

    finally:
        conn.close()


def replace_draft_recipients(*, draft_uuid: str, recipients: list[dict]) -> None:
    """
    Replace all direct-invite recipient rows for a draft.

    This intentionally deletes previous rows first so a saved paste fully
    replaces prior recipient state.
    """

    conn = _connect()

    try:
        conn.start_transaction()
        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM bonus_survey_draft_recipients
            WHERE draft_uuid = %s
            """,
            (draft_uuid,),
        )

        if recipients:
            rows = []

            for recipient in recipients:
                rows.append(
                    (
                        draft_uuid,
                        recipient.get("raw_email") or "",
                        recipient.get("normalized_email"),
                        recipient.get("matched_user_id"),
                        recipient.get("status"),
                    )
                )

            cur.executemany(
                """
                INSERT INTO bonus_survey_draft_recipients (
                    draft_uuid,
                    raw_email,
                    normalized_email,
                    matched_user_id,
                    status
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                rows,
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def delete_draft_recipients(*, draft_uuid: str) -> None:
    """
    Remove all direct-invite recipient rows for a draft.
    Used when switching back to open invitation.
    """

    conn = _connect()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM bonus_survey_draft_recipients
            WHERE draft_uuid = %s
            """,
            (draft_uuid,),
        )

        conn.commit()
        cur.close()

    finally:
        conn.close()


def get_draft_recipients(*, draft_uuid: str) -> list[dict]:
    """
    Return saved direct-invite recipients for a draft.
    """

    conn = _connect()

    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                recipient_id,
                draft_uuid,
                raw_email,
                normalized_email,
                matched_user_id,
                status,
                created_at,
                updated_at
            FROM bonus_survey_draft_recipients
            WHERE draft_uuid = %s
            ORDER BY
                FIELD(status, 'matched', 'unmatched', 'invalid'),
                normalized_email,
                raw_email
            """,
            (draft_uuid,),
        )

        rows = cur.fetchall()
        cur.close()

        return rows

    finally:
        conn.close()


def get_draft_recipient_counts(*, draft_uuid: str) -> dict:
    """
    Return recipient counts by status.
    """

    conn = _connect()

    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                status,
                COUNT(*) AS count
            FROM bonus_survey_draft_recipients
            WHERE draft_uuid = %s
            GROUP BY status
            """,
            (draft_uuid,),
        )

        rows = cur.fetchall()
        cur.close()

        counts = {
            "matched": 0,
            "unmatched": 0,
            "invalid": 0,
            "total": 0,
        }

        for row in rows:
            status = row.get("status")
            count = int(row.get("count") or 0)

            if status in counts:
                counts[status] = count
                counts["total"] += count

        return counts

    finally:
        conn.close()