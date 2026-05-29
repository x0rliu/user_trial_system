from app.db.connection import get_db_connection


def _clean_text(value):
    return str(value or "").strip()


def _format_product_type_display(product_type_key):
    key = _clean_text(product_type_key).lower()

    display_by_key = {
        "accessory": "Accessory",
        "audio": "Audio",
        "camera": "Camera",
        "device": "Gaming Device",
        "dock": "Dock",
        "headset": "Headset",
        "keyboard": "Keyboard",
        "lighting": "Lighting",
        "mouse": "Mouse",
        "video": "Video Device",
        "webcam": "Webcam",
    }

    if key in display_by_key:
        return display_by_key[key]

    return key.replace("_", " ").title()


def list_product_type_options_for_creation():
    """
    Return existing product type options from the DB.

    Historical project creation should use explicit taxonomy values already present
    in products instead of inventing a new product type in the UI.
    """

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT DISTINCT
                product_type_key,
                product_type_display
            FROM products
            WHERE product_type_key IS NOT NULL
              AND TRIM(product_type_key) <> ''
            ORDER BY product_type_display ASC, product_type_key ASC
            """
        )

        options = []
        for row in cursor.fetchall():
            product_type_key = _clean_text(row.get("product_type_key")).lower()
            product_type_display = _clean_text(row.get("product_type_display"))

            if not product_type_key:
                continue

            options.append({
                "product_type_key": product_type_key,
                "product_type_display": product_type_display or _format_product_type_display(product_type_key),
            })

        return options

    finally:
        cursor.close()
        conn.close()


def list_business_group_options_for_creation():
    """
    Return existing business group options from the DB.
    """

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT DISTINCT business_group
            FROM products
            WHERE business_group IS NOT NULL
              AND TRIM(business_group) <> ''
            ORDER BY business_group ASC
            """
        )

        return [
            _clean_text(row.get("business_group"))
            for row in cursor.fetchall()
            if _clean_text(row.get("business_group"))
        ]

    finally:
        cursor.close()
        conn.close()


def product_type_key_is_valid_for_creation(product_type_key):
    safe_key = _clean_text(product_type_key).lower()
    if not safe_key:
        return False

    return any(
        option.get("product_type_key") == safe_key
        for option in list_product_type_options_for_creation()
    )


def business_group_is_valid_for_creation(business_group):
    safe_group = _clean_text(business_group)
    if not safe_group:
        return False

    return safe_group in set(list_business_group_options_for_creation())


def create_product(internal_name, market_name, product_type_key, business_group):
    internal_name = _clean_text(internal_name)
    market_name = _clean_text(market_name) or None
    product_type_key = _clean_text(product_type_key).lower()
    business_group = _clean_text(business_group)
    product_type_display = _format_product_type_display(product_type_key)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO products (
                internal_name,
                market_name,
                product_type_key,
                product_type_display,
                business_group
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            internal_name,
            market_name,
            product_type_key,
            product_type_display,
            business_group
        ))

        conn.commit()
        return cursor.lastrowid

    finally:
        cursor.close()
        conn.close()