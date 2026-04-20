# app/services/bonus_survey_analysis_builder.py

from app.db.bonus_survey_answers import get_bonus_survey_answer_rows


def build_bonus_survey_analysis_payload(bonus_survey_id: int):
    """
    Reconstruct survey data into analysis-ready structure.

    Source of truth:
    - answers → bonus_survey_answers
    - structure → bonus_survey_question_structure

    No text matching. No guessing. No normalization.
    """

    from app.db.bonus_survey_answers import get_bonus_survey_answer_rows
    from app.db.bonus_survey_question_structure import get_bonus_survey_structure_rows

    rows = get_bonus_survey_answer_rows(bonus_survey_id)

    if not rows:
        return {
            "bonus_survey_id": bonus_survey_id,
            "survey_title": None,
            "response_count": 0,
            "responses": [],
            "sections": {},
            "structure": [],
        }

    survey_title = rows[0]["survey_title"]

    responses_map = {}

    # -------------------------
    # LOAD STRUCTURE (SOURCE OF TRUTH)
    # -------------------------
    structure_rows = get_bonus_survey_structure_rows(
        bonus_survey_id=bonus_survey_id
    )

    structure_map = {}
    sections_map = {}

    for r in structure_rows:
        q_hash = r["question_hash"]

        structure_map[q_hash] = r

        if r["placement_type"] == "section":
            key = r["section_key"] or "unknown"
            sections_map.setdefault(key, [])

    # 🔥 prevent duplicates from joins
    seen_answers = set()

    for r in rows:
        pid = r["bonus_survey_participation_id"]
        user_id = r["user_id"]

        # -------------------------
        # INIT RESPONSE
        # -------------------------
        if pid not in responses_map:
            responses_map[pid] = {
                "participation_id": pid,
                "user_id": user_id,
                "completed_at": r["completed_at"],

                "demographics": {
                    "gender": r.get("Gender"),
                    "birth_year": r.get("BirthYear"),
                    "country": r.get("CountryCode"),
                    "city": r.get("City"),
                },

                "profiles": {},
                "answers": []
            }

        # -------------------------
        # PROFILE AGGREGATION
        # -------------------------
        category = r.get("CategoryName")
        level = r.get("LevelDescription")

        if category and level:
            responses_map[pid]["profiles"].setdefault(category, [])

            if level not in responses_map[pid]["profiles"][category]:
                responses_map[pid]["profiles"][category].append(level)

        # -------------------------
        # DEDUP ANSWERS
        # -------------------------
        answer_key = (
            pid,
            r["QuestionHash"],
            r["AnswerText"]
        )

        if answer_key in seen_answers:
            continue

        seen_answers.add(answer_key)

        question_hash = r["QuestionHash"]
        question_text = (r["QuestionText"] or "").strip()
        answer_text = r["AnswerText"]

        answer_record = {
            "question_text": question_text,
            "question_hash": question_hash,
            "answer_text": answer_text,
            "created_at": (
                r["answer_created_at"].isoformat()
                if r.get("answer_created_at")
                else None
            )
        }

        responses_map[pid]["answers"].append(answer_record)

        # -------------------------
        # STRUCTURE-DRIVEN SECTION MAPPING
        # -------------------------
        struct = structure_map.get(question_hash)

        if not struct:
            continue

        if struct["placement_type"] != "section":
            continue

        section_key = struct["section_key"] or "unknown"

        if answer_text:
            sections_map.setdefault(section_key, []).append({
                "participation_id": pid,
                "user_id": user_id,
                "question_text": question_text,
                "question_hash": question_hash,
                "answer_text": answer_text,
                "created_at": (
                    r["answer_created_at"].isoformat()
                    if r.get("answer_created_at")
                    else None
                )
            })

    # Only count participants with actual answers
    responses = [
        r for r in responses_map.values()
        if r.get("answers")
    ]

    # -------------------------
    # STRUCTURE SNAPSHOT (FOR AI + DEBUGGING)
    # -------------------------
    structure_snapshot = []

    for r in structure_rows:
        structure_snapshot.append({
            "question_text": r["question_text"],
            "question_hash": r["question_hash"],
            "placement_type": r["placement_type"],
            "section_key": r["section_key"],
            "question_order": r["question_order"],
        })

    return {
        "bonus_survey_id": bonus_survey_id,
        "survey_title": survey_title,
        "response_count": len(responses),
        "responses": responses,
        "sections": sections_map,
        "structure": structure_snapshot,
    }