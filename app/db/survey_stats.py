import mysql.connector
from app.config.config import DB_CONFIG


def get_surveys_for_round(round_id: int):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT SurveyID, SurveyTitle, SurveyDate
            FROM survey_tracker
            WHERE RoundID = %s
            ORDER BY SurveyDate DESC
            """,
            (round_id,),
        )

        return cur.fetchall()

    finally:
        conn.close()


def get_survey_basic_stats(round_id: int, survey_id: int):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # Total participants (source of truth)
        cur.execute(
            """
            SELECT COUNT(*) AS total_participants
            FROM project_participants
            WHERE RoundID = %s
            """,
            (round_id,),
        )
        total_participants = cur.fetchone()["total_participants"]

        # Completed
        cur.execute(
            """
            SELECT COUNT(*) AS completed
            FROM survey_distribution
            WHERE RoundID = %s
              AND SurveyID = %s
              AND Status = 'completed'
            """,
            (round_id, survey_id),
        )
        completed = cur.fetchone()["completed"]

        # Total answer rows
        cur.execute(
            """
            SELECT COUNT(*) AS total_answers
            FROM survey_answers
            WHERE RoundID = %s
              AND SurveyID = %s
            """,
            (round_id, survey_id),
        )
        total_answers = cur.fetchone()["total_answers"]

        return {
            "total_participants": total_participants,
            "completed_count": completed,
            "total_answers": total_answers,
        }

    finally:
        conn.close()

def get_round_surveys_basic_stats(round_id: int):
    """
    Returns:
        [
            {
                "SurveyID": ...,
                "SurveyTitle": ...,
                "SurveyDate": ...,
                "total_participants": ...,
                "completed": ...,
                "total_answers": ...
            },
            ...
        ]
    """

    surveys = get_surveys_for_round(round_id)

    results = []

    for s in surveys:
        survey_id = s["SurveyID"]

        stats = get_survey_basic_stats(round_id, survey_id)

        results.append({
            "SurveyID": survey_id,
            "SurveyTitle": s.get("SurveyTitle"),
            "SurveyDate": s.get("SurveyDate"),
            "total_participants": stats["total_participants"],
            "completed_count": stats["completed_count"],
            "total_answers": stats["total_answers"],
        })


    return results
