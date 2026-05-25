# app/db/admin_view_modes.py

import mysql.connector

from app.config.config import DB_CONFIG


def get_admin_view_mode(*, session_id: str, actor_user_id: str) -> dict | None:
    """
    Return the active admin view mode for this exact session/user pair.

    Read-only by design. Expired rows are ignored rather than cleaned up here
    so GET render paths do not mutate state.
    """

    if not session_id or not actor_user_id:
        return None

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                AdminViewModeID,
                SessionID,
                ActorUserID,
                RealPermissionLevel,
                ViewAsPermissionLevel,
                ExpiresAt,
                CreatedAt,
                UpdatedAt
            FROM admin_view_modes
            WHERE SessionID = %s
              AND ActorUserID = %s
              AND ExpiresAt > UTC_TIMESTAMP()
            LIMIT 1
            """,
            (session_id, actor_user_id),
        )
        return cur.fetchone()
    finally:
        conn.close()


def set_admin_view_mode(
    *,
    session_id: str,
    actor_user_id: str,
    real_permission_level: int,
    view_as_permission_level: int,
) -> None:
    """
    Persist one admin view mode selection for this session.

    The service layer validates who may call this and which levels are allowed.
    This DB layer only writes already-validated state.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO admin_view_modes
                (
                    SessionID,
                    ActorUserID,
                    RealPermissionLevel,
                    ViewAsPermissionLevel,
                    ExpiresAt,
                    CreatedAt,
                    UpdatedAt
                )
            VALUES
                (%s, %s, %s, %s, UTC_TIMESTAMP() + INTERVAL 24 HOUR, UTC_TIMESTAMP(), UTC_TIMESTAMP())
            ON DUPLICATE KEY UPDATE
                RealPermissionLevel = VALUES(RealPermissionLevel),
                ViewAsPermissionLevel = VALUES(ViewAsPermissionLevel),
                ExpiresAt = VALUES(ExpiresAt),
                UpdatedAt = UTC_TIMESTAMP()
            """,
            (
                session_id,
                actor_user_id,
                int(real_permission_level),
                int(view_as_permission_level),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def clear_admin_view_mode(*, session_id: str, actor_user_id: str) -> None:
    """
    Clear admin view mode for this exact session/user pair.
    """

    if not session_id or not actor_user_id:
        return

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM admin_view_modes
            WHERE SessionID = %s
              AND ActorUserID = %s
            """,
            (session_id, actor_user_id),
        )
        conn.commit()
    finally:
        conn.close()