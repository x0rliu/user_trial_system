# app/db/user_roles.py

import mysql.connector
from app.config.config import DB_CONFIG

def get_effective_permission_level(user_id: str) -> int:
    """
    Returns the highest PermissionLevel assigned to the user.
    PermissionLevel is authoritative.
    Defaults to 0 (Guest).
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT MAX(PermissionLevel) AS PermissionLevel
            FROM user_role_map
            WHERE user_id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
        return int(row["PermissionLevel"]) if row and row["PermissionLevel"] is not None else 0
    finally:
        conn.close()

def get_users_with_permission_levels(levels: list[int]):
    """
    Returns users whose PermissionLevel is exactly one of the provided values.
    Used for UT Lead / Admin assignment.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        placeholders = ",".join(["%s"] * len(levels))

        cur.execute(
            f"""
            SELECT
                u.user_id,
                u.FirstName,
                u.LastName,
                urm.PermissionLevel
            FROM user_pool u
            JOIN user_role_map urm
              ON urm.user_id = u.user_id
            WHERE urm.PermissionLevel IN ({placeholders})
            ORDER BY u.FirstName, u.LastName
            """,
            tuple(levels),
        )

        return cur.fetchall()

    finally:
        conn.close()



