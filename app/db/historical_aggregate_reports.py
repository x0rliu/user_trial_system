# app/db/historical_aggregate_reports.py

from __future__ import annotations

import json

import mysql.connector
from mysql.connector import errorcode

from app.config.config import DB_CONFIG


class HistoricalAggregateReportsTableMissing(RuntimeError):
    """Raised when the DB migration for historical_aggregate_reports has not been applied."""


def _is_missing_table_error(exc: Exception) -> bool:
    return isinstance(exc, mysql.connector.Error) and exc.errno == errorcode.ER_NO_SUCH_TABLE


def _round_publication_key(*, product_id: int, round_number: int) -> str:
    return f"legacy_round:{int(product_id)}:{int(round_number)}"


def get_historical_aggregate_report(*, product_id: int, round_number: int) -> dict:
    """
    Read the saved aggregate report for one legacy product round.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                aggregate_report_id,
                product_id,
                round_number,
                report_json,
                generated_by_user_id,
                generation_version,
                data_hash,
                created_at,
                updated_at
            FROM historical_aggregate_reports
            WHERE product_id = %s
              AND round_number = %s
            LIMIT 1
            """,
            (int(product_id), int(round_number)),
        )

        row = cur.fetchone()
        if not row:
            return {
                "success": False,
                "report": None,
                "row": None,
                "error": "not_found",
            }

        try:
            report = json.loads(row.get("report_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            return {
                "success": False,
                "report": None,
                "row": row,
                "error": "invalid_report_json",
            }

        if not isinstance(report, dict):
            return {
                "success": False,
                "report": None,
                "row": row,
                "error": "invalid_report_shape",
            }

        report.setdefault("metadata", {})
        report["metadata"].update({
            "aggregate_report_id": row.get("aggregate_report_id"),
            "product_id": row.get("product_id"),
            "round_number": row.get("round_number"),
            "generated_by_user_id": row.get("generated_by_user_id"),
            "generation_version": row.get("generation_version"),
            "data_hash": row.get("data_hash"),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
        })

        return {
            "success": True,
            "report": report,
            "row": row,
            "error": None,
        }

    except Exception as exc:
        if _is_missing_table_error(exc):
            return {
                "success": False,
                "report": None,
                "row": None,
                "error": "table_missing",
            }
        raise

    finally:
        cur.close()
        conn.close()


def upsert_historical_aggregate_report(
    *,
    product_id: int,
    round_number: int,
    report: dict,
    generated_by_user_id: str,
    generation_version: str,
    data_hash: str | None,
) -> None:
    """
    Save or replace the generated aggregate report for one legacy product round.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO historical_aggregate_reports (
                product_id,
                round_number,
                report_json,
                generated_by_user_id,
                generation_version,
                data_hash
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                report_json = VALUES(report_json),
                generated_by_user_id = VALUES(generated_by_user_id),
                generation_version = VALUES(generation_version),
                data_hash = VALUES(data_hash),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                int(product_id),
                int(round_number),
                json.dumps(report, ensure_ascii=False),
                generated_by_user_id,
                generation_version,
                data_hash,
            ),
        )
        conn.commit()

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            raise HistoricalAggregateReportsTableMissing(
                "historical_aggregate_reports table does not exist"
            ) from exc
        raise

    finally:
        cur.close()
        conn.close()


def get_historical_aggregate_report_status(*, product_id: int, round_number: int | None) -> dict:
    """
    Lightweight read model for legacy project list buttons.
    """

    if round_number is None:
        return {
            "exists": False,
            "is_published": False,
            "is_stale": False,
            "error": "missing_round",
            "aggregate_report_id": None,
            "updated_at": None,
            "published_at": None,
        }

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        publication_key = _round_publication_key(
            product_id=int(product_id),
            round_number=int(round_number),
        )

        cur.execute(
            """
            SELECT
                har.aggregate_report_id,
                har.data_hash,
                har.updated_at,
                hrp.publication_id,
                hrp.status,
                hrp.visible_to_reporting_insights,
                hrp.published_at
            FROM historical_aggregate_reports har
            LEFT JOIN historical_report_publications hrp
                ON hrp.publication_key = %s
               AND hrp.publication_scope = 'round'
            WHERE har.product_id = %s
              AND har.round_number = %s
            LIMIT 1
            """,
            (publication_key, int(product_id), int(round_number)),
        )

        row = cur.fetchone()
        if not row:
            return {
                "exists": False,
                "is_published": False,
                "is_stale": False,
                "error": None,
                "aggregate_report_id": None,
                "updated_at": None,
                "published_at": None,
            }

        return {
            "exists": True,
            "is_published": row.get("status") == "published" and bool(row.get("visible_to_reporting_insights")),
            "is_stale": False,
            "error": None,
            "aggregate_report_id": row.get("aggregate_report_id"),
            "updated_at": row.get("updated_at"),
            "published_at": row.get("published_at"),
        }

    except Exception as exc:
        if _is_missing_table_error(exc):
            return {
                "exists": False,
                "is_published": False,
                "is_stale": False,
                "error": "table_missing",
                "aggregate_report_id": None,
                "updated_at": None,
                "published_at": None,
            }
        raise

    finally:
        cur.close()
        conn.close()


def publish_historical_aggregate_report(*, product_id: int, round_number: int, user_id: str) -> bool:
    """
    Publish the saved aggregate report for Reporting & Insights.
    """

    report_result = get_historical_aggregate_report(
        product_id=int(product_id),
        round_number=int(round_number),
    )
    if not report_result.get("success"):
        return False

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        publication_key = _round_publication_key(
            product_id=int(product_id),
            round_number=int(round_number),
        )

        cur.execute(
            """
            INSERT INTO historical_report_publications (
                publication_key,
                publication_scope,
                product_id,
                round_number,
                context_id,
                status,
                visible_to_product_team,
                visible_to_reporting_insights,
                published_by_user_id,
                published_at,
                withdrawn_by_user_id,
                withdrawn_at
            )
            VALUES (
                %s,
                'round',
                %s,
                %s,
                NULL,
                'published',
                1,
                1,
                %s,
                NOW(),
                NULL,
                NULL
            )
            ON DUPLICATE KEY UPDATE
                publication_scope = 'round',
                product_id = VALUES(product_id),
                round_number = VALUES(round_number),
                context_id = NULL,
                status = 'published',
                visible_to_product_team = 1,
                visible_to_reporting_insights = 1,
                published_by_user_id = VALUES(published_by_user_id),
                published_at = NOW(),
                withdrawn_by_user_id = NULL,
                withdrawn_at = NULL
            """,
            (
                publication_key,
                int(product_id),
                int(round_number),
                user_id,
            ),
        )

        cur.execute(
            """
            UPDATE historical_report_publications
            SET
                status = 'withdrawn',
                visible_to_product_team = 0,
                visible_to_reporting_insights = 0,
                withdrawn_by_user_id = %s,
                withdrawn_at = NOW()
            WHERE publication_scope = 'survey'
              AND product_id = %s
              AND round_number = %s
              AND status = 'published'
              AND visible_to_reporting_insights = 1
            """,
            (
                user_id,
                int(product_id),
                int(round_number),
            ),
        )

        conn.commit()
        return True

    finally:
        cur.close()
        conn.close()


def withdraw_historical_aggregate_report(*, product_id: int, round_number: int, user_id: str) -> bool:
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        publication_key = _round_publication_key(
            product_id=int(product_id),
            round_number=int(round_number),
        )

        cur.execute(
            """
            UPDATE historical_report_publications
            SET
                status = 'withdrawn',
                visible_to_product_team = 0,
                visible_to_reporting_insights = 0,
                withdrawn_by_user_id = %s,
                withdrawn_at = NOW()
            WHERE publication_key = %s
              AND publication_scope = 'round'
            """,
            (user_id, publication_key),
        )
        conn.commit()
        return cur.rowcount > 0

    finally:
        cur.close()
        conn.close()


def _dashboard_report_kpi_value(value: object) -> float | None:
    if value in (None, "", "null"):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def list_published_historical_aggregate_reports_for_reporting_insights() -> list[dict]:
    """
    Published legacy aggregate reports exposed as report objects.
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
                hrp.updated_at,

                har.aggregate_report_id,
                har.product_id,
                har.round_number,
                har.data_hash,
                har.updated_at AS report_updated_at,

                p.internal_name,
                p.market_name,
                p.product_type_display,
                p.business_group,

                JSON_UNQUOTE(JSON_EXTRACT(har.report_json, '$.kpis.star_rating')) AS star_rating,
                JSON_UNQUOTE(JSON_EXTRACT(har.report_json, '$.kpis.software_rating')) AS software_rating,
                JSON_UNQUOTE(JSON_EXTRACT(har.report_json, '$.kpis.nps')) AS nps,
                JSON_UNQUOTE(JSON_EXTRACT(har.report_json, '$.kpis.ready_for_sales')) AS ready_for_sales,

                COALESCE(JSON_LENGTH(JSON_EXTRACT(har.report_json, '$.source_surveys')), 0) AS survey_count,
                COALESCE(JSON_LENGTH(JSON_EXTRACT(har.report_json, '$.sections')), 0) AS section_count,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(har.report_json, '$.summary.answer_count')) AS UNSIGNED) AS answer_count,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(har.report_json, '$.summary.response_count')) AS UNSIGNED) AS response_count,
                1 AS round_count

            FROM historical_report_publications hrp
            JOIN historical_aggregate_reports har
                ON har.product_id = hrp.product_id
               AND har.round_number = hrp.round_number
            JOIN products p
                ON p.product_id = har.product_id

            WHERE hrp.publication_scope = 'round'
              AND hrp.status = 'published'
              AND hrp.visible_to_reporting_insights = 1

            ORDER BY
                hrp.published_at DESC,
                p.internal_name ASC,
                p.market_name ASC,
                har.round_number ASC
            """
        )

        rows = cur.fetchall()
        for row in rows:
            row["dataset_count"] = row.get("survey_count")
            row["report_href"] = (
                f"/reporting/insights/rounds/report?product_id={int(row.get('product_id'))}"
                f"&round_number={int(row.get('round_number'))}"
            )

            for key in ("star_rating", "software_rating", "nps", "ready_for_sales"):
                row[key] = _dashboard_report_kpi_value(row.get(key))

        return rows

    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise

    finally:
        cur.close()
        conn.close()


def historical_aggregate_report_is_visible_to_reporting_insights(*, product_id: int, round_number: int) -> bool:
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        publication_key = _round_publication_key(
            product_id=int(product_id),
            round_number=int(round_number),
        )

        cur.execute(
            """
            SELECT 1
            FROM historical_report_publications hrp
            JOIN historical_aggregate_reports har
                ON har.product_id = hrp.product_id
               AND har.round_number = hrp.round_number
            WHERE hrp.publication_key = %s
              AND hrp.publication_scope = 'round'
              AND hrp.status = 'published'
              AND hrp.visible_to_reporting_insights = 1
            LIMIT 1
            """,
            (publication_key,),
        )

        return cur.fetchone() is not None

    except Exception as exc:
        if _is_missing_table_error(exc):
            return False
        raise

    finally:
        cur.close()
        conn.close()