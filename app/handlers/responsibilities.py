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


def handle_responsibilities_post(handler):
    uid = handler._get_uid_from_cookie()

    if not uid:
        handler.send_response(302)
        handler.send_header("Location", "/login")
        handler.end_headers()
        return

    round_id = handler._get_post_param("round_id")

    if not round_id:
        handler.send_response(302)
        handler.send_header("Location", "/trials/active")
        handler.end_headers()
        return

    action = handler._get_post_param("action")

    # -------------------------
    # DECLINE → withdraw
    # -------------------------
    if action == "decline":
        from app.db.project_applicants import withdraw_application

        withdraw_application(
            user_id=uid,
            round_id=int(round_id)
        )

        handler.send_response(302)
        handler.send_header("Location", "/trials/recruiting")
        handler.end_headers()
        return

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
        if not handler._get_post_param(field):
            handler.send_response(302)
            handler.send_header(
                "Location",
                f"/trials/responsibilities?round_id={round_id}"
            )
            handler.end_headers()
            return

    print("[RESPONSIBILITIES AGREED]", uid, round_id)

    handler.send_response(302)
    handler.send_header("Location", "/trials/active")
    handler.end_headers()


# -------------------------
# WRAPPERS FOR MAIN.PY COMPATIBILITY
# -------------------------

def render_responsibilities(handler):
    return render_responsibilities_get(handler)


def handle_responsibilities(handler):
    return handle_responsibilities_post(handler)