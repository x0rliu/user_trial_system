# app/db/dashboard_admin_stats.py

from datetime import datetime, timedelta

import mysql.connector
from app.config.config import DB_CONFIG


DEFAULT_WINDOW_DAYS = 30
_ALLOWED_WINDOW_DAYS = {30, 90, 180, 365}
_DUMMY_PATTERN = r"(^|[^a-z0-9])(test|dummy|demo|sample|fake|placeholder|asdf|fixture|seed)([^a-z0-9]|$)"
_DUMMY_EMAIL_PATTERNS = [
    "%@example.%",
    "%@test.%",
    "%@fake.%",
    "%@dummy.%",
    "%@demo.%",
]
_TERMINAL_ROUND_STATUSES = ("closed", "completed", "withdrawn", "declined", "cancelled")
_CURRENT_ROUND_STATUSES = ("recruiting", "screening", "active", "running")
_PLANNING_ROUND_STATUSES = ("pending_ut_review", "info_requested", "change_requested")


def _safe_window_days(window_days: int | None) -> int:
    try:
        safe_days = int(window_days or DEFAULT_WINDOW_DAYS)
    except (TypeError, ValueError):
        return DEFAULT_WINDOW_DAYS

    if safe_days in _ALLOWED_WINDOW_DAYS:
        return safe_days

    return DEFAULT_WINDOW_DAYS


def _cutoff_for_window(window_days: int) -> datetime:
    return datetime.now() - timedelta(days=window_days)


def _not_dummy_condition(fields: list[str]) -> tuple[str, list[str]]:
    checks = []
    params = []

    for field in fields:
        checks.append(f"LOWER(COALESCE({field}, '')) NOT REGEXP %s")
        params.append(_DUMMY_PATTERN)

    if not checks:
        return "1 = 1", []

    return "(" + " AND ".join(checks) + ")", params


def _real_user_condition(alias: str = "up") -> tuple[str, list]:
    condition, params = _not_dummy_condition([
        f"{alias}.user_id",
        f"{alias}.Email",
        f"{alias}.FirstName",
        f"{alias}.LastName",
    ])

    email_checks = []
    for pattern in _DUMMY_EMAIL_PATTERNS:
        email_checks.append(f"LOWER(COALESCE({alias}.Email, '')) NOT LIKE %s")
        params.append(pattern)

    if email_checks:
        condition = f"({condition} AND {' AND '.join(email_checks)})"

    return condition, params


def _real_project_condition(alias: str = "pp") -> tuple[str, list[str]]:
    return _not_dummy_condition([
        f"{alias}.ProjectID",
        f"{alias}.ProjectName",
        f"{alias}.MarketName",
    ])


def _real_product_condition(alias: str = "p") -> tuple[str, list[str]]:
    return _not_dummy_condition([
        f"{alias}.internal_name",
        f"{alias}.market_name",
        f"{alias}.product_type_display",
    ])


def _real_bonus_survey_condition(alias: str = "bs") -> tuple[str, list[str]]:
    return _not_dummy_condition([
        f"{alias}.survey_title",
    ])


def _fetch_one(cur, sql: str, params: list | tuple | None = None) -> dict:
    cur.execute(sql, tuple(params or []))
    return cur.fetchone() or {}


def _fetch_int(cur, sql: str, params: list | tuple | None = None, key: str = "total") -> int:
    row = _fetch_one(cur, sql, params)
    try:
        return int(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _fetch_rows(cur, sql: str, params: list | tuple | None = None) -> list[dict]:
    cur.execute(sql, tuple(params or []))
    return cur.fetchall() or []


def _percentage(numerator: int, denominator: int) -> int:
    if not denominator:
        return 0
    return int(round((int(numerator or 0) / int(denominator or 1)) * 100))


def get_admin_dashboard_stats(window_days: int | None = DEFAULT_WINDOW_DAYS) -> dict:
    """
    Return dashboard-ready Admin intelligence stats derived from DB state.

    This helper intentionally excludes obvious dummy/test/demo/sample data at the
    query layer so admin cards do not inflate sitewide metrics with fixture rows.
    """

    safe_window_days = _safe_window_days(window_days)
    cutoff_at = _cutoff_for_window(safe_window_days)
    terminal_statuses = list(_TERMINAL_ROUND_STATUSES)
    current_statuses = list(_CURRENT_ROUND_STATUSES)
    planning_statuses = list(_PLANNING_ROUND_STATUSES)

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor(dictionary=True)

        user_condition, user_params = _real_user_condition("up")
        project_condition, project_params = _real_project_condition("pp")
        product_condition, product_params = _real_product_condition("p")
        bonus_condition, bonus_params = _real_bonus_survey_condition("bs")

        total_users = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM user_pool up
            WHERE {user_condition}
              AND up.UnregisteredAt IS NULL
            """,
            user_params,
        )
        users_logged_in_window = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM user_pool up
            WHERE {user_condition}
              AND up.UnregisteredAt IS NULL
              AND up.LastLoginAt >= %s
            """,
            user_params + [cutoff_at],
        )
        new_users_window = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM user_pool up
            WHERE {user_condition}
              AND up.UnregisteredAt IS NULL
              AND up.CreatedAt >= %s
            """,
            user_params + [cutoff_at],
        )
        profile_complete_users = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM user_pool up
            WHERE {user_condition}
              AND up.UnregisteredAt IS NULL
              AND up.profile_completed_at IS NOT NULL
            """,
            user_params,
        )
        countries_represented = _fetch_int(
            cur,
            f"""
            SELECT COUNT(DISTINCT up.CountryCode) AS total
            FROM user_pool up
            WHERE {user_condition}
              AND up.UnregisteredAt IS NULL
              AND up.CountryCode IS NOT NULL
              AND up.CountryCode != ''
            """,
            user_params,
        )
        elevated_users = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM user_pool up
            JOIN user_role_map urm
                ON urm.user_id = up.user_id
            WHERE {user_condition}
              AND up.UnregisteredAt IS NULL
              AND COALESCE(urm.PermissionLevel, 0) >= 30
            """,
            user_params,
        )

        trials_started_window = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            WHERE {project_condition}
              AND pr.StartDate >= %s
            """,
            project_params + [cutoff_at.date()],
        )
        current_trials = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            WHERE {project_condition}
              AND LOWER(pr.Status) IN ({','.join(['%s'] * len(current_statuses))})
            """,
            project_params + current_statuses,
        )
        planning_trials = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            WHERE {project_condition}
              AND LOWER(pr.Status) IN ({','.join(['%s'] * len(planning_statuses))})
            """,
            project_params + planning_statuses,
        )
        upcoming_trials = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            WHERE {project_condition}
              AND LOWER(pr.Status) NOT IN ({','.join(['%s'] * len(terminal_statuses))})
              AND pr.StartDate > CURDATE()
            """,
            project_params + terminal_statuses,
        )
        completed_trials_window = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            WHERE {project_condition}
              AND LOWER(pr.Status) IN ('closed', 'completed')
              AND COALESCE(pr.CompletedAt, pr.EndDate, DATE(pr.UpdatedAt)) >= %s
            """,
            project_params + [cutoff_at.date()],
        )
        selected_participants = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM project_participants ppn
            JOIN project_rounds pr
                ON pr.RoundID = ppn.RoundID
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            WHERE {project_condition}
            """,
            project_params,
        )

        assigned_trials = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            WHERE {project_condition}
              AND LOWER(pr.Status) NOT IN ({','.join(['%s'] * len(terminal_statuses))})
              AND pr.UTLead_UserID IS NOT NULL
              AND pr.UTLead_UserID != ''
            """,
            project_params + terminal_statuses,
        )
        unassigned_planning_trials = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            WHERE {project_condition}
              AND LOWER(pr.Status) IN ({','.join(['%s'] * len(planning_statuses))})
              AND (pr.UTLead_UserID IS NULL OR pr.UTLead_UserID = '')
            """,
            project_params + planning_statuses,
        )
        active_ut_leads = _fetch_int(
            cur,
            f"""
            SELECT COUNT(DISTINCT pr.UTLead_UserID) AS total
            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            WHERE {project_condition}
              AND LOWER(pr.Status) NOT IN ({','.join(['%s'] * len(terminal_statuses))})
              AND pr.UTLead_UserID IS NOT NULL
              AND pr.UTLead_UserID != ''
            """,
            project_params + terminal_statuses,
        )
        top_ut_leads = _fetch_rows(
            cur,
            f"""
            SELECT
                pr.UTLead_UserID,
                NULLIF(TRIM(CONCAT(COALESCE(up.FirstName, ''), ' ', COALESCE(up.LastName, ''))), '') AS UTLeadName,
                COUNT(*) AS active_trials
            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            LEFT JOIN user_pool up
                ON up.user_id = pr.UTLead_UserID
            WHERE {project_condition}
              AND LOWER(pr.Status) NOT IN ({','.join(['%s'] * len(terminal_statuses))})
              AND pr.UTLead_UserID IS NOT NULL
              AND pr.UTLead_UserID != ''
            GROUP BY pr.UTLead_UserID, up.FirstName, up.LastName
            ORDER BY active_trials DESC, UTLeadName ASC
            LIMIT 3
            """,
            project_params + terminal_statuses,
        )

        active_business_groups = _fetch_int(
            cur,
            f"""
            SELECT COUNT(DISTINCT pp.BusinessGroup) AS total
            FROM project_projects pp
            WHERE {project_condition}
              AND pp.BusinessGroup IS NOT NULL
              AND pp.BusinessGroup != ''
            """,
            project_params,
        )
        active_product_types = _fetch_int(
            cur,
            f"""
            SELECT COUNT(DISTINCT pp.ProductType) AS total
            FROM project_projects pp
            WHERE {project_condition}
              AND pp.ProductType IS NOT NULL
              AND pp.ProductType != ''
            """,
            project_params,
        )
        top_business_groups = _fetch_rows(
            cur,
            f"""
            SELECT
                pp.BusinessGroup AS label,
                COUNT(*) AS total
            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            WHERE {project_condition}
              AND pp.BusinessGroup IS NOT NULL
              AND pp.BusinessGroup != ''
            GROUP BY pp.BusinessGroup
            ORDER BY total DESC, pp.BusinessGroup ASC
            LIMIT 3
            """,
            project_params,
        )
        top_product_types = _fetch_rows(
            cur,
            f"""
            SELECT
                pp.ProductType AS label,
                COUNT(*) AS total
            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            WHERE {project_condition}
              AND pp.ProductType IS NOT NULL
              AND pp.ProductType != ''
            GROUP BY pp.ProductType
            ORDER BY total DESC, pp.ProductType ASC
            LIMIT 3
            """,
            project_params,
        )

        historical_published_total = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM historical_report_publications hrp
            JOIN products p
                ON p.product_id = hrp.product_id
            WHERE {product_condition}
              AND hrp.status = 'published'
            """,
            product_params,
        )
        historical_published_window = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM historical_report_publications hrp
            JOIN products p
                ON p.product_id = hrp.product_id
            WHERE {product_condition}
              AND hrp.status = 'published'
              AND COALESCE(hrp.published_at, hrp.created_at) >= %s
            """,
            product_params + [cutoff_at],
        )
        product_trial_reports_total = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM product_trial_reports ptr
            JOIN project_projects pp
                ON pp.ProjectID = ptr.project_id
            WHERE {project_condition}
            """,
            project_params,
        )
        product_trial_reports_window = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM product_trial_reports ptr
            JOIN project_projects pp
                ON pp.ProjectID = ptr.project_id
            WHERE {project_condition}
              AND ptr.created_at >= %s
            """,
            project_params + [cutoff_at],
        )
        bonus_survey_reports_total = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM bonus_survey_reports bsr
            JOIN bonus_surveys bs
                ON bs.bonus_survey_id = bsr.bonus_survey_id
            WHERE {bonus_condition}
            """,
            bonus_params,
        )
        bonus_survey_reports_window = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM bonus_survey_reports bsr
            JOIN bonus_surveys bs
                ON bs.bonus_survey_id = bsr.bonus_survey_id
            WHERE {bonus_condition}
              AND bsr.created_at >= %s
            """,
            bonus_params + [cutoff_at],
        )
        completed_rounds_without_report = _fetch_int(
            cur,
            f"""
            SELECT COUNT(*) AS total
            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            LEFT JOIN product_trial_reports ptr
                ON ptr.round_id = pr.RoundID
            WHERE {project_condition}
              AND LOWER(pr.Status) IN ('closed', 'completed')
              AND ptr.report_id IS NULL
            """,
            project_params,
        )

        reports_window_total = (
            historical_published_window
            + product_trial_reports_window
            + bonus_survey_reports_window
        )

        return {
            "window_days": safe_window_days,
            "site_overview": {
                "registered_users": total_users,
                "logged_in_window": users_logged_in_window,
                "logged_in_window_percent": _percentage(users_logged_in_window, total_users),
                "trials_started_window": trials_started_window,
                "reports_window": reports_window_total,
                "current_trials": current_trials,
            },
            "user_pool": {
                "registered_users": total_users,
                "new_users_window": new_users_window,
                "profile_complete_users": profile_complete_users,
                "profile_complete_percent": _percentage(profile_complete_users, total_users),
                "logged_in_window": users_logged_in_window,
                "logged_in_window_percent": _percentage(users_logged_in_window, total_users),
                "countries_represented": countries_represented,
                "elevated_users": elevated_users,
            },
            "trial_stats": {
                "current_trials": current_trials,
                "planning_trials": planning_trials,
                "upcoming_trials": upcoming_trials,
                "completed_trials_window": completed_trials_window,
                "selected_participants": selected_participants,
            },
            "ut_lead_stats": {
                "assigned_trials": assigned_trials,
                "unassigned_planning_trials": unassigned_planning_trials,
                "active_ut_leads": active_ut_leads,
                "top_ut_leads": top_ut_leads,
            },
            "bg_product_stats": {
                "active_business_groups": active_business_groups,
                "active_product_types": active_product_types,
                "top_business_groups": top_business_groups,
                "top_product_types": top_product_types,
            },
            "reporting_stats": {
                "reports_window": reports_window_total,
                "historical_published_total": historical_published_total,
                "historical_published_window": historical_published_window,
                "product_trial_reports_total": product_trial_reports_total,
                "product_trial_reports_window": product_trial_reports_window,
                "bonus_survey_reports_total": bonus_survey_reports_total,
                "bonus_survey_reports_window": bonus_survey_reports_window,
                "completed_rounds_without_report": completed_rounds_without_report,
            },
            "dummy_filter": {
                "enabled": True,
                "pattern": _DUMMY_PATTERN,
            },
        }

    finally:
        conn.close()