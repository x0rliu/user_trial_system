# app/db/dashboard_cards.py

import mysql.connector

from app.config.config import DB_CONFIG


def get_user_card_preferences(user_id: str) -> dict:
    """
    Return persisted dashboard card preferences for one user.

    Default visibility/order lives in the curated dashboard card registry.
    This table only stores explicit user overrides.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                CardKey,
                IsVisible,
                SortOrder
            FROM dashboard_user_cards
            WHERE UserID = %s
            """,
            (user_id,),
        )

        rows = cur.fetchall() or []

        preferences = {}
        for row in rows:
            card_key = row.get("CardKey")
            if not card_key:
                continue

            preferences[card_key] = {
                "is_visible": bool(row.get("IsVisible")),
                "sort_order": row.get("SortOrder"),
            }

        return preferences

    finally:
        conn.close()


def set_dashboard_card_visibility(*, user_id: str, card_key: str, is_visible: bool) -> None:
    """
    Persist one user's visibility choice for one curated dashboard card.
    Idempotent: repeated hide/show operations are safe.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO dashboard_user_cards
                (UserID, CardKey, IsVisible, SortOrder, CreatedAt, UpdatedAt)
            VALUES
                (%s, %s, %s, NULL, NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                IsVisible = VALUES(IsVisible),
                UpdatedAt = NOW()
            """,
            (user_id, card_key, 1 if is_visible else 0),
        )
        conn.commit()

    finally:
        conn.close()