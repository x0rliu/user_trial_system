# app/services/constraint_capture_service.py

from app.db.project_constraints import (
    ALLOWED_CONSTRAINT_CATEGORIES,
    ALLOWED_CONSTRAINT_PRIORITIES,
    ALLOWED_CONSTRAINT_SOURCES,
    active_constraint_exists,
    create_project_round_constraint,
    deactivate_project_round_constraint,
    list_constraints_for_project,
)


MAX_CONSTRAINT_KEY_LENGTH = 100
MAX_CONSTRAINT_VALUE_LENGTH = 1000


def _clean_text(value) -> str:
    return str(value or "").strip()


def _normalize_free_text(value) -> str:
    return " ".join(_clean_text(value).split())


def _group_constraints_by_category(constraints: list[dict]) -> dict:
    grouped = {}

    for constraint in constraints:
        category = constraint.get("constraint_category") or "other"
        grouped.setdefault(category, [])
        grouped[category].append(constraint)

    return grouped


def build_constraint_capture_packet(
    *,
    project_id: str,
    round_id: int | None = None,
) -> dict:
    """
    Build a read-only packet of constraints for display/analysis.

    No inference.
    No recommendations.
    """

    constraints = list_constraints_for_project(
        project_id=project_id,
        round_id=round_id,
        active_only=True,
    )

    limitations = []

    if not constraints:
        limitations.append(
            "No explicit constraints have been captured for this project or round yet."
        )

    must_have_count = len([
        item for item in constraints
        if item.get("constraint_priority") == "must_have"
    ])

    should_have_count = len([
        item for item in constraints
        if item.get("constraint_priority") == "should_have"
    ])

    nice_to_have_count = len([
        item for item in constraints
        if item.get("constraint_priority") == "nice_to_have"
    ])

    unknown_priority_count = len([
        item for item in constraints
        if item.get("constraint_priority") == "unknown"
    ])

    project_scope_count = len([
        item for item in constraints
        if item.get("round_id") is None
    ])

    round_scope_count = len([
        item for item in constraints
        if item.get("round_id") is not None
    ])

    return {
        "project_id": project_id,
        "round_id": round_id,
        "constraint_count": len(constraints),
        "project_scope_count": project_scope_count,
        "round_scope_count": round_scope_count,
        "must_have_count": must_have_count,
        "should_have_count": should_have_count,
        "nice_to_have_count": nice_to_have_count,
        "unknown_priority_count": unknown_priority_count,
        "constraints": constraints,
        "constraints_by_category": _group_constraints_by_category(constraints),
        "allowed_categories": sorted(ALLOWED_CONSTRAINT_CATEGORIES),
        "allowed_priorities": sorted(ALLOWED_CONSTRAINT_PRIORITIES),
        "allowed_sources": sorted(ALLOWED_CONSTRAINT_SOURCES),
        "limitations": limitations,
    }


def save_explicit_constraint(
    *,
    project_id: str,
    round_id: int | None,
    constraint_category: str,
    constraint_key: str,
    constraint_value: str,
    created_by_user_id: str,
    constraint_priority: str = "unknown",
    constraint_source: str = "ut_lead",
) -> dict:
    """
    Save one explicit constraint.

    This service does not validate ownership. Callers must validate ownership
    and permission before calling.
    """

    project_id = _clean_text(project_id)
    constraint_key = _normalize_free_text(constraint_key)
    constraint_value = _normalize_free_text(constraint_value)
    created_by_user_id = _clean_text(created_by_user_id)

    if not project_id:
        return {
            "success": False,
            "constraint_id": None,
            "error": "missing_project_id",
        }

    if not constraint_key:
        return {
            "success": False,
            "constraint_id": None,
            "error": "missing_constraint_key",
        }

    if not constraint_value:
        return {
            "success": False,
            "constraint_id": None,
            "error": "missing_constraint_value",
        }

    if not created_by_user_id:
        return {
            "success": False,
            "constraint_id": None,
            "error": "missing_created_by_user_id",
        }

    if len(constraint_key) > MAX_CONSTRAINT_KEY_LENGTH:
        return {
            "success": False,
            "constraint_id": None,
            "error": "constraint_key_too_long",
        }

    if len(constraint_value) > MAX_CONSTRAINT_VALUE_LENGTH:
        return {
            "success": False,
            "constraint_id": None,
            "error": "constraint_value_too_long",
        }

    if active_constraint_exists(
        project_id=project_id,
        round_id=round_id,
        constraint_category=constraint_category,
        constraint_key=constraint_key,
        constraint_value=constraint_value,
    ):
        return {
            "success": False,
            "constraint_id": None,
            "error": "duplicate_constraint",
        }

    try:
        constraint_id = create_project_round_constraint(
            project_id=project_id,
            round_id=round_id,
            constraint_category=constraint_category,
            constraint_key=constraint_key,
            constraint_value=constraint_value,
            created_by_user_id=created_by_user_id,
            constraint_priority=constraint_priority,
            constraint_source=constraint_source,
        )
    except Exception:
        return {
            "success": False,
            "constraint_id": None,
            "error": "save_failed",
        }

    return {
        "success": True,
        "constraint_id": constraint_id,
        "error": None,
    }

def deactivate_explicit_constraint(
    *,
    project_id: str,
    constraint_id: int,
) -> dict:
    """
    Deactivate one explicit constraint.

    This service does not validate ownership. Callers must validate ownership
    and permission before calling.
    """

    if not _clean_text(project_id):
        return {
            "success": False,
            "error": "missing_project_id",
        }

    try:
        constraint_id = int(constraint_id)
    except (TypeError, ValueError):
        return {
            "success": False,
            "error": "invalid_constraint_id",
        }

    try:
        affected_rows = deactivate_project_round_constraint(
            project_id=project_id,
            constraint_id=constraint_id,
        )
    except Exception:
        return {
            "success": False,
            "error": "deactivate_failed",
        }

    if affected_rows <= 0:
        return {
            "success": False,
            "error": "constraint_not_found",
        }

    return {
        "success": True,
        "error": None,
    }