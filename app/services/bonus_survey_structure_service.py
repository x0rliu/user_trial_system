# app/services/bonus_survey_structure_service.py

from collections import defaultdict

from app.db.bonus_survey_question_structure import (
    bonus_survey_structure_exists,
    initialize_bonus_survey_structure_as_unassigned,
    get_bonus_survey_structure_rows,
)
from app.services.bonus_survey_section_generator import (
    generate_bonus_survey_sections,
)


def ensure_structure_initialized(*, bonus_survey_id: int) -> None:
    """
    Ensure structure rows exist.

    If not:
    - seed all questions as unassigned
    """

    exists = bonus_survey_structure_exists(
        bonus_survey_id=bonus_survey_id
    )

    if not exists:
        initialize_bonus_survey_structure_as_unassigned(
            bonus_survey_id=bonus_survey_id
        )


def apply_ai_section_suggestions(
    *,
    bonus_survey_id: int,
    payload: dict,
) -> None:
    """
    Deterministic section builder.

    Behavior:
    - Uses question order to group sections.
    - Pairs qualitative questions to the preceding quantitative block.
    - Does NOT use AI for grouping.

    Structure identity contract:
    - QuestionHash + QuestionOrder identifies a question position.

    Answer identity contract:
    - AnswerID identifies a single answer row.

    This function mutates only bonus_survey_question_structure through
    update_bonus_survey_question_placement().
    """

    from app.db.bonus_survey_question_structure import (
        get_bonus_survey_structure_rows,
        update_bonus_survey_question_placement,
    )
    from app.db.bonus_survey_answers import get_bonus_survey_answer_rows

    # -------------------------
    # Helpers
    # -------------------------
    def _is_profile(q: str) -> bool:
        ql = q.lower().strip()

        return any([
            ql.startswith("what is your gender"),
            ql.startswith("what is your age"),
            ql.startswith("what country"),
            ql.startswith("what is your name"),
            ql.startswith("what logitech product"),
            ql.startswith("in your best estimation"),
            ql.startswith("when you encounter an issue"),
        ])

    def _is_admin(q: str) -> bool:
        ql = q.lower()
        return any([
            "do you agree" in ql,
            "consent" in ql,
            "opt" in ql,
        ])

    # -------------------------
    # Load structure rows
    # -------------------------
    rows = get_bonus_survey_structure_rows(
        bonus_survey_id=bonus_survey_id,
    )

    filtered_rows = []

    for row in rows:
        question_text = (row.get("question_text") or "").strip()

        if not question_text:
            continue

        if row["placement_type"] != "unassigned":
            continue

        if _is_profile(question_text) or _is_admin(question_text):
            continue

        filtered_rows.append(row)

    ordered_rows = sorted(
        filtered_rows,
        key=lambda row: row.get("question_order") or 0,
    )

    # -------------------------
    # Build answer map
    # -------------------------
    answer_rows = get_bonus_survey_answer_rows(
        bonus_survey_id=bonus_survey_id,
    )

    answer_map = _build_answer_map(answer_rows)

    # -------------------------
    # Build sections deterministically
    # -------------------------
    sections = []
    current_section = []

    for row in ordered_rows:
        question_text = (row.get("question_text") or "").strip()

        if not question_text:
            continue

        if _is_profile(question_text) or _is_admin(question_text):
            continue

        question_hash = row.get("question_hash")
        question_order = row.get("question_order")
        question_key = f"{question_hash}__{question_order}"

        # -------------------------
        # QUAL → attach to previous section
        # -------------------------
        answers = answer_map.get(question_key, [])
        is_qual = _is_qual_by_answers(answers)

        if is_qual:
            if current_section:
                current_section.append(row)
            elif sections:
                sections[-1].append(row)
            else:
                sections.append([row])
            continue

        # -------------------------
        # QUANT → start new section
        # -------------------------
        if current_section:
            sections.append(current_section)

        current_section = [row]

    if current_section:
        sections.append(current_section)

    # -------------------------
    # Persist sections
    # -------------------------
    section_order_counter = 1

    for section in sections:
        question_order_counter = 1

        for row in section:
            question_text = (row.get("question_text") or "").strip()

            if row["placement_type"] != "unassigned":
                continue

            # HARD GUARD — never allow profile/admin questions into sections.
            if _is_profile(question_text) or _is_admin(question_text):
                continue

            update_bonus_survey_question_placement(
                structure_id=row["structure_id"],
                placement_type="section",
                section_key=f"section_{section_order_counter}",
                section_order=section_order_counter,
                question_order=question_order_counter,
            )

            question_order_counter += 1

        section_order_counter += 1

from collections import defaultdict

def _build_answer_map(rows):
    """
    Build answer map keyed by question identity.

    Question identity:
    - QuestionHash + QuestionOrder

    Answer row identity:
    - AnswerID

    This prevents repeated question text/hash values from leaking answers across
    different positions in the survey structure.
    """

    answer_map = defaultdict(list)
    seen_answer_ids = set()

    for row in rows:
        question_hash = row.get("question_hash")
        if question_hash is None:
            question_hash = row.get("QuestionHash")

        question_order = row.get("question_order")
        if question_order is None:
            question_order = row.get("QuestionOrder")

        answer_id = row.get("answer_id")
        if answer_id is None:
            answer_id = row.get("AnswerID")

        answer_text = row.get("answer_text")
        if answer_text is None:
            answer_text = row.get("AnswerText")

        answer_text = (answer_text or "").strip()

        if answer_id is not None and answer_id in seen_answer_ids:
            continue

        if answer_id is not None:
            seen_answer_ids.add(answer_id)

        if not question_hash or not answer_text:
            continue

        question_key = f"{question_hash}__{question_order}"
        answer_map[question_key].append(answer_text)

    return answer_map


def build_structure_view_model(*, bonus_survey_id: int) -> dict:
    """
    Build grouped structure for UI consumption.

    Structure identity contract:
    - QuestionHash + QuestionOrder identifies a question position.

    Answer row identity contract:
    - AnswerID identifies a single answer row.

    This function is GET/render support only. It does not mutate DB state.
    """

    from collections import defaultdict
    from app.db.bonus_survey_question_structure import get_bonus_survey_structure_rows
    from app.db.bonus_survey_answers import get_bonus_survey_answer_rows

    # -------------------------
    # Load data
    # -------------------------
    rows = get_bonus_survey_structure_rows(
        bonus_survey_id=bonus_survey_id
    )

    answer_rows = get_bonus_survey_answer_rows(
        bonus_survey_id=bonus_survey_id
    )

    # -------------------------
    # Build answer map
    # -------------------------
    answer_map = _build_answer_map(answer_rows)

    def _is_qual(question_hash: str, question_order) -> bool:
        question_key = f"{question_hash}__{question_order}"
        return _is_qual_by_answers(answer_map.get(question_key, []))

    # -------------------------
    # Build raw buckets
    # -------------------------
    profile = []
    unassigned = []

    sections_map = defaultdict(list)
    section_order_map = {}

    for row in rows:
        placement = row["placement_type"]
        question_text = (row["question_text"] or "").strip()

        if placement == "profile":
            profile.append(question_text)

        elif placement == "unassigned":
            unassigned.append(question_text)

        elif placement == "section":
            section_key = row["section_key"] or "unknown"

            sections_map[section_key].append({
                "question_text": question_text,
                "question_order": row["question_order"],
            })

            section_order_map[section_key] = row["section_order"]

    # -------------------------
    # Reattach QUAL (display only)
    # -------------------------
    # Goal:
    # If a qualitative question is sitting in unassigned, attach it to the
    # nearest preceding section based on original question order.
    #
    # Important:
    # The qualitative check must use QuestionHash + QuestionOrder, not
    # QuestionHash alone.
    # -------------------------
    ordered_questions = [
        {
            "question_text": (row["question_text"] or "").strip(),
            "question_hash": row.get("question_hash"),
            "question_order": row.get("question_order", 0),
            "placement": row["placement_type"],
            "section_key": row.get("section_key"),
        }
        for row in rows
    ]

    last_section_key = None

    for item in ordered_questions:
        question_text = item["question_text"]

        if item["placement"] == "section":
            last_section_key = item["section_key"]

        elif (
            item["placement"] == "unassigned"
            and _is_qual(
                item.get("question_hash"),
                item.get("question_order"),
            )
        ):
            if last_section_key:
                sections_map[last_section_key].append({
                    "question_text": question_text,
                    "question_order": 999,  # push to end of section
                })

                if question_text in unassigned:
                    unassigned.remove(question_text)

    # -------------------------
    # Sort sections
    # -------------------------
    sorted_sections = []

    for section_key, questions in sections_map.items():
        sorted_questions = sorted(
            questions,
            key=lambda question: question["question_order"],
        )

        sorted_sections.append({
            "section_key": section_key,
            "questions": [
                question["question_text"]
                for question in sorted_questions
            ],
            "section_order": section_order_map.get(section_key, 0),
        })

    sorted_sections.sort(key=lambda section: section["section_order"])

    return {
        "profile": sorted(profile),
        "sections": sorted_sections,
        "unassigned": sorted(unassigned),
    }

def _is_qual_by_answers(answers: list[str]) -> bool:
    if not answers:
        return False

    unique_answers = set(answers)

    # heuristic thresholds
    avg_len = sum(len(a) for a in answers) / len(answers)

    # high variability + longer text → qual
    if len(unique_answers) > 10:
        return True

    if avg_len > 25:
        return True

    return False

def update_bonus_survey_question_placement_batch(
    *,
    bonus_survey_id: int,
    updates: list[dict],
) -> None:
    """
    Batch update question placement.

    updates = [
        {
            "structure_id": int,
            "placement_type": "section" | "profile" | "unassigned" | "ignored",
            "section_key": str | None,
            "section_order": int,
            "question_order": int,
        }
    ]

    Behavior:
    - Only updates rows where values actually changed
    - Safe for repeated calls
    - No inserts, no deletes
    """

    if not updates:
        return

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # -------------------------
        # Load current state
        # -------------------------
        structure_ids = [u["structure_id"] for u in updates]

        format_strings = ",".join(["%s"] * len(structure_ids))

        cur.execute(
            f"""
            SELECT
                structure_id,
                placement_type,
                section_key,
                section_order,
                question_order
            FROM bonus_survey_question_structure
            WHERE bonus_survey_id = %s
              AND structure_id IN ({format_strings})
            """,
            [bonus_survey_id, *structure_ids],
        )

        existing_rows = {row["structure_id"]: row for row in cur.fetchall()}

        # -------------------------
        # Apply diff updates
        # -------------------------
        for update in updates:
            sid = update["structure_id"]
            current = existing_rows.get(sid)

            if not current:
                continue

            new_placement = update.get("placement_type")
            new_section = update.get("section_key")
            new_section_order = update.get("section_order", 0)
            new_question_order = update.get("question_order", 0)

            # normalize section_key
            if new_placement != "section":
                new_section = None
                new_section_order = 0
                new_question_order = 0

            # check diff
            if (
                current["placement_type"] == new_placement and
                (current["section_key"] or None) == new_section and
                (current["section_order"] or 0) == new_section_order and
                (current["question_order"] or 0) == new_question_order
            ):
                continue  # no change

            # update
            cur.execute(
                """
                UPDATE bonus_survey_question_structure
                SET
                    placement_type = %s,
                    section_key = %s,
                    section_order = %s,
                    question_order = %s
                WHERE structure_id = %s
                """,
                (
                    new_placement,
                    new_section,
                    new_section_order,
                    new_question_order,
                    sid,
                ),
            )

        conn.commit()

    finally:
        conn.close()

def save_bonus_survey_structure_assignments(
    *,
    bonus_survey_id: int,
    assignments: list[dict],
) -> None:
    """
    Persist section assignments using diff-based update.
    """

    from collections import defaultdict
    from app.db.bonus_survey_question_structure import (
        get_bonus_survey_structure_rows,
        update_bonus_survey_question_placement_batch,
    )

    if not assignments:
        return

    # -------------------------
    # Load current state
    # -------------------------
    rows = get_bonus_survey_structure_rows(
        bonus_survey_id=bonus_survey_id
    )

    # structure_id → current row
    row_map = {
        r["structure_id"]: r
        for r in rows
    }

    # -------------------------
    # Merge current + incoming
    # -------------------------
    merged = {}

    for r in rows:
        merged[r["structure_id"]] = {
            "structure_id": r["structure_id"],
            "placement_type": r["placement_type"],
            "section_key": r.get("section_key"),
        }

    for a in assignments:
        sid = a["structure_id"]

        if sid not in merged:
            continue

        merged[sid]["placement_type"] = a.get("placement_type")
        merged[sid]["section_key"] = a.get("section_key")

    # -------------------------
    # Group sections
    # -------------------------
    sections = defaultdict(list)

    for item in merged.values():
        if item["placement_type"] != "section":
            continue

        key = item["section_key"] or "unknown"
        sections[key].append(item["structure_id"])

    # -------------------------
    # Assign ordering
    # -------------------------
    sorted_keys = sorted(sections.keys())

    section_order_map = {
        key: idx + 1
        for idx, key in enumerate(sorted_keys)
    }

    # -------------------------
    # Build updates
    # -------------------------
    updates = []

    for item in merged.values():
        sid = item["structure_id"]
        placement = item["placement_type"]
        section_key = item["section_key"]

        if placement == "section" and section_key:
            section_order = section_order_map[section_key]

            # 🔒 CRITICAL: preserve original order
            question_order = row_map[sid]["question_order"]

        else:
            section_order = 0

            # 🔒 CRITICAL: preserve original order
            question_order = row_map[sid]["question_order"]

            if placement != "section":
                section_key = None

        updates.append({
            "structure_id": sid,
            "placement_type": placement,
            "section_key": section_key,
            "section_order": section_order,
            "question_order": question_order,
        })

    # -------------------------
    # Persist
    # -------------------------
    update_bonus_survey_question_placement_batch(
        bonus_survey_id=bonus_survey_id,
        updates=updates,
    )

def build_structured_results(*, bonus_survey_id: int) -> dict:
    """
    Combine:
    - structure (ordering + grouping)
    - answers (raw data)

    Returns structured numeric results only.

    Source-of-truth identity:
    - QuestionHash + QuestionOrder identifies the question position.
    - AnswerID identifies the answer row.

    Important:
    get_bonus_survey_answer_rows() joins profile data, which can duplicate
    answer rows. Numeric averages must dedupe by AnswerID, not by AnswerText.
    """

    from collections import defaultdict
    from app.db.bonus_survey_question_structure import get_bonus_survey_structure_rows
    from app.db.bonus_survey_answers import get_bonus_survey_answer_rows

    structure_rows = get_bonus_survey_structure_rows(
        bonus_survey_id=bonus_survey_id
    )

    answer_rows = get_bonus_survey_answer_rows(
        bonus_survey_id=bonus_survey_id
    )

    # -------------------------
    # Build numeric answer map
    # -------------------------
    answers_by_question = defaultdict(list)
    seen_answer_ids = set()

    for row in answer_rows:
        answer_id = row.get("AnswerID")

        if answer_id in seen_answer_ids:
            continue

        seen_answer_ids.add(answer_id)

        question_hash = row.get("QuestionHash")
        question_order = row.get("QuestionOrder")
        answer_text = row.get("AnswerText")

        if not question_hash:
            continue

        if answer_text is None:
            continue

        try:
            numeric_value = float(answer_text)
        except (TypeError, ValueError):
            continue

        question_key = f"{question_hash}__{question_order}"
        answers_by_question[question_key].append(numeric_value)

    # -------------------------
    # Build sections
    # -------------------------
    sections = defaultdict(list)
    section_order_map = {}

    for row in structure_rows:
        placement = row["placement_type"]

        if placement == "profile":
            section_key = "Profile"
        elif placement == "section":
            section_key = row["section_key"] or "Unknown"
        elif placement == "unassigned":
            section_key = "Unassigned"
        else:
            continue

        sections[section_key].append(row)

        if placement == "section":
            section_order_map[section_key] = row.get("section_order") or 0

    # -------------------------
    # Compute metrics
    # -------------------------
    result = []

    sorted_section_names = sorted(
        sections.keys(),
        key=lambda key: section_order_map.get(key, 9999),
    )

    for section_name in sorted_section_names:
        questions = sorted(
            sections[section_name],
            key=lambda row: row.get("question_order") or 0,
        )

        question_results = []
        section_scores = []

        for question in questions:
            question_hash = question["question_hash"]
            question_text = question["question_text"]
            question_order = question.get("question_order")
            question_key = f"{question_hash}__{question_order}"

            values = answers_by_question.get(question_key, [])

            if values:
                avg = round(sum(values) / len(values), 2)
                section_scores.append(avg)
            else:
                avg = None

            question_results.append({
                "question_text": question_text,
                "question_hash": question_hash,
                "question_order": question_order,
                "avg": avg,
                "response_count": len(values),
            })

        section_avg = (
            round(sum(section_scores) / len(section_scores), 2)
            if section_scores else None
        )

        result.append({
            "section_name": section_name,
            "questions": question_results,
            "section_avg": section_avg,
        })

    return {
        "sections": result,
    }

def build_structured_qualitative_results(*, bonus_survey_id: int) -> dict:
    """
    Build qualitative responses per question.

    Source-of-truth identity:
    - QuestionHash + QuestionOrder identifies the question position.
    - AnswerID identifies the answer row.

    Important:
    get_bonus_survey_answer_rows() joins profile data, which can duplicate
    answer rows. Qualitative answers must dedupe by AnswerID, not by AnswerText.

    If two different participants submit the same text, both responses remain
    valid survey responses and should be preserved.
    """

    from collections import defaultdict
    from app.db.bonus_survey_question_structure import get_bonus_survey_structure_rows
    from app.db.bonus_survey_answers import get_bonus_survey_answer_rows

    structure_rows = get_bonus_survey_structure_rows(
        bonus_survey_id=bonus_survey_id
    )

    answer_rows = get_bonus_survey_answer_rows(
        bonus_survey_id=bonus_survey_id
    )

    # -------------------------
    # Build qualitative answer map
    # -------------------------
    qual_answers_by_question = defaultdict(list)
    seen_answer_ids = set()

    for row in answer_rows:
        answer_id = row.get("AnswerID")

        if answer_id in seen_answer_ids:
            continue

        seen_answer_ids.add(answer_id)

        question_hash = row.get("QuestionHash")
        question_order = row.get("QuestionOrder")

        if not question_hash:
            continue

        question_key = f"{question_hash}__{question_order}"

        answer_text = row.get("AnswerText")

        if answer_text is None:
            continue

        answer_text = str(answer_text).strip()
        if not answer_text:
            continue

        try:
            float(answer_text)
            continue  # skip numeric
        except (TypeError, ValueError):
            qual_answers_by_question[question_key].append(answer_text)

    # -------------------------
    # Build sections
    # -------------------------
    sections = defaultdict(list)
    section_order_map = {}

    for row in structure_rows:
        placement = row["placement_type"]

        if placement == "profile":
            section_key = "Profile"
        elif placement == "section":
            section_key = row["section_key"] or "Unknown"
        elif placement == "unassigned":
            section_key = "Unassigned"
        else:
            continue

        sections[section_key].append(row)

        if placement == "section":
            section_order_map[section_key] = row.get("section_order") or 0

    # -------------------------
    # Build result
    # -------------------------
    result = []

    sorted_section_names = sorted(
        sections.keys(),
        key=lambda key: section_order_map.get(key, 9999),
    )

    for section_name in sorted_section_names:
        questions = sorted(
            sections[section_name],
            key=lambda row: row.get("question_order") or 0,
        )

        question_results = []

        for question in questions:
            question_hash = question["question_hash"]
            question_text = question["question_text"]
            question_order = question.get("question_order")

            lookup_key = f"{question_hash}__{question_order}"
            answers = qual_answers_by_question.get(lookup_key, [])

            if not answers:
                continue

            question_results.append({
                "question_text": question_text,
                "question_hash": question_hash,
                "question_order": question_order,
                "answers": answers,
                "response_count": len(answers),
            })

        result.append({
            "section_name": section_name,
            "questions": question_results,
        })

    return {
        "sections": result,
    }