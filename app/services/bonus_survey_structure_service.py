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
    - Uses question order to group sections
    - Pairs qualitative questions to preceding quant block
    - Does NOT use AI for grouping
    """

    from app.db.bonus_survey_question_structure import (
        get_bonus_survey_structure_rows,
        update_bonus_survey_question_placement
    )

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
    # Load structure rows (ordered)
    # -------------------------
    rows = get_bonus_survey_structure_rows(
        bonus_survey_id=bonus_survey_id
    )

    filtered_rows = []

    for r in rows:
        q = (r.get("question_text") or "").strip()

        if not q:
            continue

        if r["placement_type"] != "unassigned":
            continue

        if _is_profile(q) or _is_admin(q):
            continue

        filtered_rows.append(r)

    ordered_rows = filtered_rows

    from app.db.bonus_survey_answers import get_bonus_survey_answer_rows

    answer_rows = get_bonus_survey_answer_rows(
        bonus_survey_id=bonus_survey_id
    )

    answer_map = defaultdict(list)

    for r in answer_rows:
        q_hash = r.get("QuestionHash")
        a = (r.get("AnswerText") or "").strip()

        if q_hash and a:
            answer_map[q_hash].append(a)

    # -------------------------
    # Build sections deterministically
    # -------------------------
    sections = []
    current_section = []

    for r in ordered_rows:
        q = (r.get("question_text") or "").strip()

        if not q:
            continue

        if _is_profile(q) or _is_admin(q):
            continue

        # -------------------------
        # QUAL → attach to previous section
        # -------------------------
        answers = answer_map.get(r.get("question_hash"), [])
        is_qual = _is_qual_by_answers(answers)

        if is_qual:
            if current_section:
                current_section.append(r)
            elif sections:
                sections[-1].append(r)
            else:
                sections.append([r])
            continue

        # -------------------------
        # QUANT → start new section
        # -------------------------
        if current_section:
            sections.append(current_section)

        current_section = [r]

    # catch final section
    if current_section:
        sections.append(current_section)

    # -------------------------
    # Persist sections
    # -------------------------
    section_order_counter = 1

    for section in sections:
        question_order_counter = 1

    for r in section:
        q = (r.get("question_text") or "").strip()

        if r["placement_type"] != "unassigned":
            continue

        # 🔥 HARD GUARD — NEVER allow profile/admin into sections
        if _is_profile(q) or _is_admin(q):
            continue

        update_bonus_survey_question_placement(
            structure_id=r["structure_id"],
            placement_type="section",
            section_key=f"section_{section_order_counter}",
            section_order=section_order_counter,
            question_order=question_order_counter,
        )

        question_order_counter += 1

        section_order_counter += 1

from collections import defaultdict

def _build_answer_map(rows):
    answer_map = defaultdict(list)

    for r in rows:
        q_hash = r.get("question_hash")
        a = (r.get("answer_text") or "").strip()

        if q_hash and a:
            answer_map[q_hash].append(a)

    return answer_map

def build_structure_view_model(*, bonus_survey_id: int) -> dict:
    """
    Build grouped structure for UI consumption.

    Output shape:

    {
        "profile": [...],
        "sections": [
            {
                "section_key": "...",
                "questions": [...],
                "section_order": int
            }
        ],
        "unassigned": [...]
    }
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
    answer_map = defaultdict(list)

    for r in answer_rows:
        q_hash = r.get("QuestionHash")
        a = (r.get("AnswerText") or "").strip()

        if q_hash and a:
            answer_map[q_hash].append(a)

    def _is_qual(q_hash: str) -> bool:
        return _is_qual_by_answers(answer_map.get(q_hash, []))

    # -------------------------
    # Build raw buckets
    # -------------------------
    profile = []
    unassigned = []

    sections_map = defaultdict(list)
    section_order_map = {}

    for r in rows:
        placement = r["placement_type"]
        q_text = (r["question_text"] or "").strip()

        if placement == "profile":
            profile.append(q_text)

        elif placement == "unassigned":
            unassigned.append(q_text)

        elif placement == "section":
            key = r["section_key"] or "unknown"

            sections_map[key].append({
                "question_text": q_text,
                "question_order": r["question_order"]
            })

            section_order_map[key] = r["section_order"]

    # -------------------------
    # Reattach QUAL (display only)
    # -------------------------
    # Goal:
    # If a qual question is sitting in unassigned,
    # attach it to the nearest preceding section
    # based on original question order.

    # Build ordered list of all questions
    ordered_questions = [
        {
            "q": (r["question_text"] or "").strip(),
            "question_hash": r.get("question_hash"),
            "placement": r["placement_type"],
            "section_key": r.get("section_key"),
            "order": r.get("question_order", 0)
        }
        for r in rows
    ]

    last_section_key = None

    for item in ordered_questions:
        q = item["q"]

        if item["placement"] == "section":
            last_section_key = item["section_key"]

        elif item["placement"] == "unassigned" and _is_qual(item.get("question_hash")):
            if last_section_key:
                sections_map[last_section_key].append({
                    "question_text": q,
                    "question_order": 999  # push to end of section
                })

                if q in unassigned:
                    unassigned.remove(q)

    # -------------------------
    # Sort sections
    # -------------------------
    sorted_sections = []

    for key, questions in sections_map.items():
        sorted_qs = sorted(
            questions,
            key=lambda x: x["question_order"]
        )

        sorted_sections.append({
            "section_key": key,
            "questions": [q["question_text"] for q in sorted_qs],
            "section_order": section_order_map.get(key, 0)
        })

    sorted_sections.sort(key=lambda x: x["section_order"])

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
    # Build answer map
    # -------------------------
    answers_by_question = defaultdict(list)

    for r in answer_rows:
        q = r["QuestionHash"]
        val = r["AnswerText"]

        if val is None:
            continue

        try:
            num = float(val)
            answers_by_question[q].append(num)
        except:
            continue  # skip qual

    # -------------------------
    # Build sections
    # -------------------------
    sections = defaultdict(list)

    for r in structure_rows:
        placement = r["placement_type"]
        key = None

        if placement == "profile":
            key = "Profile"
        elif placement == "section":
            key = r["section_key"] or "Unknown"
        elif placement == "unassigned":
            key = "Unassigned"
        else:
            continue

        sections[key].append(r)

    # -------------------------
    # Compute metrics
    # -------------------------
    result = []

    for section_name, questions in sections.items():
        q_results = []
        section_scores = []

        for q in questions:
            q_hash = q["question_hash"]
            q_text = q["question_text"]

            values = answers_by_question.get(q_hash, [])

            if values:
                avg = sum(values) / len(values)
                section_scores.append(avg)
            else:
                avg = None

            q_results.append({
                "question_text": q_text,
                "question_hash": q_hash,                 # ✅ ADD
                "question_order": q.get("question_order"),  # ✅ ADD
                "avg": avg,
            })

        section_avg = (
            sum(section_scores) / len(section_scores)
            if section_scores else None
        )

        result.append({
            "section_name": section_name,
            "questions": q_results,
            "section_avg": section_avg,
        })

    return {
        "sections": result
    }

def build_structured_qualitative_results(*, bonus_survey_id: int) -> dict:
    """
    Build qualitative responses per question.

    Returns:
    {
        "sections": [
            {
                "section_name": str,
                "questions": [
                    {
                        "question_text": str,
                        "question_hash": str,
                        "question_order": int,
                        "answers": [str, ...]
                    }
                ]
            }
        ]
    }
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

    for r in answer_rows:
        q_hash = r["QuestionHash"]
        q_order = r.get("QuestionOrder")

        # 🔑 CRITICAL: combine hash + order to preserve structure identity
        q_key = f"{q_hash}__{q_order}"

        val = r["AnswerText"]

        if val is None:
            continue

        val = str(val).strip()
        if not val:
            continue

        try:
            float(val)
            continue  # skip numeric
        except:
            if val not in qual_answers_by_question[q_key]:
                qual_answers_by_question[q_key].append(val)
                
    # -------------------------
    # Build sections
    # -------------------------
    sections = defaultdict(list)

    for r in structure_rows:
        placement = r["placement_type"]

        if placement == "profile":
            key = "Profile"
        elif placement == "section":
            key = r["section_key"] or "Unknown"
        elif placement == "unassigned":
            key = "Unassigned"
        else:
            continue

        sections[key].append(r)

    # -------------------------
    # Build result
    # -------------------------
    result = []

    for section_name, questions in sections.items():
        q_results = []

        for q in questions:
            q_hash = q["question_hash"]
            q_text = q["question_text"]

            lookup_key = f"{q_hash}__{q.get('question_order')}"
            answers = qual_answers_by_question.get(lookup_key, [])

            if not answers:
                continue

            q_results.append({
                "question_text": q_text,
                "question_hash": q_hash,
                "question_order": q.get("question_order"),
                "answers": answers
            })

        result.append({
            "section_name": section_name,
            "questions": q_results
        })

    return {
        "sections": result
    }