# app/services/permission_context.py

from app.constants.permission_levels import PERMISSION_LEVELS
from app.db.user_roles import get_effective_permission_level

ROLE_LABELS = {
    0: "Guest",
    20: "Participant",
    30: "Legal Team",
    40: "Bonus Survey Creator",
    50: "Product Team",
    60: "Management",
    70: "UT Lead",
    80: "IT Admin",
    100: "Admin",
}

ADMIN_VIEW_MODE_MIN_LEVEL = 100
ADMIN_VIEW_MODE_LEVELS = [20, 30, 40, 50, 60, 70, 80, 100]


def get_role_label(permission_level: int) -> str:
    try:
        safe_level = int(permission_level or 0)
    except (TypeError, ValueError):
        safe_level = 0

    return ROLE_LABELS.get(safe_level, f"Level {safe_level}")


def get_admin_view_mode_levels() -> list[dict]:
    rows = []

    for level in ADMIN_VIEW_MODE_LEVELS:
        rows.append({
            "permission_level": level,
            "label": get_role_label(level),
        })

    return rows


def _normalize_permission_level(value) -> int | None:
    try:
        safe_value = int(value)
    except (TypeError, ValueError):
        return None

    if safe_value not in set(PERMISSION_LEVELS):
        return None

    return safe_value


def get_permission_context(*, user_id: str, session_id: str | None = None) -> dict:
    """
    Return real and display permission levels for the current request.

    Real permission level remains authoritative for mutations/security.
    Effective permission level is for rendering/admin preview mode only.
    """

    real_permission_level = get_effective_permission_level(user_id)
    effective_permission_level = real_permission_level
    view_as_permission_level = None

    can_use_admin_view_mode = real_permission_level >= ADMIN_VIEW_MODE_MIN_LEVEL

    if can_use_admin_view_mode and session_id:
        from app.db.admin_view_modes import get_admin_view_mode

        mode = get_admin_view_mode(
            session_id=session_id,
            actor_user_id=user_id,
        )

        if mode:
            normalized_view_as = _normalize_permission_level(mode.get("ViewAsPermissionLevel"))
            if normalized_view_as in ADMIN_VIEW_MODE_LEVELS:
                view_as_permission_level = normalized_view_as
                effective_permission_level = normalized_view_as

    return {
        "real_permission_level": real_permission_level,
        "real_permission_label": get_role_label(real_permission_level),
        "effective_permission_level": effective_permission_level,
        "effective_permission_label": get_role_label(effective_permission_level),
        "view_as_permission_level": view_as_permission_level,
        "view_as_permission_label": get_role_label(view_as_permission_level) if view_as_permission_level is not None else "",
        "is_viewing_as": view_as_permission_level is not None,
        "can_use_admin_view_mode": can_use_admin_view_mode,
        "admin_view_mode_levels": get_admin_view_mode_levels(),
    }


def set_admin_view_mode_for_session(*, user_id: str, session_id: str, view_as_permission_level) -> dict:
    """
    Validate and persist an admin view mode selection.
    """

    if not user_id or not session_id:
        return {"ok": False, "error": "missing_session"}

    real_permission_level = get_effective_permission_level(user_id)
    if real_permission_level < ADMIN_VIEW_MODE_MIN_LEVEL:
        return {"ok": False, "error": "not_allowed"}

    normalized_view_as = _normalize_permission_level(view_as_permission_level)
    if normalized_view_as not in ADMIN_VIEW_MODE_LEVELS:
        return {"ok": False, "error": "invalid_permission_level"}

    from app.db.admin_view_modes import set_admin_view_mode

    set_admin_view_mode(
        session_id=session_id,
        actor_user_id=user_id,
        real_permission_level=real_permission_level,
        view_as_permission_level=normalized_view_as,
    )

    return {"ok": True}


def clear_admin_view_mode_for_session(*, user_id: str, session_id: str) -> dict:
    """
    Clear this session's admin view mode.
    """

    if not user_id or not session_id:
        return {"ok": False, "error": "missing_session"}

    real_permission_level = get_effective_permission_level(user_id)
    if real_permission_level < ADMIN_VIEW_MODE_MIN_LEVEL:
        return {"ok": False, "error": "not_allowed"}

    from app.db.admin_view_modes import clear_admin_view_mode

    clear_admin_view_mode(
        session_id=session_id,
        actor_user_id=user_id,
    )

    return {"ok": True}