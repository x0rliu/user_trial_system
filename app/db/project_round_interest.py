import mysql.connector
from app.config.config import DB_CONFIG

def record_round_interest(*, user_id: str, round_id: int):
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT IGNORE INTO project_round_interest
                (RoundID, user_id)
            VALUES (%s, %s)
            """,
            (round_id, user_id),
        )

        conn.commit()

    finally:
        conn.close()

def get_unnotified_watchers(round_id: int) -> list[str]:
    """
    Users who asked to be notified AND have not been notified yet.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id
            FROM project_round_interest
            WHERE RoundID = %s
              AND NotifiedAt IS NULL
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
    """
    if not user_ids:
        return 0

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        placeholders = ",".join(["%s"] * len(user_ids))
        params = [round_id] + user_ids

        cur.execute(
            f"""
            UPDATE project_round_interest
            SET NotifiedAt = NOW()
            WHERE RoundID = %s
              AND user_id IN ({placeholders})
              AND NotifiedAt IS NULL
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
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT 1
            FROM project_round_interest
            WHERE RoundID = %s
              AND user_id = %s
            LIMIT 1
            """,
            (round_id, user_id),
        )

        return cur.fetchone() is not None

    finally:
        conn.close()

