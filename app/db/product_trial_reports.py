# app/db/product_trial_reports.py

from __future__ import annotations

import json

import mysql.connector
from mysql.connector import errorcode

from app.config.config import DB_CONFIG


class ProductTrialReportsTableMissing(RuntimeError):
    """Raised when the DB migration for product_trial_reports has not been applied."""


def _is_missing_table_error(exc: Exception) -> bool:
    return isinstance(exc, mysql.connector.Error) and exc.errno == errorcode.ER_NO_SUCH_TABLE


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