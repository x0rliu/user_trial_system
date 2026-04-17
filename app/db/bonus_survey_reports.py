# app/db/bonus_survey_reports.py

import json
import mysql.connector
from app.config.config import DB_CONFIG


def upsert_bonus_survey_report(*, bonus_survey_id: int, report: dict) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

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
        conn.close()


def get_bonus_survey_report(*, bonus_survey_id: int) -> dict:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

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
                "report": None
            }

        return {
            "success": True,
            "report": json.loads(row["report_json"])
        }

    finally:
        cur.close()
        conn.close()