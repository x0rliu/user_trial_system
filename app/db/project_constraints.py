# app/db/project_constraints.py

from app.db.connection import get_db_connection


ALLOWED_CONSTRAINT_CATEGORIES = {
    "audience",
    "timeline",
    "geography",
    "sample",
    "product",
    "logistics",
    "survey",
    "recruiting",
    "success_metric",
    "exclusion",
    "risk",
    "other",
}

ALLOWED_CONSTRAINT_PRIORITIES = {
    "must_have",
    "should_have",
    "nice_to_have",
    "unknown",
}

ALLOWED_CONSTRAINT_SOURCES = {
    "product_team",
    "ut_lead",
    "historical",
    "system",
    "ai_suggested",
    "manual",
}


def _clean_text(value) -> str:
    return str(value or "").strip()


def _normalize_category(value) -> str:
    category = _clean_text(value).lower()
    return category if category in ALLOWED_CONSTRAINT_CATEGORIES else "other"


def _normalize_priority(value) -> str:
    priority = _clean_text(value).lower()
    return priority if priority in ALLOWED_CONSTRAINT_PRIORITIES else "unknown"


def _normalize_source(value) -> str:
    source = _clean_text(value).lower()
    return source if source in ALLOWED_CONSTRAINT_SOURCES else "manual"


def _format_constraint_row(row: dict) -> dict:
    return {
        "constraint_id": row.get("ConstraintID"),
        "project_id": row.get("ProjectID"),
        "round_id": row.get("RoundID"),
        "constraint_category": row.get("ConstraintCategory"),
        "constraint_key": row.get("ConstraintKey"),
        "constraint_value": row.get("ConstraintValue"),
        "constraint_priority": row.get("ConstraintPriority"),
        "constraint_source": row.get("ConstraintSource"),
        "is_active": int(row.get("IsActive") or 0),
        "created_by_user_id": row.get("CreatedByUserID"),
        "created_at": row.get("CreatedAt"),
        "updated_at": row.get("UpdatedAt"),
    }

def active_constraint_exists(
    *,
    project_id: str,
    round_id: int | None,
    constraint_category: str,
    constraint_key: str,
    constraint_value: str,
) -> bool:
    """
    Check whether the same active explicit constraint already exists.

    Exact-scope check:
    - round_id None checks project-level constraints only
    - round_id value checks that specific round only
    """

    project_id = _clean_text(project_id)
    category = _normalize_category(constraint_category)
    constraint_key = _clean_text(constraint_key)
    constraint_value = _clean_text(constraint_value)

    if not project_id or not constraint_key or not constraint_value:
        return False

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if round_id is None:
            cursor.execute(
                """
                SELECT 1
                FROM project_round_constraints
                WHERE ProjectID = %s
                  AND RoundID IS NULL
                  AND ConstraintCategory = %s
                  AND LOWER(ConstraintKey) = LOWER(%s)
                  AND LOWER(ConstraintValue) = LOWER(%s)
                  AND IsActive = 1
                LIMIT 1
                """,
                (
                    project_id,
                    category,
                    constraint_key,
                    constraint_value,
                ),
            )
        else:
            cursor.execute(
                """
                SELECT 1
                FROM project_round_constraints
                WHERE ProjectID = %s
                  AND RoundID = %s
                  AND ConstraintCategory = %s
                  AND LOWER(ConstraintKey) = LOWER(%s)
                  AND LOWER(ConstraintValue) = LOWER(%s)
                  AND IsActive = 1
                LIMIT 1
                """,
                (
                    project_id,
                    round_id,
                    category,
                    constraint_key,
                    constraint_value,
                ),
            )

        return cursor.fetchone() is not None

    finally:
        cursor.close()
        conn.close()


def create_project_round_constraint(
    *,
    project_id: str,
    round_id: int | None,
    constraint_category: str,
    constraint_key: str,
    constraint_value: str,
    created_by_user_id: str,
    constraint_priority: str = "unknown",
    constraint_source: str = "ut_lead",
) -> int:
    """
    Create one explicit project/round constraint.

    Mutates DB. Caller must validate ownership/permission before calling.
    """

    project_id = _clean_text(project_id)
    constraint_key = _clean_text(constraint_key)
    constraint_value = _clean_text(constraint_value)
    created_by_user_id = _clean_text(created_by_user_id)

    if not project_id:
        raise ValueError("project_id is required")

    if not constraint_key:
        raise ValueError("constraint_key is required")

    if not constraint_value:
        raise ValueError("constraint_value is required")

    if not created_by_user_id:
        raise ValueError("created_by_user_id is required")

    category = _normalize_category(constraint_category)
    priority = _normalize_priority(constraint_priority)
    source = _normalize_source(constraint_source)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO project_round_constraints (
                ProjectID,
                RoundID,
                ConstraintCategory,
                ConstraintKey,
                ConstraintValue,
                ConstraintPriority,
                ConstraintSource,
                IsActive,
                CreatedByUserID
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s)
            """,
            (
                project_id,
                round_id,
                category,
                constraint_key,
                constraint_value,
                priority,
                source,
                created_by_user_id,
            ),
        )

        constraint_id = cursor.lastrowid
        conn.commit()
        return constraint_id

    finally:
        cursor.close()
        conn.close()


def list_constraints_for_project(
    *,
    project_id: str,
    round_id: int | None = None,
    active_only: bool = True,
) -> list[dict]:
    """
    List explicit constraints for a project.

    If round_id is provided, returns project-level constraints plus constraints
    for that round.
    """

    project_id = _clean_text(project_id)
    if not project_id:
        return []

    where_parts = ["ProjectID = %s"]
    params = [project_id]

    if round_id is not None:
        where_parts.append("(RoundID IS NULL OR RoundID = %s)")
        params.append(round_id)

    if active_only:
        where_parts.append("IsActive = 1")

    where_sql = " AND ".join(where_parts)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            f"""
            SELECT
                ConstraintID,
                ProjectID,
                RoundID,
                ConstraintCategory,
                ConstraintKey,
                ConstraintValue,
                ConstraintPriority,
                ConstraintSource,
                IsActive,
                CreatedByUserID,
                CreatedAt,
                UpdatedAt
            FROM project_round_constraints
            WHERE {where_sql}
            ORDER BY
                FIELD(ConstraintPriority, 'must_have', 'should_have', 'nice_to_have', 'unknown'),
                ConstraintCategory ASC,
                ConstraintKey ASC,
                ConstraintID ASC
            """,
            tuple(params),
        )

        return [
            _format_constraint_row(row)
            for row in cursor.fetchall()
        ]

    finally:
        cursor.close()
        conn.close()


def list_constraints_for_round(
    *,
    round_id: int,
    active_only: bool = True,
) -> list[dict]:
    """
    List explicit constraints attached directly to one round.
    """

    if not round_id:
        return []

    where_parts = ["RoundID = %s"]
    params = [round_id]

    if active_only:
        where_parts.append("IsActive = 1")

    where_sql = " AND ".join(where_parts)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            f"""
            SELECT
                ConstraintID,
                ProjectID,
                RoundID,
                ConstraintCategory,
                ConstraintKey,
                ConstraintValue,
                ConstraintPriority,
                ConstraintSource,
                IsActive,
                CreatedByUserID,
                CreatedAt,
                UpdatedAt
            FROM project_round_constraints
            WHERE {where_sql}
            ORDER BY
                FIELD(ConstraintPriority, 'must_have', 'should_have', 'nice_to_have', 'unknown'),
                ConstraintCategory ASC,
                ConstraintKey ASC,
                ConstraintID ASC
            """,
            tuple(params),
        )

        return [
            _format_constraint_row(row)
            for row in cursor.fetchall()
        ]

    finally:
        cursor.close()
        conn.close()


def deactivate_project_round_constraint(
    *,
    constraint_id: int,
    project_id: str,
) -> int:
    """
    Soft-delete a constraint by marking it inactive.

    ProjectID is required so callers cannot deactivate constraints outside the
    project they already proved access to.
    """

    project_id = _clean_text(project_id)

    if not constraint_id:
        raise ValueError("constraint_id is required")

    if not project_id:
        raise ValueError("project_id is required")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE project_round_constraints
            SET IsActive = 0
            WHERE ConstraintID = %s
              AND ProjectID = %s
              AND IsActive = 1
            """,
            (
                constraint_id,
                project_id,
            ),
        )

        affected_rows = cursor.rowcount
        conn.commit()
        return affected_rows

    finally:
        cursor.close()
        conn.close()