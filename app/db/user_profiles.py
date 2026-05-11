# app/db/user_profiles.py

import mysql.connector
from app.config.config import DB_CONFIG

def get_connection():
    return mysql.connector.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
    )

def get_profiles_by_category_ids(category_ids):
    """
    Returns raw profile definition rows for the given category IDs.
    No grouping, no interpretation.

    SECURITY NOTE:
    - Uses parameterized placeholders (%s) to prevent SQL injection
    - Validates category_ids to ensure only integers are used
    """

    if not category_ids:
        return []

    # Defensive validation
    try:
        safe_category_ids = [int(cid) for cid in category_ids]
    except (TypeError, ValueError):
        raise ValueError("Invalid category_ids")

    if not safe_category_ids:
        return []

    # Build safe placeholders for IN clause
    placeholders = ",".join(["%s"] * len(safe_category_ids))

    query = f"""
        SELECT
            ProfileUID,
            CategoryID,
            CategoryName,
            LevelCode,
            LevelDescription,
            ProfileCode,
            ProfileDescription
        FROM user_profiles
        WHERE CategoryID IN ({placeholders})
        ORDER BY CategoryID, LevelCode
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute(query, tuple(safe_category_ids))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows

def get_all_profiles():
    """
    Returns all profile definitions for dropdown usage.
    """

    query = """
        SELECT
            ProfileUID,
            CategoryName,
            LevelDescription
        FROM user_profiles
        ORDER BY CategoryName, LevelCode
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute(query)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows

def get_profile_categories():
    """
    Returns distinct profile categories for dropdown usage.
    """

    query = """
        SELECT DISTINCT
            CategoryID,
            CategoryName
        FROM user_profiles
        ORDER BY CategoryName
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute(query)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows

def get_profile_levels_by_category(category_id):
    """
    Returns all profile levels for a given category.
    """

    try:
        safe_category_id = int(category_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid category_id")

    query = """
        SELECT
            ProfileUID,
            LevelCode,
            LevelDescription
        FROM user_profiles
        WHERE CategoryID = %s
        ORDER BY LevelCode
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute(query, (safe_category_id,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows

def get_profile_levels_by_category_id(category_id: int):
    try:
        safe_category_id = int(category_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid category_id")

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            ProfileUID,
            CategoryID,
            LevelDescription
        FROM user_profiles
        WHERE CategoryID = %s
        ORDER BY LevelCode
        """,
        (safe_category_id,),
    )

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows