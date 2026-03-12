# app/db/user_interest_map.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_user_interest_uids(user_id: str):
    """
    Returns rows like: [{"InterestUID": "..."}]
    Mirrors get_user_profile_uids() pattern.
    """
    query = """
        SELECT
            InterestUID
        FROM user_interest_map
        WHERE user_id = %s
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute(query, (user_id,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows


def save_user_interests(user_id: str, interest_uids: list[str]):
    """
    Replaces all interest selections for a user with the provided list.
    Mirrors save_user_profiles().
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        # 🔥 REPLACE SEMANTICS: clear existing selections first
        cur.execute(
            "DELETE FROM user_interest_map WHERE user_id = %s",
            (user_id,),
        )

        # Insert new selections (if any)
        if interest_uids:
            cur.executemany(
                """
                INSERT INTO user_interest_map (user_id, InterestUID, CreatedAt)
                VALUES (%s, %s, NOW())
                """,
                [(user_id, uid) for uid in interest_uids],
            )

        conn.commit()
    finally:
        conn.close()

