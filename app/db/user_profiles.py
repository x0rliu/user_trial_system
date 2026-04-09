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
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE user_pool
            SET
                FirstName = %s,
                LastName = %s,
                PhoneNumber = %s,
                gender_hash = %s,
                birth_year_hash = %s,
                country_hash = %s,
                city_hash = %s
            WHERE user_id = %s
            """,
            (
                first_name.strip(),
                last_name.strip(),
                phone_number.strip(),
                _hash(gender),
                _hash(birth_year),
                _hash(country),
                _hash(city),
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
    """

    if not category_ids:
        return []

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

    cursor.execute(query, category_ids)
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