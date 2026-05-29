# app/db/product_type_comparison_reports.py

from __future__ import annotations

import json

import mysql.connector
from mysql.connector import errorcode

from app.config.config import DB_CONFIG


class ProductTypeComparisonReportsTableMissing(RuntimeError):
    """Raised when the DB migration for product_type_comparison_reports has not been applied."""


def _is_missing_table_error(exc: Exception) -> bool:
    return isinstance(exc, mysql.connector.Error) and exc.errno == errorcode.ER_NO_SUCH_TABLE


def _loads_json(value: object, fallback):
    try:
        parsed = json.loads(value or "")
        return parsed if parsed is not None else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def list_latest_product_type_comparison_reports() -> list[dict]:
    """
    Return saved product-type comparison report status rows for the R&I hub.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                comparison_report_id,
                product_type_key,
                product_type_display,
                generation_version,
                data_hash,
                generated_by_user_id,
                created_at,
                updated_at
            FROM product_type_comparison_reports
            ORDER BY updated_at DESC, product_type_display ASC
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


def get_latest_product_type_comparison_report(*, product_type_display: str) -> dict:
    """
    Read the saved comparison report for one product type.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                comparison_report_id,
                product_type_key,
                product_type_display,
                comparison_report_json,
                input_payload_json,
                included_report_keys_json,
                generated_by_user_id,
                generation_version,
                data_hash,
                created_at,
                updated_at
            FROM product_type_comparison_reports
            WHERE LOWER(product_type_display) = LOWER(%s)
            LIMIT 1
            """,
            (str(product_type_display or "").strip(),),
        )

        row = cur.fetchone()
        if not row:
            return {
                "success": False,
                "report": None,
                "input_payload": None,
                "row": None,
                "error": "not_found",
            }

        report = _loads_json(row.get("comparison_report_json"), {})
        if not isinstance(report, dict):
            return {
                "success": False,
                "report": None,
                "input_payload": None,
                "row": row,
                "error": "invalid_report_json",
            }

        input_payload = _loads_json(row.get("input_payload_json"), {})
        included_report_keys = _loads_json(row.get("included_report_keys_json"), [])

        report.setdefault("metadata", {})
        report["metadata"].update({
            "comparison_report_id": row.get("comparison_report_id"),
            "product_type_key": row.get("product_type_key"),
            "product_type_display": row.get("product_type_display"),
            "generated_by_user_id": row.get("generated_by_user_id"),
            "generation_version": row.get("generation_version"),
            "data_hash": row.get("data_hash"),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
        })

        return {
            "success": True,
            "report": report,
            "input_payload": input_payload if isinstance(input_payload, dict) else {},
            "included_report_keys": included_report_keys if isinstance(included_report_keys, list) else [],
            "row": row,
            "error": None,
        }

    except Exception as exc:
        if _is_missing_table_error(exc):
            return {
                "success": False,
                "report": None,
                "input_payload": None,
                "row": None,
                "error": "table_missing",
            }
        raise

    finally:
        cur.close()
        conn.close()


def list_published_report_objects_for_product_type(*, product_type_display: str) -> list[dict]:
    """
    Return published R&I report objects for a product type, including report_json.

    First pass intentionally uses published aggregate report objects as the source.
    That keeps comparison generation bounded to what R&I already exposes.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                CONCAT('legacy_round:', har.product_id, ':', har.round_number) AS report_key,
                'legacy' AS report_source,
                'Legacy' AS report_source_label,
                'aggregate_round' AS report_scope,

                hrp.publication_id,
                hrp.published_at,
                hrp.updated_at AS publication_updated_at,

                har.aggregate_report_id,
                har.product_id,
                har.round_number,
                har.report_json,
                har.data_hash,
                har.updated_at AS report_updated_at,

                p.internal_name,
                p.market_name,
                p.product_type_key,
                p.product_type_display,
                p.business_group

            FROM historical_report_publications hrp
            JOIN historical_aggregate_reports har
                ON har.product_id = hrp.product_id
               AND har.round_number = hrp.round_number
            JOIN products p
                ON p.product_id = har.product_id

            WHERE hrp.publication_scope = 'round'
              AND hrp.status = 'published'
              AND hrp.visible_to_reporting_insights = 1
              AND LOWER(p.product_type_display) = LOWER(%s)

            ORDER BY
                hrp.published_at DESC,
                p.internal_name ASC,
                p.market_name ASC,
                har.round_number ASC
            """,
            (str(product_type_display or "").strip(),),
        )
        return cur.fetchall()

    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise

    finally:
        cur.close()
        conn.close()


def upsert_product_type_comparison_report(
    *,
    product_type_key: str,
    product_type_display: str,
    report: dict,
    input_payload: dict,
    included_report_keys: list[str],
    generated_by_user_id: str,
    generation_version: str,
    data_hash: str | None,
) -> None:
    """
    Save or replace the generated product-type comparison report.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO product_type_comparison_reports (
                product_type_key,
                product_type_display,
                comparison_report_json,
                input_payload_json,
                included_report_keys_json,
                generated_by_user_id,
                generation_version,
                data_hash
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                product_type_display = VALUES(product_type_display),
                comparison_report_json = VALUES(comparison_report_json),
                input_payload_json = VALUES(input_payload_json),
                included_report_keys_json = VALUES(included_report_keys_json),
                generated_by_user_id = VALUES(generated_by_user_id),
                generation_version = VALUES(generation_version),
                data_hash = VALUES(data_hash),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                str(product_type_key or "").strip().lower(),
                str(product_type_display or "").strip(),
                json.dumps(report, ensure_ascii=False, default=str),
                json.dumps(input_payload, ensure_ascii=False, default=str),
                json.dumps(included_report_keys, ensure_ascii=False, default=str),
                generated_by_user_id,
                generation_version,
                data_hash,
            ),
        )
        conn.commit()

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            raise ProductTypeComparisonReportsTableMissing(
                "product_type_comparison_reports table does not exist"
            ) from exc
        raise

    finally:
        cur.close()
        conn.close()