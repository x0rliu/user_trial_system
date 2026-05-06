# app/handlers/surveys_notifications.py

def _bonus_survey_href(payload: dict, *, fallback: str = "/surveys/bonus") -> str:
    bonus_survey_id = payload.get("bonus_survey_id")

    if bonus_survey_id:
        return f"/surveys/bonus/pending?survey_id={bonus_survey_id}"

    return fallback


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


def render_bonus_survey_info_requested(payload: dict) -> dict:
    survey_title = payload.get("survey_title") or "Untitled bonus survey"
    reason = payload.get("reason") or "UT has requested additional information."

    return {
        "title": "More Information Requested",
        "message": (
            f'UT requested more information for the bonus survey "{survey_title}". '
            f"Reason: {reason}"
        ),
        "actions": [
            {
                "label": "View Bonus Survey",
                "href": _bonus_survey_href(payload),
                "style": "primary",
            }
        ],
    }


def render_bonus_survey_changes_requested(payload: dict) -> dict:
    survey_title = payload.get("survey_title") or "Untitled bonus survey"
    reason = payload.get("reason") or "UT has requested changes before approval."

    return {
        "title": "Changes Requested",
        "message": (
            f'UT requested changes for the bonus survey "{survey_title}". '
            f"Reason: {reason}"
        ),
        "actions": [
            {
                "label": "View Bonus Survey",
                "href": _bonus_survey_href(payload),
                "style": "primary",
            }
        ],
    }


def render_bonus_survey_declined(payload: dict) -> dict:
    survey_title = payload.get("survey_title") or "Untitled bonus survey"
    reason = payload.get("reason") or "No reason provided."

    return {
        "title": "Bonus Survey Declined",
        "message": (
            f'The bonus survey "{survey_title}" was declined. '
            f"Reason: {reason}"
        ),
        "actions": [
            {
                "label": "View Bonus Surveys",
                "href": "/surveys/bonus",
                "style": "primary",
            }
        ],
    }