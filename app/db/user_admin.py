# app/db/user_admin.py

import mysql.connector
from app.config.config import DB_CONFIG

def get_all_users_for_admin():
    """
    Returns basic user info + effective permission level.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                u.user_id,
                u.FirstName,
                u.LastName,
                u.Email,
                COALESCE(MAX(r.PermissionLevel), 0) AS PermissionLevel
            FROM user_pool u
            LEFT JOIN user_role_map urm ON urm.user_id = u.user_id
            LEFT JOIN user_role r ON r.RoleID = urm.RoleID
            GROUP BY u.user_id
            ORDER BY PermissionLevel DESC, u.Email
            """
        )
        return cur.fetchall()
    finally:
        conn.close()
