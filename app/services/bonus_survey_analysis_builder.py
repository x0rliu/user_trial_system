# app/services/bonus_survey_analysis_builder.py

from app.db.bonus_survey_answers import get_bonus_survey_answer_rows


def _empty_attribution_summary() -> dict:
    return {
        "responses_analyzed": 0,
        "matched_by_token": 0,
        "matched_by_email": 0,
        "anonymous": 0,
        "unmatched": 0,
        "manual": 0,
        "needs_review": 0,
    }


def _answer_has_content(value) -> bool:
    if value is None:
        return False

    return str(value).strip() != ""


def _response_has_any_answer(response: dict) -> bool:
    for answer in response.get("answers") or []:
        if _answer_has_content(answer.get("answer_text")):
            return True

    return False


def build_bonus_survey_analysis_payload(bonus_survey_id: int):
    """
    Reconstruct survey data into analysis-ready structure.

    Source of truth:
    - answers → bonus_survey_answers
    - structure → bonus_survey_question_structure

    No text matching. No guessing. No normalization.

    Important:
    - get_bonus_survey_answer_rows() may return duplicate answer rows because
      profile joins can create one row per user profile.
    - Duplicate joined rows are deduped by AnswerID.
    - Identical AnswerText values from different participants are preserved.
    """

    from app.db.bonus_survey_answers import get_bonus_survey_answer_rows
    from app.db.bonus_survey_question_structure import get_bonus_survey_structure_rows

    rows = get_bonus_survey_answer_rows(bonus_survey_id)

    if not rows:
        return {
            "bonus_survey_id": bonus_survey_id,
            "survey_title": None,
            "response_count": 0,
            "attribution_summary": _empty_attribution_summary(),
            "responses": [],
            "sections": [],
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
    for row in structure_rows:
        key = f"{row['question_hash']}__{row.get('question_order')}"
        structure_map[key] = row

    # -------------------------
    # BUILD RESPONSES
    # -------------------------
    seen_answer_ids = set()

    for row in rows:
        pid = row["bonus_survey_participation_id"]
        user_id = row["user_id"]

        if pid not in responses_map:
            responses_map[pid] = {
                "participation_id": pid,
                "user_id": user_id,
                "completed_at": row["completed_at"],
                "attribution": {
                    "source_email": row.get("source_email"),
                    "source_token": row.get("source_token"),
                    "source_response_key": row.get("source_response_key"),
                    "match_method": row.get("match_method"),
                    "match_confidence": row.get("match_confidence"),
                    "needs_review": int(row.get("needs_review") or 0),
                    "match_notes": row.get("match_notes"),
                },
                "demographics": {
                    "gender": row.get("Gender"),
                    "birth_year": row.get("BirthYear"),
                    "country": row.get("CountryCode"),
                    "city": row.get("City"),
                },
                "profiles": {},
                "answers": [],
            }

        # profiles
        category = row.get("CategoryName")
        level = row.get("LevelDescription")

        if category and level:
            responses_map[pid]["profiles"].setdefault(category, [])
            if level not in responses_map[pid]["profiles"][category]:
                responses_map[pid]["profiles"][category].append(level)

        answer_id = row.get("AnswerID")

        if answer_id in seen_answer_ids:
            continue

        seen_answer_ids.add(answer_id)

        question_hash = row["QuestionHash"]
        question_text = (row["QuestionText"] or "").strip()
        answer_text = row["AnswerText"]

        responses_map[pid]["answers"].append({
            "answer_id": answer_id,
            "question_text": question_text,
            "question_hash": question_hash,
            "question_order": row.get("QuestionOrder"),
            "answer_text": answer_text,
            "created_at": (
                row["answer_created_at"].isoformat()
                if row.get("answer_created_at")
                else None
            ),
        })

    responses = [
        response
        for response in responses_map.values()
        if _response_has_any_answer(response)
    ]

    attribution_summary = _empty_attribution_summary()
    attribution_summary["responses_analyzed"] = len(responses)

    for response in responses:
        attribution = response.get("attribution") or {}
        match_method = (attribution.get("match_method") or "").strip().lower()

        if match_method == "token":
            attribution_summary["matched_by_token"] += 1
        elif match_method == "email":
            attribution_summary["matched_by_email"] += 1
        elif match_method == "anonymous":
            attribution_summary["anonymous"] += 1
        elif match_method == "unmatched":
            attribution_summary["unmatched"] += 1
        elif match_method == "manual":
            attribution_summary["manual"] += 1

        if int(attribution.get("needs_review") or 0) == 1:
            attribution_summary["needs_review"] += 1

    # -------------------------
    # GROUP QUESTIONS (SOURCE OF TRUTH)
    # -------------------------
    grouped_questions = group_answers_by_question(rows)

    # -------------------------
    # BUILD SECTIONS (QUESTION-LEVEL, NOT ANSWER-LEVEL)
    # -------------------------
    sections_map = {}

    for question in grouped_questions:
        question_hash = question["question_hash"]
        question_text = question["question_text"]
        question_order = question.get("question_order")

        lookup_key = f"{question_hash}__{question_order}"
        structure_row = structure_map.get(lookup_key)

        if not structure_row:
            continue

        if structure_row["placement_type"] != "section":
            continue

        section_key = structure_row["section_key"] or "unknown"

        sections_map.setdefault(section_key, {
            "section_key": section_key,
            "questions": [],
        })

        answers = question["answers"]

        # -------------------------
        # Compute avg (numeric only)
        # -------------------------
        numeric_vals = []
        for answer in answers:
            try:
                val = float(answer)
                numeric_vals.append(val)
            except (TypeError, ValueError):
                continue

        avg = None
        if numeric_vals:
            avg = round(sum(numeric_vals) / len(numeric_vals), 2)

        sections_map[section_key]["questions"].append({
            "question_text": question_text,
            "question_hash": question_hash,
            "question_order": question_order,
            "avg": avg,
            "response_count": len([
                answer for answer in answers
                if _answer_has_content(answer)
            ]),
        })

    # -------------------------
    # STRUCTURE SNAPSHOT
    # -------------------------
    structure_snapshot = []

    for row in structure_rows:
        structure_snapshot.append({
            "question_text": row["question_text"],
            "question_hash": row["question_hash"],
            "placement_type": row["placement_type"],
            "section_key": row["section_key"],
            "question_order": row["question_order"],
        })

    return {
        "bonus_survey_id": bonus_survey_id,
        "survey_title": survey_title,
        "response_count": len(responses),
        "attribution_summary": attribution_summary,
        "responses": responses,
        "sections": list(sections_map.values()),
        "structure": structure_snapshot,
    }

def group_answers_by_question(rows):
    """
    Group answers by question identity.

    Question identity:
    - QuestionHash
    - QuestionOrder

    Row dedupe identity:
    - AnswerID

    Do not dedupe by AnswerText. If 20 participants all answer "5", that is
    20 valid responses and must count as 20 values in averages.
    """

    question_map = {}
    seen_answer_ids = set()

    for row in rows:
        question_hash = row.get("QuestionHash")
        question_text = (row.get("QuestionText") or "").strip()
        question_order = row.get("QuestionOrder")
        answer = row.get("AnswerText")
        answer_id = row.get("AnswerID")

        if not question_hash:
            continue

        if answer_id in seen_answer_ids:
            continue

        seen_answer_ids.add(answer_id)

        key = f"{question_hash}__{question_order}"

        if key not in question_map:
            question_map[key] = {
                "question_hash": question_hash,
                "question_text": question_text,
                "question_order": question_order,
                "answers": [],
            }

        question_map[key]["answers"].append(answer)

    return sorted(
        question_map.values(),
        key=lambda item: item["question_order"] or 0,
    )