# app/handlers/settings.py

from pathlib import Path
from app.db.user_pool import get_user_by_userid
# from app.services.demographics import update_demographics
from app.utils.response import json_response

# --------------------------------------------------
# SETTINGS ROUTE DISPATCHER
# --------------------------------------------------
# This file only defines handlers.
# main.py is responsible for routing to these functions.
# --------------------------------------------------


# --------------------------------------------------
# SETTINGS DEMOGRAPHICS EDITOR
# --------------------------------------------------

# app/handlers/settings.py

DEMOGRAPHICS_TEMPLATE = Path("app/templates/settings/edit_demographics.html")
SETTINGS_TEMPLATE = Path("app/templates/settings.html")

def render_settings_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict | None = None,
):
    """
    Full Settings page shell.

    GET renders only.
    Any status messages are derived from query parameters after POST redirect.
    """

    query_params = query_params or {}

    body_html = SETTINGS_TEMPLATE.read_text(encoding="utf-8")

    password_status = query_params.get("password", [None])[0]
    password_error = query_params.get("password_error", [None])[0]

    flash_html = ""

    if password_status == "changed":
        flash_html = """
        <div class="settings-flash success">
            Password updated successfully.
        </div>
        """

    elif password_error:
        error_messages = {
            "current_password_required": "Enter your current password.",
            "new_password_required": "Enter a new password.",
            "confirm_password_required": "Confirm your new password.",
            "new_password_mismatch": "New password and confirmation do not match.",
            "new_password_too_short": "New password must be at least 12 characters.",
            "current_password_invalid": "Current password is incorrect.",
            "password_not_set": "This account does not currently have a password set.",
            "new_password_same": "New password must be different from your current password.",
            "user_not_found": "Account could not be found.",
            "user_missing": "Account could not be resolved.",
            "unknown": "Password could not be updated.",
        }

        message = error_messages.get(
            password_error,
            "Password could not be updated.",
        )

        flash_html = f"""
        <div class="settings-flash error">
            {message}
        </div>
        """

    body_html = body_html.replace(
        "__SETTINGS_FLASH__",
        flash_html,
    )

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Settings")
    html = html.replace("__BODY__", body_html)

    return {"html": html}

def handle_settings_password_change_post(user_id: str, data: dict):
    """
    POST handler for changing password.

    Mutates through service only.
    Returns redirect only.
    """

    from app.services.password_service import change_password

    result = change_password(
        user_id=user_id,
        current_password=data.get("current_password") or "",
        new_password=data.get("new_password") or "",
        confirm_password=data.get("confirm_password") or "",
    )

    if result.success:
        return {
            "redirect": "/settings?password=changed"
        }

    return {
        "redirect": f"/settings?password_error={result.error_code or 'unknown'}"
    }