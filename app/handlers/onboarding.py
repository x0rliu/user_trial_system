from app.db.user_pool import (
    get_user_by_userid,
    mark_guidelines_completed,
)
from app.services.onboarding_state import get_onboarding_state
from app.db.user_pool_country_codes import get_country_codes
import mysql.connector
from app.config.config import DB_CONFIG
from app.config.error_messages import ERROR_MESSAGES
from app.db.legal_documents import get_latest_published_document
from app.db.user_legal_acceptance import record_user_legal_acceptance
from app.utils.html_escape import escape_html as e
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



def render_guidelines_page():
    return """
        <h2>Participation Guidelines</h2>

        <div style="max-height: 320px; overflow-y: auto; border: 1px solid #ccc; padding: 1rem; margin-bottom: 1rem; background: #fafafa;">
            <p><strong>User Trial Participation Guidelines</strong></p>
            <p>
                We’re excited to have you join our User Trials program.
                Our goal is to create an open, reliable, and respectful testing community where your feedback
                genuinely influences our products.
            </p>

            <h3 style="margin-top: 1rem;">1. General Expectations</h3>
            <ul>
                <li><strong>Be responsive and reliable.</strong> Reply promptly when contacted about onboarding, NDAs, shipping, or surveys.</li>
                <li><strong>Be thoughtful.</strong> Share your honest experiences — optional comments are your chance to tell us why something worked or didn’t.</li>
                <li><strong>Be respectful.</strong> Interact professionally with Logitech staff and other participants.</li>
                <li><strong>Protect confidentiality.</strong> All trial information is private unless otherwise stated.</li>
            </ul>

            <h3>2. Communication &amp; Reminders</h3>
            <ul>
                <li>If you need more than two personal reminders (for NDA signing, survey completion, or device return), your participation record may be marked as incomplete.</li>
                <li>Consistent follow-through helps maintain eligibility for future trials.</li>
            </ul>

            <h3>3. NDA and Confidentiality</h3>
            <ul>
                <li>NDAs must be signed and correctly submitted before you can begin a trial.</li>
                <li>Failing to sign or misrouting your NDA may delay or cancel participation.</li>
                <li>Sharing or posting confidential product details, photos, or files will result in immediate removal from all current and future trials.</li>
            </ul>

            <h3>4. Surveys and Feedback Quality</h3>
            <p>Your feedback drives product decisions. Please complete all required questions and offer at least some comments across sections.</p>
            <p><strong>Examples of poor-quality feedback (may affect eligibility):</strong></p>
            <ul>
                <li>Leaving all open comment fields blank.</li>
                <li>Writing the same short phrase (e.g., “good,” “fine”) for every question.</li>
                <li>Copying and pasting one paragraph into multiple sections regardless of topic.</li>
            </ul>
            <p>We understand not every topic will inspire a long answer — that’s fine. We simply ask that you contribute thoughtful input where you have opinions or experiences to share.</p>

            <h3>5. Sample Handling</h3>
            <ul>
                <li>Treat all samples as company property unless otherwise stated.</li>
                <li>If you cannot complete the trial, notify us and arrange a return.</li>
                <li>Damaged or lost samples may affect your eligibility for future programs.</li>
                <li>Not returning a device or intentionally misusing it will result in permanent exclusion from all user trials.</li>
            </ul>

            <h3>6. Conduct</h3>
            <ul>
                <li>Inappropriate, abusive, or unprofessional behavior toward staff or other testers will lead to permanent removal.</li>
                <li>We maintain a safe and respectful environment for everyone.</li>
            </ul>

            <h3>7. Consequences and Eligibility</h3>
            <p>We track participation history to ensure fair opportunities for all testers. Depending on the issue, consequences may include temporary suspension or permanent removal.</p>

            <h3>8. Positive Participation</h3>
            <ul>
                <li>Consistent, thoughtful, and timely participation may qualify you for priority selection in future trials.</li>
                <li>Our most valued testers communicate clearly, meet deadlines, and provide meaningful insights — even brief ones.</li>
            </ul>

            <p style="margin-top: 1rem;"><strong>Thank you.</strong> If you ever have questions about these guidelines, reach out to your User Trials contact.</p>
        </div>

        <form method="POST" action="/participation-guidelines">
            <label>
                <input type="checkbox" name="ack" required>
                I have read and acknowledge the participation guidelines
            </label>
            <br><br>
            <button type="submit">Continue</button>
        </form>
    """



def handle_guidelines_get(user_id: str):
    user = get_user_by_userid(user_id)
    state = get_onboarding_state(user)

    if state != "participation_guidelines":
        return {
            "redirect": "/"
        }

    return {
        "body": render_guidelines_page(),
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
    """

    first_name = data.get("first_name", [""])[0].strip()
    last_name = data.get("last_name", [""])[0].strip()
    gender = data.get("gender", [""])[0]
    birth_year_raw = data.get("birth_year", [""])[0]
    country = data.get("country", [""])[0].strip()
    city = data.get("city", [""])[0].strip()

    # ---- mobile phone extraction (AUTHORITATIVE) ----
    mobile_country_code = data.get("mobile_country_code", [""])[0].strip()
    mobile_national = data.get("mobile_national", [""])[0].strip()

    # ---- normalize digits ----
    digits_country = "".join(c for c in mobile_country_code if c.isdigit())
    digits_national = "".join(c for c in mobile_national if c.isdigit())

    # ---- validation ----
    if not digits_country:
        return {"redirect": "/demographics?error=invalid_mobile_code"}

    if len(digits_national) < 8:
        return {"redirect": "/demographics?error=invalid_mobile_number"}

    # ---- E.164 assembly ----
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
            city=city,
            mobile_country_code=f"+{digits_country}",
            mobile_national=digits_national,
            mobile_e164=mobile_e164,
        )
    except Exception as e_err:
        print("[ERROR] Demographics update failed:", e)
        return {"redirect": "/demographics?error=demographics_save_failed"}

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

    state = get_onboarding_state(user)

    if state != "nda":
        return {"redirect": "/"}

    if "agree" not in form:
        return {"redirect": "/nda"}

    nda = get_latest_published_document("nda")
    if not nda:
        return {"redirect": "/nda"}

    # ---- Perform mutation (atomic) ----
    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        conn.start_transaction()

        mark_global_nda_signed(user_id)

        record_user_legal_acceptance(
            user_id=user_id,
            document_id=nda["id"],
            document_type="nda",
        )

        conn.commit()

    except Exception as e_err:
        conn.rollback()
        print("[ERROR] NDA signing failed:", e)

        return {"redirect": "/nda"}

    finally:
        conn.close()

    return {"redirect": "/participation-guidelines"}

from app.db.user_pool import (
    get_user_by_userid,
    mark_welcome_seen,
)
from app.services.onboarding_state import get_onboarding_state


def handle_welcome_post(user_id: str):
    """
    Handles POST /welcome onboarding logic.
    Input: user_id
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

    # Idempotent: safe even if already marked
    mark_welcome_seen(user_id)

    return {
        "redirect": "/dashboard"
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

    body_html = template_path

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

    country_options = ""

    for c in countries:
        code = e(c["CountryCode"])
        name = e(c["CountryName"])

        if c["CountryCode"] == user.get("Country"):
            country_options += f'<option value="{code}" selected>{name}</option>'
        else:
            country_options += f'<option value="{code}">{name}</option>'

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
    body_html = inject_value(body_html, "phone_number", user.get("PhoneNumber"))
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

    if nda:
        body_html = template_path.replace("__NDA_CONTENT__", nda["content"])
    else:
        body_html = template_path.replace(
            "__NDA_CONTENT__",
            "<p>NDA document not available.</p>"
        )

    body_html = body_html.replace("__FULL_NAME__", full_name)

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

    body_html = template_path

    return {"html": body_html}