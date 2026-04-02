# app/db/bonus_survey.py


from app.config.config import DB_CONFIG
import mysql.connector


def get_bonus_survey_by_id(bonus_survey_id: int) -> dict | None:
    """
    Fetch a single bonus survey by ID.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT *
            FROM bonus_surveys
            WHERE bonus_survey_id = %s
            LIMIT 1
            """,
            (bonus_survey_id,),
        )

        return cur.fetchone()

    finally:
        conn.close()