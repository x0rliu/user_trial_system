# app/services/bonus_survey_analysis_builder.py

from app.db.bonus_survey_answers import get_bonus_survey_answer_rows
from app.db.surveys import get_bonus_survey_sections


def build_bonus_survey_analysis_payload(bonus_survey_id: int):
    """
    Reconstruct survey data into analysis-ready structure.

    Handles:
    - duplicated rows from profile joins
    - demographics extraction
    - profile aggregation
    - section mapping (DB-driven)
    """

    rows = get_bonus_survey_answer_rows(bonus_survey_id)

    if not rows:
        return {
            "bonus_survey_id": bonus_survey_id,
            "survey_title": None,
            "response_count": 0,
            "responses": [],
            "sections": {},
        }

    survey_title = rows[0]["survey_title"]

    responses_map = {}

    # -------------------------
    # Load section config (DB source of truth)
    # -------------------------
    section_config = get_bonus_survey_sections(
        bonus_survey_id=bonus_survey_id
    )

    sections_map = {}
    question_to_section = {}

    if section_config and "sections" in section_config:
        for sec in section_config["sections"]:
            key = sec.get("section_key")

            if not key:
                continue

            sections_map[key] = []

            def _normalize_question(text: str) -> str:
                return " ".join((text or "").strip().lower().split())


            for q in sec.get("questions", []):
                if q:
                    normalized_q = _normalize_question(q)
                    question_to_section[normalized_q] = key

    # 🔥 used to prevent duplicate answers (because of profile joins)
    seen_answers = set()

    for r in rows:
        pid = r["bonus_survey_participation_id"]
        user_id = r["user_id"]

        # -------------------------
        # Initialize response
        # -------------------------
        if pid not in responses_map:
            responses_map[pid] = {
                "participation_id": pid,
                "user_id": user_id,
                "completed_at": r["completed_at"],

                # 🔥 DEMOGRAPHICS (from user_pool)
                "demographics": {
                    "gender": r.get("Gender"),
                    "birth_year": r.get("BirthYear"),
                    "country": r.get("CountryCode"),
                    "city": r.get("City"),
                },

                # 🔥 PROFILE MAP (Category → [Levels])
                "profiles": {},

                "answers": []
            }

        # -------------------------
        # Aggregate profiles
        # -------------------------
        category = r.get("CategoryName")
        level = r.get("LevelDescription")

        if category and level:
            responses_map[pid]["profiles"].setdefault(category, [])

            if level not in responses_map[pid]["profiles"][category]:
                responses_map[pid]["profiles"][category].append(level)

        # -------------------------
        # Deduplicate answers
        # -------------------------
        answer_key = (
            pid,
            r["QuestionHash"],
            r["AnswerText"]
        )

        if answer_key not in seen_answers:
            seen_answers.add(answer_key)

            question_text = (r["QuestionText"] or "").strip()
            answer_text = r["AnswerText"]

            answer_record = {
                "question_text": question_text,
                "question_hash": r["QuestionHash"],
                "answer_text": answer_text,
                "created_at": r["answer_created_at"]
            }

            responses_map[pid]["answers"].append(answer_record)

            # -------------------------
            # Section mapping (DB-driven)
            # -------------------------
            normalized_question = _normalize_question(question_text)
            section_name = question_to_section.get(normalized_question)

            if section_name and answer_text:
                sections_map.setdefault(section_name, []).append({
                    "participation_id": pid,
                    "user_id": user_id,
                    "question_text": question_text,
                    "question_hash": r["QuestionHash"],
                    "answer_text": answer_text,
                    "created_at": r["answer_created_at"],
                })

    responses = list(responses_map.values())

    return {
        "bonus_survey_id": bonus_survey_id,
        "survey_title": survey_title,
        "response_count": len(responses),
        "responses": responses,
        "sections": sections_map,
    }