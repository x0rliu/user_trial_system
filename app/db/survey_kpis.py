# app/db/survey_kpis.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_round_product_kpis(round_id: int) -> dict:
    """
    Derives high-level Product KPIs for a given round.

    Returns:
    {
        "star_rating": float | None,
        "software_rating": float | None,
        "nps": int | None,
        "ready_for_sales": float | None,
    }
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    # ---------------------------------------------------------
    # 1️⃣ Star Rating (1–5)
    # ---------------------------------------------------------
    cursor.execute("""
        SELECT AVG(AnswerNumeric) AS avg_rating
        FROM survey_answers
        WHERE RoundID = %s
        AND LOWER(QuestionText) LIKE %s
    """, (
        round_id,
        "%rate this product%"
    ))


    star_row = cursor.fetchone()
    star_rating = round(float(star_row["avg_rating"]), 2) if star_row["avg_rating"] else None

    # ---------------------------------------------------------
    # 2️⃣ Software Rating (1–5)
    # ---------------------------------------------------------
    cursor.execute("""
        SELECT AVG(AnswerNumeric) AS avg_rating
        FROM survey_answers
        WHERE RoundID = %s
        AND LOWER(QuestionText) LIKE %s
    """, (
        round_id,
        "%software experience%"
    ))


    sw_row = cursor.fetchone()
    software_rating = round(float(sw_row["avg_rating"]), 2) if sw_row["avg_rating"] else None

    # ---------------------------------------------------------
    # 3️⃣ NPS (1–10)
    # ---------------------------------------------------------
    cursor.execute("""
        SELECT AnswerNumeric
        FROM survey_answers
        WHERE RoundID = %s
          AND AnswerNumeric IS NOT NULL
          AND LOWER(QuestionText) LIKE %s
    """, (round_id,"%recommend this product%"))

    nps_rows = cursor.fetchall()

    nps = None
    if nps_rows:
        scores = [float(r["AnswerNumeric"]) for r in nps_rows]

        total = len(scores)
        promoters = len([s for s in scores if s >= 9])
        detractors = len([s for s in scores if s <= 6])

        pct_promoters = (promoters / total) * 100
        pct_detractors = (detractors / total) * 100

        nps = round(pct_promoters - pct_detractors)

    # ---------------------------------------------------------
    # 4️⃣ Ready For Sales
    # ---------------------------------------------------------

    cursor.execute("""
        SELECT user_id,
               MAX(CASE 
                    WHEN LOWER(QuestionText) LIKE %s
                    THEN AnswerValue 
               END) AS hurdles_answer,
               MAX(CASE 
                    WHEN LOWER(QuestionText) LIKE %s
                    THEN AnswerValue 
               END) AS ready_answer
        FROM survey_answers
        WHERE RoundID = %s
        GROUP BY user_id
    """, (
        "%functional hurdles%",
        "%ready for sales%",
        round_id,
    ))

    readiness_rows = cursor.fetchall()

    ready_for_sales = None

    if readiness_rows:
        valid_count = 0
        issue_count = 0

        for row in readiness_rows:
            hurdles = (row["hurdles_answer"] or "").lower()
            ready = (row["ready_answer"] or "").lower()

            if hurdles and ready:
                valid_count += 1

                if "yes" in hurdles and "no" in ready:
                    issue_count += 1

        if valid_count > 0:
            ready_for_sales = round(
                ((valid_count - issue_count) / valid_count) * 100,
                1
            )

    cursor.close()
    conn.close()

    return {
        "star_rating": star_rating if "star_rating" in locals() else None,
        "software_rating": software_rating if "software_rating" in locals() else None,
        "nps": nps if "nps" in locals() else None,
        "ready_for_sales": ready_for_sales if "ready_for_sales" in locals() else None,
    }

