from app.db.bonus_survey_answers import get_bonus_survey_answer_rows


def _classify_section(question_text: str) -> str | None:
    """
    Classify a question into a survey section.
    """

    q = (question_text or "").strip().lower()

    if "overall" in q:
        return "overall"

    if (
        "find your device" in q
        or "navigation menus" in q
        or "site map" in q
    ):
        return "site_nav"

    if (
        "solve your issue" in q
        or "read and understand" in q
        or "native language" in q
    ):
        return "solutions"

    return None


def build_bonus_survey_analysis_payload(bonus_survey_id: int):
    """
    Reconstruct survey data into analysis-ready structure.

    Handles:
    - duplicated rows from profile joins
    - demographics extraction
    - profile aggregation
    """

    rows = get_bonus_survey_answer_rows(bonus_survey_id)

    if not rows:
        return {
            "bonus_survey_id": bonus_survey_id,
            "survey_title": None,
            "response_count": 0,
            "responses": [],
            "sections": {
                "overall": [],
                "site_nav": [],
                "solutions": [],
            },
        }

    survey_title = rows[0]["survey_title"]

    responses_map = {}

    sections_map = {
        "overall": [],
        "site_nav": [],
        "solutions": [],
    }

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

            answer_record = {
                "question_text": r["QuestionText"],
                "question_hash": r["QuestionHash"],
                "answer_text": r["AnswerText"],
                "created_at": r["answer_created_at"]
            }

            responses_map[pid]["answers"].append(answer_record)

            # -------------------------
            # Section classification
            # -------------------------
            section_name = _classify_section(r["QuestionText"])
            answer_text = r["AnswerText"]

            if section_name and answer_text:
                sections_map[section_name].append({
                    "participation_id": pid,
                    "user_id": user_id,
                    "question_text": r["QuestionText"],
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