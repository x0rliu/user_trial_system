def get_user_profiles(user_id: str) -> dict:
    """
    Returns:
        {
            CategoryID: set(ProfileUID)
        }
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT upm.ProfileUID, pd.CategoryID
            FROM user_profile_map upm
            JOIN user_profiles pd
                ON upm.ProfileUID = pd.ProfileUID
            WHERE upm.user_id = %s
        """, (user_id,))

        result = {}

        for row in cur.fetchall():
            cat = row["CategoryID"]

            if cat not in result:
                result[cat] = set()

            result[cat].add(row["ProfileUID"])

        return result

    finally:
        conn.close()