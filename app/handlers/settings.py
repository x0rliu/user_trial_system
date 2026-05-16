# app/handlers/settings.py

from datetime import datetime
from pathlib import Path

from app.db.user_pool import (
    get_user_by_userid,
    update_user_demographics,
)
from app.db.legal_documents import get_latest_published_document
from app.db.project_ndas import get_signed_project_ndas_for_user
from app.db.user_legal_acceptance import get_user_signed_document
from app.db.user_pool_country_codes import get_country_codes
from app.services.gender_values import canonicalize_gender_value
from app.utils.html_escape import escape_html as e
from app.utils.csrf import generate_csrf_token
from app.utils.debug import debug_log
from app.utils.templates import render_template

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
    password_csrf_token = generate_csrf_token(user_id)

    body_html = body_html.replace(
        "__PASSWORD_CSRF_TOKEN__",
        e(password_csrf_token),
    )

    demographics_form_html = render_settings_demographics_form(user_id)

    body_html = body_html.replace(
        "__DEMOGRAPHICS_FORM__",
        demographics_form_html,
    )

    nda_status = build_settings_nda_status(user_id)

    body_html = body_html.replace(
        "__NDA_STATUS_BADGE__",
        nda_status["badge_html"],
    )

    body_html = body_html.replace(
        "__NDA_STATUS_PANEL__",
        nda_status["panel_html"],
    )

    password_status = query_params.get("password", [None])[0]
    password_error = query_params.get("password_error", [None])[0]

    demographics_status = query_params.get("demographics", [None])[0]
    demographics_error = query_params.get("demographics_error", [None])[0]

    flash_html = ""

    if password_status == "changed":
        flash_html = """
        <div class="settings-flash success">
            Password updated successfully.
        </div>
        """

    elif password_error:
        password_error_messages = {
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

        message = password_error_messages.get(
            password_error,
            "Password could not be updated.",
        )

        flash_html = f"""
        <div class="settings-flash error">
            {e(message)}
        </div>
        """

    elif demographics_status == "updated":
        flash_html = """
        <div class="settings-flash success">
            Personal details saved.
        </div>
        """

    elif demographics_error:
        demographics_error_messages = {
            "first_name_required": "First name is required.",
            "last_name_required": "Last name is required.",
            "gender_required": "Gender is required. You may select Prefer not to say.",
            "birth_year_required": "Birth year is required to confirm eligibility.",
            "invalid_birth_year": "Birth year must be between 1900 and the current year.",
            "country_required": "Country is required because trial eligibility depends on region.",
            "invalid_mobile_code": "If you enter a mobile number, include a valid country code.",
            "invalid_mobile_number": "If you enter a mobile number, include a valid phone number.",
            "demographics_save_failed": "Personal details could not be saved.",
            "unknown": "Personal details could not be saved.",
        }

        message = demographics_error_messages.get(
            demographics_error,
            "Personal details could not be saved.",
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

def _format_signed_date(value) -> str:
    if not value:
        return "—"

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")

    raw = str(value).strip()
    if not raw:
        return "—"

    return raw.split(" ")[0]


def build_settings_nda_status(user_id: str) -> dict:
    """
    Build the Settings > Legal > NDA Status panel.

    GET render only. No mutation.
    """

    rows = []

    user = get_user_by_userid(user_id)
    global_acceptance = get_user_signed_document(user_id, "nda")

    global_signed_at = None
    global_document_id = None

    if global_acceptance:
        global_signed_at = global_acceptance.get("accepted_at")
        global_document_id = global_acceptance.get("document_id")
    elif user and user.get("GlobalNDA_Status") == "Signed":
        global_signed_at = user.get("GlobalNDA_SignedAt")

        global_version = (user.get("GlobalNDA_Version") or "").strip()
        latest_nda = get_latest_published_document("nda")

        if latest_nda and (not global_version or str(latest_nda.get("version")) == global_version):
            global_document_id = latest_nda.get("id")

    if global_signed_at:
        view_html = '<a class="settings-link-button" href="/legal/signed/nda">View</a>'

        if global_document_id:
            download_html = f'<a class="settings-link-button" href="/legal/download/{e(global_document_id)}">Download</a>'
        else:
            download_html = '<span class="settings-link-button disabled">Download FPO</span>'

        rows.append(f"""
        <tr>
            <td>Global NDA</td>
            <td>{e(_format_signed_date(global_signed_at))}</td>
            <td>{view_html}</td>
            <td>{download_html}</td>
        </tr>
        """)

    for nda in get_signed_project_ndas_for_user(user_id=user_id):
        project_name = nda.get("ProjectName") or "Project NDA"
        round_name = nda.get("RoundName") or f"Round {nda.get('RoundNumber') or ''}".strip()
        label = f"{project_name} — {round_name}" if round_name else project_name
        round_id = nda.get("RoundID")

        view_html = f'<a class="settings-link-button" href="/trials/nda?round_id={e(round_id)}&mode=review">View</a>'
        download_html = '<span class="settings-link-button disabled">Download FPO</span>'

        rows.append(f"""
        <tr>
            <td>{e(label)}</td>
            <td>{e(_format_signed_date(nda.get("DateSigned")))}</td>
            <td>{view_html}</td>
            <td>{download_html}</td>
        </tr>
        """)

    signed_count = len(rows)

    if not rows:
        return {
            "badge_html": '<span class="settings-status-pill muted">No signed NDAs</span>',
            "panel_html": """
            <p>
              No signed NDA records were found for this account yet.
            </p>
            """,
        }

    label = "1 signed NDA" if signed_count == 1 else f"{signed_count} signed NDAs"

    panel_html = f"""
    <div class="settings-table-wrap">
      <table class="settings-nda-table">
        <thead>
          <tr>
            <th>NDA</th>
            <th>Date Signed</th>
            <th>View</th>
            <th>Download</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </div>
    """

    return {
        "badge_html": f'<span class="settings-status-pill active">{e(label)}</span>',
        "panel_html": panel_html,
    }

# --------------------------------------------------
# SETTINGS DEMOGRAPHICS EDITOR
# --------------------------------------------------

def _build_gender_options(selected_gender: str | None) -> str:
    selected_gender = canonicalize_gender_value(selected_gender) or ""

    gender_options = [
        ("", "Select"),
        ("female", "Female"),
        ("male", "Male"),
        ("non_binary", "Non-binary"),
        ("prefer_not_to_say", "Prefer not to say"),
    ]

    rows = []

    for value, label in gender_options:
        selected = " selected" if value == selected_gender else ""

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
    csrf_token = generate_csrf_token(user_id)

    return render_template(
        "settings/edit_demographics.html",
        {
            "CSRF_TOKEN": e(csrf_token),
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


def handle_settings_demographics_save_post(user_id: str, data: dict):
    """
    POST handler for saving editable demographics from Settings.

    Mutates through the DB layer only.
    Returns redirect only.

    Required Settings fields:
    - first name
    - last name
    - gender
    - birth year
    - country

    Optional Settings fields:
    - city
    - mobile number
    """

    from urllib.parse import quote

    def redirect_error(error_code: str) -> dict:
        safe_error = quote(error_code or "unknown")
        return {
            "redirect": f"/settings?demographics_error={safe_error}"
        }

    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    gender_raw = (data.get("gender") or "").strip()
    birth_year_raw = (data.get("birth_year") or "").strip()
    country = (data.get("country") or "").strip()
    city = (data.get("city") or "").strip()
    mobile_country_code = (data.get("mobile_country_code") or "").strip()
    mobile_national = (data.get("mobile_national") or "").strip()

    gender = canonicalize_gender_value(gender_raw)

    if not first_name:
        return redirect_error("first_name_required")

    if not last_name:
        return redirect_error("last_name_required")

    if not gender:
        return redirect_error("gender_required")

    if not birth_year_raw:
        return redirect_error("birth_year_required")

    if not country:
        return redirect_error("country_required")

    try:
        birth_year = int(birth_year_raw)
    except ValueError:
        return redirect_error("invalid_birth_year")

    current_year = datetime.utcnow().year

    if birth_year < 1900 or birth_year > current_year:
        return redirect_error("invalid_birth_year")

    mobile_result = _normalize_mobile_fields(
        mobile_country_code=mobile_country_code,
        mobile_national=mobile_national,
    )

    if not mobile_result["ok"]:
        return redirect_error(mobile_result["error"])

    try:
        update_user_demographics(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            birth_year=birth_year,
            country=country,
            city=city or None,
            mobile_country_code=mobile_result["mobile_country_code"],
            mobile_national=mobile_result["mobile_national"],
            mobile_e164=mobile_result["mobile_e164"],
        )

    except Exception as err:
        debug_log("Settings demographics update failed:", repr(err))
        return redirect_error("demographics_save_failed")

    return {
        "redirect": "/settings?demographics=updated"
    }

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