from pathlib import Path

from app.services.registration import register_user, RegistrationInput
from app.services.login import login_user, LoginInput
from app.constants.blocked_domains import is_blocked_domain
from app.utils.html_escape import escape_html as e
from urllib.parse import urlparse, parse_qs

def handle_register_post(data):
    email = data.get("email", [""])[0].strip().lower()
    confirm_email = data.get("confirm_email", [""])[0].strip().lower()
    password = data.get("password", [""])[0]
    confirm_password = data.get("confirm_password", [""])[0]

    # ---- email match check ----
    if email != confirm_email:
        return {"error": "Email addresses do not match.", "email": email}

    # ---- password match check ----
    if password != confirm_password:
        return {"error": "Passwords do not match.", "email": email}

    # ---- basic email format check ----
    if "@" not in email:
        return {"error": "Please enter a valid email address.", "email": email}

    # ---- extract domain ----
    domain = email.split("@")[-1].lower()

    # ---- blocked domain check ----
    if is_blocked_domain(domain):
        return {
            "error": "Corporate or disposable email domains are not permitted. Please register with a personal email address.",
            "email": email
        }

    # ---- registration ----
    result = register_user(
        RegistrationInput(email=email, password=password)
    )

    if not result.success:
        return {"error": result.message, "email": email}

    return {
        "redirect": f"/verify-email?token={result.token}"
    }


def handle_verify_email_post(token):
    if not token:
        return {"error": "Missing verification token."}

    from app.cache.registration_cache import (
        get_registration_entry,
        delete_registration_entry,
    )

    from app.db.user_pool import (
        insert_user_pool,
        get_user_by_email,
    )

    entry = get_registration_entry(token)
    if not entry:
        return {"error": "Invalid or expired verification token."}

    email = entry["email"]

    # ---------------------------------------
    # Idempotent user creation
    # ---------------------------------------
    user = get_user_by_email(email)

    if not user:
        insert_user_pool(
            email=email,
            password_hash=entry["password_hash"],
            internal_user=entry["internal_user"],
            status=0,
            global_nda_status="Not Sent",
            email_verified=1,
        )

        user = get_user_by_email(email)
        if not user:
            return {"error": "User creation failed."}

    # ---------------------------------------
    # ALERT: REAL user created (verified)
    # ---------------------------------------
    from app.services.email_smtp import send_new_user_alert

    try:
        send_new_user_alert(
            email=user.get("Email"),
            user_id=user.get("user_id"),
        )
        print("[DEBUG] Alert sent successfully")
    except Exception as e_err:
        print("[DEBUG] User creation alert failed:", e_err)

    # ---------------------------------------
    # ALWAYS cleanup token (resumability)
    # ---------------------------------------
    try:
        delete_registration_entry(token)
    except Exception as e_err:
        print("[DEBUG] Token cleanup failed:", e_err)

    return {"user": user}


def handle_login_post(data, ip):
    email = data.get("email", [""])[0].strip().lower()
    password = data.get("password", [""])[0]

    result = login_user(
        LoginInput(email=email, password=password),
        ip
    )

    if not result.success:
        return {"error": result.message}

    return {
        "user": result.user,
        "onboarding_state": result.onboarding_state
    }

from urllib.parse import urlparse, parse_qs


def render_register_get(base_html: str, register_template_path):
    from pathlib import Path
    body_html = register_template_path

    body_html = body_html.replace("__EMAIL__", "")
    body_html = body_html.replace("__ERROR_BLOCK__", "")

    html = base_html.replace("__BODY_CLASS__", "auth-page")
    html = html.replace("__BODY__", body_html)

    return {"html": html}


def handle_logout_get(handler):
    # logout is still a side-effect, so let main own cookies
    handler._handle_logout()


def render_login_get(handler, base_html: str, login_template_path, query):
    uid = handler._get_uid_from_cookie()

    # If already logged in, redirect via user_context
    if uid:
        from app.db.user_pool import get_user_by_userid
        from app.services.user_context import build_user_context

        user = get_user_by_userid(uid)
        if user:
            ctx = build_user_context(user)
            landing = ctx["routing"].get("landing_path")

            if landing and landing != "/login":
                return {"redirect": landing}

    body_html = login_template_path

    success_block = ""
    error_block = ""

    if query.get("registered") == ["1"]:
        success_block = (
            '<div class="form-success">'
            'Registration successful. Please log in to continue.'
            '</div>'
        )

    if query.get("verified") == ["1"]:
        success_block = (
            '<div class="form-success">'
            'Email verified successfully. Please log in.'
            '</div>'
        )

    body_html = body_html.replace("__SUCCESS_BLOCK__", success_block)
    body_html = body_html.replace("__ERROR_BLOCK__", error_block)

    html = base_html.replace("__BODY_CLASS__", "auth-page")
    html = html.replace("__BODY__", body_html)

    return {"html": html}


def render_verify_email_get(base_html: str, path: str):
    parsed_url = urlparse(path)
    query = parse_qs(parsed_url.query)

    token = query.get("token", [None])[0]

    if not token:
        return {
            "status": 400,
            "html": "<p>Invalid or missing verification token.</p>"
        }

    safe_token = e(token)

    body_html = f"""
        <h2>Email Verification</h2>

        <p>
            Click the button below to verify your email and activate your account.
        </p>

        <form method="POST" action="/verify-email">
            <input type="hidden" name="token" value="{safe_token}">
            <button type="submit">Verify Email & Continue</button>
        </form>
    """

    html = base_html.replace("__BODY__", body_html)
    return {"html": html}