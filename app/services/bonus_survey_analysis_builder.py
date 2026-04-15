from collections import defaultdict
from app.db.bonus_survey_answers import get_bonus_survey_answer_rows


def build_bonus_survey_analysis_payload(bonus_survey_id: int):
    """
    Reconstruct survey data into analysis-ready structure.

    Output is stable, inspectable, and AI-ready.
    """

    rows = get_bonus_survey_answer_rows(bonus_survey_id)

    if not rows:
        return {
            "bonus_survey_id": bonus_survey_id,
            "survey_title": None,
            "responses": []
        }

    survey_title = rows[0]["survey_title"]

    # Group by participation (user response)
    responses_map = {}

    for r in rows:
        pid = r["bonus_survey_participation_id"]

        if pid not in responses_map:
            responses_map[pid] = {
                "participation_id": pid,
                "user_id": r["user_id"],
                "completed_at": r["completed_at"],
                "answers": []
            }

        responses_map[pid]["answers"].append({
            "question_text": r["QuestionText"],
            "question_hash": r["QuestionHash"],
            "answer_text": r["AnswerText"],
            "created_at": r["answer_created_at"]
        })

    responses = list(responses_map.values())

    return {
        "bonus_survey_id": bonus_survey_id,
        "survey_title": survey_title,
        "response_count": len(responses),
        "responses": responses
    }