from app.navigation import (
    trials,
    product_team,
    surveys,
    legal,
    reporting_insights,
    user_trial_lead,
    administration,
)


def build_role_nav(permission_level: int) -> str:
    parts = [
        trials.get_navigation(permission_level=permission_level),
        legal.get_navigation(permission_level=permission_level),
        surveys.get_navigation(permission_level=permission_level),
        product_team.get_navigation(permission_level=permission_level),
        reporting_insights.get_navigation(permission_level=permission_level),
        user_trial_lead.get_navigation(permission_level=permission_level),
        administration.get_navigation(permission_level=permission_level),
    ]

    return "\n".join(p for p in parts if p) or ""
