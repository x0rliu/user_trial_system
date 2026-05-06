import hashlib
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

def _hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()

def update_basic_demographics(
    user_id: str,
    first_name: str,
    last_name: str,
    phone_number: str,
    gender: str,
    birth_year: str,
    country: str,
    city: str,
):
    """
    Legacy compatibility updater for basic demographics.

    Important:
    - phone_number is intentionally ignored.
    - user_pool.PhoneNumber is deprecated and should not receive new writes.
    - Account mobile is now stored through:
        MobileCountryCode
        MobileNational
        MobileE164
    - Shipping phone remains trial-specific and belongs on project/shipping records.
    """

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE user_pool
            SET
                FirstName = %s,
                LastName = %s,
                Gender = %s,
                BirthYear = %s,
                CountryCode = %s,
                City = %s,
                UpdatedAt = NOW()
            WHERE user_id = %s
            """,
            (
                first_name.strip(),
                last_name.strip(),
                gender.strip(),
                birth_year,
                country.strip(),
                city.strip() or None,
                user_id,
            )
        )
        conn.commit()
    finally:
        conn.close()

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
    if not all(isinstance(cid, int) for cid in category_ids):
        raise ValueError("Invalid category_ids")

    # Build safe placeholders for IN clause
    placeholders = ",".join(["%s"] * len(category_ids))

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

    cursor.execute(query, tuple(category_ids))
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

    cursor.execute(query, (category_id,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows

def get_profile_levels_by_category_id(category_id: int):
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
        (category_id,),
    )

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows