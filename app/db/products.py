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

def _normalize_product_name_for_duplicate_check(value):
    cleaned = _clean_text(value).lower()
    return "".join(char for char in cleaned if char.isalnum())


def _product_name_similarity(left, right):
    from difflib import SequenceMatcher

    safe_left = _normalize_product_name_for_duplicate_check(left)
    safe_right = _normalize_product_name_for_duplicate_check(right)

    if not safe_left or not safe_right:
        return 0.0

    return SequenceMatcher(None, safe_left, safe_right).ratio()


def find_project_creation_duplicate_candidates(
    *,
    internal_name,
    market_name=None,
    product_type_key=None,
    business_group=None,
    near_threshold=0.88,
):
    """
    Return exact and near duplicate product candidates before creating a project.

    Exact duplicates are checked across all products. Near duplicates are scoped
    to the selected product type or business group so typo detection catches
    cases like "Alcie Plus" without blocking unrelated products too broadly.
    """

    submitted_names = [
        _clean_text(internal_name),
        _clean_text(market_name),
    ]
    submitted_names = [name for name in submitted_names if name]

    if not submitted_names:
        return {"exact_matches": [], "near_matches": []}

    submitted_normalized = {
        _normalize_product_name_for_duplicate_check(name)
        for name in submitted_names
        if _normalize_product_name_for_duplicate_check(name)
    }

    safe_product_type_key = _clean_text(product_type_key).lower()
    safe_business_group = _clean_text(business_group).lower()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                product_id,
                internal_name,
                market_name,
                product_type_key,
                product_type_display,
                business_group
            FROM products
            ORDER BY internal_name ASC, market_name ASC
            """
        )

        exact_matches = []
        near_matches = []
        near_match_ids = set()

        for row in cursor.fetchall():
            existing_names = [
                _clean_text(row.get("internal_name")),
                _clean_text(row.get("market_name")),
            ]
            existing_names = [name for name in existing_names if name]
            existing_normalized = {
                _normalize_product_name_for_duplicate_check(name)
                for name in existing_names
                if _normalize_product_name_for_duplicate_check(name)
            }

            if submitted_normalized.intersection(existing_normalized):
                exact_matches.append(row)
                continue

            existing_product_type_key = _clean_text(row.get("product_type_key")).lower()
            existing_business_group = _clean_text(row.get("business_group")).lower()
            same_scope = (
                bool(safe_product_type_key and safe_product_type_key == existing_product_type_key)
                or bool(safe_business_group and safe_business_group == existing_business_group)
            )

            if not same_scope:
                continue

            strongest_score = 0.0
            for submitted_name in submitted_names:
                for existing_name in existing_names:
                    strongest_score = max(
                        strongest_score,
                        _product_name_similarity(submitted_name, existing_name),
                    )

            product_id = row.get("product_id")
            if strongest_score >= near_threshold and product_id not in near_match_ids:
                near_match_ids.add(product_id)
                row["duplicate_score"] = strongest_score
                near_matches.append(row)

        near_matches = sorted(
            near_matches,
            key=lambda item: item.get("duplicate_score") or 0,
            reverse=True,
        )

        return {
            "exact_matches": exact_matches,
            "near_matches": near_matches[:5],
        }

    finally:
        cursor.close()
        conn.close()

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