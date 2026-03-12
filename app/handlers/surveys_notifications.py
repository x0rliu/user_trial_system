def render_approve_bonus_survey(payload: dict) -> dict:
    return {
        "title": "Bonus Survey Approval Required",
        "message": (
            f"The bonus survey "
            f"<strong>{payload.get('survey_title')}</strong> "
            f"has been submitted and is awaiting approval."
        ),
        "actions": [
            {
                "label": "View Approvals",
                "href": "/admin/approvals",
                "style": "primary",
            }
        ],
    }
