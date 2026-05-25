# app/handlers/product_trial_survey_notifications.py


def render_product_trial_survey_activated(payload: dict) -> dict:
    project_name = payload.get("project_name") or "Product Trial"
    round_name = payload.get("round_name") or "round"
    survey_name = payload.get("survey_name") or "Survey"

    return {
        "title": "Product Trial Survey Available",
        "message": (
            f"{survey_name} is now available for {project_name} / {round_name}. "
            "Please open Active Trials to complete it."
        ),
        "actions": [
            {
                "label": "Open Active Trials",
                "href": "/trials/active",
                "style": "primary",
            }
        ],
    }