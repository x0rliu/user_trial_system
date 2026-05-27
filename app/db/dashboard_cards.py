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

def set_dashboard_card_sort_orders(*, user_id: str, ordered_card_keys: list[str]) -> None:
    """
    Persist one user's explicit dashboard card order.

    The dashboard registry decides which card keys are valid for a role.
    The handler passes only validated, currently visible keys here.
    SortOrder is stored in spaced increments so future inserts can fit between rows
    if needed.
    """

    clean_keys = []
    seen = set()
    for card_key in ordered_card_keys:
        safe_key = str(card_key or "").strip()
        if not safe_key or safe_key in seen:
            continue
        clean_keys.append(safe_key)
        seen.add(safe_key)

    if not clean_keys:
        return

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        for index, card_key in enumerate(clean_keys, start=1):
            cur.execute(
                """
                INSERT INTO dashboard_user_cards
                    (UserID, CardKey, IsVisible, SortOrder, CreatedAt, UpdatedAt)
                VALUES
                    (%s, %s, 1, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE
                    SortOrder = VALUES(SortOrder),
                    UpdatedAt = NOW()
                """,
                (user_id, card_key, index * 10),
            )

        conn.commit()

    finally:
        conn.close()