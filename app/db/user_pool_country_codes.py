# app/db/user_pool_country_codes.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_country_codes():
    """
    Returns all country codes for demographic dropdown.

    Expected columns in user_pool_country_codes:
      - CountryCode
      - CountryName
      - Region
    """

    query = """
        SELECT
            CountryCode,
            CountryName,
            Region
        FROM user_pool_country_codes
        ORDER BY CountryName
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute(query)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows


def get_user_country(user_id: str):

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT CountryCode
            FROM user_pool_country_codes
            WHERE user_id = %s
            LIMIT 1
        """, (user_id,))

        row = cur.fetchone()

        if not row:
            return None

        return row["CountryCode"]

    finally:
        conn.close()