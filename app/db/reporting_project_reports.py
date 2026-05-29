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