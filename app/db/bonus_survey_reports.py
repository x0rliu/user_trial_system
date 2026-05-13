# app/db/bonus_survey_reports.py

import json
import mysql.connector
from app.config.config import DB_CONFIG


def upsert_bonus_survey_report(*, bonus_survey_id: int, report: dict) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO bonus_survey_reports (
                bonus_survey_id,
                report_json
            )
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                report_json = VALUES(report_json)
            """,
            (
                bonus_survey_id,
                json.dumps(report, ensure_ascii=False),
            ),
        )

        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_bonus_survey_report(*, bonus_survey_id: int) -> dict:
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT report_json
            FROM bonus_survey_reports
            WHERE bonus_survey_id = %s
            """,
            (bonus_survey_id,),
        )

        row = cur.fetchone()

        if not row:
            return {
                "success": False,
                "report": None,
                "error": "not_found",
            }

        try:
            report = json.loads(row["report_json"] or "{}")
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

        return {
            "success": True,
            "report": report,
            "error": None,
        }

    finally:
        cur.close()
        conn.close()