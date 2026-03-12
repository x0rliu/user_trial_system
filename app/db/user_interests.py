# app/db/user_interests.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_interests_by_category_ids(category_ids: list[int]):
    """
    Returns interest definition rows for the given CategoryIDs.

    Expected columns in user_interests:
      - InterestUID
      - CategoryID
      - CategoryName
      - LevelCode
      - LevelName
      - InterestCode
      - InterestDescription
    """
    if not category_ids:
        return []

    placeholders = ",".join(["%s"] * len(category_ids))

    query = f"""
        SELECT
            InterestUID,
            CategoryID,
            CategoryName,
            LevelCode,
            LevelName,
            InterestCode,
            InterestDescription
        FROM user_interests
        WHERE CategoryID IN ({placeholders})
        ORDER BY CategoryID, LevelCode
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute(query, tuple(category_ids))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows
