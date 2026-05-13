# app/services/product_taxonomy_service.py

from app.db.product_taxonomy import (
    get_product_for_comparison,
    get_product_taxonomy_audit,
    list_business_group_counts,
    list_product_type_counts,
    list_products_for_comparison,
)


def _clean_text(value) -> str:
    return str(value or "").strip()


def _product_display_name(product: dict | None) -> str:
    if not product:
        return "Unknown product"

    internal_name = _clean_text(product.get("internal_name"))
    market_name = _clean_text(product.get("market_name"))

    if internal_name and market_name:
        return f"{internal_name} ({market_name})"

    if internal_name:
        return internal_name

    if market_name:
        return market_name

    product_id = product.get("product_id")
    if product_id:
        return f"Product {product_id}"

    return "Unknown product"


def _taxonomy_limitations_for_product(product: dict | None) -> list[str]:
    limitations = []

    if not product:
        return ["Product was not found."]

    if not product.get("product_id"):
        limitations.append("Product ID is missing.")

    if not _clean_text(product.get("product_type_key")):
        limitations.append(
            "Product type is missing, so this product cannot be used for strong product-type comparison."
        )

    if not _clean_text(product.get("business_group")):
        limitations.append(
            "Business group is missing, so this product cannot be used for business-group comparison."
        )

    return limitations


def build_product_taxonomy_audit() -> dict:
    """
    Build a product taxonomy readiness audit.

    Read-only.
    No inference.
    No recommendations.
    """

    audit = get_product_taxonomy_audit()

    products_total = int(audit.get("products_total") or 0)
    products_ready = int(audit.get("products_ready") or 0)

    readiness_rate = None
    if products_total > 0:
        readiness_rate = round((products_ready / products_total) * 100, 1)

    return {
        "products_total": products_total,
        "products_ready": products_ready,
        "readiness_rate": readiness_rate,
        "products_missing_type": audit.get("products_missing_type") or [],
        "products_missing_business_group": audit.get("products_missing_business_group") or [],
        "product_types": audit.get("product_types") or [],
        "business_groups": audit.get("business_groups") or [],
        "limitations": audit.get("limitations") or [],
    }


def build_product_comparison_readiness(product_id: int) -> dict:
    """
    Return whether one product is ready for comparison.

    This does not infer missing taxonomy.
    """

    product = get_product_for_comparison(product_id)

    if not product:
        return {
            "product": None,
            "display_name": "Unknown product",
            "is_comparison_ready": False,
            "comparison_basis": {
                "product_type_key": None,
                "product_type_display": None,
                "business_group": None,
            },
            "limitations": ["Product was not found."],
        }

    limitations = _taxonomy_limitations_for_product(product)

    return {
        "product": product,
        "display_name": _product_display_name(product),
        "is_comparison_ready": bool(product.get("is_comparison_ready")),
        "comparison_basis": {
            "product_type_key": product.get("product_type_key"),
            "product_type_display": product.get("product_type_display"),
            "business_group": product.get("business_group"),
        },
        "limitations": limitations,
    }


def build_product_taxonomy_summary() -> dict:
    """
    Return a compact taxonomy summary for comparison planning.

    Read-only.
    """

    products = list_products_for_comparison()
    product_types = list_product_type_counts()
    business_groups = list_business_group_counts()

    ready_products = [
        product
        for product in products
        if product.get("is_comparison_ready")
    ]

    missing_type_count = len([
        product
        for product in products
        if not _clean_text(product.get("product_type_key"))
    ])

    missing_business_group_count = len([
        product
        for product in products
        if not _clean_text(product.get("business_group"))
    ])

    return {
        "products_total": len(products),
        "products_ready": len(ready_products),
        "missing_type_count": missing_type_count,
        "missing_business_group_count": missing_business_group_count,
        "product_type_count": len(product_types),
        "business_group_count": len(business_groups),
        "product_types": product_types,
        "business_groups": business_groups,
        "limitations": [
            limitation
            for limitation in [
                (
                    "Some products are missing product_type_key."
                    if missing_type_count > 0 else None
                ),
                (
                    "Some products are missing business_group."
                    if missing_business_group_count > 0 else None
                ),
                (
                    "No products are currently comparison-ready."
                    if products and not ready_products else None
                ),
                (
                    "No products were found."
                    if not products else None
                ),
            ]
            if limitation
        ],
    }