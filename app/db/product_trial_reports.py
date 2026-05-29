# app/db/product_trial_reports.py

from __future__ import annotations

import json

import mysql.connector
from mysql.connector import errorcode

from app.config.config import DB_CONFIG


class ProductTrialReportsTableMissing(RuntimeError):
    """Raised when the DB migration for product_trial_reports has not been applied."""

class ProductTrialReportPublicationFieldsMissing(RuntimeError):
    """Raised when Product Trial publication fields have not been migrated yet."""

def _is_missing_table_error(exc: Exception) -> bool:
    return isinstance(exc, mysql.connector.Error) and exc.errno == errorcode.ER_NO_SUCH_TABLE

def _is_missing_publication_column_error(exc: Exception) -> bool:
    return isinstance(exc, mysql.connector.Error) and exc.errno == errorcode.ER_BAD_FIELD_ERROR

def get_product_trial_report(*, round_id: int) -> dict:
    """
    Read the latest saved Product Trial report for one round.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                report_id,
                project_id,
                round_id,
                report_json,
                generated_by_user_id,
                generation_version,
                data_hash,
                created_at,
                updated_at
            FROM product_trial_reports
            WHERE round_id = %s
            LIMIT 1
            """,
            (int(round_id),),
        )

        row = cur.fetchone()

        if not row:
            return {
                "success": False,
                "report": None,
                "error": "not_found",
            }

        try:
            report = json.loads(row.get("report_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            return {
                "success": False,
                "report": None,
                "error": "invalid_report_json",
            }

        if not isinstance(report, dict):
            return {
                "success": False,
                "report": None,
                "error": "invalid_report_shape",
            }

        report.setdefault("metadata", {})
        report["metadata"].update({
            "report_id": row.get("report_id"),
            "project_id": row.get("project_id"),
            "round_id": row.get("round_id"),
            "generated_by_user_id": row.get("generated_by_user_id"),
            "generation_version": row.get("generation_version"),
            "data_hash": row.get("data_hash"),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
        })

        return {
            "success": True,
            "report": report,
            "error": None,
        }

    except Exception as exc:
        if _is_missing_table_error(exc):
            return {
                "success": False,
                "report": None,
                "error": "table_missing",
            }
        raise

    finally:
        cur.close()
        conn.close()


def upsert_product_trial_report(
    *,
    project_id: str,
    round_id: int,
    report: dict,
    generated_by_user_id: str,
    generation_version: str,
    data_hash: str | None,
) -> None:
    """
    Save or replace the generated Product Trial report for a round.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO product_trial_reports (
                project_id,
                round_id,
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
                project_id,
                int(round_id),
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
            raise ProductTrialReportsTableMissing(
                "product_trial_reports table does not exist"
            ) from exc
        raise

    finally:
        cur.close()
        conn.close()


def get_product_trial_report_publication_status(*, round_id: int) -> dict:
    """
    Return publication state for one saved Product Trial report.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                report_id,
                round_id,
                publication_status,
                visible_to_product_team,
                visible_to_reporting_insights,
                published_by_user_id,
                published_at,
                withdrawn_by_user_id,
                withdrawn_at,
                updated_at
            FROM product_trial_reports
            WHERE round_id = %s
            LIMIT 1
            """,
            (int(round_id),),
        )

        row = cur.fetchone()
        if not row:
            return {
                "success": False,
                "error": "not_found",
                "is_published": False,
            }

        publication_status = str(row.get("publication_status") or "draft").lower()
        is_published = (
            publication_status == "published"
            and bool(row.get("visible_to_reporting_insights"))
        )

        return {
            "success": True,
            "error": None,
            "is_published": is_published,
            "publication_status": publication_status,
            "visible_to_product_team": bool(row.get("visible_to_product_team")),
            "visible_to_reporting_insights": bool(row.get("visible_to_reporting_insights")),
            "published_by_user_id": row.get("published_by_user_id"),
            "published_at": row.get("published_at"),
            "withdrawn_by_user_id": row.get("withdrawn_by_user_id"),
            "withdrawn_at": row.get("withdrawn_at"),
            "updated_at": row.get("updated_at"),
        }

    except Exception as exc:
        if _is_missing_table_error(exc):
            return {"success": False, "error": "table_missing", "is_published": False}
        if _is_missing_publication_column_error(exc):
            return {"success": False, "error": "publication_fields_missing", "is_published": False}
        raise

    finally:
        cur.close()
        conn.close()


def publish_product_trial_report(*, round_id: int, user_id: str) -> bool:
    """
    Publish a generated Product Trial report to Reporting & Insights.
    """

    report_result = get_product_trial_report(round_id=int(round_id))
    if not report_result.get("success"):
        return False

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE product_trial_reports
            SET
                publication_status = 'published',
                visible_to_product_team = 1,
                visible_to_reporting_insights = 1,
                published_by_user_id = %s,
                published_at = NOW(),
                withdrawn_by_user_id = NULL,
                withdrawn_at = NULL
            WHERE round_id = %s
            """,
            (user_id, int(round_id)),
        )
        conn.commit()
        return cur.rowcount > 0

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            raise ProductTrialReportsTableMissing("product_trial_reports table does not exist") from exc
        if _is_missing_publication_column_error(exc):
            raise ProductTrialReportPublicationFieldsMissing(
                "product_trial_reports publication fields do not exist"
            ) from exc
        raise

    finally:
        cur.close()
        conn.close()


def withdraw_product_trial_report(*, round_id: int, user_id: str) -> bool:
    """
    Withdraw a Product Trial report from Reporting & Insights without deleting it.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE product_trial_reports
            SET
                publication_status = 'withdrawn',
                visible_to_product_team = 0,
                visible_to_reporting_insights = 0,
                withdrawn_by_user_id = %s,
                withdrawn_at = NOW()
            WHERE round_id = %s
            """,
            (user_id, int(round_id)),
        )
        conn.commit()
        return cur.rowcount > 0

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            raise ProductTrialReportsTableMissing("product_trial_reports table does not exist") from exc
        if _is_missing_publication_column_error(exc):
            raise ProductTrialReportPublicationFieldsMissing(
                "product_trial_reports publication fields do not exist"
            ) from exc
        raise

    finally:
        cur.close()
        conn.close()


def list_published_product_trial_reports_for_reporting_insights() -> list[dict]:
    """
    Published Product Trial reports exposed as Reporting & Insights report objects.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
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

                ptr.report_id,
                ptr.project_id,
                ptr.round_id,
                pr.RoundNumber AS round_number,
                ptr.data_hash,
                ptr.updated_at AS report_updated_at,

                pp.ProjectName AS internal_name,
                pp.MarketName AS market_name,
                pp.ProductType AS product_type_display,
                pp.BusinessGroup AS business_group,

                COALESCE(JSON_LENGTH(JSON_EXTRACT(ptr.report_json, '$.source_surveys')), 0) AS survey_count,
                COALESCE(JSON_LENGTH(JSON_EXTRACT(ptr.report_json, '$.source_surveys')), 0) AS dataset_count,
                COALESCE(JSON_LENGTH(JSON_EXTRACT(ptr.report_json, '$.sections')), 0) AS section_count,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(ptr.report_json, '$.summary.answer_count')) AS UNSIGNED) AS answer_count,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(ptr.report_json, '$.summary.response_count')) AS UNSIGNED) AS response_count,
                1 AS round_count

            FROM product_trial_reports ptr
            JOIN project_rounds pr
                ON pr.RoundID = ptr.round_id
            JOIN project_projects pp
                ON pp.ProjectID = ptr.project_id

            WHERE ptr.publication_status = 'published'
              AND ptr.visible_to_reporting_insights = 1

            ORDER BY
                ptr.published_at DESC,
                pp.ProjectName ASC,
                pp.MarketName ASC,
                pr.RoundNumber ASC
            """
        )

        rows = cur.fetchall()
        for row in rows:
            row["report_href"] = f"/reporting/insights/product-trial-report?round_id={int(row.get('round_id'))}"

        return rows

    except Exception as exc:
        if _is_missing_table_error(exc) or _is_missing_publication_column_error(exc):
            return []
        raise

    finally:
        cur.close()
        conn.close()



def get_published_product_trial_report_for_reporting_insights(*, round_id: int) -> dict:
    """
    Return one published Product Trial report for the read-only Reporting & Insights view.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                ptr.report_id,
                ptr.project_id,
                ptr.round_id,
                ptr.report_json,
                ptr.generated_by_user_id,
                ptr.generation_version,
                ptr.data_hash,
                ptr.publication_status,
                ptr.visible_to_product_team,
                ptr.visible_to_reporting_insights,
                ptr.published_by_user_id,
                ptr.published_at,
                ptr.withdrawn_by_user_id,
                ptr.withdrawn_at,
                ptr.created_at,
                ptr.updated_at,

                pr.RoundNumber AS round_number,

                pp.ProjectName AS internal_name,
                pp.MarketName AS market_name,
                pp.ProductType AS product_type_display,
                pp.BusinessGroup AS business_group

            FROM product_trial_reports ptr
            JOIN project_rounds pr
                ON pr.RoundID = ptr.round_id
            JOIN project_projects pp
                ON pp.ProjectID = ptr.project_id

            WHERE ptr.round_id = %s
              AND ptr.publication_status = 'published'
              AND ptr.visible_to_reporting_insights = 1

            LIMIT 1
            """,
            (int(round_id),),
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
            "report_id": row.get("report_id"),
            "project_id": row.get("project_id"),
            "round_id": row.get("round_id"),
            "round_number": row.get("round_number"),
            "generated_by_user_id": row.get("generated_by_user_id"),
            "generation_version": row.get("generation_version"),
            "data_hash": row.get("data_hash"),
            "publication_status": row.get("publication_status"),
            "visible_to_product_team": bool(row.get("visible_to_product_team")),
            "visible_to_reporting_insights": bool(row.get("visible_to_reporting_insights")),
            "published_by_user_id": row.get("published_by_user_id"),
            "published_at": str(row.get("published_at") or ""),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
            "report_source": "product_trial",
            "report_source_label": "Product Trial",
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

        if isinstance(exc, mysql.connector.Error) and exc.errno == errorcode.ER_BAD_FIELD_ERROR:
            return {
                "success": False,
                "report": None,
                "row": None,
                "error": "publication_fields_missing",
            }

        raise

    finally:
        cur.close()
        conn.close()


def get_product_trial_report_source_answers(*, round_id: int) -> list[dict]:
    """
    Read DB-backed survey answer rows used for Product Trial reporting.

    Excludes recruiting, consolidated/internal, and report-issue surveys.
    Includes Survey 1/OOBE and later participant result surveys.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                sa.AnswerID,
                sa.SurveyID,
                sa.DistributionID,
                sa.user_id,
                sa.ProjectID,
                sa.RoundID,
                sa.SurveyTypeID,
                st.SurveyTypeName,
                sa.QuestionID,
                sa.QuestionText,
                sa.AnswerValue,
                sa.AnswerNumeric,
                sa.SubmittedAt,
                sa.UpdatedAt
            FROM survey_answers sa
            LEFT JOIN survey_types st
                ON st.SurveyTypeID = sa.SurveyTypeID
            WHERE sa.RoundID = %s
              AND sa.SurveyTypeID NOT IN (
                    'UTSurveyType0001',
                    'UTSurveyType0027',
                    'UTSurveyType0028'
              )
            ORDER BY
                sa.SurveyTypeID ASC,
                sa.DistributionID ASC,
                sa.AnswerID ASC
            """,
            (int(round_id),),
        )

        return cur.fetchall()

    finally:
        cur.close()
        conn.close()