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


def _decorate_source_report_rows(rows: list[dict]) -> list[dict]:
    decorated = []

    for row in rows or []:
        report_json = _loads_json(row.pop("source_report_json", None), {})
        if not isinstance(report_json, dict):
            report_json = {}

        row["source_report_json"] = report_json
        row["has_saved_report_json"] = bool(report_json)

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

        return _decorate_source_report_rows(cur.fetchall())

    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise

    finally:
        cur.close()
        conn.close()