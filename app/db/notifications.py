import json
import mysql.connector
from app.config.config import DB_CONFIG


def create_notification(*, type_key: str, payload: dict, created_by: str) -> str:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        import uuid
        import json

        notification_id = str(uuid.uuid4())

        # --------------------------------------------------
        # Resolve notification_type_id (fail loudly)
        # --------------------------------------------------
        cur.execute(
            """
            SELECT notification_type_id
            FROM notification_types
            WHERE type_key = %s
            """,
            (type_key,),
        )

        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                f"Unknown notification type_key: {type_key}"
            )

        notification_type_id = row[0]

        # --------------------------------------------------
        # Insert notification
        # --------------------------------------------------
        cur.execute(
            """
            INSERT INTO notification_notifications
                (notification_id, notification_type_id, payload, created_by)
            VALUES (%s, %s, %s, %s)
            """,
            (
                notification_id,
                notification_type_id,
                json.dumps(payload),
                created_by,
            ),
        )

        conn.commit()
        return notification_id

    finally:
        conn.close()





def add_notification_recipient(*, notification_id: str, user_id: str) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO notification_recipients
            (notification_id, user_id, is_read, is_dismissed, created_at)
            VALUES (%s, %s, 0, 0, NOW())
            """,
            (notification_id, user_id),
        )

        conn.commit()

    finally:
        conn.close()

def mark_notification_dismissed(*, notification_id: str, user_id: str) -> None:
    """
    Marks a notification as read + dismissed for this user.
    Idempotent: safe to call multiple times.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        print("[DEBUG] dismiss attempt")
        print("[DEBUG] notification_id:", notification_id)
        print("[DEBUG] user_id:", user_id)

        cur.execute(
            """
            UPDATE notification_recipients
            SET
                is_read = 1,
                read_at = NOW(),
                is_dismissed = 1,
                dismissed_at = NOW()
            WHERE
                notification_id = %s
                AND user_id = %s
            """,
            (notification_id, user_id),
        )

        print("[DEBUG] dismiss rowcount:", cur.rowcount)

        conn.commit()

    finally:
        conn.close()

def mark_notification_read(*, notification_id: str, user_id: str) -> None:
    """
    Marks a notification as read (not dismissed).
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE notification_recipients
            SET
                is_read = 1,
                read_at = NOW()
            WHERE
                notification_id = %s
                AND user_id = %s
            """,
            (notification_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()

def mark_notification_read(*, notification_id: str, user_id: str) -> int:
    """
    Marks a notification as read for this user (does NOT dismiss).
    Returns affected rowcount.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE notification_recipients
            SET
                is_read = 1,
                read_at = NOW()
            WHERE
                notification_id = %s
                AND user_id = %s
                AND is_read = 0
            """,
            (notification_id, user_id),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_notification_for_user(*, notification_id: str, user_id: str) -> dict | None:
    """
    Fetch one notification + type metadata + recipient state for a given user.
    Returns None if the notification is not addressed to the user.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                n.notification_id,
                n.payload,
                n.created_at,

                nt.type_key,
                nt.title,
                nt.description,
                nt.severity,

                r.is_read,
                r.read_at,
                r.is_dismissed,
                r.dismissed_at
            FROM notification_notifications n
            JOIN notification_recipients r
              ON n.notification_id = r.notification_id
            JOIN notification_types nt
              ON n.notification_type_id = nt.notification_type_id
            WHERE n.notification_id = %s
              AND r.user_id = %s
            LIMIT 1
            """,
            (notification_id, user_id),
        )
        row = cur.fetchone()
        return row
    finally:
        conn.close()

# app/db/notifications.py

import json
import uuid
import mysql.connector
from app.config.config import DB_CONFIG


def create_notification_event(
    *,
    type_key: str,
    payload: dict | None,
    user_ids: list[str],
    created_by: str | None = None,
) -> str:
    """
    Create ONE notification row, attach MANY recipients.
    Returns notification_id.

    This is DB-layer primitive: inserts notification_notifications + notification_recipients.
    Delivery channels (email/slack/etc) are handled elsewhere (future dispatcher).
    """

    if not user_ids:
        return ""

    created_by = created_by or "system"
    notification_id = f"notif_{uuid.uuid4().hex[:24]}"

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # Resolve type_key -> notification_type_id
        cur.execute(
            "SELECT notification_type_id FROM notification_types WHERE type_key = %s LIMIT 1",
            (type_key,),
        )
        t = cur.fetchone()
        if not t:
            raise RuntimeError(f"Unknown notification type_key: {type_key}")

        notification_type_id = t["notification_type_id"]

        # Insert notification
        cur.execute(
            """
            INSERT INTO notification_notifications
                (notification_id, notification_type_id, payload, created_by)
            VALUES (%s, %s, %s, %s)
            """,
            (
                notification_id,
                notification_type_id,
                json.dumps(payload or {}),
                created_by,
            ),
        )

        # Insert recipients
        # NOTE: notification_recipients.notification_id FK must exist in notification_notifications (it will now)
        for uid in user_ids:
            cur.execute(
                """
                INSERT INTO notification_recipients
                    (notification_id, user_id)
                VALUES (%s, %s)
                """,
                (notification_id, uid),
            )

        conn.commit()
        return notification_id

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

