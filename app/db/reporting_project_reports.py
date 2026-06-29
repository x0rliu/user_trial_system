# app/db/reporting_project_reports.py

from __future__ import annotations

import json

import mysql.connector
from mysql.connector import errorcode

from app.config.config import DB_CONFIG


class ReportingProjectReportsTableMissing(RuntimeError):
    """Raised when the DB migration for reporting_project_reports has not been applied."""


def _is_missing_table_error(exc: Exception) -> bool:
    return isinstance(exc, mysql.connector.Error) and exc.errno == errorcode.ER_NO_SUCH_TABLE


def _loads_json(value: object, fallback):
    try:
        parsed = json.loads(value or "")
        return parsed if parsed is not None else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def list_latest_reporting_project_reports() -> list[dict]:
    """
    Return saved project-level report status rows for the R&I Projects view.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                project_report_id,
                project_key,
                project_source,
                project_label,
                internal_name,
                market_name,
                product_type_display,
                business_group,
                generation_version,
                data_hash,
                generated_by_user_id,
                created_at,
                updated_at
            FROM reporting_project_reports
            ORDER BY updated_at DESC, project_label ASC
            """
        )
        return cur.fetchall()

    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise

    finally:
        cur.close()
        conn.close()


def get_reporting_project_report_for_reporting_insights(*, project_key: str) -> dict:
    """
    Return one saved project-level report for the read-only Reporting & Insights view.
    """

    safe_project_key = str(project_key or "").strip()
    if not safe_project_key:
        return {"success": False, "error": "missing_project_key", "report": None, "row": None}

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                project_report_id,
                project_key,
                project_source,
                project_label,
                internal_name,
                market_name,
                product_type_display,
                business_group,
                project_report_json,
                input_payload_json,
                included_report_keys_json,
                generated_by_user_id,
                generation_version,
                data_hash,
                created_at,
                updated_at
            FROM reporting_project_reports
            WHERE project_key = %s
            LIMIT 1
            """,
            (safe_project_key,),
        )
        row = cur.fetchone()

        if not row:
            return {"success": False, "error": "not_found", "report": None, "row": None}

        report = _loads_json(row.get("project_report_json"), {})
        if not isinstance(report, dict):
            return {"success": False, "error": "invalid_report_json", "report": None, "row": row}

        report.setdefault("metadata", {})
        report["metadata"].update({
            "project_report_id": row.get("project_report_id"),
            "project_key": row.get("project_key"),
            "project_source": row.get("project_source"),
            "generation_version": row.get("generation_version"),
            "data_hash": row.get("data_hash"),
            "generated_by_user_id": row.get("generated_by_user_id"),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
            "report_source": "project_report",
            "report_source_label": "Project Report",
        })

        return {"success": True, "error": None, "report": report, "row": row}

    except Exception as exc:
        if _is_missing_table_error(exc):
            return {"success": False, "error": "table_missing", "report": None, "row": None}
        raise

    finally:
        cur.close()
        conn.close()


def upsert_reporting_project_report(
    *,
    project_key: str,
    project_source: str,
    project_label: str,
    internal_name: str,
    market_name: str,
    product_type_display: str,
    business_group: str,
    report: dict,
    input_payload: dict,
    included_report_keys: list[str],
    generated_by_user_id: str,
    generation_version: str,
    data_hash: str,
) -> None:
    """
    Save or replace one generated project-level report.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO reporting_project_reports (
                project_key,
                project_source,
                project_label,
                internal_name,
                market_name,
                product_type_display,
                business_group,
                project_report_json,
                input_payload_json,
                included_report_keys_json,
                generated_by_user_id,
                generation_version,
                data_hash
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                project_source = VALUES(project_source),
                project_label = VALUES(project_label),
                internal_name = VALUES(internal_name),
                market_name = VALUES(market_name),
                product_type_display = VALUES(product_type_display),
                business_group = VALUES(business_group),
                project_report_json = VALUES(project_report_json),
                input_payload_json = VALUES(input_payload_json),
                included_report_keys_json = VALUES(included_report_keys_json),
                generated_by_user_id = VALUES(generated_by_user_id),
                generation_version = VALUES(generation_version),
                data_hash = VALUES(data_hash),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                str(project_key or "").strip(),
                str(project_source or "").strip(),
                str(project_label or "").strip(),
                str(internal_name or "").strip(),
                str(market_name or "").strip(),
                str(product_type_display or "").strip(),
                str(business_group or "").strip(),
                json.dumps(report or {}, ensure_ascii=False),
                json.dumps(input_payload or {}, ensure_ascii=False),
                json.dumps(included_report_keys or [], ensure_ascii=False),
                generated_by_user_id,
                generation_version,
                data_hash,
            ),
        )
        conn.commit()

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            raise ReportingProjectReportsTableMissing(
                "reporting_project_reports table does not exist"
            ) from exc
        raise

    finally:
        cur.close()
        conn.close()


def _int_or_none(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _project_key_parts(project_key: str) -> tuple[str, object | None]:
    safe_project_key = str(project_key or "").strip()

    if safe_project_key.startswith("product:"):
        product_id = _int_or_none(safe_project_key.split(":", 1)[1])
        if product_id is not None:
            return "product", product_id

    if safe_project_key.startswith("project:"):
        project_id = safe_project_key.split(":", 1)[1].strip()
        if project_id:
            return "project", project_id

    return "unsupported", None


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rounded_metric(value: object, digits: int = 2) -> float | None:
    numeric_value = _float_or_none(value)
    if numeric_value is None:
        return None
    return round(numeric_value, digits)


def _average_metric(values: list[float]) -> float | None:
    numeric_values = [
        _float_or_none(value)
        for value in values
        if _float_or_none(value) is not None
    ]

    if not numeric_values:
        return None

    return round(sum(numeric_values) / len(numeric_values), 2)


def _nps_metric(values: list[float]) -> float | None:
    numeric_values = [
        _float_or_none(value)
        for value in values
        if _float_or_none(value) is not None
    ]

    if not numeric_values:
        return None

    promoters = len([value for value in numeric_values if value >= 9])
    detractors = len([value for value in numeric_values if value <= 6])
    total = len(numeric_values)

    return round(((promoters / total) * 100) - ((detractors / total) * 100), 1)


def _is_star_rating_question(question_text: object) -> bool:
    text = str(question_text or "").lower()
    return (
        "star" in text
        and "product" in text
        and ("overall" in text or "rate" in text)
    )


def _is_nps_question(question_text: object, values: list[float]) -> bool:
    text = str(question_text or "").lower()
    max_value = max([_float_or_none(value) or 0 for value in values] or [0])

    return (
        "recommend" in text
        and ("friend" in text or "colleague" in text or "product" in text)
        and max_value > 5
    )


def _is_ready_for_sales_question(question_text: object) -> bool:
    text = str(question_text or "").lower()
    return (
        "ready" in text
        and (
            "market" in text
            or "release" in text
            or "sales" in text
        )
    )


def _group_numeric_validation_answers(rows: list[dict]) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}

    for row in rows or []:
        context_id = _int_or_none(row.get("context_id"))
        if context_id is None:
            continue

        grouped.setdefault(context_id, []).append(row)

    return grouped


def _group_option_validation_answers(rows: list[dict]) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}

    for row in rows or []:
        context_id = _int_or_none(row.get("context_id"))
        if context_id is None:
            continue

        grouped.setdefault(context_id, []).append(row)

    return grouped


def _numeric_question_groups(rows: list[dict]) -> list[dict]:
    grouped = {}

    for row in rows or []:
        key = (
            _int_or_none(row.get("question_position")) or 0,
            str(row.get("question_text") or "").strip(),
        )

        if key not in grouped:
            grouped[key] = {
                "question_position": key[0],
                "question_text": key[1],
                "dataset_id": row.get("dataset_id"),
                "dataset_type": row.get("dataset_type"),
                "values": [],
            }

        numeric_value = _float_or_none(row.get("answer_numeric"))
        if numeric_value is not None:
            grouped[key]["values"].append(numeric_value)

    return [
        value for value in grouped.values()
        if value.get("values")
    ]


def _ready_for_sales_metric(rows: list[dict]) -> dict:
    yes_count = 0
    no_count = 0
    question_text = ""

    for row in rows or []:
        current_question_text = str(row.get("question_text") or "").strip()
        if not _is_ready_for_sales_question(current_question_text):
            continue

        answer_value = str(row.get("answer_value") or "").strip().lower()
        question_text = current_question_text or question_text

        if answer_value == "yes":
            yes_count += 1
        elif answer_value == "no":
            no_count += 1

    total = yes_count + no_count
    if total <= 0:
        return {}

    return {
        "question_text": question_text,
        "yes_count": yes_count,
        "no_count": no_count,
        "count": total,
        "value": round((yes_count / total) * 100, 2),
    }


def _build_validation_kpis_payload(
    *,
    source_row: dict,
    numeric_rows: list[dict],
    option_rows: list[dict],
) -> dict:
    numeric_groups = _numeric_question_groups(numeric_rows)

    star_group = None
    nps_group = None

    for group in numeric_groups:
        question_text = group.get("question_text")
        values = group.get("values") or []

        if star_group is None and _is_star_rating_question(question_text):
            star_group = group

        if nps_group is None and _is_nps_question(question_text, values):
            nps_group = group

    ready_for_sales = _ready_for_sales_metric(option_rows)

    kpis = {}
    kpi_questions = []

    if star_group:
        values = star_group.get("values") or []
        kpis["star_rating"] = _average_metric(values)
        kpis["star_rating_count"] = len(values)
        kpi_questions.append({
            "kpi_key": "star_rating",
            "question_position": star_group.get("question_position"),
            "question_text": star_group.get("question_text"),
            "value": kpis["star_rating"],
            "count": kpis["star_rating_count"],
        })

    if nps_group:
        values = nps_group.get("values") or []
        kpis["nps"] = _nps_metric(values)
        kpis["nps_count"] = len(values)
        kpi_questions.append({
            "kpi_key": "nps",
            "question_position": nps_group.get("question_position"),
            "question_text": nps_group.get("question_text"),
            "value": kpis["nps"],
            "count": kpis["nps_count"],
        })

    if ready_for_sales:
        kpis["ready_for_sales"] = ready_for_sales.get("value")
        kpis["ready_for_sales_count"] = ready_for_sales.get("count")
        kpi_questions.append({
            "kpi_key": "ready_for_sales",
            "question_position": None,
            "question_text": ready_for_sales.get("question_text"),
            "value": ready_for_sales.get("value"),
            "count": ready_for_sales.get("count"),
            "yes_count": ready_for_sales.get("yes_count"),
            "no_count": ready_for_sales.get("no_count"),
        })

    if not kpis:
        return {}

    round_number = _int_or_none(source_row.get("round_number"))
    round_label = f"Round {round_number}" if round_number is not None else "Validation Survey"

    return {
        "source_type": "legacy_validation_survey",
        "source_label": round_label,
        "report_key": str(source_row.get("report_key") or "").strip(),
        "context_id": source_row.get("context_id"),
        "dataset_id": source_row.get("dataset_id"),
        "round_number": round_number,
        "report_scope": source_row.get("report_scope") or "survey",
        "kpis": kpis,
        "kpi_questions": kpi_questions,
    }


def _attach_legacy_survey_validation_kpis(cur, rows: list[dict]) -> list[dict]:
    context_ids = sorted({
        _int_or_none(row.get("context_id"))
        for row in rows or []
        if str(row.get("report_source") or "").strip() == "legacy_survey"
        and _int_or_none(row.get("context_id")) is not None
    })

    if not context_ids:
        return rows

    placeholders = ", ".join(["%s"] * len(context_ids))

    cur.execute(
        f"""
        SELECT
            hd.context_id,
            hd.dataset_id,
            hd.dataset_type,
            hsa.question_position,
            hsa.question_text,
            hsa.answer_numeric
        FROM historical_datasets hd
        JOIN historical_survey_answers hsa
            ON hsa.dataset_id = hd.dataset_id
        WHERE hd.context_id IN ({placeholders})
          AND hsa.answer_numeric IS NOT NULL
        ORDER BY
            hd.context_id,
            hsa.question_position,
            hsa.id
        """,
        tuple(context_ids),
    )
    numeric_rows_by_context = _group_numeric_validation_answers(cur.fetchall())

    cur.execute(
        f"""
        SELECT
            hd.context_id,
            hd.dataset_id,
            hd.dataset_type,
            hsa.question_position,
            hsa.question_text,
            COALESCE(NULLIF(hsa.answer_option, ''), hsa.answer_text) AS answer_value
        FROM historical_datasets hd
        JOIN historical_survey_answers hsa
            ON hsa.dataset_id = hd.dataset_id
        WHERE hd.context_id IN ({placeholders})
          AND hsa.answer_numeric IS NULL
          AND COALESCE(NULLIF(hsa.answer_option, ''), hsa.answer_text) IS NOT NULL
        ORDER BY
            hd.context_id,
            hsa.question_position,
            hsa.id
        """,
        tuple(context_ids),
    )
    option_rows_by_context = _group_option_validation_answers(cur.fetchall())

    for row in rows or []:
        if str(row.get("report_source") or "").strip() != "legacy_survey":
            continue

        context_id = _int_or_none(row.get("context_id"))
        if context_id is None:
            continue

        payload = _build_validation_kpis_payload(
            source_row=row,
            numeric_rows=numeric_rows_by_context.get(context_id, []),
            option_rows=option_rows_by_context.get(context_id, []),
        )

        if payload:
            row["validation_kpis_json"] = json.dumps(payload, default=str)

    return rows


def _decorate_source_report_rows(rows: list[dict]) -> list[dict]:
    decorated = []

    for row in rows or []:
        report_json = _loads_json(row.pop("source_report_json", None), {})
        if not isinstance(report_json, dict):
            report_json = {}

        validation_kpis = _loads_json(row.pop("validation_kpis_json", None), {})
        if not isinstance(validation_kpis, dict):
            validation_kpis = {}

        row["source_report_json"] = report_json
        row["has_saved_report_json"] = bool(report_json)
        row["validation_kpis"] = validation_kpis
        row["has_validation_kpis"] = bool(validation_kpis.get("kpis"))

        product_id = _int_or_none(row.get("product_id"))
        context_id = _int_or_none(row.get("context_id"))
        round_id = _int_or_none(row.get("round_id"))
        round_number = _int_or_none(row.get("round_number"))
        report_source = str(row.get("report_source") or "").strip()

        if report_source == "legacy" and product_id is not None and round_number is not None:
            row["report_href"] = (
                f"/reporting/insights/rounds/report?product_id={product_id}"
                f"&round_number={round_number}"
            )
        elif report_source == "legacy_survey" and context_id is not None:
            row["report_href"] = f"/historical/context?context_id={context_id}"
        elif report_source == "product_trial" and round_id is not None:
            row["report_href"] = f"/reporting/insights/product-trial-report?round_id={round_id}"
        else:
            row["report_href"] = ""

        decorated.append(row)

    return decorated


def list_reporting_project_source_reports_for_generation(*, project_key: str) -> list[dict]:
    """
    Return published source reports for one project report generation pass.

    This is intentionally read-only. It reads saved report JSON where the DB has
    a saved report artifact and does not infer project conclusions from raw
    answer-row counts.
    """

    key_type, key_value = _project_key_parts(project_key)
    if key_type == "unsupported" or key_value is None:
        return []

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        if key_type == "product":
            cur.execute(
                """
                SELECT
                    CONCAT('legacy_round:', har.product_id, ':', har.round_number) AS report_key,
                    'legacy' AS report_source,
                    'Legacy' AS report_source_label,
                    'aggregate_round' AS report_scope,

                    hrp.publication_id,
                    hrp.published_at,
                    hrp.updated_at,

                    har.aggregate_report_id AS source_report_id,
                    NULL AS context_id,
                    NULL AS dataset_id,
                    har.product_id,
                    NULL AS project_id,
                    NULL AS round_id,
                    har.round_number,

                    p.internal_name,
                    p.market_name,
                    p.product_type_display,
                    p.business_group,

                    COALESCE(JSON_LENGTH(JSON_EXTRACT(har.report_json, '$.source_surveys')), 0) AS survey_count,
                    COALESCE(JSON_LENGTH(JSON_EXTRACT(har.report_json, '$.source_surveys')), 0) AS dataset_count,
                    COALESCE(JSON_LENGTH(JSON_EXTRACT(har.report_json, '$.sections')), 0) AS section_count,
                    COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(har.report_json, '$.summary.answer_count')) AS UNSIGNED), 0) AS answer_count,
                    COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(har.report_json, '$.summary.response_count')) AS UNSIGNED), 0) AS response_count,
                    1 AS round_count,

                    har.report_json AS source_report_json

                FROM historical_report_publications hrp
                JOIN historical_aggregate_reports har
                    ON har.product_id = hrp.product_id
                   AND har.round_number = hrp.round_number
                JOIN products p
                    ON p.product_id = har.product_id

                WHERE hrp.publication_scope = 'round'
                  AND hrp.status = 'published'
                  AND hrp.visible_to_reporting_insights = 1
                  AND har.product_id = %s

                UNION ALL

                SELECT
                    CONCAT('legacy_survey:', hc.context_id) AS report_key,
                    'legacy_survey' AS report_source,
                    'Legacy Survey' AS report_source_label,
                    'survey' AS report_scope,

                    hrp.publication_id,
                    hrp.published_at,
                    hrp.updated_at,

                    NULL AS source_report_id,
                    hc.context_id,
                    hd.dataset_id,
                    hc.product_id,
                    NULL AS project_id,
                    NULL AS round_id,
                    COALESCE(hc.round_number, hd.round_number) AS round_number,

                    p.internal_name,
                    p.market_name,
                    p.product_type_display,
                    p.business_group,

                    1 AS survey_count,
                    1 AS dataset_count,
                    0 AS section_count,
                    COUNT(ha.id) AS answer_count,
                    COUNT(DISTINCT ha.response_group_id) AS response_count,
                    1 AS round_count,

                    NULL AS source_report_json

                FROM historical_report_publications hrp
                JOIN historical_trial_contexts hc
                    ON hc.context_id = hrp.context_id
                JOIN historical_datasets hd
                    ON hd.context_id = hc.context_id
                JOIN products p
                    ON p.product_id = hc.product_id
                LEFT JOIN historical_survey_answers ha
                    ON ha.dataset_id = hd.dataset_id

                WHERE hrp.publication_scope = 'survey'
                  AND hrp.status = 'published'
                  AND hrp.visible_to_reporting_insights = 1
                  AND hc.product_id = %s

                GROUP BY
                    report_key,
                    report_source,
                    report_source_label,
                    report_scope,
                    hrp.publication_id,
                    hrp.published_at,
                    hrp.updated_at,
                    hc.context_id,
                    hd.dataset_id,
                    hc.product_id,
                    hc.round_number,
                    hd.round_number,
                    p.internal_name,
                    p.market_name,
                    p.product_type_display,
                    p.business_group

                ORDER BY
                    round_number ASC,
                    published_at ASC,
                    report_key ASC
                """,
                (int(key_value), int(key_value)),
            )
        else:
            cur.execute(
                """
                SELECT
                    CONCAT('product_trial_round:', ptr.project_id, ':', ptr.round_id) AS report_key,
                    'product_trial' AS report_source,
                    'Product Trial' AS report_source_label,
                    'product_trial_round' AS report_scope,

                    NULL AS publication_id,
                    ptr.published_at,
                    ptr.updated_at,

                    ptr.report_id AS source_report_id,
                    NULL AS context_id,
                    NULL AS dataset_id,
                    NULL AS product_id,
                    ptr.project_id,
                    ptr.round_id,
                    pr.RoundNumber AS round_number,

                    pp.ProjectName AS internal_name,
                    pp.MarketName AS market_name,
                    pp.ProductType AS product_type_display,
                    pp.BusinessGroup AS business_group,

                    COALESCE(JSON_LENGTH(JSON_EXTRACT(ptr.report_json, '$.source_surveys')), 0) AS survey_count,
                    COALESCE(JSON_LENGTH(JSON_EXTRACT(ptr.report_json, '$.source_surveys')), 0) AS dataset_count,
                    COALESCE(JSON_LENGTH(JSON_EXTRACT(ptr.report_json, '$.sections')), 0) AS section_count,
                    COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(ptr.report_json, '$.summary.answer_count')) AS UNSIGNED), 0) AS answer_count,
                    COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(ptr.report_json, '$.summary.response_count')) AS UNSIGNED), 0) AS response_count,
                    1 AS round_count,

                    ptr.report_json AS source_report_json

                FROM product_trial_reports ptr
                JOIN project_rounds pr
                    ON pr.RoundID = ptr.round_id
                JOIN project_projects pp
                    ON pp.ProjectID = ptr.project_id

                WHERE ptr.publication_status = 'published'
                  AND ptr.visible_to_reporting_insights = 1
                  AND ptr.project_id = %s

                ORDER BY
                    pr.RoundNumber ASC,
                    ptr.published_at ASC,
                    ptr.report_id ASC
                """,
                (str(key_value),),
            )

        rows = cur.fetchall()
        rows = _attach_legacy_survey_validation_kpis(cur, rows)
        return _decorate_source_report_rows(rows)

    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise

    finally:
        cur.close()
        conn.close()