# app/handlers/settings.py

from datetime import datetime
from pathlib import Path

from app.db.user_pool import (
    get_user_by_userid,
    update_user_demographics,
)
from app.utils.html_escape import escape_html as e
from app.utils.response import json_response
from app.utils.templates import render_template
from app.db.user_pool_country_codes import get_country_codes

# --------------------------------------------------
# SETTINGS ROUTE DISPATCHER
# --------------------------------------------------
# This file only defines handlers.
# main.py is responsible for routing to these functions.
# --------------------------------------------------


# --------------------------------------------------
# SETTINGS TEMPLATES
# --------------------------------------------------

SETTINGS_TEMPLATE = Path("app/templates/settings.html")


# --------------------------------------------------
# SETTINGS PAGE SHELL
# --------------------------------------------------

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

    demographics_form_html = render_settings_demographics_form(user_id)

    body_html = body_html.replace(
        "__DEMOGRAPHICS_FORM__",
        demographics_form_html,
    )

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
            {e(message)}
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


# --------------------------------------------------
# SETTINGS DEMOGRAPHICS EDITOR
# --------------------------------------------------

def _build_gender_options(selected_gender: str | None) -> str:
    gender_options = [
        ("", "Select"),
        ("female", "Female"),
        ("male", "Male"),
        ("non_binary", "Non-binary"),
        ("prefer_not_to_say", "Prefer not to say"),
    ]

    rows = []

    for value, label in gender_options:
        selected = " selected" if value == (selected_gender or "") else ""

        rows.append(
            f'<option value="{e(value)}"{selected}>{e(label)}</option>'
        )

    return "\n".join(rows)

def _build_country_options(selected_country_code: str | None) -> str:
    rows = ['<option value="">Select country</option>']

    for country in get_country_codes():
        code = str(country.get("CountryCode") or "").strip()
        name = str(country.get("CountryName") or "").strip()

        if not code or not name:
            continue

        selected = " selected" if code == (selected_country_code or "") else ""

        rows.append(
            f'<option value="{e(code)}"{selected}>{e(name)}</option>'
        )

    return "\n".join(rows)

def render_settings_demographics_form(user_id: str) -> str:
    """
    Settings demographics fragment.

    GET render only.
    Settings is the canonical edit location for demographics after onboarding.
    Profile should display this data read-only.
    """

    user = get_user_by_userid(user_id)
    if not user:
        return """
        <div class="settings-fragment-error">
            Unable to load demographics.
        </div>
        """

    current_year = datetime.utcnow().year

    return render_template(
        "settings/edit_demographics.html",
        {
            "FIRST_NAME": e(user.get("FirstName") or ""),
            "LAST_NAME": e(user.get("LastName") or ""),
            "GENDER_OPTIONS": _build_gender_options(user.get("Gender")),
            "BIRTH_YEAR": e(user.get("BirthYear") or ""),
            "COUNTRY_OPTIONS": _build_country_options(user.get("CountryCode")),
            "CITY": e(user.get("City") or ""),
            "MOBILE_COUNTRY_CODE": e(user.get("MobileCountryCode") or ""),
            "MOBILE_NATIONAL": e(user.get("MobileNational") or ""),
            "CURRENT_YEAR": str(current_year),
        },
    )


def _normalize_mobile_fields(
    *,
    mobile_country_code: str,
    mobile_national: str,
) -> dict:
    """
    Normalizes optional mobile fields for settings.

    If both fields are blank, mobile remains unset.
    If either field is provided, both must be valid enough to construct E.164.
    """

    mobile_country_code = (mobile_country_code or "").strip()
    mobile_national = (mobile_national or "").strip()

    if not mobile_country_code and not mobile_national:
        return {
            "ok": True,
            "mobile_country_code": None,
            "mobile_national": None,
            "mobile_e164": None,
        }

    digits_country = "".join(c for c in mobile_country_code if c.isdigit())
    digits_national = "".join(c for c in mobile_national if c.isdigit())

    if not digits_country:
        return {
            "ok": False,
            "error": "invalid_mobile_code",
        }

    if len(digits_national) < 8:
        return {
            "ok": False,
            "error": "invalid_mobile_number",
        }

    return {
        "ok": True,
        "mobile_country_code": f"+{digits_country}",
        "mobile_national": digits_national,
        "mobile_e164": f"+{digits_country}{digits_national}",
    }


def save_demographics_inline(user_id: str, data: dict):
    """
    Saves editable demographics from Settings.

    POST mutation.
    Current route is an intentional JSON/AJAX exception documented in route_map.md.
    """

    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    gender = (data.get("gender") or "").strip()
    birth_year_raw = (data.get("birth_year") or "").strip()
    country = (data.get("country") or "").strip()
    city = (data.get("city") or "").strip()
    mobile_country_code = (data.get("mobile_country_code") or "").strip()
    mobile_national = (data.get("mobile_national") or "").strip()

    if not first_name:
        return json_response(
            {
                "ok": False,
                "error": "first_name_required",
            },
            status=400,
        )

    if not last_name:
        return json_response(
            {
                "ok": False,
                "error": "last_name_required",
            },
            status=400,
        )

    if not birth_year_raw:
        return json_response(
            {
                "ok": False,
                "error": "birth_year_required",
            },
            status=400,
        )

    try:
        birth_year = int(birth_year_raw)
    except ValueError:
        return json_response(
            {
                "ok": False,
                "error": "invalid_birth_year",
            },
            status=400,
        )

    current_year = datetime.utcnow().year

    if birth_year < 1900 or birth_year > current_year:
        return json_response(
            {
                "ok": False,
                "error": "invalid_birth_year",
            },
            status=400,
        )

    mobile_result = _normalize_mobile_fields(
        mobile_country_code=mobile_country_code,
        mobile_national=mobile_national,
    )

    if not mobile_result["ok"]:
        return json_response(
            {
                "ok": False,
                "error": mobile_result["error"],
            },
            status=400,
        )

    try:
        update_user_demographics(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            birth_year=birth_year,
            country=country,
            city=city,
            mobile_country_code=mobile_result["mobile_country_code"],
            mobile_national=mobile_result["mobile_national"],
            mobile_e164=mobile_result["mobile_e164"],
        )

    except Exception as err:
        print("[ERROR] Settings demographics update failed:", err)

        return json_response(
            {
                "ok": False,
                "error": "demographics_save_failed",
            },
            status=500,
        )

    return json_response(
        {
            "ok": True,
            "error": None,
        },
        status=200,
    )


# --------------------------------------------------
# SETTINGS PASSWORD
# --------------------------------------------------

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