def render_approve_bonus_survey(payload: dict) -> dict:
    survey_title = payload.get("survey_title") or "Untitled bonus survey"

    return {
        "title": "Bonus Survey Approval Required",
        "message": (
            f'The bonus survey "{survey_title}" was submitted '
            f"for approval."
        ),
        "actions": [
            {
                "label": "View Approvals",
                "href": "/admin/approvals",
                "style": "primary",
            }
        ],
    }