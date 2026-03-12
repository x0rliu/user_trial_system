def hydrate_project_from_db(*, project_row: dict, round_row: dict):
    """
    Canonical DB → view hydration.
    DB is authoritative.
    """

    return {
        "project_id": project_row["ProjectID"],
        "basics": {
            "project_name": project_row["ProjectName"],
            "market_name": project_row.get("MarketName"),
            "business_group": project_row.get("BusinessGroup"),
            "product_category": project_row.get("ProductType"),
            "purpose": project_row.get("Description"),
        },
        "timing_scope": {
            "shipping_date": round_row.get("StartDate"),
            "gate_x_date": project_row.get("GateX_Date"),
            "regions": round_row.get("Region"),
            "min_age": round_row.get("MinAge"),
            "max_age": round_row.get("MaxAge"),
        },
        "meta": {
            "project_status": project_row.get("ProjectStatus"),
            "round_status": round_row.get("Status"),
            "round_number": round_row.get("RoundNumber"),
            "round_id": round_row.get("RoundID"),
        },
    }
