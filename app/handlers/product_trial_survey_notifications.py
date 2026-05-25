# app/handlers/product_trial_survey_notifications.py


def render_product_trial_survey_activated(payload: dict) -> dict:
    project_name = payload.get("project_name") or "Product Trial"
    round_name = payload.get("round_name") or "round"
    survey_name = payload.get("survey_name") or "Survey"
    survey_deadline = str(payload.get("survey_deadline") or "").strip()

    deadline_text = ""
    if survey_deadline:
        deadline_text = f" Please complete it by {survey_deadline}."

    return {
        "title": "Product Trial Survey Available",
        "message": (
            f"{survey_name} is now available for {project_name} / {round_name}."
            f"{deadline_text} "
            "Open Active Trials to complete it."
        ),
        "actions": [
            {
                "label": "Open Active Trials",
                "href": "/trials/active",
                "style": "primary",
            }
        ],
    }