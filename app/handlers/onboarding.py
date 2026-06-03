from app.db.user_pool import (
    get_user_by_userid,
    mark_guidelines_completed,
)
from app.services.onboarding_state import get_onboarding_state
from app.db.user_pool_country_codes import get_country_codes
import mysql.connector
from pathlib import Path
from app.config.config import DB_CONFIG
from app.config.error_messages import ERROR_MESSAGES
from app.db.legal_documents import get_latest_published_document
from app.db.user_legal_acceptance import record_user_legal_acceptance
from app.utils.html_escape import escape_html as e
from app.utils.csrf import generate_csrf_token
from app.utils.debug import debug_log
from bs4 import BeautifulSoup


def ensure_participant_permission(user_id: str):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO user_role_map
                (user_id, RoleID, PermissionLevel, CreatedAt, UpdatedAt)
            VALUES
                (%s, 'Participant', 20, NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                PermissionLevel = CASE
                    WHEN PermissionLevel < 20 THEN 20
                    ELSE PermissionLevel
                END,
                UpdatedAt = NOW()
            """,
            (user_id,)
        )

        conn.commit()

    finally:
        conn.close()



PARTICIPATION_GUIDELINES_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "onboarding"
    / "participation_guidelines.html"
).read_text(encoding="utf-8")


def render_guidelines_page(csrf_token: str = "", include_form: bool = True):
    safe_csrf_token = e(csrf_token or "")

    html = PARTICIPATION_GUIDELINES_TEMPLATE.replace(
        "__CSRF_TOKEN__",
        safe_csrf_token,
    )

    if not include_form:
        form_start = "<!-- GUIDELINES_ACK_FORM_START -->"
        form_end = "<!-- GUIDELINES_ACK_FORM_END -->"

        if form_start in html and form_end in html:
            before_form, remainder = html.split(form_start, 1)
            _form_html, after_form = remainder.split(form_end, 1)
            html = before_form + after_form

    return html



def handle_guidelines_get(user_id: str):
    user = get_user_by_userid(user_id)
    state = get_onboarding_state(user)

    if state != "participation_guidelines":
        return {
            "redirect": "/"
        }

    csrf_token = generate_csrf_token(user_id)

    return {
        "body": render_guidelines_page(csrf_token),
        "title": "Participation Guidelines"
    }


def handle_guidelines_post(user_id: str):
    user = get_user_by_userid(user_id)
    state = get_onboarding_state(user)

    if state != "participation_guidelines":
        return {
            "redirect": "/"
        }

    mark_guidelines_completed(user_id)
    from app.handlers.onboarding import ensure_participant_permission

    ensure_participant_permission(user_id)

    return {
        "redirect": "/welcome"
    }

def render_participation_guidelines(user_id: str) -> str:
    """
    Used by main.py GET /participation-guidelines.
    Returns the HTML body only (main.py handles the base template).
    """
    result = handle_guidelines_get(user_id)

    # main.py's GET block expects a body string, not a redirect dict.
    # So if the user isn't in the right state, we return a tiny message.
    if isinstance(result, dict) and "redirect" in result:
        return """
            <h2>Participation Guidelines</h2>
            <p>You can’t access this step right now.</p>
            <p><a href="/">Continue</a></p>
        """

    return result["body"]

from app.db.user_pool import get_user_by_userid
from app.db.legal_documents import get_latest_published_document

def render_nda_page(user):

    full_name = f"{user['FirstName']} {user['LastName']}".strip()

    nda = get_latest_published_document("nda")

    if not nda:
        nda_title = "Non-Disclosure Agreement"
        nda_version = ""
        nda_content = "<p>NDA document not available.</p>"
    else:
        nda_title = e(nda["title"])
        nda_version = e(str(nda["version"]))

        # --------------------------------
        # Sanitize NDA HTML content
        # --------------------------------
        raw_content = nda["content"]

        soup = BeautifulSoup(raw_content, "html.parser")

        allowed_tags = {
            "p",
            "h1",
            "h2",
            "h3",
            "ul",
            "ol",
            "li",
            "strong",
            "em"
        }

        for tag in soup.find_all(True):
            if tag.name not in allowed_tags:
                tag.unwrap()
            tag.attrs = {}

        nda_content = str(soup)

    safe_full_name = e(full_name)

    return f"""
        <h2>{nda_title}</h2>

        <div class="nda-box">
            <p><strong>Version {nda_version}</strong></p>
            {nda_content}
        </div>

        <form method="POST" action="/nda">
            <label>
                <input type="checkbox" name="agree" required>
                I, <strong>{safe_full_name}</strong>, acknowledge that I have read and
                agree to the Non-Disclosure Agreement.
            </label>

            <br><br>

            <button type="submit">Submit and Continue</button>
        </form>
    """

from app.db.user_pool import (
    update_user_demographics,
    get_user_by_userid,
)
from app.services.onboarding_state import get_onboarding_state


def handle_demographics_post(user_id: str, data: dict):
    """
    Handles POST /demographics business logic.
    Input: user_id, parsed POST data (dict from parse_qs)
    Output: dict with redirect OR error

    Required onboarding fields:
    - first name
    - last name
    - gender
    - birth year
    - country

    Optional onboarding fields:
    - city
    - mobile number
    """

    first_name = data.get("first_name", [""])[0].strip()
    last_name = data.get("last_name", [""])[0].strip()
    gender = data.get("gender", [""])[0].strip()
    birth_year_raw = data.get("birth_year", [""])[0].strip()
    country = data.get("country", [""])[0].strip()
    city = data.get("city", [""])[0].strip()

    # ---- required field validation ----
    if not first_name:
        return {"redirect": "/demographics?error=first_name_required"}

    if not last_name:
        return {"redirect": "/demographics?error=last_name_required"}

    if not gender:
        return {"redirect": "/demographics?error=gender_required"}

    if not birth_year_raw:
        return {"redirect": "/demographics?error=birth_year_required"}

    if not country:
        return {"redirect": "/demographics?error=country_required"}

    # ---- mobile phone extraction (optional) ----
    mobile_country_code = data.get("mobile_country_code", [""])[0].strip()
    mobile_national = data.get("mobile_national", [""])[0].strip()

    # ---- normalize digits ----
    digits_country = "".join(c for c in mobile_country_code if c.isdigit())
    digits_national = "".join(c for c in mobile_national if c.isdigit())

    mobile_country_code_value = None
    mobile_national_value = None
    mobile_e164 = None

    # If either mobile field is provided, both must be valid enough to save.
    if digits_country or digits_national:
        if not digits_country:
            return {"redirect": "/demographics?error=invalid_mobile_code"}

        if len(digits_national) < 8:
            return {"redirect": "/demographics?error=invalid_mobile_number"}

        mobile_country_code_value = f"+{digits_country}"
        mobile_national_value = digits_national
        mobile_e164 = f"+{digits_country}{digits_national}"

    # ---- birth year validation ----
    from datetime import datetime

    try:
        birth_year = int(birth_year_raw)
    except ValueError:
        return {"redirect": "/demographics?error=invalid_birth_year"}

    current_year = datetime.utcnow().year

    # sanity range check
    if birth_year < 1900 or birth_year > current_year:
        return {"redirect": "/demographics?error=invalid_birth_year"}

    age = current_year - birth_year

    # hard block for minors
    if age < 19:
        return {"redirect": "/demographics?error=underage"}

    # ---- DB write ----
    try:
        update_user_demographics(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            birth_year=birth_year,
            country=country,
            city=city or None,
            mobile_country_code=mobile_country_code_value,
            mobile_national=mobile_national_value,
            mobile_e164=mobile_e164,
        )
    except Exception as e_err:
        debug_log("NDA signing failed:", repr(e_err))
        return {"redirect": "/nda"}
    
    # ---- determine next step ----
    user = get_user_by_userid(user_id)
    state = get_onboarding_state(user)

    if state == "email_verification":
        next_path = "/verify-email"
    elif state == "demographics":
        next_path = "/demographics"
    elif state == "nda":
        next_path = "/nda"
    elif state == "welcome":
        next_path = "/welcome"
    else:
        next_path = "/dashboard"

    return {
        "redirect": next_path
    }

from app.db.user_pool import (
    get_user_by_userid,
    mark_global_nda_signed,
)
from app.services.onboarding_state import get_onboarding_state


def nda_signed(user: dict) -> bool:
    return (
        user.get("GlobalNDA_Status") == "Signed"
        and bool(user.get("GlobalNDA_SignedAt"))
    )


from app.services.global_nda_service import sign_global_nda


def handle_nda_post(user_id: str, form: dict):

    user = get_user_by_userid(user_id)
    if not user:
        return {
            "redirect": "/logout"
        }

    # Prevent duplicate NDA submissions
    if nda_signed(user):
        return {"redirect": "/participation-guidelines"}

    state = get_onboarding_state(user)

    # Gate: only allow NDA signing at the NDA step
    if state != "nda":
        return {
            "redirect": "/"
        }

    if "agree" not in form:
        return {"redirect": "/nda"}

    nda = get_latest_published_document("nda")
    if not nda:
        return {"redirect": "/nda"}

    try:
        sign_global_nda(
            user_id=user_id,
            nda=nda,
        )

    except Exception as e_err:
        debug_log("NDA signing failed:", repr(e_err))
        return {"redirect": "/nda"}

    return {"redirect": "/participation-guidelines"}

from app.db.user_pool import (
    get_user_by_userid,
    mark_welcome_seen,
)
from app.services.onboarding_state import get_onboarding_state


def handle_welcome_post(user_id: str, next_path: str | None = None):
    """
    Handles POST /welcome onboarding logic.
    Input: user_id, optional next_path from the welcome form
    Output: dict with redirect
    """

    user = get_user_by_userid(user_id)
    if not user:
        return {
            "redirect": "/logout"
        }

    state = get_onboarding_state(user)

    # Gate: welcome is only valid at welcome or after
    if state not in ("welcome", "ready"):
        return {
            "redirect": "/"
        }

    allowed_next_paths = {
        "/profile/wizard": "/profile/wizard",
        "/dashboard": "/dashboard",
        "/": "/dashboard",
        "": "/dashboard",
        None: "/dashboard",
    }

    redirect_path = allowed_next_paths.get(next_path, "/dashboard")

    # Idempotent: safe even if already marked
    mark_welcome_seen(user_id)

    return {
        "redirect": redirect_path
    }

from app.db.user_pool import get_user_by_userid
from app.services.user_context import build_user_context


def render_demographics_get(user_id: str, base_html: str, template_path, error_key=None):
    user = get_user_by_userid(user_id)
    if not user:
        return {"redirect": "/login"}

    ctx = build_user_context(user)

    # Gate: only demographics step allowed
    if ctx["states"]["onboarding"] != "demographics":
        return {"redirect": ctx["routing"]["landing_path"]}

    csrf_token = generate_csrf_token(user_id)

    body_html = template_path
    body_html = body_html.replace("__CSRF_TOKEN__", e(csrf_token))

    # --------------------------------
    # Static replacements (escaped)
    # --------------------------------
    body_html = body_html.replace("__EMAIL__", e(user.get("Email", "")))

    error_block = ""

    if error_key:
        message = ERROR_MESSAGES.get(error_key)

        if message:
            error_block = f"""
            <div class="form-error-banner">
                {e(message)}
            </div>
            """

    body_html = body_html.replace("__ERROR_BLOCK__", error_block)

    # --------------------------------
    # Country dropdown
    # --------------------------------
    countries = get_country_codes()
    selected_country_code = (user.get("CountryCode") or "").strip().upper()

    country_options = ""

    for country in countries:
        raw_code = str(country.get("CountryCode") or "").strip().upper()
        code = e(raw_code)
        name = e(country.get("CountryName") or "")

        selected = " selected" if raw_code == selected_country_code else ""
        country_options += f'<option value="{code}"{selected}>{name}</option>'

    body_html = body_html.replace("__COUNTRY_OPTIONS__", country_options)

    # --------------------------------
    # Safe attribute injection helper
    # --------------------------------
    def inject_value(html, field, value):
        safe_value = e(value or "")
        return html.replace(
            f'name="{field}"',
            f'name="{field}" value="{safe_value}"'
        )

    body_html = inject_value(body_html, "first_name", user.get("FirstName"))
    body_html = inject_value(body_html, "last_name", user.get("LastName"))
    body_html = inject_value(body_html, "birth_year", user.get("BirthYear"))
    body_html = inject_value(body_html, "city", user.get("City"))

    # --------------------------------
    # Gender select (escaped)
    # --------------------------------
    if user.get("Gender"):
        safe_gender = e(user["Gender"])
        body_html = body_html.replace(
            f'<option value="{safe_gender}">',
            f'<option value="{safe_gender}" selected>'
        )

    return {"html": body_html}

def render_nda_get(user_id: str, template_path):
    user = get_user_by_userid(user_id)
    if not user:
        return {"redirect": "/login"}

    from app.services.user_context import build_user_context
    ctx = build_user_context(user)

    if ctx["states"]["onboarding"] != "nda":
        return {"redirect": ctx["routing"]["landing_path"]}

    from app.db.legal_documents import get_latest_published_document

    full_name = f"{user['FirstName']} {user['LastName']}".strip()

    nda = get_latest_published_document("nda")

    csrf_token = generate_csrf_token(user_id)

    if nda:
        body_html = template_path.replace("__NDA_CONTENT__", nda["content"])
    else:
        body_html = template_path.replace(
            "__NDA_CONTENT__",
            "<p>NDA document not available.</p>"
        )

    body_html = body_html.replace("__FULL_NAME__", full_name)
    body_html = body_html.replace("__CSRF_TOKEN__", e(csrf_token))

    return {"html": body_html}

def render_welcome_get(user_id: str, base_html: str, template_path):
    user = get_user_by_userid(user_id)
    if not user:
        return {"redirect": "/login"}

    from app.services.user_context import build_user_context
    ctx = build_user_context(user)

    if ctx["states"]["onboarding"] == "welcome":
        # GET does NOT mutate state
        pass
    elif ctx["states"]["onboarding"] == "ready":
        return {"redirect": ctx["routing"]["landing_path"]}
    else:
        return {"redirect": ctx["routing"]["landing_path"]}

    csrf_token = generate_csrf_token(user_id)

    body_html = template_path
    body_html = body_html.replace("__CSRF_TOKEN__", e(csrf_token))

    return {"html": body_html}