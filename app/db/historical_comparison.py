# app/db/historical_comparison.py

from app.db.connection import get_db_connection


_CONTEXT_SELECT = """
    SELECT
        htc.context_id,
        htc.product_id,
        htc.round_number,
        htc.lifecycle_stage,
        htc.trial_purpose,
        htc.internal_vs_external_mix,
        htc.invited_user_count,
        htc.description,
        htc.start_date,
        htc.end_date,
        htc.created_at,
        htc.source,
        p.internal_name,
        p.market_name,
        p.product_type_key,
        p.product_type_display,
        p.business_group,
        (
            SELECT COUNT(*)
            FROM historical_datasets hd
            WHERE hd.context_id = htc.context_id
        ) AS dataset_count
    FROM historical_trial_contexts htc
    JOIN products p
        ON p.product_id = htc.product_id
"""


def _clean_text(value) -> str:
    return str(value or "").strip()


def _format_date(value):
    if value is None:
        return None

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return value


def _format_context_row(row: dict) -> dict:
    product_type_key = _clean_text(row.get("product_type_key"))
    product_type_display = _clean_text(row.get("product_type_display"))
    business_group = _clean_text(row.get("business_group"))

    internal_name = _clean_text(row.get("internal_name"))
    market_name = _clean_text(row.get("market_name"))

    if internal_name and market_name:
        product_display_name = f"{internal_name} ({market_name})"
    elif internal_name:
        product_display_name = internal_name
    elif market_name:
        product_display_name = market_name
    else:
        product_display_name = f"Product {row.get('product_id')}"

    return {
        "context_id": row.get("context_id"),
        "product_id": row.get("product_id"),
        "product_name": product_display_name,
        "internal_name": internal_name or None,
        "market_name": market_name or None,
        "product_type_key": product_type_key or None,
        "product_type_display": product_type_display or None,
        "business_group": business_group or None,
        "round_number": row.get("round_number"),
        "lifecycle_stage": row.get("lifecycle_stage"),
        "trial_purpose": row.get("trial_purpose"),
        "internal_vs_external_mix": row.get("internal_vs_external_mix"),
        "invited_user_count": row.get("invited_user_count"),
        "description": row.get("description"),
        "start_date": _format_date(row.get("start_date")),
        "end_date": _format_date(row.get("end_date")),
        "created_at": _format_date(row.get("created_at")),
        "source": row.get("source"),
        "dataset_count": int(row.get("dataset_count") or 0),
        "is_taxonomy_ready": bool(
            row.get("product_id")
            and product_type_key
            and business_group
        ),
    }


def _normalize_context_ids(context_ids) -> list[int]:
    normalized = []

    for context_id in context_ids or []:
        try:
            normalized_id = int(context_id)
        except (TypeError, ValueError):
            continue

        if normalized_id not in normalized:
            normalized.append(normalized_id)

    return normalized


def get_historical_context_for_comparison(context_id: int) -> dict | None:
    """
    Return one historical context with explicit product taxonomy fields.

    Read-only. No inference.
    """

    if not context_id:
        return None

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            _CONTEXT_SELECT + """
            WHERE htc.context_id = %s
            LIMIT 1
            """,
            (context_id,),
        )

        row = cursor.fetchone()

        if not row:
            return None

        return _format_context_row(row)

    finally:
        cursor.close()
        conn.close()


def list_historical_context_candidates(exclude_context_id: int | None = None) -> list[dict]:
    """
    Return historical comparison candidates with explicit product taxonomy fields.

    Read-only. No inference.
    """

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        params = []
        where_sql = ""

        if exclude_context_id:
            where_sql = "WHERE htc.context_id <> %s"
            params.append(exclude_context_id)

        cursor.execute(
            _CONTEXT_SELECT + f"""
            {where_sql}
            ORDER BY
                htc.created_at DESC,
                htc.context_id DESC
            """,
            tuple(params),
        )

        return [
            _format_context_row(row)
            for row in cursor.fetchall()
        ]

    finally:
        cursor.close()
        conn.close()


def get_historical_metrics_for_contexts(context_ids: list[int]) -> dict[int, dict]:
    """
    Return metrics keyed by context_id.

    Read-only.
    """

    normalized_ids = _normalize_context_ids(context_ids)
    if not normalized_ids:
        return {}

    placeholders = ",".join(["%s"] * len(normalized_ids))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            f"""
            SELECT
                context_id,
                total_responses,
                survey_1_responses,
                survey_2_responses,
                completion_rate,
                drop_off_rate,
                first_response_at,
                last_response_at,
                response_window_days,
                trial_start_date,
                trial_end_date,
                avg_response_length,
                median_response_length,
                empty_response_rate,
                quant_question_count,
                qual_question_count,
                generation_version
            FROM historical_trial_metrics
            WHERE context_id IN ({placeholders})
            """,
            tuple(normalized_ids),
        )

        rows = cursor.fetchall()
        return {
            row["context_id"]: row
            for row in rows
        }

    finally:
        cursor.close()
        conn.close()


def get_latest_historical_insights_for_contexts(context_ids: list[int]) -> dict[int, list[dict]]:
    """
    Return insight rows from the latest insight run per context.

    Read-only.
    """

    normalized_ids = _normalize_context_ids(context_ids)
    if not normalized_ids:
        return {}

    placeholders = ",".join(["%s"] * len(normalized_ids))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            f"""
            SELECT
                hti.id,
                hti.insight_run_id,
                hti.context_id,
                hti.section_name,
                hti.insight_type,
                hti.insight_summary,
                hti.insight_json,
                hti.source_sample_size,
                hti.filters_applied,
                hti.created_at,
                hir.trigger_type,
                hir.generation_version,
                hir.generated_at
            FROM historical_trial_insights hti
            JOIN historical_insight_runs hir
                ON hir.insight_run_id = hti.insight_run_id
            JOIN (
                SELECT
                    context_id,
                    MAX(generated_at) AS latest_generated_at
                FROM historical_insight_runs
                WHERE context_id IN ({placeholders})
                GROUP BY context_id
            ) latest
                ON latest.context_id = hir.context_id
               AND latest.latest_generated_at = hir.generated_at
            WHERE hti.context_id IN ({placeholders})
            ORDER BY
                hti.context_id ASC,
                hti.created_at ASC,
                hti.id ASC
            """,
            tuple(normalized_ids + normalized_ids),
        )

        grouped = {}

        for row in cursor.fetchall():
            context_id = row["context_id"]
            grouped.setdefault(context_id, [])
            grouped[context_id].append(row)

        return grouped

    finally:
        cursor.close()
        conn.close()