# app/db/product_taxonomy.py

from app.db.connection import get_db_connection


def _clean_text(value) -> str:
    return str(value or "").strip()


def _is_product_comparison_ready(product: dict) -> bool:
    if not product:
        return False

    return bool(
        product.get("product_id")
        and _clean_text(product.get("product_type_key"))
        and _clean_text(product.get("business_group"))
    )


def _format_product_for_comparison(row: dict) -> dict:
    product_type_key = _clean_text(row.get("product_type_key"))
    product_type_display = _clean_text(row.get("product_type_display"))
    business_group = _clean_text(row.get("business_group"))

    return {
        "product_id": row.get("product_id"),
        "internal_name": row.get("internal_name"),
        "market_name": row.get("market_name"),
        "product_type_key": product_type_key or None,
        "product_type_display": product_type_display or None,
        "business_group": business_group or None,
        "is_comparison_ready": bool(
            row.get("product_id")
            and product_type_key
            and business_group
        ),
    }


def list_products_for_comparison() -> list[dict]:
    """
    Return all products with explicit DB-backed taxonomy fields.

    Read-only. No inference.
    """

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
            ORDER BY
                product_type_key ASC,
                business_group ASC,
                internal_name ASC,
                market_name ASC,
                product_id ASC
            """
        )

        return [
            _format_product_for_comparison(row)
            for row in cursor.fetchall()
        ]

    finally:
        cursor.close()
        conn.close()


def get_product_for_comparison(product_id: int) -> dict | None:
    """
    Return one product's explicit taxonomy fields.

    Read-only. No inference.
    """

    if not product_id:
        return None

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
            WHERE product_id = %s
            LIMIT 1
            """,
            (product_id,),
        )

        row = cursor.fetchone()

        if not row:
            return None

        return _format_product_for_comparison(row)

    finally:
        cursor.close()
        conn.close()


def list_product_type_counts() -> list[dict]:
    """
    Summarize product counts by explicit product_type_key.

    Read-only. No inference.
    """

    products = list_products_for_comparison()
    product_type_map = {}

    for product in products:
        product_type_key = product.get("product_type_key")

        if not product_type_key:
            continue

        if product_type_key not in product_type_map:
            product_type_map[product_type_key] = {
                "product_type_key": product_type_key,
                "product_type_display": product.get("product_type_display"),
                "product_count": 0,
                "business_groups": set(),
            }

        product_type_map[product_type_key]["product_count"] += 1

        if product.get("business_group"):
            product_type_map[product_type_key]["business_groups"].add(
                product["business_group"]
            )

    rows = []

    for item in product_type_map.values():
        rows.append({
            "product_type_key": item["product_type_key"],
            "product_type_display": item["product_type_display"],
            "product_count": item["product_count"],
            "business_groups": sorted(item["business_groups"]),
        })

    return sorted(
        rows,
        key=lambda row: (
            row["product_type_key"] or "",
            row["product_type_display"] or "",
        ),
    )


def list_business_group_counts() -> list[dict]:
    """
    Summarize product counts by explicit business_group.

    Read-only. No inference.
    """

    products = list_products_for_comparison()
    business_group_map = {}

    for product in products:
        business_group = product.get("business_group")

        if not business_group:
            continue

        if business_group not in business_group_map:
            business_group_map[business_group] = {
                "business_group": business_group,
                "product_count": 0,
                "product_types": set(),
            }

        business_group_map[business_group]["product_count"] += 1

        if product.get("product_type_key"):
            business_group_map[business_group]["product_types"].add(
                product["product_type_key"]
            )

    rows = []

    for item in business_group_map.values():
        rows.append({
            "business_group": item["business_group"],
            "product_count": item["product_count"],
            "product_types": sorted(item["product_types"]),
        })

    return sorted(
        rows,
        key=lambda row: row["business_group"] or "",
    )


def get_product_taxonomy_audit() -> dict:
    """
    Return a DB-backed taxonomy readiness audit.

    This is intentionally read-only and conservative:
    - missing taxonomy stays missing
    - product type is never inferred from product name
    - business group is never inferred from market name or internal name
    """

    products = list_products_for_comparison()

    products_ready = [
        product
        for product in products
        if _is_product_comparison_ready(product)
    ]

    products_missing_type = [
        product
        for product in products
        if not _clean_text(product.get("product_type_key"))
    ]

    products_missing_business_group = [
        product
        for product in products
        if not _clean_text(product.get("business_group"))
    ]

    limitations = []

    if products_missing_type:
        limitations.append(
            "Some products are missing product_type_key and cannot be used for strong product-type comparison."
        )

    if products_missing_business_group:
        limitations.append(
            "Some products are missing business_group and cannot be used for business-group comparison."
        )

    if not products:
        limitations.append(
            "No products were found in the products table."
        )

    return {
        "products_total": len(products),
        "products_ready": len(products_ready),
        "products_missing_type": products_missing_type,
        "products_missing_business_group": products_missing_business_group,
        "product_types": list_product_type_counts(),
        "business_groups": list_business_group_counts(),
        "limitations": limitations,
    }