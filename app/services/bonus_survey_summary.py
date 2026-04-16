# app/services/bonus_survey_summary.py

from app.services.bonus_survey_analysis_builder import build_bonus_survey_analysis_payload


def get_bonus_survey_summary(bonus_survey_id: int) -> dict:
    payload = build_bonus_survey_analysis_payload(bonus_survey_id)

    responses = payload.get("responses", [])
    response_count = payload.get("response_count", 0)

    if not responses:
        return {
            "responses": 0,
            "questions": 0,
            "avg_answers": 0,
            "consistency": 0,
        }

    # All users should now have same number of answers (after your ingestion fix)
    question_count = len(responses[0]["answers"])

    # Avg answers per user
    total_answers = sum(len(r["answers"]) for r in responses)
    avg_answers = round(total_answers / response_count, 2)

    # Consistency check
    lengths = set(len(r["answers"]) for r in responses)
    consistency = 100 if len(lengths) == 1 else 0

    return {
        "responses": response_count,
        "questions": question_count,
        "avg_answers": avg_answers,
        "consistency": consistency,
    }