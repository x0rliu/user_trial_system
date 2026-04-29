from pathlib import Path


RESPONSIBILITIES_TEMPLATE = Path(
    "app/templates/responsibilities.html"
).read_text(encoding="utf-8")


def render_responsibilities_get(
    *,
    user_id,
    base_template,
    inject_nav,
    query_params,
):
    round_id = query_params.get("round_id", [None])[0]
    error = query_params.get("error", [None])[0]

    if not round_id:
        return {"redirect": "/trials/active"}

    from pathlib import Path

    responsibilities_template = Path(
        "app/templates/responsibilities.html"
    ).read_text(encoding="utf-8")

    body_html = responsibilities_template.replace(
        "__ROUND_ID__", str(round_id)
    )

    # -------------------------
    # Inject error message
    # -------------------------
    if error == "missing_confirm":
        error_html = """
        <div class="form-error-banner">
            You must confirm all responsibilities before proceeding.
        </div>
        """
    else:
        error_html = ""

    body_html = error_html + body_html

    html = base_template
    html = inject_nav(html)
    html = html.replace("{{ title }}", "Responsibilities")
    html = html.replace("__BODY__", body_html)

    return {"html": html}


def handle_responsibilities_post(*, user_id: str, data: dict):

    round_id = data.get("round_id")

    if not round_id:
        return {"redirect": "/trials/active"}

    try:
        round_id = int(round_id)
    except ValueError:
        return {"redirect": "/trials/active"}

    from app.services.round_access import validate_round_access

    validated_round = validate_round_access(
        actor_user_id=user_id,
        round_id=round_id,
        required_role="participant",
        allow_admin=True,
    )

    if not validated_round:
        return {"redirect": "/dashboard"}

    action = data.get("action")

    # -------------------------
    # DECLINE → withdraw
    # -------------------------
    if action == "decline":
        from app.db.project_applicants import withdraw_application

        withdraw_application(
            user_id=user_id,
            round_id=round_id
        )

        return {"redirect": "/trials/recruiting"}

    # -------------------------
    # AGREE → enforce checks
    # -------------------------
    required_checks = [
        "confirm_pickup",
        "confirm_tracking",
        "confirm_surveys",
        "confirm_participation",
    ]

    for field in required_checks:
        if not data.get(field):
            return {
                "redirect": f"/trials/responsibilities?round_id={round_id}&error=missing_confirm"
            }

    # -------------------------
    # 🔥 SAVE ACCEPTANCE
    # -------------------------
    from app.db.project_participants import confirm_responsibilities

    confirm_responsibilities(
        user_id=user_id,
        round_id=round_id
    )

    return {"redirect": "/trials/active"}


# -------------------------
# WRAPPERS FOR MAIN.PY COMPATIBILITY
# -------------------------

def render_responsibilities(handler):
    return render_responsibilities_get(handler)


def handle_responsibilities(handler):
    return handle_responsibilities_post(handler)