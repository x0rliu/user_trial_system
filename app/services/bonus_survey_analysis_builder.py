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
    for r in structure_rows:
        key = f"{r['question_hash']}__{r.get('question_order')}"
        structure_map[key] = r

    # -------------------------
    # BUILD RESPONSES (unchanged)
    # -------------------------
    seen_answers = set()

    for r in rows:
        pid = r["bonus_survey_participation_id"]
        user_id = r["user_id"]

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

        # profiles
        category = r.get("CategoryName")
        level = r.get("LevelDescription")

        if category and level:
            responses_map[pid]["profiles"].setdefault(category, [])
            if level not in responses_map[pid]["profiles"][category]:
                responses_map[pid]["profiles"][category].append(level)

        # dedupe answers
        answer_key = (pid, r["QuestionHash"], r["AnswerText"])
        if answer_key in seen_answers:
            continue
        seen_answers.add(answer_key)

        question_hash = r["QuestionHash"]
        question_text = (r["QuestionText"] or "").strip()
        answer_text = r["AnswerText"]

        responses_map[pid]["answers"].append({
            "question_text": question_text,
            "question_hash": question_hash,
            "answer_text": answer_text,
            "created_at": (
                r["answer_created_at"].isoformat()
                if r.get("answer_created_at")
                else None
            )
        })

    responses = [
        r for r in responses_map.values()
        if r.get("answers")
    ]

    # -------------------------
    # ✅ NEW: GROUP QUESTIONS (SOURCE OF TRUTH)
    # -------------------------
    grouped_questions = group_answers_by_question(rows)

    # -------------------------
    # ✅ BUILD SECTIONS (QUESTION-LEVEL, NOT ANSWER-LEVEL)
    # -------------------------
    sections_map = {}

    for q in grouped_questions:
        q_hash = q["question_hash"]
        q_text = q["question_text"]
        q_order = q.get("question_order")

        lookup_key = f"{q_hash}__{q_order}"
        struct = structure_map.get(lookup_key)

        if not struct:
            continue

        if struct["placement_type"] != "section":
            continue

        section_key = struct["section_key"] or "unknown"

        sections_map.setdefault(section_key, {
            "section_key": section_key,
            "questions": []
        })

        answers = q["answers"]

        # -------------------------
        # Compute avg (numeric only)
        # -------------------------
        numeric_vals = []
        for a in answers:
            try:
                val = float(a)
                numeric_vals.append(val)
            except (TypeError, ValueError):
                continue

        avg = None
        if numeric_vals:
            avg = round(sum(numeric_vals) / len(numeric_vals), 2)

        sections_map[section_key]["questions"].append({
            "question_text": q_text,
            "question_hash": q_hash,
            "question_order": q_order,
            "avg": avg
        })

    # -------------------------
    # STRUCTURE SNAPSHOT
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
        "sections": list(sections_map.values()),
        "structure": structure_snapshot,
    }

def group_answers_by_question(rows):
    question_map = {}

    for r in rows:
        q_hash = r.get("QuestionHash")
        q_text = (r.get("QuestionText") or "").strip()
        q_order = r.get("QuestionOrder")
        answer = r.get("AnswerText")

        if not q_hash:
            continue

        key = f"{q_hash}__{q_order}"

        if key not in question_map:
            question_map[key] = {
                "question_hash": q_hash,
                "question_text": q_text,
                "question_order": q_order,
                "answers": []
            }

        if answer not in question_map[key]["answers"]:
            question_map[key]["answers"].append(answer)
            
    return sorted(
        question_map.values(),
        key=lambda x: x["question_order"] or 0
    )