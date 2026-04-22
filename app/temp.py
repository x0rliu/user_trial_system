# app/temp/test_grouping.py

from app.db.bonus_survey_answers import get_bonus_survey_answer_rows
from app.services.bonus_survey_analysis_builder import group_answers_by_question


def run():
    rows = get_bonus_survey_answer_rows(29)
    grouped = group_answers_by_question(rows)

    for q in grouped:
        print(q["question_text"], q["question_order"])


if __name__ == "__main__":
    run()