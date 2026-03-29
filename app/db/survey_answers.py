# app/db/survey_answers.py

def has_responses_for_round(round_id: int) -> bool:

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT 1
            FROM survey_answers
            WHERE RoundID = %s
            LIMIT 1
        """, (round_id,))

        return cur.fetchone() is not None

    finally:
        conn.close()