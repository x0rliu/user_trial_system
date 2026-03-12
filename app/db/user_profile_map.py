import mysql.connector
from app.config.config import DB_CONFIG


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def get_user_profiles(user_id: str) -> set[str]:
    """
    Returns a set of ProfileUIDs already selected by the user
    """
    rows = get_user_profile_uids(user_id)
    return {row["ProfileUID"] for row in rows}


def save_user_profiles_for_categories(
    user_id: str,
    profile_uids: list[str],
    category_ids: list[int],
):
    """
    Replace profile selections ONLY for the given category IDs.
    Other categories remain untouched.
    """
    if not category_ids:
        return

    conn = get_connection()
    try:
        cur = conn.cursor()

        # 1) Delete existing selections for these categories only
        cur.execute(
            f"""
            DELETE upm
            FROM user_profile_map upm
            JOIN user_profiles up
              ON up.ProfileUID = upm.ProfileUID
            WHERE upm.user_id = %s
              AND up.CategoryID IN ({",".join(["%s"] * len(category_ids))})
            """,
            [user_id, *category_ids],
        )

        # 2) Insert new selections
        if profile_uids:
            cur.executemany(
                """
                INSERT INTO user_profile_map (user_id, ProfileUID, CreatedAt)
                VALUES (%s, %s, NOW())
                """,
                [(user_id, uid) for uid in profile_uids],
            )

        conn.commit()
    finally:
        conn.close()



def get_user_profile_uids(user_id: str):
    """
    Returns all explicit profile selections for a user.
    One row per category selection.
    """
    query = """
        SELECT
            ProfileUID
        FROM user_profile_map
        WHERE user_id = %s
    """

    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, (user_id,))
        return cursor.fetchall()
    finally:
        conn.close()
