#app/db/survey_recruiting_kpis.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_recruiting_kpis(*, round_id: int) -> dict:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # Total applicants
        cur.execute("""
            SELECT COUNT(DISTINCT user_id) AS total_applicants
            FROM project_applicants
            WHERE RoundID = %s
        """, (round_id,))
        total_applicants = cur.fetchone()["total_applicants"] or 0

        # Completed (users with survey answers)
        cur.execute("""
            SELECT COUNT(DISTINCT user_id) AS completed_count
            FROM survey_answers
            WHERE RoundID = %s
        """, (round_id,))
        completed_count = cur.fetchone()["completed_count"] or 0

        # Total answer rows
        cur.execute("""
            SELECT COUNT(*) AS total_answer_rows
            FROM survey_answers
            WHERE RoundID = %s
        """, (round_id,))
        total_answer_rows = cur.fetchone()["total_answer_rows"] or 0

        quitter_count = max(total_applicants - completed_count, 0)

        return {
            "total_applicants": total_applicants,
            "completed_count": completed_count,
            "quitter_count": quitter_count,
            "total_answer_rows": total_answer_rows,
        }

    finally:
        conn.close()