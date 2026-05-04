# app/handlers/surveys_notifications.py

def render_approve_bonus_survey(payload: dict) -> dict:
    survey_title = payload.get("survey_title") or "Untitled bonus survey"

    return {
        "title": "Bonus Survey Approval Required",
        "message": (
            f'The bonus survey "{survey_title}" has been submitted '
            "and is awaiting approval."
        ),
        "actions": [
            {
                "label": "View Approvals",
                "href": "/admin/approvals",
                "style": "primary",
            }
        ],
    }


def render_bonus_survey_approved(payload: dict) -> dict:
    survey_title = payload.get("survey_title") or "Untitled bonus survey"
    bonus_survey_id = payload.get("bonus_survey_id")

    href = "/surveys/bonus"
    if bonus_survey_id:
        href = f"/surveys/bonus/active?survey_id={bonus_survey_id}"

    return {
        "title": "Bonus Survey Approved",
        "message": (
            f'The bonus survey "{survey_title}" has been approved and is now active.'
        ),
        "actions": [
            {
                "label": "View Bonus Survey",
                "href": href,
                "style": "primary",
            }
        ],
    }