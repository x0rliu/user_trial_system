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


def get_survey_response_attribution_summary(
    *,
    round_id: int,
    survey_type_id: str,
) -> dict:
    """
    Return persistent attribution counts for PT/result survey uploads.

    Source of truth:
    - survey_distribution stores one row per uploaded response.
    - survey_answers stores answer rows tied to those distribution rows.

    Recruiting remains identity-strict in the upload service. This helper only
    reports what was already stored.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                COUNT(*) AS responses_analyzed,

                SUM(CASE WHEN MatchMethod = 'token' THEN 1 ELSE 0 END)
                    AS matched_by_token,

                SUM(CASE WHEN MatchMethod = 'email' THEN 1 ELSE 0 END)
                    AS matched_by_email,

                SUM(CASE WHEN MatchMethod = 'anonymous' THEN 1 ELSE 0 END)
                    AS anonymous,

                SUM(CASE WHEN MatchMethod = 'unmatched' THEN 1 ELSE 0 END)
                    AS unmatched,

                SUM(CASE WHEN MatchMethod = 'manual' THEN 1 ELSE 0 END)
                    AS manual,

                SUM(CASE WHEN NeedsReview = 1 THEN 1 ELSE 0 END)
                    AS needs_review
            FROM survey_distribution
            WHERE RoundID = %s
              AND SurveyTypeID = %s
              AND Status = 'completed'
            """,
            (int(round_id), survey_type_id),
        )

        row = cur.fetchone() or {}

        cur.execute(
            """
            SELECT COUNT(*) AS total_answers
            FROM survey_answers
            WHERE RoundID = %s
              AND SurveyTypeID = %s
            """,
            (int(round_id), survey_type_id),
        )

        answer_row = cur.fetchone() or {}

        return {
            "responses_analyzed": int(row.get("responses_analyzed") or 0),
            "matched_by_token": int(row.get("matched_by_token") or 0),
            "matched_by_email": int(row.get("matched_by_email") or 0),
            "anonymous": int(row.get("anonymous") or 0),
            "unmatched": int(row.get("unmatched") or 0),
            "manual": int(row.get("manual") or 0),
            "needs_review": int(row.get("needs_review") or 0),
            "total_answers": int(answer_row.get("total_answers") or 0),
        }

    finally:
        conn.close()