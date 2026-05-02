# app/db/system_office_locations.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_active_office_locations() -> list[dict]:
    """
    Returns active Logitech office/site locations for targeting dropdowns.

    Expected columns in system_office_locations:
      - OfficeID
      - OfficeName
      - City
      - StateRegion
      - Country
      - IsActive
    """

    query = """
        SELECT
            OfficeID,
            OfficeName,
            City,
            StateRegion,
            Country
        FROM system_office_locations
        WHERE IsActive = 1
        ORDER BY
            Country,
            City,
            OfficeName
    """

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()

        return rows

    finally:
        conn.close()