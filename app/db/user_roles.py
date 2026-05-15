# app/db/user_roles.py

import mysql.connector
from app.config.config import DB_CONFIG
from app.constants.permission_levels import PERMISSION_LEVELS

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

    SECURITY NOTE:
    - Uses parameterized placeholders (%s) to prevent SQL injection
    - Validates levels to ensure only integers are used
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    if not levels:
        return []

    # Defensive validation (important for access control queries)
    try:
        safe_levels = [int(level) for level in levels]
    except (TypeError, ValueError):
        raise ValueError("Invalid permission levels")

    allowed_levels = set(PERMISSION_LEVELS)
    if not all(level in allowed_levels for level in safe_levels):
        raise ValueError("Invalid permission levels")

    placeholders = ",".join(["%s"] * len(safe_levels))

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

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
            tuple(safe_levels),
        )

        return cur.fetchall()

    finally:
        conn.close()



