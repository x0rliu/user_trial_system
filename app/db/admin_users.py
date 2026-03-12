# app/db/admin_users.py

import mysql.connector
from app.config.config import DB_CONFIG

def get_all_users_with_permissions():
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                u.user_id,
                CONCAT(u.FirstName, ' ', u.LastName) AS FullName,
                u.Email,
                COALESCE(MAX(urm.PermissionLevel), 0) AS PermissionLevel
            FROM user_pool u
            LEFT JOIN user_role_map urm
                ON u.user_id = urm.user_id
            GROUP BY
                u.user_id, u.FirstName, u.LastName, u.Email
            ORDER BY
                PermissionLevel DESC, FullName ASC
            """
        )
        return cur.fetchall()
    finally:
        conn.close()

def update_user_permission_level(*, user_id: str, permission_level: int) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Does a role row already exist?
    cur.execute(
        "SELECT 1 FROM user_role_map WHERE user_id = %s LIMIT 1",
        (user_id,),
    )
    exists = cur.fetchone() is not None

    if exists:
        cur.execute(
            """
            UPDATE user_role_map
            SET PermissionLevel = %s,
                UpdatedAt = NOW()
            WHERE user_id = %s
            """,
            (permission_level, user_id),
        )
    else:
        cur.execute(
            """
            INSERT INTO user_role_map
                (user_id, RoleID, PermissionLevel, CreatedAt, UpdatedAt)
            VALUES
                (%s, 'Participant', %s, NOW(), NOW())
            """,
            (user_id, permission_level),
        )

    conn.commit()
    conn.close()
