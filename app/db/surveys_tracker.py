# app/db/surveys_tracker.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_tracker_by_id(tracker_id: int) -> dict | None:
    """
    Fetch a tracker row by ID.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT *
            FROM survey_tracker
            WHERE tracker_id = %s
            """,
            (tracker_id,),
        )

        return cur.fetchone()

    finally:
        conn.close()


def get_tracker_entries(tracker_id: int) -> list[dict]:
    """
    TEMP ADAPTER:
    Your DB does not have a tracker_entries table.

    So we return a single "entry" synthesized from survey_tracker.
    This preserves handler expectations WITHOUT lying about DB structure.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                tracker_id,
                current_state,
                updated_at
            FROM survey_tracker
            WHERE tracker_id = %s
            """,
            (tracker_id,),
        )

        row = cur.fetchone()

        if not row:
            return []

        # synthesize a single entry
        return [
            {
                "actor_user_id": "system",
                "entry_type": row.get("current_state", "unknown"),
                "detail_text": "",
                "created_at": row.get("updated_at"),
            }
        ]

    finally:
        conn.close()

def get_pending_bonus_survey_approvals() -> list[dict]:
    """
    TEMP STUB.

    Bonus survey approvals are handled in a separate system.
    This prevents system crash while keeping contract intact.
    """

    return []