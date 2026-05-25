import mysql.connector
from app.config.config import DB_CONFIG


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def record_round_interest(*, user_id: str, round_id: int):
    """
    Create or reactivate a user's active watch preference for an upcoming round.

    DB source of truth:
    - active watch: WithdrawnAt IS NULL
    - stopped watch: WithdrawnAt IS NOT NULL
    """
    conn = get_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO project_round_interest
                (RoundID, user_id, CreatedAt, NotifiedAt, WithdrawnAt)
            VALUES (%s, %s, NOW(), NULL, NULL)
            ON DUPLICATE KEY UPDATE
                CreatedAt = NOW(),
                NotifiedAt = NULL,
                WithdrawnAt = NULL
            """,
            (round_id, user_id),
        )

        conn.commit()

    finally:
        conn.close()


def stop_watching_round(*, user_id: str, round_id: int) -> int:
    """
    Soft-withdraw a user's active watch preference for an upcoming round.

    Returns rows affected. The WHERE clause includes user_id so this cannot
    stop another user's watch record even if a round_id is tampered with.
    """
    conn = get_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE project_round_interest
            SET WithdrawnAt = NOW()
            WHERE RoundID = %s
              AND user_id = %s
              AND WithdrawnAt IS NULL
            """,
            (round_id, user_id),
        )

        conn.commit()
        return cur.rowcount

    finally:
        conn.close()


def get_unnotified_watchers(round_id: int) -> list[str]:
    """
    Users who asked to be notified, have not stopped watching,
    and have not been notified yet.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id
            FROM project_round_interest
            WHERE RoundID = %s
              AND NotifiedAt IS NULL
              AND WithdrawnAt IS NULL
            """,
            (round_id,),
        )
        return [r[0] for r in cur.fetchall() or []]
    finally:
        conn.close()


def mark_watchers_notified(round_id: int, user_ids: list[str]) -> int:
    """
    Mark NotifiedAt for this round for these users.
    Returns rows affected.

    SECURITY NOTE:
    Uses parameterized placeholders (%s) for all user_ids to prevent SQL injection.
    """
    if not user_ids:
        return 0

    try:
        safe_round_id = int(round_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid round_id")

    safe_user_ids = [str(uid).strip() for uid in user_ids if str(uid or "").strip()]
    if not safe_user_ids:
        return 0

    conn = get_connection()
    try:
        cur = conn.cursor()

        placeholders = ",".join(["%s"] * len(safe_user_ids))
        params = [safe_round_id] + safe_user_ids

        cur.execute(
            f"""
            UPDATE project_round_interest
            SET NotifiedAt = NOW()
            WHERE RoundID = %s
              AND user_id IN ({placeholders})
              AND NotifiedAt IS NULL
              AND WithdrawnAt IS NULL
            """,
            tuple(params),
        )

        conn.commit()
        return cur.rowcount

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def user_has_interest(*, user_id: str, round_id: int) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT 1
            FROM project_round_interest
            WHERE RoundID = %s
              AND user_id = %s
              AND WithdrawnAt IS NULL
            LIMIT 1
            """,
            (round_id, user_id),
        )

        return cur.fetchone() is not None

    finally:
        conn.close()