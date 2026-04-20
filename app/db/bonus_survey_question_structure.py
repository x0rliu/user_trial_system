# app/db/bonus_survey_question_structure.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_distinct_bonus_survey_questions(*, bonus_survey_id: int) -> list[dict]:
    """
    Return the distinct raw questions present in bonus_survey_answers
    for a given bonus survey.

    This is the source set used to initialize structure rows.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                a.QuestionHash AS question_hash,
                a.QuestionText AS question_text,
                a.AnswerID AS first_seen_id
            FROM bonus_survey_answers a
            JOIN bonus_survey_participation p
                ON p.bonus_survey_participation_id = a.bonus_survey_participation_id
            WHERE p.bonus_survey_id = %s
            AND p.bonus_survey_participation_id = (
                    SELECT MIN(p2.bonus_survey_participation_id)
                    FROM bonus_survey_participation p2
                    WHERE p2.bonus_survey_id = %s
                )
            ORDER BY
                a.AnswerID ASC
            """,
            (bonus_survey_id, bonus_survey_id),  # ← FIX
        )

        return cur.fetchall() or []
    finally:
        cur.close()
        conn.close()


def get_bonus_survey_structure_rows(*, bonus_survey_id: int) -> list[dict]:
    """
    Return all persisted structure rows for a bonus survey.

    Ordering:
    - profile first
    - section second
    - unassigned last
    - then section_order
    - then question_order
    - then question_text
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                structure_id,
                bonus_survey_id,
                question_hash,
                question_text,
                placement_type,
                section_key,
                section_order,
                question_order,
                is_locked,
                created_at,
                updated_at
            FROM bonus_survey_question_structure
            WHERE bonus_survey_id = %s
            ORDER BY
                question_order ASC,
                structure_id ASC
            """,
            (bonus_survey_id,),
        )

        return cur.fetchall() or []
    finally:
        cur.close()
        conn.close()


def bonus_survey_structure_exists(*, bonus_survey_id: int) -> bool:
    """
    Check whether structure rows already exist for this survey.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT 1
            FROM bonus_survey_question_structure
            WHERE bonus_survey_id = %s
            LIMIT 1
            """,
            (bonus_survey_id,),
        )

        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def initialize_bonus_survey_structure_as_unassigned(*, bonus_survey_id: int) -> int:
    """
    Seed structure rows using FIRST participant as canonical survey structure.

    Guarantees:
    - preserves column order
    - preserves duplicate question labels
    - avoids GROUP BY collapse
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # Step 1 — get first participant
        cur.execute(
            """
            SELECT MIN(p.bonus_survey_participation_id) AS pid
            FROM bonus_survey_participation p
            WHERE p.bonus_survey_id = %s
            """,
            (bonus_survey_id,),
        )

        row = cur.fetchone()
        if not row or not row["pid"]:
            return 0

        first_pid = row["pid"]

        # Step 2 — get ordered answers for that participant
        cur.execute(
            """
            SELECT
                a.QuestionHash AS question_hash,
                a.QuestionText AS question_text,
                a.AnswerID
            FROM bonus_survey_answers a
            WHERE a.bonus_survey_participation_id = %s
            ORDER BY a.AnswerID ASC
            """,
            (first_pid,),
        )

        questions = cur.fetchall()

        if not questions:
            return 0

        # Step 3 — insert structure rows
        inserted_count = 0

        for idx, q in enumerate(questions, start=1):
            question_hash = (q["question_hash"] or "").strip()
            question_text = (q["question_text"] or "").strip()

            if not question_hash or not question_text:
                continue

            cur.execute(
                """
                INSERT INTO bonus_survey_question_structure (
                    bonus_survey_id,
                    question_hash,
                    question_text,
                    placement_type,
                    section_key,
                    section_order,
                    question_order,
                    is_locked
                )
                VALUES (%s, %s, %s, 'unassigned', NULL, 0, %s, 0)
                """,
                (
                    bonus_survey_id,
                    question_hash,
                    question_text,
                    idx,
                ),
            )

            if cur.rowcount == 1:
                inserted_count += 1

        conn.commit()
        return inserted_count

    finally:
        cur.close()
        conn.close()


def update_bonus_survey_question_placement(
    *,
    structure_id: int,
    placement_type: str,
    section_key: str | None,
    section_order: int,
    question_order: int,
) -> None:
    """
    Update a single question row's placement.

    Valid placement_type values:
    - profile
    - section
    - unassigned

    Rules:
    - profile => section_key forced to NULL
    - unassigned => section_key forced to NULL
    - section => section_key required
    - locked rows cannot be modified
    """

    normalized_placement = (placement_type or "").strip().lower()
    normalized_section_key = (section_key or "").strip() or None

    if normalized_placement not in {"profile", "section", "unassigned"}:
        raise ValueError(f"Invalid placement_type: {placement_type}")

    if normalized_placement == "section" and not normalized_section_key:
        raise ValueError("section_key is required when placement_type='section'")

    if normalized_placement in {"profile", "unassigned"}:
        normalized_section_key = None

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_survey_question_structure
            SET
                placement_type = %s,
                section_key = %s,
                section_order = %s,
                question_order = %s
            WHERE structure_id = %s
              AND is_locked = 0
            """,
            (
                normalized_placement,
                normalized_section_key,
                section_order,
                question_order,
                structure_id,
            ),
        )

        conn.commit()

        if cur.rowcount == 0:
            raise RuntimeError(
                f"Structure row not updated. It may not exist or may already be locked. structure_id={structure_id}"
            )
    finally:
        cur.close()
        conn.close()


def rename_bonus_survey_section(
    *,
    bonus_survey_id: int,
    old_section_key: str,
    new_section_key: str,
) -> None:
    """
    Rename a section across all unlocked rows in the survey.

    Rules:
    - only affects rows with placement_type='section'
    - locked rows cannot be modified
    - new_section_key must be non-empty
    """

    normalized_old = (old_section_key or "").strip()
    normalized_new = (new_section_key or "").strip()

    if not normalized_old:
        raise ValueError("old_section_key is required")

    if not normalized_new:
        raise ValueError("new_section_key is required")

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_survey_question_structure
            SET section_key = %s
            WHERE bonus_survey_id = %s
              AND placement_type = 'section'
              AND section_key = %s
              AND is_locked = 0
            """,
            (
                normalized_new,
                bonus_survey_id,
                normalized_old,
            ),
        )

        conn.commit()
    finally:
        cur.close()
        conn.close()


def lock_bonus_survey_structure(*, bonus_survey_id: int) -> None:
    """
    Lock all structure rows for a survey.

    This should only be called after validation in the service layer.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_survey_question_structure
            SET is_locked = 1
            WHERE bonus_survey_id = %s
            """,
            (bonus_survey_id,),
        )

        conn.commit()
    finally:
        cur.close()
        conn.close()


def unlock_bonus_survey_structure(*, bonus_survey_id: int) -> None:
    """
    Unlock all structure rows for a survey.

    Use sparingly. This exists for controlled admin/service workflows.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_survey_question_structure
            SET is_locked = 0
            WHERE bonus_survey_id = %s
            """,
            (bonus_survey_id,),
        )

        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_bonus_survey_structure_summary(*, bonus_survey_id: int) -> dict:
    """
    Return lightweight counts for structure state.

    Useful for gating UI and future validation.

    Output:
    {
        "total_questions": int,
        "profile_count": int,
        "section_count": int,
        "unassigned_count": int,
        "locked_count": int
    }
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                COUNT(*) AS total_questions,
                SUM(CASE WHEN placement_type = 'profile' THEN 1 ELSE 0 END) AS profile_count,
                SUM(CASE WHEN placement_type = 'section' THEN 1 ELSE 0 END) AS section_count,
                SUM(CASE WHEN placement_type = 'unassigned' THEN 1 ELSE 0 END) AS unassigned_count,
                SUM(CASE WHEN is_locked = 1 THEN 1 ELSE 0 END) AS locked_count
            FROM bonus_survey_question_structure
            WHERE bonus_survey_id = %s
            """,
            (bonus_survey_id,),
        )

        row = cur.fetchone() or {}

        return {
            "total_questions": int(row.get("total_questions") or 0),
            "profile_count": int(row.get("profile_count") or 0),
            "section_count": int(row.get("section_count") or 0),
            "unassigned_count": int(row.get("unassigned_count") or 0),
            "locked_count": int(row.get("locked_count") or 0),
        }
    finally:
        cur.close()
        conn.close()

def reset_bonus_survey_structure_to_unassigned(*, bonus_survey_id: int):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_survey_question_structure
            SET
                placement_type = 'unassigned',
                section_key = NULL,
                section_order = 0,
                question_order = 0
            WHERE bonus_survey_id = %s
              AND is_locked = 0
            """,
            (bonus_survey_id,),
        )

        conn.commit()
    finally:
        cur.close()
        conn.close()

def classify_profile_questions(*, bonus_survey_id: int):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT structure_id, question_text
            FROM bonus_survey_question_structure
            WHERE bonus_survey_id = %s
              AND placement_type = 'unassigned'
            """,
            (bonus_survey_id,)
        )

        rows = cur.fetchall()

        def _is_profile(q: str) -> bool:
            ql = q.lower()
            return any([
                "gender" in ql,
                "age" in ql,
                "country" in ql,
                "name" in ql,
                "what logitech product" in ql,
                "how often do you" in ql,
                "what go-to avenues" in ql,
            ])

        for r in rows:
            if _is_profile(r["question_text"]):
                cur.execute(
                    """
                    UPDATE bonus_survey_question_structure
                    SET placement_type = 'profile'
                    WHERE structure_id = %s
                    """,
                    (r["structure_id"],)
                )

        conn.commit()
    finally:
        cur.close()
        conn.close()

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

                # 🔒 CRITICAL: NEVER TOUCH question_order
                new_question_order = current["question_order"]

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