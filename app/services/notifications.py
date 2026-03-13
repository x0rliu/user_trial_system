"""
Notification service layer.

Responsibilities:
- Read notification state for a user
- Return simple, presentation-ready data
- Contain zero UI logic
- Contain zero enforcement logic

This module is intentionally conservative.
"""

from typing import List
import mysql.connector
from app.config.config import DB_CONFIG

# --------------------------------------------------
# Public API
# --------------------------------------------------

def get_unread_count(user_id: str) -> int:
    """
    Return the number of unread, non-dismissed notifications for a user.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    query = """
        SELECT COUNT(*)
        FROM notification_recipients
        WHERE user_id = %s
          AND is_read = FALSE
          AND is_dismissed = FALSE
    """

    cursor.execute(query, (user_id,))
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    return int(result[0]) if result else 0


def get_recent_notifications(user_id: str, limit: int = 5) -> list[dict]:
    """
    Return a list of recent unread notifications.
    Presentation-ready but still structured.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT
          n.notification_id,
          nt.type_key,
          nt.title,
          nt.approval_intent,
          n.payload,
          n.created_at
        FROM notification_notifications n
        JOIN notification_recipients r
          ON n.notification_id = r.notification_id
        JOIN notification_types nt
          ON n.notification_type_id = nt.notification_type_id
        WHERE r.user_id = %s
          AND r.is_read = FALSE
          AND (is_dismissed = FALSE OR is_dismissed IS NULL)
        ORDER BY n.created_at DESC
        LIMIT %s
    """

    import json

    cursor.execute(query, (user_id, limit))
    rows = cursor.fetchall() or []

    # Normalize payload JSON → dict
    for r in rows:
        payload = r.get("payload")
        if isinstance(payload, str):
            try:
                r["payload"] = json.loads(payload)
            except json.JSONDecodeError:
                r["payload"] = {}

    cursor.close()
    conn.close()

    return rows

def get_all_notifications(
    user_id: str,
    *,
    limit: int = 50,
    include_dismissed: bool = True,
) -> list[dict]:
    """
    Return recent notifications for a user, including read ones.
    Intended for the notifications history page.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT
          n.notification_id,
          nt.type_key,
          nt.title,
          n.payload,
          n.created_at,
          r.is_read,
          r.is_dismissed
        FROM notification_notifications n
        JOIN notification_recipients r
          ON n.notification_id = r.notification_id
        JOIN notification_types nt
          ON n.notification_type_id = nt.notification_type_id
        WHERE r.user_id = %s
    """

    params = [user_id]

    if not include_dismissed:
        query += " AND (r.is_dismissed = FALSE OR r.is_dismissed IS NULL)"

    query += """
        ORDER BY n.created_at DESC
        LIMIT %s
    """

    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall() or []

    # Normalize payload JSON → dict
    import json
    for r in rows:
        payload = r.get("payload")
        if isinstance(payload, str):
            try:
                r["payload"] = json.loads(payload)
            except json.JSONDecodeError:
                r["payload"] = {}

    cursor.close()
    conn.close()

    return rows


def get_notification_by_id(user_id: str, notification_id: str) -> dict | None:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT
            n.notification_id,
            nt.type_key,
            nt.title,
            n.payload,
            n.created_at
        FROM notification_notifications n
        JOIN notification_recipients r
          ON n.notification_id = r.notification_id
        JOIN notification_types nt
          ON n.notification_type_id = nt.notification_type_id
        WHERE r.user_id = %s
          AND n.notification_id = %s
        LIMIT 1
    """

    cursor.execute(query, (user_id, notification_id))
    row = cursor.fetchone()

    if row:
        payload = row.get("payload")
        if isinstance(payload, str):
            import json
            try:
                row["payload"] = json.loads(payload)
            except json.JSONDecodeError:
                row["payload"] = {}

    cursor.close()
    conn.close()

    return row



def get_notification_detail(user_id: str, notification_id: str) -> dict | None:
    """
    Returns a single notification row (joined with types + recipient state).
    """
    from app.db.notifications import get_notification_for_user

    row = get_notification_for_user(
        notification_id=notification_id,
        user_id=user_id,
    )
    if not row:
        return None

    import json
    payload_raw = row.get("payload") or "{}"
    try:
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else (payload_raw or {})
    except Exception:
        payload = {}

    row["payload"] = payload
    return row

def notify_user(
    *,
    user_id: str,
    type_key: str,
    context: dict | None = None,
    created_by: str | None = None,
):
    """
    Create and deliver a notification to a single user.
    Thin service-layer wrapper over DB notification primitives.
    """

    from app.db.notifications import (
        create_notification,
        add_notification_recipient,
    )

    # Fallback: system-generated notification
    created_by = created_by or "system"

    # 1️⃣ Create notification
    notification_id = create_notification(
        type_key=type_key,
        payload=context or {},
        created_by=created_by,
    )

    # 2️⃣ Attach recipient
    add_notification_recipient(
        notification_id=notification_id,
        user_id=user_id,
    )

def notify_many_users(
    *,
    user_ids: list[str],
    type_key: str,
    context: dict | None = None,
    created_by: str | None = None,
) -> str | None:
    """
    Create one notification event and attach multiple recipients.

    Used for system events such as:
    - trial recruiting opening
    - project updates
    - admin broadcasts
    """

    if not user_ids:
        return None

    from app.db.notifications import (
        create_notification,
        add_notification_recipient,
    )

    created_by = created_by or "system"

    # --------------------------------------------------
    # create notification event
    # --------------------------------------------------

    notification_id = create_notification(
        type_key=type_key,
        payload=context or {},
        created_by=created_by,
    )

    # --------------------------------------------------
    # attach recipients
    # --------------------------------------------------

    for uid in user_ids:
        add_notification_recipient(
            notification_id=notification_id,
            user_id=uid,
        )

    return notification_id


def mark_all_notifications_read(user_id: str):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE notification_recipients
            SET
                is_read = 1,
                read_at = NOW()
            WHERE user_id = %s
            AND is_read = 0
            """,
            (user_id,),
        )

        conn.commit()

    finally:
        conn.close()