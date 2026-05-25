# app/main.py

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from os import path
from pathlib import Path
from unittest import result
from urllib.parse import urlparse, parse_qs
import multiprocessing

from app.db.content_pages import get_page_by_slug
from app.services.registration import register_user, RegistrationInput
from app.config.config import SESSION_COOKIE_SECURE
from app.config.config import MAX_POST_BODY_BYTES
from http import cookies
from app.services.demographics import save_demographics, DemographicsInput
from app.services.login import login_user, LoginInput
from app.config.profile_layout import BASIC_PROFILE_SECTIONS
from app.config.profile_layout import ADVANCED_PROFILE_SECTIONS
from app.services.onboarding_state import get_onboarding_state
from app.utils.templates import render_template
from app.config.error_messages import ERROR_MESSAGES
import json
import urllib.parse
from app.utils.external_redirects import (
    is_allowed_external_survey_redirect as _is_allowed_external_survey_redirect,
)
from app.handlers.my_trials import render_past_trials_get
from app.handlers.legal_download import render_download_document
from app.db.user_pool import mark_email_verified
from app.services.notifications import get_all_notifications
from app.handlers.notifications import render_notification
from app.handlers.survey_upload import (
    render_survey_upload_get,
    handle_survey_upload_post,
)
from app.handlers.responsibilities import (
    render_responsibilities,
    handle_responsibilities,
)
from app.utils.html_escape import escape_html as e
from app.utils.debug import debug_log

# -------------------------
# Templates
# -------------------------
BASE_TEMPLATE = Path("app/templates/base.html").read_text(encoding="utf-8")
BONUS_BASE_TEMPLATE = Path("app/templates/surveys/base_bonus_surveys.html").read_text(encoding="utf-8")
LOGIN_TEMPLATE = Path("app/templates/login.html").read_text(encoding="utf-8")
REGISTER_TEMPLATE = Path("app/templates/register.html").read_text(encoding="utf-8")
DEMOGRAPHICS_TEMPLATE = Path("app/templates/demographics.html").read_text(encoding="utf-8")
NDA_TEMPLATE = Path("app/templates/nda.html").read_text(encoding="utf-8")
WELCOME_TEMPLATE = Path("app/templates/welcome.html").read_text(encoding="utf-8")
CONTACT_FORM_HTML = Path("app/templates/contact_form.html").read_text(encoding="utf-8")
BASE_LEGAL = Path("app/templates/legal/base_legal.html").read_text(encoding="utf-8")
SELECTION_BASE_TEMPLATE = Path("app/templates/user_selection/base_user_selection.html").read_text(encoding="utf-8")
RESPONSIBILITIES_TEMPLATE = Path("app/templates/responsibilities.html").read_text(encoding="utf-8")

# -------------------------
# Debug output
# -------------------------
debug = debug_log


def render_profile_summary_html(full_summary: dict) -> str:
    html = []

    def _safe(value) -> str:
        return e(str(value or ""))

    def _safe_int(value) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _safe_values(values) -> str:
        if not isinstance(values, list):
            return ""
        return ", ".join(_safe(value) for value in values)

    # -------------------------
    # Demographics
    # -------------------------
    demo = full_summary.get("demographics", {})
    html.append("<section class='profile-summary demographics'>")
    html.append(f"<h2>{_safe(demo.get('title'))}</h2>")

    for item in demo.get("items", []):
        html.append(
            f"<div class='summary-row'>"
            f"<span class='label'>{_safe(item.get('label'))}</span>: "
            f"<span class='value'>{_safe(item.get('value'))}</span>"
            f"</div>"
        )
    html.append("</section>")

    # -------------------------
    # Interests / Basic / Advanced
    # -------------------------
    def render_sections(title, sections):
        html.append(f"<section class='profile-summary'><h2>{_safe(title)}</h2>")

        for s in sections:
            completed = _safe_int(s.get("completed"))
            total = _safe_int(s.get("total"))

            html.append("<details>")
            html.append(
                f"<summary>{_safe(s.get('title'))} ({completed} / {total})</summary>"
            )

            # Child sections (Product Types)
            if "children" in s:
                for child in s["children"]:
                    html.append(
                        f"<div class='summary-child'>"
                        f"<strong>{_safe(child.get('title'))}</strong>"
                        f"</div>"
                    )
                    for cat in child.get("categories", []):
                        html.append(
                            f"<div>{_safe(cat.get('category_name'))}: "
                            f"{_safe_values(cat.get('values', []))}</div>"
                        )
            else:
                for cat in s.get("categories", []):
                    html.append(
                        f"<div>{_safe(cat.get('category_name'))}: "
                        f"{_safe_values(cat.get('values', []))}</div>"
                    )

            missing = _safe_int(s.get("missing"))
            if missing > 0:
                html.append(
                    f"<div class='missing'>{missing} not specified</div>"
                )

            html.append("</details>")

        html.append("</section>")

    render_sections("Interests", full_summary.get("interests", []))
    render_sections("Basic Profile", full_summary.get("basic_profile", []))
    render_sections("Advanced Profile", full_summary.get("advanced_profile", []))

    return "\n".join(html)

class RequestHandler(BaseHTTPRequestHandler):
    def _send_security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self' https://docs.google.com https://forms.gle;"
        )

        if not self.path.startswith(("/static/", "/images/")):
            self.send_header("Cache-Control", "no-store")

    def end_headers(self):
        self._send_security_headers()
        super().end_headers()

    def _client_ip_from_trusted_proxy(self) -> str:
        import ipaddress
        import os

        socket_ip = self.client_address[0] if self.client_address else ""
        trusted_proxy_config = os.getenv("TRUSTED_PROXY_IPS", "")
        trusted_proxy_ranges = [
            item.strip()
            for item in trusted_proxy_config.split(",")
            if item.strip()
        ]

        def _is_valid_ip(value: str) -> bool:
            try:
                ipaddress.ip_address(value)
                return True
            except ValueError:
                return False

        def _is_trusted_proxy(value: str) -> bool:
            if not value or not trusted_proxy_ranges:
                return False

            try:
                parsed_ip = ipaddress.ip_address(value)
            except ValueError:
                return False

            for raw_range in trusted_proxy_ranges:
                try:
                    if parsed_ip in ipaddress.ip_network(raw_range, strict=False):
                        return True
                except ValueError:
                    continue

            return False

        if not _is_trusted_proxy(socket_ip):
            return socket_ip

        x_real_ip = (self.headers.get("X-Real-IP") or "").strip()
        if x_real_ip and _is_valid_ip(x_real_ip):
            return x_real_ip

        x_forwarded_for = self.headers.get("X-Forwarded-For") or ""
        forwarded_ip = x_forwarded_for.split(",")[0].strip()
        if forwarded_ip and _is_valid_ip(forwarded_ip):
            return forwarded_ip

        return socket_ip

    def _reject_oversized_post_if_needed(self) -> bool:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self.send_response(400)
            self.end_headers()
            return True

        if content_length > MAX_POST_BODY_BYTES:
            self.send_response(413)
            self.end_headers()
            return True

        return False

    # -------------------------
    # Static assets
    # -------------------------
    def _serve_static(self):
        from urllib.parse import urlparse
        import mimetypes

        parsed = urlparse(self.path)
        static_path = Path("app") / parsed.path.lstrip("/")
        if not static_path.exists() or not static_path.is_file():
            self._send_404()
            return

        content_type, _ = mimetypes.guess_type(str(static_path))
        if static_path.suffix.lower() == ".js":
            content_type = "application/javascript"
        elif static_path.suffix.lower() == ".css":
            content_type = "text/css"
        elif not content_type:
            content_type = "application/octet-stream"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(static_path.read_bytes())

    def _serve_image(self):
        from urllib.parse import urlparse
        import mimetypes

        parsed = urlparse(self.path)
        image_path = Path("app") / parsed.path.lstrip("/")

        if not image_path.exists() or not image_path.is_file():
            debug("Image not found:", image_path)
            self._send_404()
            return

        if image_path.suffix.lower() == ".svg":
            content_type = "image/svg+xml"
        else:
            content_type, _ = mimetypes.guess_type(str(image_path))
            if not content_type:
                content_type = "application/octet-stream"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(image_path.read_bytes())

    # -------------------------
    # Role Navigation Gating
    # -------------------------

    def _get_primary_role_id(self, user_id: str) -> int:
        """
        Returns the highest numeric RoleID for the user.
        Defaults to 0 if none found.
        """
        if not user_id:
            return 0

        import mysql.connector
        from app.config.config import DB_CONFIG

        conn = mysql.connector.connect(**DB_CONFIG)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT MAX(RoleID) FROM user_role_map WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()
            role_id = row[0] if row else None
            return int(role_id) if role_id is not None else 0
        finally:
            conn.close()

    # -------------------------
    # GET requests
    # -------------------------

    def do_GET(self):
        # -------------------------
        # Static assets (ALWAYS FIRST)
        # -------------------------
        if self.path.startswith("/static/"):
            self._serve_static()
            return
        if self.path.startswith("/images/"):
            self._serve_image()
            return
        # -------------------------
        # URL parsing (single source of truth)
        # -------------------------
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(self.path)
        path = parsed.path.strip("/")
        query = parse_qs(parsed.query)

        # ==================================================
        # GET HANDLERS (render-only)
        # ==================================================
        if path == "":
            self._render_home()
            return
        if path == "register":
            self._render_register()
            return
        if path == "verify-email":
            self._render_verify_email()
            return
        if path == "login":
            self._render_login(query=query)
            return
        if path == "sso/login":
            self._render_sso_login()
            return
        if path == "sso/callback":
            self._render_sso_callback(query=query)
            return
        if path == "logout":
            self._render_logout()
            return
        if path == "demographics":
            self._render_demographics()
            return
        if path == "nda":
            self._render_nda()
            return
        if path == "participation-guidelines":
            self._render_participation_guidelines()
            return
        if path == "welcome":
            self._render_welcome()
            return
        if path == "profile/wizard":
            self._render_profile_wizard()
            return
        if path == "profile/interests":
            self._render_profile_interests()
            return
        if path == "profile/basic":
            self._render_profile_basic()
            return
        if path == "profile/advanced":
            self._render_profile_advanced()
            return
        if path == "profile":
            self._render_profile_summary()
            return
        if path == "settings":
            self._render_settings_page()
            return
        if path == "settings/participation-guidelines":
            self._render_settings_participation_guidelines()
            return
        if path == "settings/demographics":
            self._render_settings_demographics_fragment()
            return
        if path == "settings/interests":
            self._render_settings_interests_fragment()
            return
        if path == "settings/basic":
            self._render_settings_basic_fragment()
            return
        if path == "settings/advanced":
            self._render_settings_advanced_fragment()
            return
        if path == "dashboard":
            self._render_dashboard()
            return
        if path == "dashboard/cards":
            self._render_dashboard_cards()
            return
        if path == "my_trials":
            self._render_my_trials()
            return
        if path == "history":
            self._render_history()
            return
        if path == "badges":
            self._render_badges()
            return
        if path == "trials/active":
            self._render_trials_active()
            return
        if path == "trials/past":
            self._render_trials_past()
            return
        if path == "trials/upcoming":
            self._render_trials_upcoming()
            return
        if path == "trials/details":
            self._render_trial_details()
            return
        if path == "trials/recruiting":
            self._render_trials_recruiting()
            return
        if path == "trials/interest":
            self._render_trials_interest()
            return
        if path == "admin/users":
            self._render_admin_users()
            return
        if path == "trials/nda":
            self._render_trial_nda()
            return
        
        # ---- Legal routes
        legal_parts = path.split("/") if path else []

        if path == "legal/nda":
            self._render_legal_nda()
            return

        if (
            len(legal_parts) == 3
            and legal_parts[0] == "legal"
            and legal_parts[1] == "download"
            and legal_parts[2]
        ):
            self._render_legal_download(path)
            return

        if (
            len(legal_parts) == 3
            and legal_parts[0] == "legal"
            and legal_parts[1] == "signed"
            and legal_parts[2]
        ):
            self._render_signed_legal_document(path)
            return

        if path == "legal/documents":
            self._render_legal_documents_index()
            return

        if (
            len(legal_parts) == 3
            and legal_parts[0] == "legal"
            and legal_parts[1] == "documents"
            and legal_parts[2]
        ):
            doc_id = legal_parts[2]
            self._render_legal_documents_index(doc_id=doc_id)
            return

        if (
            len(legal_parts) == 2
            and legal_parts[0] == "legal"
            and legal_parts[1]
        ):
            self._render_legal_document_view(path)
            return
        
        # ---- Survey routes

        if path == "surveys/bonus":
            self._render_bonus_surveys()
            return
        if path == "surveys/bonus/create":
            self._render_bonus_survey_create()
            return
        if path == "surveys/ut":
            self._render_ut_surveys()
            return
        if path == "surveys/recruitment":
            self._render_recruitment_surveys()
            return
        if path == "surveys/bonus/create/template":
            self._render_bonus_survey_template()
            return
        if path == "surveys/bonus/create/targeting":
            self._render_bonus_survey_targeting()
            return
        if path == "surveys/bonus/create/review":
            self._render_bonus_survey_review()
            return
        if path == "surveys/bonus/submitted":
            self._render_bonus_survey_submitted()
            return
        if path == "surveys/bonus/pending":
            self._render_bonus_survey_pending_view()
            return
        if path == "surveys/bonus/upload":
            self._render_bonus_survey_upload()
            return
        if path == "surveys/bonus/structure":
            self._render_bonus_survey_structure()
            return

        # ---- Admin routes

        if path == "admin/approvals":
            self._render_admin_approvals()
            return

        if path == "admin/approvals/view":
            self._render_admin_approval_view()
            return

        if path == "admin/approvals/project":
            self._render_admin_approval_project()
            return

        if path == "surveys/bonus/active":
            self._render_bonus_survey_active()
            return
        if path == "surveys/bonus/archived":
            self._render_bonus_survey_archived()
            return
        if path == "surveys/bonus/take":
            self._render_bonus_survey_take()
            return
        if path == "surveys/bonus/take/open":
            self._render_bonus_survey_take_open()
            return

        # ---- Notifcations
        # ---- Notifications
        if path == "notifications":
            self._render_notifications()
            return
        if path == "notifications/view":
            self._render_notification_view()
            return
        if path in ("notifications/dismiss", "notifications/mark-read", "notifications/open"):
            self.send_response(302)
            self.send_header("Location", "/notifications")
            self.end_headers()
            return
        # -------------------------
        # Product Team Routes
        # -------------------------
        if path == "product/request-trial":
            self._render_product_request_trial()
            return
        if path == "product/current-trials":
            self._render_product_current_trials()
            return
        if path == "product/past-trials":
            self._render_product_past_trials()
            return
        if path == "product/comparisons":
            self._render_product_comparisons()
            return
        if path == "product/reports":
            self._render_product_reports()
            return
        if path == "reporting/insights":
            self._render_reporting_insights("projects")
            return
        if path == "reporting/insights/projects":
            self._render_reporting_insights("projects")
            return
        if path == "reporting/insights/product-types":
            self._render_reporting_insights("product_types")
            return
        if path == "reporting/insights/business-groups":
            self._render_reporting_insights("business_groups")
            return
        if path == "reporting/insights/overall":
            self._render_reporting_insights("overall")
            return
        if path == "reporting/insights/tiers":
            self._render_reporting_insights("tiers")
            return
        if path == "product/request-trial/wizard/basics":
            self._render_product_request_trial_wizard_basics()
            return
        if path == "product/request-trial/wizard/timing":
            self._render_product_request_trial_wizard_timing()
            return
        if path == "product/request-trial/wizard/stakeholders":
            self._render_product_request_trial_wizard_stakeholders()
            return
        if path == "product/request-trial/wizard/review":
            self._render_product_request_trial_wizard_review()
            return
        if path == "product/request-trial/pending":
            self._render_product_request_trial_pending()
            return
        if path == "product/request-trial/info-requested":
            self._render_product_request_trial_info_requested()
            return
        if path == "product/request-trial/change-requested":
            self._render_product_request_trial_change_requested()
            return
        # -------------------------
        # UT Lead Routes
        # -------------------------
        if path == "ut-lead/trials":
            self._render_ut_lead_trials()
            return
        if path == "ut-lead/project":
            self._render_ut_lead_project()
            return
        if path == "api/profile-levels":
            self._render_api_profile_levels()
            return
        if path == "trials/selection":
            self._render_user_selection()
            return
        if path == "trials/selection/confirm":
            self._render_user_selection_confirm()
            return
        if path == "survey/upload":
            self._render_survey_upload()
            return
            
        # -------------------------
        # Active Trials
        # -------------------------        
        if path == "trials/responsibilities":
            self._render_responsibilities()
            return
        # -------------------------
        # debug route for selection flow testing
        # -------------------------
        if path == "debug/selection-test":
            self._redirect("/dashboard")
            return
        
        # -------------------------
        # Historical Trials (Pre UTS)
        # -------------------------   

        # ---- Historical Upload
        if path == "historical/upload":
            self._render_historical_upload()
            return
        # ---- Historical Landing
        if path == "historical":
            self._render_historical_landing()
            return
        # ---- Historical Product Lifecycle
        if path == "historical/product":
            self._render_historical_product_lifecycle()
            return
        # ---- Historical Product Taxonomy
        if path == "historical/product-taxonomy":
            self._render_historical_product_taxonomy()
            return
        # ---- Historical Create Context
        if path == "historical/create-context":
            self._render_historical_create_context()
            return
        # ---- Historical Context
        if path == "historical/context":
            self._render_historical_context()
            return
        # ---- Historical Aggregate Report
        if path == "historical/aggregate-report":
            self._render_historical_aggregate_report()
            return
        # ---- Historical Comparison
        if path == "historical/comparison":
            self._render_historical_comparison()
            return
        # ---- Historical Raw Data
        if path == "historical/raw":
            self._render_historical_raw()
            return
        # ---- Create Product
        if path == "products/create":
            self._render_create_product()
            return

        # ---- Catch-all for unhandled GET routes
        self._render_guest_content(path)

    def _debug_selection_test(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from app.services.selection_service import (
            create_or_get_selection_session,
            get_current_pool,
            apply_selection_step,
        )

        from app.services.user_score_service import calculate_user_score

        ROUND_ID = 26
        TARGET = 45

        session = create_or_get_selection_session(
            round_id=ROUND_ID,
            user_id=uid,
            target_users=TARGET
        )

        session_id = session["SessionID"]

        pool_before = get_current_pool(session_id=session_id)

        from app.services.selection_service import simulate_filter

        result = simulate_filter(
            session_id=session_id,
            criteria_type="blacklist",
            criteria_value=""
        )

        pool_after = get_current_pool(session_id=session_id)

        # -------------------------
        # APPLY SCORING (NEW)
        # -------------------------
        context = {
            "eligible_pool_size": len(pool_after),
            "target_users": TARGET
        }

        scored_pool = []

        for i, user in enumerate(pool_after):

            # =========================
            # FORCED TEST DIFFERENCES
            # =========================
            if i == 0:
                user["completed_trials"] = 5  # strong positive

            elif i == 1:
                user["missed_deadlines"] = 3  # strong negative

            elif i == 2:
                user["in_cooldown"] = True   # cooldown penalty
            # =========================

            result_score = calculate_user_score(user, context)

            user["score"] = result_score["score"]
            user["score_breakdown"] = result_score["breakdown"]

            scored_pool.append(user)

        # -------------------------
        # SORT (NEW)
        # -------------------------
        scored_pool = sorted(
            scored_pool,
            key=lambda x: x["score"],
            reverse=True
        )

        selected = scored_pool[:TARGET]
        alternates = scored_pool[TARGET:TARGET + 3]

        # -------------------------
        # BUILD DEBUG TABLES (NEW)
        # -------------------------

        def build_table(users, title):
            rows = ""
            for u in users:
                rows += f"""
                <tr>
                    <td>{e(u["user_id"])}</td>
                    <td>{e(u.get("score", ""))}</td>
                    <td>{e(u.get("score_breakdown", {}))}</td>
                </tr>
                """
            return f"""
            <h3>{e(title)}</h3>
            <table border="1" cellpadding="5">
                <tr>
                    <th>User ID</th>
                    <th>Score</th>
                    <th>Breakdown</th>
                </tr>
                {rows}
            </table>
            """

        html = f"""
        <h2>Selection Debug</h2>

        <p><b>Session ID:</b> {e(session_id)}</p>

        <p><b>Initial Pool:</b> {len(pool_before)}</p>
        <p><b>After Step:</b> {len(pool_after)}</p>

        <p><b>Step Result:</b> {e(result)}</p>

        {build_table(scored_pool[:10], "Top 10 Scored Users")}
        {build_table(selected, "Selected Users")}
        {build_table(alternates, "Alternates")}
        """

    # ---- Landing (root)
    def _render_home(self):
        uid = self._get_uid_from_cookie()

        from app.db.user_pool import get_user_by_userid
        from app.services.user_context import build_user_context

        user = get_user_by_userid(uid) if uid else None
        ctx = build_user_context(user)

        self.send_response(302)
        self.send_header("Location", ctx["routing"]["landing_path"])
        self.end_headers()


    # ---- Register page
    def _render_register(self):
        from app.handlers.auth import render_register_get

        base_html = BASE_TEMPLATE

        # Inject auth body class
        base_html = base_html.replace("__BODY_CLASS__", "auth-page")

        result = render_register_get(
            base_html=base_html,
            register_template_path=REGISTER_TEMPLATE,
        )

        # ---- Handle redirects explicitly
        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        # ---- Handle errors explicitly (optional, but recommended)
        if "error" in result:
            html = result.get("html", base_html)
            html = self._inject_nav(html)
            self._send_html(html)
            return

        # ---- Normal HTML render
        html = result["html"]
        html = self._inject_nav(html, mode="public")
        self._send_html(html)

    # ---- Logout page (GET)
    def _render_logout(self):
        from app.handlers.auth import render_logout_get

        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from app.utils.csrf import generate_csrf_token

        csrf_token = generate_csrf_token(uid)

        result = render_logout_get(BASE_TEMPLATE, csrf_token=csrf_token)
        html = self._inject_nav(result["html"])
        self._send_html(html)


    # ---- Login page
    def _render_login(self, *, query=None):
        from app.handlers.auth import render_login_get

        base_html = BASE_TEMPLATE

        # Inject auth body class
        base_html = base_html.replace("__BODY_CLASS__", "auth-page")

        result = render_login_get(
            handler=self,
            base_html=base_html,
            login_template_path=LOGIN_TEMPLATE,
            query=query or {},
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        if "html" not in result:
            raise RuntimeError("render_login_get did not return html or redirect")

        html = self._inject_nav(result["html"], mode="public")
        self._send_html(html)


    def _render_sso_login(self):
        from app.services.sso_service import build_sso_login_redirect

        result = build_sso_login_redirect()

        if not result.success:
            self._redirect("/login?error=sso_not_configured")
            return

        c = cookies.SimpleCookie()

        c["sso_state"] = result.state
        c["sso_state"]["path"] = "/"
        c["sso_state"]["httponly"] = True
        c["sso_state"]["samesite"] = "Lax"
        c["sso_state"]["max-age"] = 600
        if SESSION_COOKIE_SECURE:
            c["sso_state"]["secure"] = True

        c["sso_nonce"] = result.nonce
        c["sso_nonce"]["path"] = "/"
        c["sso_nonce"]["httponly"] = True
        c["sso_nonce"]["samesite"] = "Lax"
        c["sso_nonce"]["max-age"] = 600
        if SESSION_COOKIE_SECURE:
            c["sso_nonce"]["secure"] = True

        c["sso_code_verifier"] = result.code_verifier
        c["sso_code_verifier"]["path"] = "/"
        c["sso_code_verifier"]["httponly"] = True
        c["sso_code_verifier"]["samesite"] = "Lax"
        c["sso_code_verifier"]["max-age"] = 600
        if SESSION_COOKIE_SECURE:
            c["sso_code_verifier"]["secure"] = True

        self.send_response(302)
        self.send_header("Set-Cookie", c["sso_state"].OutputString())
        self.send_header("Set-Cookie", c["sso_nonce"].OutputString())
        self.send_header("Set-Cookie", c["sso_code_verifier"].OutputString())
        self.send_header("Location", result.redirect_url)
        self.end_headers()


    def _render_sso_callback(self, *, query):
        from app.services.sso_service import complete_sso_callback
        from app.services.session_service import create_session

        code = query.get("code", [""])[0]
        returned_state = query.get("state", [""])[0]

        raw_cookie = self.headers.get("Cookie")
        expected_state = ""
        expected_nonce = ""
        code_verifier = ""

        if raw_cookie:
            parsed_cookie = cookies.SimpleCookie()
            parsed_cookie.load(raw_cookie)

            state_morsel = parsed_cookie.get("sso_state")
            if state_morsel:
                expected_state = state_morsel.value.strip()

            nonce_morsel = parsed_cookie.get("sso_nonce")
            if nonce_morsel:
                expected_nonce = nonce_morsel.value.strip()

            verifier_morsel = parsed_cookie.get("sso_code_verifier")
            if verifier_morsel:
                code_verifier = verifier_morsel.value.strip()

        try:
            result = complete_sso_callback(
                code=code,
                returned_state=returned_state,
                expected_state=expected_state,
                code_verifier=code_verifier,
                expected_nonce=expected_nonce,
            )
        except Exception as err:
            debug("SSO callback failed", repr(err))
            self._redirect("/login?error=sso_failed")
            return

        if not result.success:
            debug("SSO callback rejected", result.message)
            self._redirect("/login?error=sso_failed")
            return

        user = result.user
        onboarding_state = result.onboarding_state
        session_id = create_session(user["user_id"])

        c = cookies.SimpleCookie()

        c["session_id"] = session_id
        c["session_id"]["path"] = "/"
        c["session_id"]["httponly"] = True
        c["session_id"]["samesite"] = "Lax"
        if SESSION_COOKIE_SECURE:
            c["session_id"]["secure"] = True

        for cookie_name in ["sso_state", "sso_nonce", "sso_code_verifier"]:
            c[cookie_name] = ""
            c[cookie_name]["path"] = "/"
            c[cookie_name]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
            c[cookie_name]["max-age"] = 0
            c[cookie_name]["httponly"] = True
            c[cookie_name]["samesite"] = "Lax"
            if SESSION_COOKIE_SECURE:
                c[cookie_name]["secure"] = True

        self.send_response(302)
        self.send_header("Set-Cookie", c["session_id"].OutputString())
        self.send_header("Set-Cookie", c["sso_state"].OutputString())
        self.send_header("Set-Cookie", c["sso_nonce"].OutputString())
        self.send_header("Set-Cookie", c["sso_code_verifier"].OutputString())

        if onboarding_state == "demographics":
            self.send_header("Location", "/demographics")
        elif onboarding_state == "nda":
            self.send_header("Location", "/nda")
        elif onboarding_state == "participation_guidelines":
            self.send_header("Location", "/participation-guidelines")
        elif onboarding_state == "welcome":
            self.send_header("Location", "/welcome")
        elif onboarding_state == "ready":
            self.send_header("Location", "/dashboard")
        else:
            self.send_header("Location", "/dashboard")

        self.end_headers()


    # ---- Verify Email
    def _render_verify_email(self):
        from app.handlers.auth import render_verify_email_get

        base_html = BASE_TEMPLATE

        result = render_verify_email_get(base_html, self.path)

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        status = result.get("status", 200)
        self.send_response(status)

        if "html" not in result:
            raise RuntimeError("render_verify_email_get did not return html")

        html = self._inject_nav(result["html"], mode="public")
        self._send_html(html)

    # ---- Demographics page (GET)
    def _render_demographics(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.onboarding import render_demographics_get

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        error_key = params.get("error", [None])[0]

        result = render_demographics_get(
            user_id=uid,
            base_html=BASE_TEMPLATE,
            template_path=DEMOGRAPHICS_TEMPLATE,
            error_key=error_key,
        )

        # ---- redirect handling ----
        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        # ---- enforce render contract ----
        if "html" not in result:
            raise RuntimeError("render_demographics_get did not return html or redirect")

        html = self._inject_nav(BASE_TEMPLATE, mode="onboarding")
        html = html.replace("__BODY__", result["html"])
        self._send_html(html)

    # ---- NDA page
    def _render_nda(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.onboarding import render_nda_get

        result = render_nda_get(
            uid,
            NDA_TEMPLATE,
        )

        # ---- redirect handling ----
        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        # ---- enforce render contract ----
        if "html" not in result:
            raise RuntimeError("render_nda_get did not return html or redirect")

        html = self._inject_nav(BASE_TEMPLATE, mode="onboarding")
        html = html.replace("__BODY__", result["html"])
        self._send_html(html)


    # ---- Participation Guidelines page (GET)
    def _render_participation_guidelines(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.onboarding import render_participation_guidelines

        body = render_participation_guidelines(uid)

        base_html = BASE_TEMPLATE
        html = self._inject_nav(base_html, mode="onboarding")
        html = html.replace("{{ title }}", "Participation Guidelines")
        html = html.replace("__BODY__", body)

        self._send_html(html)

    # ---- Welcome / Activation page
    def _render_welcome(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.onboarding import render_welcome_get

        base_html = BASE_TEMPLATE

        result = render_welcome_get(
            uid,
            base_html,
            WELCOME_TEMPLATE,
        )

        # ---- redirect handling ----
        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        # ---- enforce render contract ----
        if "html" not in result:
            raise RuntimeError("render_welcome_get did not return html or redirect")

        html = self._inject_nav(BASE_TEMPLATE)
        html = html.replace("__BODY__", result["html"])
        self._send_html(html)

    # ---- Profile Wizard entry (GET only)
    def _render_profile_wizard(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.profile import render_profile_wizard_get

        base_html = BASE_TEMPLATE

        result = render_profile_wizard_get(
            user_id=uid,
            base_template=base_html,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])
    
    # ---- Profile Interests page (GET only)
    def _render_profile_interests(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.profile import render_profile_interests_get

        base_html = BASE_TEMPLATE

        result = render_profile_interests_get(
            user_id=uid,
            base_template=base_html,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        if "html" not in result:
            raise RuntimeError("render_profile_interests_get did not return html or redirect")

        html = self._inject_nav(result["html"])
        self._send_html(html)


    # ---- Basic Profile (GET)
    def _render_profile_basic(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.profile import render_profile_basic_get

        base_html = BASE_TEMPLATE

        result = render_profile_basic_get(
            user_id=uid,
            base_template=base_html,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])
    
    # ---- Advanced Profile page (GET only)
    def _render_profile_advanced(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.profile import render_profile_advanced_get

        base_html = BASE_TEMPLATE

        result = render_profile_advanced_get(
            user_id=uid,
            base_template=base_html,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # ---- Profile Summary page (GET only)
    def _render_profile_summary(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.profile import render_profile_summary_get

        base_html = BASE_TEMPLATE

        result = render_profile_summary_get(
            user_id=uid,
            base_template=base_html,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # ---- Settings page (GET)
    def _render_settings_page(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.settings import render_settings_get

        query_params = parse_qs(
            urlparse(self.path).query
        )

        base_html = BASE_TEMPLATE

        result = render_settings_get(
            user_id=uid,
            base_template=base_html,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        self._send_html(result["html"])

    # ---- Settings: Demographics fragment (GET)
    def _render_settings_participation_guidelines(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from app.handlers.settings import render_settings_participation_guidelines_get

        result = render_settings_participation_guidelines_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    def _render_settings_demographics_fragment(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._send_401()
            return

        from app.handlers.settings import render_settings_demographics_form

        fragment = render_settings_demographics_form(uid)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(fragment.encode("utf-8"))

    
    # ---- Settings: Interests fragment (GET)
    def _render_settings_interests_fragment(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._send_401()
            return

        from app.handlers.settings import render_interests_form

        fragment = render_interests_form(uid)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(fragment.encode("utf-8"))

    # ---- Settings: Basic Profile fragment (GET)
    def _render_settings_basic_fragment(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._send_401()
            return

        from app.handlers.settings import render_basic_form

        fragment = render_basic_form(uid)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(fragment.encode("utf-8"))

    # ---- Settings: Advanced Profile fragment (GET)
    def _render_settings_advanced_fragment(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.settings import render_advanced_form

        fragment = render_advanced_form(uid)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(fragment.encode("utf-8"))

    # My Trials page
    def _render_my_trials(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.my_trials import render_my_trials_get

        result = render_my_trials_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        self._send_html(result["html"])

    # History page (dummy)
    def _render_history(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.history import render_history_get

        result = render_history_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        self._send_html(result["html"])

    # Badges page (dummy)
    def _render_badges(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.badges import render_badges_get

        result = render_badges_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        self._send_html(result["html"])

    # ---- Dashboard (GET)
    def _render_dashboard(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.services.permission_context import get_permission_context
        from app.handlers.dashboard import render_dashboard_get
        from app.utils.csrf import generate_csrf_token

        permission_context = get_permission_context(
            user_id=uid,
            session_id=self._get_session_id_from_cookie(),
        )

        result = render_dashboard_get(
            user_id=uid,
            permission_level=permission_context["effective_permission_level"],
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            csrf_token=generate_csrf_token(uid),
        )

        self._send_html(result["html"])

    # ---- Dashboard Cards (GET)
    def _render_dashboard_cards(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.services.permission_context import get_permission_context
        from app.handlers.dashboard import render_dashboard_cards_get
        from app.utils.csrf import generate_csrf_token

        permission_context = get_permission_context(
            user_id=uid,
            session_id=self._get_session_id_from_cookie(),
        )

        result = render_dashboard_cards_get(
            user_id=uid,
            permission_level=permission_context["effective_permission_level"],
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            csrf_token=generate_csrf_token(uid),
        )

        self._send_html(result["html"])

    # ---- Active Trials page (GET)
    def _render_trials_active(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.trials import render_active_trials

        body = render_active_trials(uid)

        html = BASE_TEMPLATE
        html = self._inject_nav(html)
        html = html.replace("__BODY_CLASS__", "trials-page")
        html = html.replace("{{ title }}", "Active Trials")
        html = html.replace("__BODY__", body)

        self._send_html(html)


    # ---- Trials: Past
    def _render_trials_past(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.my_trials import render_past_trials_get

        result = render_past_trials_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        self._send_html(result["html"])

    # ---- Upcoming Trials page (GET)
    def _render_trials_upcoming(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.trials import render_upcoming_trials

        body = render_upcoming_trials(uid)

        html = BASE_TEMPLATE
        html = self._inject_nav(html)
        html = html.replace("__BODY_CLASS__", "trials-page")
        html = html.replace("{{ title }}", "Upcoming Trials")
        html = html.replace("__BODY__", body)

        self._send_html(html)


    def _render_trial_details(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.trials import render_trial_details_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = render_trial_details_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])


    def _render_trial_nda(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.trials import render_trial_nda_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = render_trial_nda_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # ---- Recruiting Trials page (GET)
    def _render_trials_recruiting(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.trials import render_recruiting_trials

        body = render_recruiting_trials(uid)

        html = BASE_TEMPLATE
        html = self._inject_nav(html)
        html = html.replace("__BODY_CLASS__", "trials-page")
        html = html.replace("{{ title }}", "Currently Recruiting Trials")
        html = html.replace("__BODY__", body)

        self._send_html(html)

    # ---- Upcoming Trials interest (GET - render only)
    def _render_trials_interest(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # GET does NOT mutate state
        # simply redirect back

        self.send_response(302)
        self.send_header("Location", "/trials/upcoming")
        self.end_headers()

    # ---- Notifications page (GET)
    def _render_notifications(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.notifications import render_notifications_page

        body = render_notifications_page(uid)

        html = BASE_TEMPLATE
        html = self._inject_nav(html)
        html = html.replace("{{ title }}", "Notifications")
        html = html.replace("__BODY__", body)

        self._send_html(html)


    # ---- Render Notifications page (GET)
    def _render_notification_view(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from urllib.parse import parse_qs, urlparse
        from app.handlers.notifications import render_notification_view

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)
        notification_id = query_params.get("notification_id", [None])[0]

        if not notification_id:
            self.send_response(302)
            self.send_header("Location", "/notifications")
            self.end_headers()
            return

        body = render_notification_view(
            user_id=uid,
            notification_id=notification_id,
        )

        html = BASE_TEMPLATE
        html = self._inject_nav(html)
        html = html.replace("{{ title }}", "Notification")
        html = html.replace("__BODY__", body)

        self._send_html(html)

    # ---- Legal NDA page (GET)
    def _render_legal_nda(self):

        uid = self._get_uid_from_cookie()

        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.legal_documents import render_legal_document_view

        result = render_legal_document_view(
            document_type="nda",
            user_id=uid,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        html = BASE_TEMPLATE
        html = self._inject_nav(html)
        html = html.replace("__BODY__", result["html"])

        self._send_html(html)

    # ---- Legal document viewer (public + gated)
    def _render_legal_document_view(self, path: str):
        uid = self._get_uid_from_cookie()

        from app.handlers.legal_documents import render_legal_document_view

        slug = path.replace("legal/", "", 1)

        SLUG_TO_DOCUMENT_TYPE = {
            "privacy": "privacy_statement",
            "trial-participation": "trial_participation_terms",
            "terms": "terms_of_service",
            "data-handling": "data_handling",
            "accessibility": "accessibility_statement",
        }

        document_type = SLUG_TO_DOCUMENT_TYPE.get(slug)

        if not document_type:
            self._send_404()
            return

        result = render_legal_document_view(
            document_type=document_type,
            user_id=uid,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        html = BASE_TEMPLATE
        html = self._inject_nav(html)
        html = html.replace("__BODY__", result["html"])

        self._send_html(html)

    # ---- Signed legal document viewer (gated)
    def _render_signed_legal_document(self, path: str):

        uid = self._get_uid_from_cookie()

        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.legal_signed import render_signed_legal_document

        slug = path.replace("legal/signed/", "", 1)

        SLUG_TO_DOCUMENT_TYPE = {
            "nda": "nda",
            "trial-participation": "trial_participation_terms",
            "privacy": "privacy_statement",
            "terms": "terms_of_service",
        }

        document_type = SLUG_TO_DOCUMENT_TYPE.get(slug)

        if not document_type:
            self._send_404()
            return

        result = render_signed_legal_document(
            document_type=document_type,
            user_id=uid,
        )

        html = BASE_TEMPLATE
        html = self._inject_nav(html)
        html = html.replace("__BODY__", result["html"])

        self._send_html(html)

    # ---- Legal documents editor index (GET)
    def _render_legal_documents_index(self, doc_id=None):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level not in {30, 70, 100}:
            self._redirect("/dashboard")
            return

        if doc_id is not None and not str(doc_id).isdigit():
            self._redirect("/legal/documents")
            return

        from app.handlers.legal_documents import render_legal_documents_index

        result = render_legal_documents_index(
            user_id=uid,
            doc_id=int(doc_id) if doc_id is not None else None,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        html = BASE_LEGAL
        html = self._inject_nav(html)
        html = html.replace("__BODY__", result["html"])

        self._send_html(html)

    # ---- Legal document download (PDF)

    def _render_legal_download(self, path: str):

        uid = self._get_uid_from_cookie()

        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # Extract document_id
        document_id = path.replace("legal/download/", "", 1)

        if not document_id.isdigit():
            self._send_404()
            return

        result = render_download_document(
            document_id=int(document_id),
            user_id=uid,
        )

        if "error" in result:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(result["error"].encode("utf-8"))
            return

        # Send file or safe error payload with the handler-provided status.
        self.send_response(int(result.get("status", 200)))
        self.send_header("Content-Type", result["content_type"])
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{result["filename"]}"'
        )
        self.end_headers()

        self.wfile.write(result["file_bytes"])

    # ---- User Administration page (GET)
    def _render_admin_users(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level
        permission_level = get_effective_permission_level(uid)

        # Administration is explicitly scoped
        if permission_level not in {70, 100}:
            self.send_response(403)
            self.end_headers()
            return

        from app.handlers.users import render_admin_users_get

        base_html = BASE_TEMPLATE

        result = render_admin_users_get(
            actor_uid=uid,
            base_template=base_html,
            inject_nav=self._inject_nav,
        )

        self._send_html(result["html"])

    # -------------------------
    # Bonus Surveys (stub)
    # -------------------------
    def _render_bonus_surveys(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level not in {40, 70, 100}:
            self._redirect("/dashboard")
            return

        from app.handlers.surveys import render_bonus_surveys_get

        result = render_bonus_surveys_get(
            user_id=uid,
            base_template=BONUS_BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        self._send_html(result["html"])

    # -------------------------
    # Bonus Surveys Create (stub)
    # -------------------------

    def _render_bonus_survey_create(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level not in {40, 70, 100}:
            self._redirect("/dashboard")
            return

        from app.handlers.surveys import render_bonus_survey_create_get

        from urllib.parse import parse_qs, urlparse

        query_params = parse_qs(
            urlparse(self.path).query
        )

        result = render_bonus_survey_create_get(
            user_id=uid,
            base_template=BONUS_BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        # ---- handle redirect explicitly ----
        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        # ---- enforce render contract ----
        if "html" not in result:
            raise RuntimeError(
                "render_bonus_survey_create_get did not return html or redirect"
            )

        self._send_html(result["html"])

    # -------------------------
    # Bonus Surveys Template (stub)
    # -------------------------

    def _render_bonus_survey_template(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level not in {40, 70, 100}:
            self._redirect("/dashboard")
            return

        # ---- parse query params (same pattern as other GET handlers) ----
        from urllib.parse import urlparse, parse_qs
        query_params = parse_qs(urlparse(self.path).query)

        from app.handlers.surveys import render_bonus_survey_template_get

        result = render_bonus_survey_template_get(
            user_id=uid,
            base_template=BONUS_BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])


    # -------------------------
    # Bonus Surveys Targeting (GET)
    # -------------------------

    def _render_bonus_survey_targeting(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level not in {40, 70, 100}:
            self._redirect("/dashboard")
            return

        from app.handlers.surveys import render_bonus_survey_targeting_get
        from urllib.parse import parse_qs, urlparse

        query_params = parse_qs(urlparse(self.path).query)

        result = render_bonus_survey_targeting_get(
            user_id=uid,
            base_template=BONUS_BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # -------------------------
    # Bonus Survey Review (GET)
    # -------------------------
    def _render_bonus_survey_review(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level not in {40, 70, 100}:
            self._redirect("/dashboard")
            return

        from urllib.parse import parse_qs, urlparse
        from app.handlers.surveys import render_bonus_survey_review_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = render_bonus_survey_review_get(
            user_id=uid,
            base_template=BONUS_BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # -------------------------
    # Bonus Survey Submitted (GET)
    # -------------------------
    def _render_bonus_survey_submitted(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level not in {40, 70, 100}:
            self._redirect("/dashboard")
            return

        from urllib.parse import parse_qs, urlparse
        from app.handlers.surveys import render_bonus_survey_submitted_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = render_bonus_survey_submitted_get(
            user_id=uid,
            base_template=BONUS_BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # -------------------------
    # Bonus Survey Pending View (GET)
    # -------------------------
    def _render_bonus_survey_pending_view(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level not in {40, 70, 100}:
            self._redirect("/dashboard")
            return

        from urllib.parse import parse_qs, urlparse
        from app.handlers.surveys import render_bonus_survey_pending_view_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = render_bonus_survey_pending_view_get(
            user_id=uid,
            base_template=BONUS_BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # -------------------------
    # Bonus Survey Upload View (GET)
    # -------------------------
    def _render_bonus_survey_upload(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level not in {40, 70, 100}:
            self._redirect("/dashboard")
            return

        from urllib.parse import parse_qs, urlparse
        from app.handlers.surveys import render_bonus_survey_upload_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = render_bonus_survey_upload_get(
            user_id=uid,
            base_template=BONUS_BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # -------------------------
    # Admin Approval (GET)
    # -------------------------

    def _render_admin_approvals(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from app.handlers.admin import render_admin_approvals_get

        result = render_admin_approvals_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # -------------------------
    # Admin Approval View (GET)
    # -------------------------

    def _render_admin_approval_view(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.admin import render_admin_approval_view_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = render_admin_approval_view_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    def _render_admin_approval_project(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from urllib.parse import urlparse, parse_qs
        query_params = parse_qs(urlparse(self.path).query)

        project_id = query_params.get("project_id", [None])[0]
        if not project_id:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing project_id")
            return

        from app.handlers.admin_approvals import render_admin_approval_project_get

        # 👇 IMPORTANT: handler returns BODY only
        result = render_admin_approval_project_get(
            user_id=uid,
            project_id=project_id,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        if "html" not in result:
            raise RuntimeError(
                "render_admin_approval_project_get did not return html or redirect"
            )

        # 👇 CONSISTENT WITH YOUR SYSTEM
        html = BASE_TEMPLATE
        html = self._inject_nav(html)
        html = html.replace("__BODY_CLASS__", "admin-page")
        html = html.replace("{{ title }}", "Project Approval")
        html = html.replace("__BODY__", result["html"])

        self._send_html(html)

    def _render_bonus_survey_active(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level not in {40, 70, 100}:
            self._redirect("/dashboard")
            return

        from urllib.parse import urlparse, parse_qs
        query_params = parse_qs(urlparse(self.path).query)

        from app.handlers.surveys import render_bonus_survey_active_get

        result = render_bonus_survey_active_get(
            user_id=uid,
            base_template=BONUS_BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        if "html" not in result:
            raise RuntimeError(
                "render_bonus_survey_active_get did not return html or redirect"
            )

        self._send_html(result["html"])

    def _render_bonus_survey_archived(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level not in {40, 70, 100}:
            self._redirect("/dashboard")
            return

        from urllib.parse import urlparse, parse_qs
        query_params = parse_qs(urlparse(self.path).query)

        from app.handlers.surveys import render_bonus_survey_archived_get

        result = render_bonus_survey_archived_get(
            user_id=uid,
            base_template=BONUS_BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        if "html" not in result:
            raise RuntimeError(
                "render_bonus_survey_archived_get did not return html or redirect"
            )

        self._send_html(result["html"])

    def _render_bonus_survey_take(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.surveys import render_bonus_survey_take_get

        result = render_bonus_survey_take_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(result["html"].encode("utf-8"))


    def _render_bonus_survey_take_open(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        body = """
        <h2>Open Bonus Survey</h2>
        <p>
            Bonus survey links must be opened from the Available Bonus Surveys page.
        </p>
        <p>
            <a href="/surveys/bonus/take">Back to Available Bonus Surveys</a>
        </p>
        """

        html = self._inject_nav(BASE_TEMPLATE)
        html = html.replace("{{ title }}", "Bonus Surveys")
        html = html.replace("__BODY__", body)

        self._send_html(html)



    # -------------------------
    # UT Surveys (stub)
    # -------------------------
    def _render_ut_surveys(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from app.handlers.surveys import render_ut_surveys_get

        result = render_ut_surveys_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        self._send_html(result["html"])


    # -------------------------
    # Recruitment Surveys (stub)
    # -------------------------
    def _render_recruitment_surveys(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from app.handlers.surveys import render_recruitment_surveys_get

        result = render_recruitment_surveys_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        self._send_html(result["html"])


    # -------------------------
    # Product Team – Request Trial (GET)
    # -------------------------
    def _render_product_request_trial(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        from app.handlers.product_team import render_product_request_trial_get
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = render_product_request_trial_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # -------------------------
    # Product Team – My Past Trials (GET)
    # -------------------------
    def _render_product_past_trials(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        from urllib.parse import parse_qs, urlparse
        from app.handlers.product_team import render_product_past_trials_get

        query_params = parse_qs(urlparse(self.path).query)

        result = render_product_past_trials_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # -------------------------
    # Product Team – Reports and Summaries (GET)
    # -------------------------

    def _render_product_reports(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        from app.handlers.product_team import render_product_reports_get

        result = render_product_reports_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        self._send_html(result["html"])


    # -------------------------
    # Reporting & Insights (GET)
    # -------------------------
    def _render_reporting_insights(self, active_view="projects"):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        from app.handlers.reporting_insights import render_reporting_insights_get

        result = render_reporting_insights_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            active_view=active_view,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])


    # -------------------------
    # Product Team – Comparisons / Benchmarks (GET)
    # -------------------------
    def _render_product_comparisons(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        from app.handlers.product_team import render_product_comparisons_get

        result = render_product_comparisons_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # -------------------------
    # Product Team – Request Wizard (GET)
    # -------------------------

    def _render_product_request_trial_wizard_basics(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        project_id = self._get_query_param("project_id")
        if not project_id:
            self._redirect("/product/request-trial?error=missing_project_id")
            return

        from app.handlers.product_team import (
            render_product_request_trial_wizard_basics_get,
        )

        result = render_product_request_trial_wizard_basics_get(
            user_id=uid,
            project_id=project_id,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])


    def _render_product_request_trial_wizard_timing(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        project_id = self._get_query_param("project_id")
        if not project_id:
            self._redirect("/product/request-trial?error=missing_project_id")
            return

        from app.handlers.product_team import (
            render_product_request_trial_wizard_timing_get,
        )

        result = render_product_request_trial_wizard_timing_get(
            user_id=uid,
            project_id=project_id,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])


    def _render_product_request_trial_wizard_stakeholders(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        project_id = self._get_query_param("project_id")
        if not project_id:
            self._redirect("/product/request-trial?error=missing_project_id")
            return

        from app.handlers.product_team import (
            render_product_request_trial_wizard_stakeholders_get,
        )

        result = render_product_request_trial_wizard_stakeholders_get(
            user_id=uid,
            project_id=project_id,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])


    def _render_product_request_trial_wizard_review(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        project_id = self._get_query_param("project_id")
        if not project_id:
            self._redirect("/product/request-trial?error=missing_project_id")
            return

        from app.handlers.product_team import (
            render_product_request_trial_wizard_review_get,
        )

        result = render_product_request_trial_wizard_review_get(
            user_id=uid,
            project_id=project_id,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])



    # -------------------------
    # Product Team – Trial pending approval (GET)
    # -------------------------

    def _render_product_request_trial_pending(self):
        """
        GET /product/request-trial/pending
        Simple read-only page after submission, before UT review.
        Uses standard product_team render flow so nav + user anchor inject properly.
        """
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        from app.handlers.product_team import render_product_request_trial_pending_get

        project_id = self._get_query_param("project_id")

        result = render_product_request_trial_pending_get(
            user_id=uid,
            project_id=project_id,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )


        if "redirect" in result:
            self._redirect(result["redirect"])
            return

        self._send_html(result["html"])

    # -------------------------
    # Product Team – Trial info requested (GET)
    # -------------------------

    def _render_product_request_trial_info_requested(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        from app.handlers.product_team import (
            render_product_request_trial_info_requested_get,
        )

        project_id = self._get_query_param("project_id")

        result = render_product_request_trial_info_requested_get(
            user_id=uid,
            project_id=project_id,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return


        self._send_html(result["html"])

    # -------------------------
    # Product Team – Trial change requested (GET)
    # -------------------------

    def _render_product_request_trial_change_requested(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        from app.handlers.product_team import (
            render_product_request_trial_change_requested_get,
        )

        project_id = self._get_query_param("project_id")

        result = render_product_request_trial_change_requested_get(
            user_id=uid,
            project_id=project_id,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return


        self._send_html(result["html"])

    def _render_product_current_trials(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.product_team import (
            render_product_current_trials_get,
        )

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = render_product_current_trials_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # -------------------------
    # UT Lead – All Trials Overview (GET)
    # -------------------------
    def _render_ut_lead_trials(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        from app.handlers.user_trial_lead import render_ut_lead_trials_get

        result = render_ut_lead_trials_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,   # ADD HERE
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    def _render_ut_lead_project(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.user_trial_lead_project import (
            render_ut_lead_project_get,
        )

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = render_ut_lead_project_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    def _render_user_selection(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.user_selection import render_user_selection_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = render_user_selection_get(
            user_id=uid,
            base_template=SELECTION_BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    def _render_user_selection_confirm(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.user_selection import handle_user_selection_confirm_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = handle_user_selection_confirm_get(
            user_id=uid,
            query_params=query_params,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        if "html" in result:
            self._send_html(result["html"])
            return

        # Fallback safety (should not happen)
        self._redirect("/trials/selection")

    def _render_survey_upload(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from app.handlers.survey_upload import render_survey_upload_get

        result = render_survey_upload_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        self._send_html(result["html"])

    # -------------------------
    # Active Trials
    # -------------------------

    def _render_responsibilities(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.responsibilities import render_responsibilities_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = render_responsibilities_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # -------------------------
    # Profile Levels API (GET)
    # -------------------------
    # -------------------------
    # Profile Levels API (GET)
    # -------------------------
    def _render_api_profile_levels(self):

        from urllib.parse import parse_qs, urlparse
        import json

        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps([]).encode("utf-8"))
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps([]).encode("utf-8"))
            return

        from app.handlers.api_profile_levels import handle_api_profile_levels

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = handle_api_profile_levels(query_params)

        # Default empty response
        payload = result.get("json", [])

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        self.wfile.write(json.dumps(payload).encode("utf-8"))

    # -------------------------
    # Bonus Survey Structure (GET)
    # -------------------------

    def _render_bonus_survey_structure(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level not in {40, 70, 100}:
            self._redirect("/dashboard")
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.bonus_survey_structure import render_bonus_survey_structure_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        bonus_survey_id = int(query_params.get("survey_id", [0])[0])

        if not bonus_survey_id:
            self.send_response(302)
            self.send_header("Location", "/surveys/bonus")
            self.end_headers()
            return

        result = render_bonus_survey_structure_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            bonus_survey_id=bonus_survey_id,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # ---- Historical Upload
    def _render_historical_context(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from urllib.parse import urlparse, parse_qs
        from app.db.user_roles import get_effective_permission_level
        from app.handlers.historical import render_historical_context_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        try:
            context_id = int(query_params.get("context_id", [0])[0])
        except (TypeError, ValueError):
            context_id = 0

        if not context_id:
            self.send_response(302)
            self.send_header("Location", "/historical")
            self.end_headers()
            return

        permission_level = get_effective_permission_level(uid)
        can_manage_report = permission_level >= 70

        if permission_level < 50:
            self._redirect("/dashboard")
            return

        if not can_manage_report:
            from app.db.historical import historical_context_is_visible_to_reporting_insights

            if not historical_context_is_visible_to_reporting_insights(context_id):
                self._redirect("/dashboard")
                return

        result = render_historical_context_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            context_id=context_id,
            query_params=query_params,
            can_manage_report=can_manage_report,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    def _render_historical_aggregate_report(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from urllib.parse import urlparse, parse_qs
        from app.db.user_roles import get_effective_permission_level
        from app.handlers.historical import render_historical_aggregate_report_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        try:
            product_id = int(query_params.get("product_id", [0])[0])
            round_number = int(query_params.get("round_number", [0])[0])
        except (TypeError, ValueError):
            product_id = 0
            round_number = 0

        if not product_id or not round_number:
            self._redirect("/historical")
            return

        permission_level = get_effective_permission_level(uid)
        can_manage_report = permission_level >= 70

        if permission_level < 50:
            self._redirect("/dashboard")
            return

        if not can_manage_report:
            from app.db.historical_aggregate_reports import historical_aggregate_report_is_visible_to_reporting_insights

            if not historical_aggregate_report_is_visible_to_reporting_insights(
                product_id=product_id,
                round_number=round_number,
            ):
                self._redirect("/dashboard")
                return

        result = render_historical_aggregate_report_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            product_id=product_id,
            round_number=round_number,
            query_params=query_params,
            can_manage_report=can_manage_report,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    def _render_historical_comparison(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.historical import render_historical_comparison_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        try:
            context_id = int(query_params.get("context_id", [0])[0])
        except (TypeError, ValueError):
            context_id = 0

        if not context_id:
            self.send_response(302)
            self.send_header("Location", "/historical")
            self.end_headers()
            return

        result = render_historical_comparison_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            context_id=context_id,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    def _render_historical_landing(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from app.handlers.historical import render_historical_landing_get

        result = render_historical_landing_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])


    def _render_historical_product_lifecycle(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.historical import render_historical_product_lifecycle_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        try:
            product_id = int(query_params.get("product_id", [0])[0])
        except (TypeError, ValueError):
            product_id = 0

        if not product_id:
            self.send_response(302)
            self.send_header("Location", "/historical")
            self.end_headers()
            return

        can_manage_publication = permission_level >= 70

        if not can_manage_publication:
            from app.db.historical import get_historical_product_publication

            publication = get_historical_product_publication(product_id)
            is_published = (publication or {}).get("status") == "published"
            is_visible = (
                bool((publication or {}).get("visible_to_product_team"))
                or bool((publication or {}).get("visible_to_reporting_insights"))
            )

            if not is_published or not is_visible:
                self._redirect("/dashboard")
                return

        result = render_historical_product_lifecycle_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            product_id=product_id,
            query_params=query_params,
            can_manage_publication=can_manage_publication,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])


    def _render_historical_product_taxonomy(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from app.handlers.historical import render_historical_product_taxonomy_get

        result = render_historical_product_taxonomy_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    def _render_historical_create_context(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from app.handlers.historical import render_historical_create_context_get

        result = render_historical_create_context_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    def _render_create_product(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from app.handlers.products import render_create_product_get

        result = render_create_product_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

        if "redirect" in result:
            self._redirect(result["redirect"])
            return

        self._send_html(result["html"])

    def _render_historical_upload(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.historical import render_historical_upload_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        context_id = query_params.get("context_id", [None])[0]

        if not context_id:
            self._redirect("/historical")
            return

        try:
            context_id = int(context_id)
        except:
            self._redirect("/historical")
            return

        result = render_historical_upload_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            context_id=context_id,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    def _render_historical_raw(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        permission_level = self._get_display_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.historical import render_historical_raw_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        context_id = query_params.get("context_id", [None])[0]
        dataset_id = query_params.get("dataset_id", [None])[0]

        if not context_id or not dataset_id:
            self.send_response(302)
            self.send_header("Location", "/historical")
            self.end_headers()
            return

        try:
            context_id = int(context_id)
            dataset_id = int(dataset_id)
        except:
            self.send_response(302)
            self.send_header("Location", "/historical")
            self.end_headers()
            return

        result = render_historical_raw_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
            dataset_id=dataset_id,
            context_id=context_id,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # -------------------------
    # Guest Pages (stub)
    # -------------------------
    def _render_guest_content(self, path: str):
        from app.db.content_pages import get_page_by_slug

        # Normalize path → slug
        slug = path.lstrip("/")

        page = get_page_by_slug(slug)

        if not page:
            self._send_404()
            return

        body = self._render_content_page(page)
        
        if slug == "contact-us":
            from app.utils.csrf import generate_csrf_token

            contact_csrf_token = generate_csrf_token("public_contact")
            contact_form_html = CONTACT_FORM_HTML.replace(
                "__CSRF_TOKEN__",
                e(contact_csrf_token),
            )

            body = body.replace(
                "{{CONTACT_FORM}}",
                contact_form_html
            )

        html = BASE_TEMPLATE
        html = self._inject_nav(html)
        html = html.replace("__BODY__", body)

        self._send_html(html)

    # -------------------------
    # POST parsing helper
    # -------------------------
    class UploadedFile:
        def __init__(self, filename, content):
            from io import BytesIO
            self.filename = filename
            self.file = BytesIO(content)


    def parse_post_data(self):
        content_length = int(self.headers.get("Content-Length", 0))
        content_type = self.headers.get("Content-Type", "")

        body = self.rfile.read(content_length)

        if "boundary=" not in content_type:
            return {}

        boundary = content_type.split("boundary=")[-1].encode()
        parts = body.split(b"--" + boundary)

        parsed = {}

        for part in parts:
            if not part or part == b"--\r\n":
                continue

            headers, _, value = part.partition(b"\r\n\r\n")
            headers_str = headers.decode(errors="ignore")

            name = None
            if 'name="' in headers_str:
                name = headers_str.split('name="')[1].split('"')[0]

            if not name:
                continue

            if 'filename="' in headers_str:
                filename = headers_str.split('filename="')[1].split('"')[0]

                parsed[name] = self.UploadedFile(
                    filename=filename,
                    content=value.rstrip(b"\r\n")
                )
            else:
                parsed[name] = value.decode(errors="ignore").strip()

        return parsed

    # -------------------------
    # POST requests
    # -------------------------
    def do_POST(self):
        from urllib.parse import urlparse

        if self._reject_oversized_post_if_needed():
            return

        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/register":
            self.handle_register_post()
            return
        if path == "/verify-email":
            self.handle_verify_email_post()
            return
        if path == "/demographics":
            self.handle_demographics_post()
            return
        if path == "/login":
            self.handle_login_post()
            return
        if path == "/logout":
            self.handle_logout_post()
            return
        if path == "/admin/view-mode/set":
            self._handle_admin_view_mode_set_post()
            return
        if path == "/admin/view-mode/clear":
            self._handle_admin_view_mode_clear_post()
            return
        if path == "/nda":
            self.handle_nda_post()
            return
        if path == "/participation-guidelines":
            self.handle_guidelines_post()
            return
        if path == "/profile/interests":
            self.handle_profile_interests_post()
            return
        if path == "/profile/basic":
            self.handle_profile_basic_post()
            return
        if path == "/profile/advanced":
            self.handle_profile_advanced_post()
            return  
        if path == "/welcome":
            self.handle_welcome_post()
            return
        if path == "/settings":
            self.handle_settings_page_post()
            return
        if path == "/settings/password/change":
            self.handle_settings_password_change_post()
            return
        if path == "/settings/demographics/save":
            self.handle_settings_demographics_save_post()
            return
        if path == "/admin/users/update-permission":
            self.handle_update_user_permission_post()
            return
        if path == "/contact-us":
            self.handle_contact_us_post()
            return
        if path == "/legal/documents/save":
            self.handle_legal_document_save_post()
            return
        if path == "/legal/documents/publish":
            self.handle_legal_document_publish_post()
            return
        if path == "/surveys/bonus/create/save-basics":
            self.handle_bonus_survey_basics_save_post()
            return
        if path == "/surveys/bonus/create/new":
            self.handle_bonus_survey_create_new_post()
            return
        if path == "/surveys/bonus/create/delete":
            self.handle_bonus_survey_draft_delete_post()
            return
        if path == "/surveys/bonus/create/save-template":
            self.handle_bonus_survey_template_save_post()
            return
        if path == "/surveys/bonus/create/save-targeting":
            self.handle_bonus_survey_targeting_save_post()
            return
        if path == "/surveys/bonus/take/open":
            self.handle_bonus_survey_take_open_post()
            return

        # -----------------------------
        # Bonus Survey actions (POST)
        # -----------------------------
        #
        # Approval decisions must go through:
        # - /admin/approvals/submit
        #
        # Do not reintroduce direct bonus approval mutation routes here.
        # They bypass approval_actions, notification creation, and the
        # centralized bonus_survey_tracker state flow.
        # -----------------------------

        if path == "/surveys/bonus/create/submit":
            self.handle_bonus_survey_submit_post()
            return
        if path == "/surveys/bonus/upload":
            self.handle_bonus_survey_upload_post()
            return
        if path == "/surveys/bonus/analyze":
            self.handle_bonus_survey_analyze_post()
            return
        if path == "/surveys/bonus/close":
            self.handle_bonus_survey_close_post()
            return
        if path == "/surveys/bonus/generate-sections":
            self.handle_bonus_survey_generate_sections_post()
            return
        
        # -----------------------------
        # Product Team Request Trial (POST)
        # -----------------------------

        if path == "/product/request-trial/create":
            self.handle_request_trial_create_post()
            return
        if path == "/product/request-trial/wizard/basics":
            self.handle_product_request_trial_wizard_basics_post()
            return
        if path == "/product/request-trial/wizard/timing":
            self.handle_product_request_trial_wizard_timing_post()
            return
        if path == "/product/request-trial/wizard/stakeholders":
            self.handle_product_request_trial_wizard_stakeholders_post()
            return
        if path == "/product/request-trial/cancel":
            self.handle_product_request_trial_cancel_post()
            return
        if path == "/product/request-trial/submit":
            self.handle_product_request_trial_submit_post()
            return
        if path == "/admin/approvals/submit":
            self.handle_admin_approval_post()
            return
        if path == "/admin/approvals/bonus/submit":
            self.handle_admin_approval_post()
            return
        if path == "/product/request-trial/info-requested/respond":
            self.handle_product_request_trial_info_requested_respond_post()
            return
        if path == "/product/request-trial/change-requested/respond":
            self.handle_product_request_trial_change_requested_respond_post()
            return
        if path == "/admin/approval":
            self.handle_admin_approval_post()
            return

        # -----------------------------
        # UT Lead (POST)
        # -----------------------------

        if path == "/ut-lead/project":
            self.handle_ut_lead_project_post()
            return

        if path == "/trials/selection":
            self.handle_user_selection_post()
            return
        
        if path == "/survey/upload":
            self.handle_survey_upload_post()
            return
        
        # -----------------------------
        # User Application to UT (POST)
        # -----------------------------

        if path == "/trials/apply":
            self.handle_trial_apply_post()
            return

        if path == "/trials/withdraw":
            self.handle_trial_withdraw_post()
            return
        
        if path == "/trials/end-recruiting":
            self.handle_end_recruiting_post()
            return
        
        if path == "/trials/nda":
            self.handle_trial_nda_post()
            return
        
        # -----------------------------
        # User project round onboarding (POST)
        # -----------------------------

        if path == "/trials/confirm-shipping":
            self.handle_confirm_shipping_post()
            return
        if path == "/trials/responsibilities":
            self.handle_responsibilities_post()
            return
        if path == "/trials/save-shipping":
            self.handle_save_shipping_post()
            return
        if path == "/trials/device-received":
            self._handle_device_received_post()
            return
        if path == "/trials/device-not-received":
            self._handle_device_not_received_post()
            return
        if path == "/trials/open-survey":
            self.handle_trial_survey_open_post()
            return

        # -----------------------------
        # Dashboard Cards (POST)
        # -----------------------------

        if path == "/dashboard/cards/hide":
            self._handle_dashboard_card_hide_post()
            return
        if path == "/dashboard/cards/show":
            self._handle_dashboard_card_show_post()
            return

        # -----------------------------
        # Notifications (POST)
        # -----------------------------

        if path == "/notifications/open":
            self.handle_notification_open_post()
            return
        if path == "/notifications/view":
            self.handle_notification_view_post()
            return
        if path == "/notifications/dismiss":
            self.handle_notification_dismiss_post()
            return
        if path == "/notifications/mark-read":
            self.handle_notifications_mark_read_post()
            return
        
        # -----------------------------
        # Trials interest (POST)
        # -----------------------------
        if path == "/trials/interest":
            self.handle_trials_interest_post()
            return

        if path == "/trials/interest/stop":
            self.handle_trials_interest_stop_post()
            return
        
        # -----------------------------
        # Trial Selection Init / Confirm (POST)
        # -----------------------------
        if path == "/trials/selection/init":
            self.handle_selection_init_post()
            return

        if path == "/trials/selection/confirm":
            self.handle_selection_confirm_post()
            return
        
        # -----------------------------
        # Bonus Survey Structure (POST)
        # -----------------------------        
        
        if path == "/surveys/bonus/structure/generate":
            self.handle_bonus_survey_structure_generate_post()
            return
       
        if path == "/surveys/bonus/structure/reset":
            self.handle_bonus_survey_structure_reset_post()
            return
        
        if path == "/surveys/bonus/structure/classify-profile":
            self.handle_bonus_survey_structure_classify_profile_post()
            return

        if path == "/surveys/bonus/structure/save":
            self.handle_bonus_survey_structure_save_post()
            return
        
        if path == "/surveys/bonus/section/add":
            self.handle_bonus_survey_section_add_post()
            return

        if path == "/surveys/bonus/section/rename":
            self.handle_bonus_survey_section_rename_post()
            return

        if path == "/surveys/bonus/section/delete":
            self.handle_bonus_survey_section_delete_post()
            return

        # ---- Historical Upload
        if path == "/historical/upload":
            self.handle_historical_upload_post()
            return
        # ---- Historical Create Context
        if path == "/historical/create-context":
            self.handle_historical_create_context_post()
            return
        # ---- Historical Product Publish
        if path == "/historical/product/publish":
            self.handle_historical_product_publish_post()
            return
        # ---- Historical Aggregate Report Generate
        if path == "/historical/aggregate-report/generate":
            self.handle_historical_aggregate_report_generate_post()
            return
        # ---- Historical Aggregate Report Generate AI
        if path == "/historical/aggregate-report/generate-ai":
            self.handle_historical_aggregate_report_generate_ai_post()
            return
        # ---- Historical Aggregate Report Publish
        if path == "/historical/aggregate-report/publish":
            self.handle_historical_aggregate_report_publish_post()
            return
        # ---- Historical Product Access
        if path == "/historical/product/access":
            self.handle_historical_product_access_post()
            return
        if path == "/products/create":
            self.handle_create_product_post()
            return
        # ---- Historical Generate Section Names
        if path == "/historical/generate-section-names":
            self.handle_generate_section_names_post()
            return
        # ---- Historical Generate Section Summaries
        if path == "/historical/generate-section-summaries":
            self.handle_generate_section_summaries_post()
            return
        # ---- Historical Generate Insights
        if path == "/historical/generate-insights":
            self.handle_generate_insights_post()
            return
        
        # -----------------------------
        # No path exists (POST)
        # -----------------------------

        self._send_404()

    # -------------------------
    # Register handler
    # -------------------------
    def handle_register_post(self):
        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._render_register_error("Invalid request. Please try again.")
            return

        data = post_body["form"]

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token("public_register", csrf_token):
            self._render_register_error("Invalid form token. Please try again.")
            return

        from app.handlers.auth import handle_register_post

        result = handle_register_post(data)

        if "error" in result:
            self._render_register_error(result["error"], result.get("email", ""))
            return

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()


    # -------------------------
    # Verify handler
    # -------------------------

    def handle_verify_email_post(self):
        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/verify-email?error=invalid_request")
            return

        data = post_body["form"]

        token = data.get("token", [None])[0]

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        csrf_user_key = f"verify_email:{token}" if token else "verify_email:missing"
        if not csrf_token or not validate_csrf_token(csrf_user_key, csrf_token):
            target = f"/verify-email?token={urllib.parse.quote(token)}&error=invalid_csrf" if token else "/verify-email?error=invalid_csrf"
            self._redirect(target)
            return

        from app.handlers.auth import handle_verify_email_post

        result = handle_verify_email_post(token)

        if "error" in result:
            error_message = result.get("error") or "Verification failed."
            if "missing" in error_message.lower():
                error_key = "missing_token"
            elif "expired" in error_message.lower() or "invalid" in error_message.lower():
                error_key = "invalid_or_expired_token"
            else:
                error_key = "verification_failed"

            if token:
                target = f"/verify-email?token={urllib.parse.quote(token)}&error={error_key}"
            else:
                target = f"/verify-email?error={error_key}"

            self._redirect(target)
            return

        user = result["user"]
        from app.services.session_service import create_session
        session_id = create_session(user["user_id"])

        # ---- set session cookie immediately after verification ----
        c = cookies.SimpleCookie()
        c["session_id"] = session_id
        c["session_id"]["path"] = "/"
        c["session_id"]["httponly"] = True
        c["session_id"]["samesite"] = "Lax"
        if SESSION_COOKIE_SECURE:
            c["session_id"]["secure"] = True

        # ---- determine next onboarding step ----
        onboarding_state = get_onboarding_state(user)

        self.send_response(302)
        self.send_header("Set-Cookie", c["session_id"].OutputString())

        if onboarding_state == "demographics":
            self.send_header("Location", "/demographics")
        elif onboarding_state == "nda":
            self.send_header("Location", "/nda")
        elif onboarding_state == "participation_guidelines":
            self.send_header("Location", "/participation-guidelines")
        elif onboarding_state == "welcome":
            self.send_header("Location", "/welcome")
        elif onboarding_state == "ready":
            self.send_header("Location", "/dashboard")
        else:
            self.send_header("Location", "/demographics")

        self.end_headers()

    # -------------------------
    # Login handler
    # -------------------------

    def handle_login_post(self):
        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._render_login_error("Invalid request. Please try again.")
            return

        data = post_body["form"]

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token("public_login", csrf_token):
            self._render_login_error("Invalid form token. Please try again.")
            return

        from app.handlers.auth import handle_login_post

        # ----------------------------------------
        # Client IP for login throttling
        # ----------------------------------------

        ip = self._client_ip_from_trusted_proxy()

        result = handle_login_post(data, ip)

        if "error" in result:
            debug("Login failed", result.get("error", "unknown_error"))
            self._render_login_error(result["error"])
            return

        user = result["user"]
        onboarding_state = result["onboarding_state"]
        from app.services.session_service import create_session
        session_id = create_session(user["user_id"])

        # ---- set session cookie ----
        c = cookies.SimpleCookie()
        c["session_id"] = session_id
        c["session_id"]["path"] = "/"
        c["session_id"]["httponly"] = True
        c["session_id"]["samesite"] = "Lax"
        if SESSION_COOKIE_SECURE:
            c["session_id"]["secure"] = True

        self.send_response(302)
        self.send_header("Set-Cookie", c["session_id"].OutputString())

        # ---- route based on onboarding state ----
        if onboarding_state == "demographics":
            self.send_header("Location", "/demographics")
        elif onboarding_state == "nda":
            self.send_header("Location", "/nda")
        elif onboarding_state == "email_verification":
            self.send_header("Location", "/verify-email")
        elif onboarding_state == "welcome":
            self.send_header("Location", "/welcome")
        elif onboarding_state == "ready":
            self.send_header("Location", "/dashboard")
        else:
            self.send_header("Location", "/login")

        self.end_headers()



    # -------------------------
    # Logout handler (POST)
    # -------------------------

    def handle_logout_post(self):
        from app.services.session_service import delete_session

        raw = self.headers.get("Cookie")
        session_id = None
        if raw:
            parsed = cookies.SimpleCookie()
            parsed.load(raw)
            morsel = parsed.get("session_id")
            if morsel:
                session_id = morsel.value.strip() or None

        uid = self._get_uid_from_cookie()
        if uid:
            data = self._parse_post_data()
            if self._redirect_on_parse_error(
                data=data,
                redirect_path="/dashboard",
            ):
                return

            from app.utils.csrf import validate_csrf_token

            csrf_token = data.get("csrf_token")
            if not csrf_token or not validate_csrf_token(uid, csrf_token):
                self._redirect("/dashboard?error=invalid_csrf")
                return

        if session_id is not None:
            delete_session(session_id)

        c = cookies.SimpleCookie()
        c["session_id"] = ""
        c["session_id"]["path"] = "/"
        c["session_id"]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        c["session_id"]["max-age"] = 0
        c["session_id"]["httponly"] = True
        c["session_id"]["samesite"] = "Lax"
        if SESSION_COOKIE_SECURE:
            c["session_id"]["secure"] = True

        self.send_response(302)
        self.send_header("Set-Cookie", c["session_id"].OutputString())
        self.send_header("Location", "/login")
        self.end_headers()

    # -------------------------
    # Admin view handlers (POST)
    # -------------------------

    def _handle_admin_view_mode_set_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(data=data, redirect_path="/dashboard"):
            return

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            self._redirect("/dashboard?error=invalid_csrf")
            return

        session_id = self._get_session_id_from_cookie()

        from app.services.permission_context import set_admin_view_mode_for_session

        result = set_admin_view_mode_for_session(
            user_id=uid,
            session_id=session_id,
            view_as_permission_level=data.get("view_as_permission_level"),
        )

        if not result.get("ok"):
            self._redirect("/dashboard?error=invalid_view_mode")
            return

        self._redirect("/dashboard")

    def _handle_admin_view_mode_clear_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(data=data, redirect_path="/dashboard"):
            return

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            self._redirect("/dashboard?error=invalid_csrf")
            return

        session_id = self._get_session_id_from_cookie()

        from app.services.permission_context import clear_admin_view_mode_for_session

        result = clear_admin_view_mode_for_session(
            user_id=uid,
            session_id=session_id,
        )

        if not result.get("ok"):
            self._redirect("/dashboard?error=invalid_view_mode")
            return

        self._redirect("/dashboard")


    # -------------------------
    # Dashboard card handlers (POST)
    # -------------------------

    def _handle_dashboard_card_hide_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(data=data, redirect_path="/dashboard"):
            return

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            self._redirect("/dashboard?error=invalid_csrf")
            return

        from app.services.permission_context import get_permission_context
        from app.handlers.dashboard import handle_dashboard_card_hide_post

        permission_context = get_permission_context(
            user_id=uid,
            session_id=self._get_session_id_from_cookie(),
        )

        result = handle_dashboard_card_hide_post(
            user_id=uid,
            permission_level=permission_context["effective_permission_level"],
            form=data,
        )
        if not result.get("ok"):
            self._redirect("/dashboard?error=invalid_dashboard_card")
            return

        self._redirect("/dashboard")

    def _handle_dashboard_card_show_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(data=data, redirect_path="/dashboard/cards"):
            return

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            self._redirect("/dashboard/cards?error=invalid_csrf")
            return

        from app.services.permission_context import get_permission_context
        from app.handlers.dashboard import handle_dashboard_card_show_post

        permission_context = get_permission_context(
            user_id=uid,
            session_id=self._get_session_id_from_cookie(),
        )

        result = handle_dashboard_card_show_post(
            user_id=uid,
            permission_level=permission_context["effective_permission_level"],
            form=data,
        )
        if not result.get("ok"):
            self._redirect("/dashboard/cards?error=invalid_dashboard_card")
            return

        self._redirect("/dashboard")

    # -------------------------
    # Demographics handler (POST)
    # -------------------------

    def handle_demographics_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/demographics?error=invalid_request")
            return

        data = post_body["form"]

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/demographics?error=invalid_csrf")
            return

        from app.handlers.onboarding import handle_demographics_post
        import urllib.parse

        result = handle_demographics_post(uid, data)

        if "error" in result:
            encoded = urllib.parse.quote(result["error"])
            self.send_response(302)
            self.send_header("Location", f"/demographics?error={encoded}")
            self.end_headers()
            return

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()


    # -------------------------
    # Participation Guidelines handler
    # -------------------------
    def handle_guidelines_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/participation-guidelines",
        ):
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/participation-guidelines?error=invalid_csrf")
            return

        from app.handlers.onboarding import handle_guidelines_post

        result = handle_guidelines_post(uid)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()


    # -------------------------
    # Interests handler
    # -------------------------
    def handle_profile_interests_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/profile/interests?error=invalid_request")
            return

        raw_body = post_body["raw_body"]
        data = post_body["form"]

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/profile/interests?error=invalid_csrf")
            return

        from app.handlers.profile import handle_profile_interests_post
        result = handle_profile_interests_post(uid, raw_body)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()


    # -------------------------
    # Basic Profile handler
    # -------------------------
    def handle_profile_basic_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/profile/basic?error=invalid_request")
            return

        raw_body = post_body["raw_body"]
        data = post_body["form"]

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/profile/basic?error=invalid_csrf")
            return

        from app.handlers.profile import handle_profile_basic_post
        result = handle_profile_basic_post(uid, raw_body)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()


    # -------------------------
    # Advanced Profile handler
    # -------------------------
    def handle_profile_advanced_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/profile/advanced?error=invalid_request")
            return

        raw_body = post_body["raw_body"]
        data = post_body["form"]

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/profile/advanced?error=invalid_csrf")
            return

        from app.handlers.profile import handle_profile_advanced_post
        result = handle_profile_advanced_post(uid, raw_body)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    # -------------------------
    # Welcome handler
    # -------------------------
    def handle_welcome_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/welcome",
        ):
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/welcome?error=invalid_csrf")
            return

        from app.handlers.onboarding import handle_welcome_post

        result = handle_welcome_post(uid)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    # -------------------------
    # NDA handler
    # -------------------------

    def handle_nda_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/nda?error=invalid_request")
            return

        form = post_body["form"]

        from app.utils.csrf import validate_csrf_token

        csrf_token = form.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/nda?error=invalid_csrf")
            return

        from app.handlers.onboarding import handle_nda_post

        result = handle_nda_post(uid, form)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()


    # -------------------------
    # Settings Handler: Settings Page
    # -------------------------

    def handle_settings_page_post(self):
        """
        POST /settings is not a mutation endpoint.

        Settings updates must go through explicit POST endpoints such as:
        - /settings/password/change
        - /settings/demographics/save

        This route exists only as a safe fallback and must not render.
        """
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/settings",
        ):
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/settings?error=invalid_csrf")
            return

        self._redirect("/settings")

    # -------------------------
    # Settings Handler: Change Password
    # -------------------------

    def handle_settings_password_change_post(self):
        user_id = self._get_uid_from_cookie()
        if not user_id:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/settings",
            error_param="password_error",
        ):
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(user_id, csrf_token):
            self._redirect("/settings?password_error=invalid_csrf")
            return

        from app.handlers.settings import handle_settings_password_change_post

        result = handle_settings_password_change_post(
            user_id=user_id,
            data=data,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    # -------------------------
    # Settings Handler: Update Demographics
    # -------------------------

    def handle_settings_demographics_save_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/settings",
            error_param="demographics_error",
        ):
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/settings?demographics_error=invalid_csrf")
            return

        from app.handlers.settings import (
            handle_settings_demographics_save_post as handle_settings_demographics_save,
        )

        result = handle_settings_demographics_save(
            user_id=uid,
            data=data,
        )

        self._redirect(result["redirect"])

    # -------------------------
    # Save Legal Draft Handler
    # -------------------------
    
    def _handle_legal_save_draft(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._send_401()
            return

        import json
        from app.handlers.legal_documents import save_legal_draft

        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8"))

        try:
            save_legal_draft(user_id=uid, data=data)
            self._send_json({"ok": True})
        except Exception:
            self._send_json({"ok": False, "error": "legal_save_failed"}, status=400)


    # -------------------------
    # Update Permissions Handler
    # -------------------------

    def handle_update_user_permission_post(self):
            uid = self._get_uid_from_cookie()
            if not uid:
                self._send_json_response(
                    {"ok": False, "error": "Authentication required."},
                    status_code=401,
                )
                return

            from app.db.user_roles import get_effective_permission_level

            permission_level = get_effective_permission_level(uid)
            if permission_level not in {70, 100}:
                self._send_json_response(
                    {"ok": False, "error": "You are not allowed to make this change."},
                    status_code=403,
                )
                return

            from app.handlers.users import handle_update_user_permission

            try:
                length = int(self.headers.get("Content-Length", 0))
            except (TypeError, ValueError):
                self._send_json_response(
                    {"ok": False, "error": "Invalid request body."},
                    status_code=400,
                )
                return

            if length < 0:
                self._send_json_response(
                    {"ok": False, "error": "Invalid request body."},
                    status_code=400,
                )
                return

            if length > MAX_POST_BODY_BYTES:
                self._send_json_response(
                    {"ok": False, "error": "Request body too large."},
                    status_code=413,
                )
                return

            try:
                raw = self.rfile.read(length).decode("utf-8")
            except UnicodeDecodeError:
                self._send_json_response(
                    {"ok": False, "error": "Invalid request encoding."},
                    status_code=400,
                )
                return

            try:
                data = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._send_json_response(
                    {"ok": False, "error": "Invalid JSON."},
                    status_code=400,
                )
                return

            if not isinstance(data, dict):
                self._send_json_response(
                    {"ok": False, "error": "Invalid JSON payload."},
                    status_code=400,
                )
                return

            from app.utils.csrf import validate_csrf_token

            csrf_token = data.get("csrf_token")
            if not csrf_token or not validate_csrf_token(uid, csrf_token):
                self._send_json_response(
                    {"ok": False, "error": "Invalid CSRF token."},
                    status_code=403,
                )
                return

            result = handle_update_user_permission(uid, data)
            self._send_json_response(result["payload"], status_code=result["status_code"])

    # -------------------------
    # Legal Save & Publish handler (POST)
    # -------------------------

    def handle_legal_document_save_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._send_json_response(
                {"ok": False, "error": "not_authenticated"},
                status_code=401,
            )
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level not in {30, 70, 100}:
            self._send_json_response(
                {"ok": False, "error": "not_authorized"},
                status_code=403,
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self._send_json_response(
                {"ok": False, "error": "invalid_request_body"},
                status_code=400,
            )
            return

        if content_length <= 0:
            self._send_json_response(
                {"ok": False, "error": "empty_request_body"},
                status_code=400,
            )
            return

        if content_length > MAX_POST_BODY_BYTES:
            self._send_json_response(
                {"ok": False, "error": "request_body_too_large"},
                status_code=413,
            )
            return

        try:
            body = self.rfile.read(content_length).decode("utf-8")
        except UnicodeDecodeError:
            self._send_json_response(
                {"ok": False, "error": "invalid_request_encoding"},
                status_code=400,
            )
            return

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json_response(
                {"ok": False, "error": "invalid_json"},
                status_code=400,
            )
            return

        if not isinstance(data, dict):
            self._send_json_response(
                {"ok": False, "error": "invalid_json_payload"},
                status_code=400,
            )
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._send_json_response(
                {"ok": False, "error": "invalid_csrf"},
                status_code=403,
            )
            return

        from app.handlers.legal_documents import handle_save_legal_draft

        result = handle_save_legal_draft(
            user_id=uid,
            data=data,
        )

        response = {
            "ok": result.get("ok", False),
            "error": result.get("error"),
            "data": result if result.get("ok") else None,
        }

        self._send_json_response(
            response,
            status_code=200 if response["ok"] else 400
        )

    def handle_legal_document_publish_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._send_json_response(
                {"ok": False, "error": "not_authenticated"},
                status_code=401,
            )
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level not in {30, 70, 100}:
            self._send_json_response(
                {"ok": False, "error": "not_authorized"},
                status_code=403,
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self._send_json_response(
                {"ok": False, "error": "invalid_request_body"},
                status_code=400,
            )
            return

        if content_length <= 0:
            self._send_json_response(
                {"ok": False, "error": "empty_request_body"},
                status_code=400,
            )
            return

        if content_length > MAX_POST_BODY_BYTES:
            self._send_json_response(
                {"ok": False, "error": "request_body_too_large"},
                status_code=413,
            )
            return

        try:
            body = self.rfile.read(content_length).decode("utf-8")
        except UnicodeDecodeError:
            self._send_json_response(
                {"ok": False, "error": "invalid_request_encoding"},
                status_code=400,
            )
            return

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json_response(
                {"ok": False, "error": "invalid_json"},
                status_code=400,
            )
            return

        if not isinstance(data, dict):
            self._send_json_response(
                {"ok": False, "error": "invalid_json_payload"},
                status_code=400,
            )
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._send_json_response(
                {"ok": False, "error": "invalid_csrf"},
                status_code=403,
            )
            return

        from app.handlers.legal_documents import handle_publish_legal_document

        result = handle_publish_legal_document(
            user_id=uid,
            data=data,
        )

        response = {
            "ok": result.get("ok", False),
            "error": result.get("error"),
            "data": result if result.get("ok") else None,
        }

        self._send_json_response(
            response,
            status_code=200 if response["ok"] else 400
        )

    # -------------------------
    # Contact Us handler (POST)
    # -------------------------
    def handle_contact_us_post(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self._redirect("/contact-us?status=invalid_request")
            return

        if content_length <= 0:
            self._redirect("/contact-us?status=error")
            return

        if content_length > 64 * 1024:
            self._redirect("/contact-us?status=too_large")
            return

        try:
            body = self.rfile.read(content_length).decode("utf-8")
            data = parse_qs(body, keep_blank_values=True)
        except Exception:
            self._redirect("/contact-us?status=invalid_request")
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token("public_contact", csrf_token):
            self._redirect("/contact-us?status=invalid_csrf")
            return

        uid = self._get_uid_from_cookie()  # may be None
        actor_ip = self.client_address[0] if self.client_address else ""

        from app.handlers.contact import handle_contact_post

        result = handle_contact_post(
            actor_uid=uid,
            form=data,
            actor_ip=actor_ip,
        )

        if "error" in result:
            self._redirect("/contact-us?status=error")
            return

        self._redirect("/contact-us?status=sent")

    # -------------------------
    # Bonus Survey Basics Save
    # -------------------------
    def handle_bonus_survey_basics_save_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/surveys/bonus?error=invalid_request")
            return

        data = post_body["form"]

        draft_id = data.get("draft_id", [""])[0]
        csrf_error_redirect = f"/surveys/bonus/create?draft={draft_id}&error=invalid_csrf" if draft_id else "/surveys/bonus?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.surveys import handle_bonus_survey_basics_post

        result = handle_bonus_survey_basics_post(
            user_id=uid,
            data=data,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_bonus_survey_create_new_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/surveys/bonus",
        ):
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/surveys/bonus?error=invalid_csrf")
            return

        from app.cache.surveys_cache import create_bonus_draft

        draft_id = create_bonus_draft(uid)

        self.send_response(302)
        self.send_header(
            "Location",
            f"/surveys/bonus/create?draft={draft_id}",
        )
        self.end_headers()


    # -------------------------
    # Bonus Survey Draft Delete
    # -------------------------
    def handle_bonus_survey_draft_delete_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/surveys/bonus?error=invalid_request")
            return

        data = post_body["form"]

        draft_id = (data.get("draft_id", [""])[0] or "").strip()
        csrf_error_redirect = (
            f"/surveys/bonus/create?draft={draft_id}&error=invalid_csrf"
            if draft_id
            else "/surveys/bonus?error=invalid_csrf"
        )

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.surveys import handle_bonus_survey_draft_delete_post

        result = handle_bonus_survey_draft_delete_post(
            user_id=uid,
            data=data,
        )

        if "redirect" not in result:
            raise RuntimeError(
                "handle_bonus_survey_draft_delete_post must return a redirect"
            )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()


    # -------------------------
    # Bonus Survey Template Save
    # -------------------------
    def handle_bonus_survey_template_save_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/surveys/bonus?error=invalid_request")
            return

        data = post_body["form"]

        draft_id = data.get("draft_id", [""])[0]
        csrf_error_redirect = f"/surveys/bonus/create/template?draft={draft_id}&error=invalid_csrf" if draft_id else "/surveys/bonus?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.surveys import handle_bonus_survey_template_post

        result = handle_bonus_survey_template_post(
            user_id=uid,
            data=data,
        )

        if "redirect" not in result:
            raise RuntimeError(
                "handle_bonus_survey_template_post must return a redirect"
            )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    # -------------------------
    # Bonus Survey Targeting Save
    # -------------------------
    def handle_bonus_survey_targeting_save_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/surveys/bonus?error=invalid_request")
            return

        data = post_body["form"]

        draft_id = data.get("draft_id", [""])[0]
        csrf_error_redirect = f"/surveys/bonus/create/targeting?draft={draft_id}&error=invalid_csrf" if draft_id else "/surveys/bonus?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.surveys import handle_bonus_survey_targeting_post

        result = handle_bonus_survey_targeting_post(
            user_id=uid,
            data=data,
        )

        if "redirect" not in result:
            raise RuntimeError(
                "handle_bonus_survey_targeting_post must return a redirect"
            )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    # -------------------------
    # Bonus Survey Submit (POST)
    # -------------------------
    def handle_bonus_survey_submit_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/surveys/bonus?error=invalid_request")
            return

        data = post_body["form"]

        draft_id = data.get("draft_id", [""])[0]
        csrf_error_redirect = f"/surveys/bonus/create/review?draft={draft_id}&error=invalid_csrf" if draft_id else "/surveys/bonus?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.surveys import handle_bonus_survey_submit_post

        result = handle_bonus_survey_submit_post(
            user_id=uid,
            data=data,
        )

        # Handler contract: redirect-only
        if "redirect" not in result:
            raise RuntimeError(
                "handle_bonus_survey_submit_post must return a redirect"
            )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_bonus_survey_take_open_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/surveys/bonus/take",
        ):
            return

        survey_id = data.get("survey_id")
        if not survey_id or not str(survey_id).isdigit():
            self._redirect("/surveys/bonus/take")
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/surveys/bonus/take?error=invalid_csrf")
            return

        from app.handlers.surveys import handle_bonus_survey_take_open_post

        try:
            result = handle_bonus_survey_take_open_post(
                user_id=uid,
                survey_id=int(survey_id),
            )
        except Exception:
            debug("Bonus Survey open failed")
            result = {"redirect": "/surveys/bonus/take"}

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    # -------------------------
    # Bonus Survey Upload (POST)
    # -------------------------
    def handle_bonus_survey_upload_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/surveys/bonus",
        ):
            return

        survey_id = data.get("survey_id")
        if survey_id and str(survey_id).isdigit():
            csrf_error_redirect = f"/surveys/bonus/upload?survey_id={int(survey_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/surveys/bonus?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.surveys import handle_bonus_survey_upload_post

        result = handle_bonus_survey_upload_post(
            user_id=uid,
            data=data,
        )

        if result and "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        # POST must not render. Fall back to the upload GET page.
        self.send_response(302)
        self.send_header("Location", "/surveys/bonus/upload?error=upload_failed")
        self.end_headers()

    # -------------------------
    # Bonus Survey Analyze (POST)
    # -------------------------
    def handle_bonus_survey_analyze_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/surveys/bonus",
        ):
            return

        survey_id = data.get("survey_id")
        if survey_id and str(survey_id).isdigit():
            csrf_error_redirect = f"/surveys/bonus/active?survey_id={int(survey_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/surveys/bonus?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.surveys import handle_bonus_survey_analyze_post

        result = handle_bonus_survey_analyze_post(
            user_id=uid,
            data=data,
        )

        if result and "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        # POST must not render. Fall back to the bonus survey list.
        self.send_response(302)
        self.send_header("Location", "/surveys/bonus?error=analysis_failed")
        self.end_headers()

    # -------------------------
    # Bonus Survey Close (POST)
    # -------------------------
    def handle_bonus_survey_close_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/surveys/bonus",
        ):
            return

        survey_id = data.get("survey_id")
        if survey_id and str(survey_id).isdigit():
            csrf_error_redirect = f"/surveys/bonus/active?survey_id={int(survey_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/surveys/bonus?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.surveys import handle_bonus_survey_close_post

        result = handle_bonus_survey_close_post(
            user_id=uid,
            data=data,
        )

        if result and "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        # POST must not render. Fall back to the bonus survey list.
        self.send_response(302)
        self.send_header("Location", "/surveys/bonus?error=close_failed")
        self.end_headers()

    # -------------------------
    # Bonus Survey Section Generator
    # -------------------------

    def handle_bonus_survey_generate_sections_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/surveys/bonus",
        ):
            return

        bonus_survey_id = data.get("bonus_survey_id")
        if bonus_survey_id and str(bonus_survey_id).isdigit():
            csrf_error_redirect = f"/surveys/bonus/pending?survey_id={int(bonus_survey_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/surveys/bonus?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.surveys import handle_bonus_survey_generate_sections_post

        result = handle_bonus_survey_generate_sections_post(
            user_id=uid,
            data=data,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._redirect("/surveys/bonus?error=section_generation_failed")

    # -------------------------
    # Product Team Request Trial (POST)
    # -------------------------

    def handle_request_trial_create_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 50:
            self._redirect("/dashboard")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/product/request-trial",
        ):
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/product/request-trial?error=invalid_csrf")
            return

        from app.cache.product_cache import create_empty_trial_project

        project_id = create_empty_trial_project(created_by=uid)

        self.send_response(302)
        self.send_header(
            "Location",
            f"/product/request-trial/wizard/basics?project_id={project_id}",
        )
        self.end_headers()

    # -------------------------
    # Product Request Trial – Basics (POST)
    # -------------------------

    def handle_product_request_trial_wizard_basics_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            project_id = data.get("project_id", [""])[0]
            if project_id:
                self._redirect(f"/product/request-trial/wizard/basics?project_id={project_id}&error=invalid_csrf")
            else:
                self._redirect("/product/request-trial?error=invalid_csrf")
            return

        from app.handlers.product_team import handle_product_request_trial_wizard_basics_post

        result = handle_product_request_trial_wizard_basics_post(
            user_id=uid,
            data=data,
        )

        if result.get("error") == "invalid_csrf":
            project_id = data.get("project_id", [""])[0]
            if project_id:
                self._redirect(f"/product/request-trial/wizard/basics?project_id={project_id}&error=invalid_csrf")
            else:
                self._redirect("/product/request-trial?error=invalid_csrf")
            return

        if "error" in result:
            self._redirect("/product/request-trial?error=save_failed")
            return

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    # -------------------------
    # Product Request Trial – Timing (POST)
    # -------------------------

    def handle_product_request_trial_wizard_timing_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            project_id = data.get("project_id", [""])[0]
            if project_id:
                self._redirect(f"/product/request-trial/wizard/timing?project_id={project_id}&error=invalid_csrf")
            else:
                self._redirect("/product/request-trial?error=invalid_csrf")
            return

        from app.handlers.product_team import (
            handle_product_request_trial_wizard_timing_post,
        )

        result = handle_product_request_trial_wizard_timing_post(
            user_id=uid,
            data=data,
        )

        if result.get("error") == "invalid_csrf":
            project_id = data.get("project_id", [""])[0]
            if project_id:
                self._redirect(f"/product/request-trial/wizard/timing?project_id={project_id}&error=invalid_csrf")
            else:
                self._redirect("/product/request-trial?error=invalid_csrf")
            return

        if "error" in result:
            self._redirect("/product/request-trial?error=save_failed")
            return

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_product_request_trial_wizard_stakeholders_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length).decode("utf-8")

        from urllib.parse import parse_qs
        data = parse_qs(raw)

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            project_id = data.get("project_id", [""])[0]
            if project_id:
                self._redirect(f"/product/request-trial/wizard/stakeholders?project_id={project_id}&error=invalid_csrf")
            else:
                self._redirect("/product/request-trial?error=invalid_csrf")
            return

        from app.handlers.product_team import (
            handle_product_request_trial_wizard_stakeholders_post,
        )

        result = handle_product_request_trial_wizard_stakeholders_post(
            user_id=uid,
            data=data,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        if result.get("error") == "invalid_csrf":
            project_id = data.get("project_id", [""])[0]
            if project_id:
                self._redirect(f"/product/request-trial/wizard/stakeholders?project_id={project_id}&error=invalid_csrf")
            else:
                self._redirect("/product/request-trial?error=invalid_csrf")
            return

        if result.get("error") == "invalid_stakeholder_email":
            project_id = result.get("project_id") or data.get("project_id", [""])[0]
            if project_id:
                self._redirect(f"/product/request-trial/wizard/stakeholders?project_id={project_id}&error=invalid_stakeholder_email")
            else:
                self._redirect("/product/request-trial?error=invalid_stakeholder_email")
            return

        self._redirect("/product/request-trial?error=save_failed")

    def handle_product_request_trial_cancel_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        project_id = data.get("project_id", [""])[0]
        redirect_path = "/product/request-trial"
        if project_id:
            redirect_path = f"/product/request-trial/wizard/basics?project_id={project_id}"

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            self._redirect(f"{redirect_path}&error=invalid_csrf" if "?" in redirect_path else f"{redirect_path}?error=invalid_csrf")
            return

        from app.handlers.product_team import (
            handle_product_request_trial_cancel_post,
        )

        result = handle_product_request_trial_cancel_post(
            user_id=uid,
            data=data,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._redirect("/product/request-trial?error=cancel_failed")

    def handle_product_request_trial_submit_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            project_id = data.get("project_id", [""])[0]
            if project_id:
                self._redirect(f"/product/request-trial/wizard/review?project_id={project_id}&error=invalid_csrf")
            else:
                self._redirect("/product/request-trial?error=invalid_csrf")
            return

        from app.handlers.product_team import (
            handle_product_request_trial_submit_post,
        )

        result = handle_product_request_trial_submit_post(
            user_id=uid,
            data=data,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        if result.get("error") == "invalid_csrf":
            project_id = data.get("project_id", [""])[0]
            if project_id:
                self._redirect(f"/product/request-trial/wizard/review?project_id={project_id}&error=invalid_csrf")
            else:
                self._redirect("/product/request-trial?error=invalid_csrf")
            return

        self._redirect("/product/request-trial?error=submission_failed")

    def handle_admin_approval_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/admin/approvals",
        ):
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/admin/approvals?error=invalid_csrf")
            return

        from app.handlers.admin_post_approvals import handle_admin_approval_post

        result = handle_admin_approval_post(
            user_id=uid,
            data=data,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._redirect("/admin/approvals?error=approval_failed")

    def handle_product_request_trial_change_requested_respond_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            self._redirect("/product/request-trial?error=invalid_csrf")
            return

        from app.handlers.product_team import (
            handle_product_request_trial_change_requested_respond_post,
        )

        result = handle_product_request_trial_change_requested_respond_post(
            user_id=uid,
            data=data,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        if result.get("error") == "invalid_csrf":
            self._redirect("/product/request-trial?error=invalid_csrf")
            return

        self._redirect("/product/request-trial?error=submission_failed")

    def handle_product_request_trial_info_requested_respond_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            project_id = data.get("project_id", [""])[0]
            if project_id:
                self._redirect(f"/product/request-trial/info-requested?project_id={project_id}&error=invalid_csrf")
            else:
                self._redirect("/product/request-trial?error=invalid_csrf")
            return

        from app.handlers.product_team import (
            handle_product_request_trial_info_requested_respond_post,
        )

        result = handle_product_request_trial_info_requested_respond_post(
            user_id=uid,
            data=data,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        if result.get("error") == "invalid_csrf":
            project_id = data.get("project_id", [""])[0]
            if project_id:
                self._redirect(f"/product/request-trial/info-requested?project_id={project_id}&error=invalid_csrf")
            else:
                self._redirect("/product/request-trial?error=invalid_csrf")
            return

        self._redirect("/product/request-trial?error=submission_failed")

    # -------------------------
    # UT Lead – Project Save (POST)
    # -------------------------

    def handle_ut_lead_project_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/ut-lead/trials",
        ):
            return

        round_id = data.get("round_id")
        if round_id and str(round_id).isdigit():
            csrf_error_redirect = f"/ut-lead/project?round_id={int(round_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/ut-lead/trials?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.user_trial_lead_project import (
            handle_ut_lead_project_post,
        )

        result = handle_ut_lead_project_post(
            user_id=uid,
            data=data,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._redirect("/ut-lead/trials?error=save_failed")

    # -------------------------
    # UT Lead – User Selection (POST)
    # -------------------------

    def handle_user_selection_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/ut-lead/trials",
        ):
            return

        round_id = data.get("round_id")
        if round_id and str(round_id).isdigit():
            csrf_error_redirect = f"/trials/selection?round_id={int(round_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/ut-lead/trials?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.user_selection import handle_user_selection_post

        result = handle_user_selection_post(
            user_id=uid,
            data=data,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._redirect("/ut-lead/trials?error=selection_failed")

    # -------------------------
    # Trial Application Handler (POST)
    # -------------------------

    def handle_trial_apply_post(self):

        uid = self._get_uid_from_cookie()

        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/trials/recruiting",
        ):
            return

        # FIXED: do NOT cast here
        round_id_raw = data.get("round_id")
        motivation = data.get("motivation_text")

        if not round_id_raw:
            self._redirect("/trials/recruiting")
            return

        try:
            round_id = int(round_id_raw)
        except ValueError:
            self._redirect("/trials/recruiting")
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/trials/recruiting?error=invalid_csrf")
            return

        from app.services.trial_visibility import get_visible_recruiting_rounds

        visible_round_ids = {
            int(r.get("RoundID") or 0)
            for r in get_visible_recruiting_rounds(uid)
        }
        if round_id not in visible_round_ids:
            self._redirect("/trials/recruiting")
            return

        from app.services.round_access import validate_round_access

        validated_round = validate_round_access(
            actor_user_id=uid,
            round_id=round_id,
            required_role="participant",
            allow_admin=True,
        )

        if not validated_round:
            self.send_response(302)
            self.send_header("Location", "/dashboard")
            self.end_headers()
            return

        from app.db.project_applicants import apply_for_trial
        from app.db.user_trial_lead import get_round_surveys
        from app.services.survey_token_service import ensure_token

        # 1. Insert applicant
        apply_for_trial(
            user_id=uid,
            round_id=validated_round["RoundID"],
            motivation=motivation
        )

        # 2. Fetch surveys
        surveys = get_round_surveys(validated_round["RoundID"])

        recruiting_link = None

        for s in surveys:
            survey_name = (s.get("SurveyTypeName") or "").lower()

            if "recruit" in survey_name:
                link = (s.get("DistributionLink") or "").strip()

                if link:
                    recruiting_link = link
                    break

        # 3. External path
        if recruiting_link:

            token = ensure_token(uid, validated_round["RoundID"], "recruiting")

            if "user_token_here" in recruiting_link:
                survey_url = recruiting_link.replace("user_token_here", token)
            else:
                separator = "&" if "?" in recruiting_link else "?"
                survey_url = f"{recruiting_link}{separator}token={token}"

            if not _is_allowed_external_survey_redirect(survey_url):
                self._redirect("/trials/recruiting?error=invalid_survey_link")
                return

            self.send_response(302)
            self.send_header("Location", survey_url)
            self.end_headers()
            return

        # 4. Fallback
        self.send_response(302)
        self.send_header("Location", "/trials/recruiting")
        self.end_headers()

    def handle_trial_withdraw_post(self):

        uid = self._get_uid_from_cookie()

        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/trials/recruiting",
        ):
            return

        round_id_raw = data.get("round_id")

        try:
            round_id = int(round_id_raw)
        except (TypeError, ValueError):
            self._redirect("/trials/recruiting")
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/trials/recruiting?error=invalid_csrf")
            return

        from app.db.project_applicants import withdraw_application

        withdraw_application(
            user_id=uid,
            round_id=round_id
        )

        self.send_response(302)
        self.send_header("Location", "/trials/recruiting")
        self.end_headers()

    def handle_end_recruiting_post(self):

        uid = self._get_uid_from_cookie()

        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/ut-lead/trials",
        ):
            return

        round_id_raw = data.get("round_id")

        try:
            round_id = int(round_id_raw)
        except (TypeError, ValueError):
            self.send_response(302)
            self.send_header("Location", "/dashboard")
            self.end_headers()
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(f"/ut-lead/project?round_id={round_id}&error=invalid_csrf")
            return

        from app.services.round_access import validate_round_access

        validated_round = validate_round_access(
            actor_user_id=uid,
            round_id=round_id,
            required_role="ut_lead",
            allow_admin=True,
        )

        if not validated_round:
            self.send_response(302)
            self.send_header("Location", "/dashboard")
            self.end_headers()
            return

        from app.db.project_rounds import close_recruiting

        close_recruiting(validated_round["RoundID"])

        self.send_response(302)
        self.send_header("Location", f"/ut-lead/project?round_id={validated_round['RoundID']}")
        self.end_headers()


    def handle_trial_survey_open_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/trials/active",
        ):
            return

        round_id = data.get("round_id")

        if round_id and str(round_id).isdigit():
            csrf_error_redirect = f"/trials/active?round_id={int(round_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/trials/active?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.trials import handle_trial_survey_open_post

        result = handle_trial_survey_open_post(
            user_id=uid,
            data=data,
        )

        self._redirect(result.get("redirect", "/trials/active"))


    def handle_trial_nda_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/trials/active",
        ):
            return

        round_id = data.get("round_id")

        if round_id and str(round_id).isdigit():
            csrf_error_redirect = f"/trials/nda?round_id={int(round_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/trials/active?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.trials import handle_trial_nda_post

        result = handle_trial_nda_post(
            user_id=uid,
            data=data,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_404()

    def handle_survey_upload_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/survey/upload",
        ):
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/survey/upload?error=invalid_csrf")
            return

        from app.handlers.survey_upload import handle_survey_upload_post

        result = handle_survey_upload_post(
            user_id=uid,
            data=data,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._redirect("/survey/upload?error=upload_failed")

    # -------------------------
    # Active Trials
    # -------------------------

    def handle_confirm_shipping_post(self):
        user_id = self._get_uid_from_cookie()

        if not user_id:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/trials/active",
        ):
            return

        round_id_raw = data.get("round_id")

        if not round_id_raw:
            self._redirect("/trials/active")
            return

        try:
            round_id = int(round_id_raw)
        except (TypeError, ValueError):
            self._redirect("/trials/active")
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(user_id, csrf_token):
            self._redirect(f"/trials/active?round_id={round_id}&error=invalid_csrf")
            return

        from app.services.round_object_binding import validate_round_object_binding

        if not validate_round_object_binding(
            round_id=round_id,
            participant_id=user_id,
        ):
            self._redirect("/trials/active")
            return

        from app.db.project_participants import confirm_shipping_address

        confirm_shipping_address(user_id=user_id, round_id=round_id)

        self.send_response(302)
        self.send_header("Location", f"/trials/active?round_id={round_id}")
        self.end_headers()

    def handle_responsibilities_post(self):

        uid = self._get_uid_from_cookie()

        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/trials/active",
        ):
            return

        round_id = data.get("round_id")

        if round_id and str(round_id).isdigit():
            csrf_error_redirect = f"/trials/responsibilities?round_id={int(round_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/trials/active?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        data["action"] = data.get("action") or data.get("decline_action")

        # -------------------------
        # 🔥 Delegate to handler
        # -------------------------
        from app.handlers.responsibilities import handle_responsibilities_post

        result = handle_responsibilities_post(
            user_id=uid,
            data=data
        )

        # -------------------------
        # 🔥 Redirect only
        # -------------------------
        redirect_url = result.get("redirect", "/trials/active")

        self.send_response(302)
        self.send_header("Location", redirect_url)
        self.end_headers()

    def handle_save_shipping_post(self):

        user_id = self._get_uid_from_cookie()

        if not user_id:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/trials/active",
        ):
            return

        round_id = data.get("round_id")

        if round_id and str(round_id).isdigit():
            csrf_error_redirect = f"/trials/active?round_id={int(round_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/trials/active?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(user_id, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        # -------------------------
        # Call proper handler
        # -------------------------
        from app.handlers.trials import handle_shipping_save_post

        result = handle_shipping_save_post(
            user_id=user_id,
            data=data
        )

        # -------------------------
        # Redirect (required by POST rule)
        # -------------------------
        redirect_to = result.get("redirect", "/trials/active")

        self.send_response(302)
        self.send_header("Location", redirect_to)
        self.end_headers()

    def _handle_device_received_post(self):

        user_id = self._get_uid_from_cookie()

        if not user_id:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/trials/active",
        ):
            return

        round_id = data.get("round_id")

        if round_id and str(round_id).isdigit():
            csrf_error_redirect = f"/trials/active?round_id={int(round_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/trials/active?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(user_id, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.trials import handle_device_received_post

        result = handle_device_received_post(
            user_id=user_id,
            data=data,
        )

        redirect_to = result.get("redirect", "/trials/active")

        self.send_response(302)
        self.send_header("Location", redirect_to)
        self.end_headers()

    def _handle_device_not_received_post(self):

        user_id = self._get_uid_from_cookie()

        if not user_id:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/trials/active",
        ):
            return

        round_id = data.get("round_id")

        if round_id and str(round_id).isdigit():
            csrf_error_redirect = f"/trials/active?round_id={int(round_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/trials/active?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(user_id, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.trials import handle_device_not_received_post

        result = handle_device_not_received_post(
            user_id=user_id,
            data=data,
        )

        redirect_to = result.get("redirect", "/trials/active")

        self.send_response(302)
        self.send_header("Location", redirect_to)
        self.end_headers()

    # ---- Open notification target (POST)
    def handle_notification_open_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.notifications import mark_notification_dismissed

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/notifications",
        ):
            return

        notification_id = data.get("notification_id")

        target_url = data.get("target_url") or "/notifications"

        if not isinstance(target_url, str) or not target_url.startswith("/") or target_url.startswith("//"):
            target_url = "/notifications"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/notifications?error=invalid_csrf")
            return

        if not notification_id:
            self._redirect("/notifications")
            return

        from app.db.notifications import get_notification_for_user

        notification = get_notification_for_user(
            notification_id=notification_id,
            user_id=uid,
        )
        if not notification:
            self._redirect("/notifications")
            return

        mark_notification_dismissed(
            notification_id=notification_id,
            user_id=uid,
        )

        self.send_response(302)
        self.send_header("Location", target_url)
        self.end_headers()


    # ---- Mark notification read (POST)
    def handle_notification_view_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.notifications import mark_notification_read

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/notifications",
        ):
            return

        notification_id = data.get("notification_id")

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/notifications?error=invalid_csrf")
            return

        if not notification_id:
            self._redirect("/notifications")
            return

        from app.db.notifications import get_notification_for_user

        notification = get_notification_for_user(
            notification_id=notification_id,
            user_id=uid,
        )
        if not notification:
            self._redirect("/notifications")
            return

        mark_notification_read(
            notification_id=notification_id,
            user_id=uid,
        )

        target = f"/notifications/view?notification_id={notification_id}"
        self.send_response(302)
        self.send_header("Location", target)
        self.end_headers()


    # ---- Dismiss notification (POST)
    def handle_notification_dismiss_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.notifications import mark_notification_dismissed

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/notifications",
        ):
            return

        notification_id = data.get("notification_id")

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/notifications?error=invalid_csrf")
            return

        if not notification_id:
            self._redirect("/notifications")
            return

        from app.db.notifications import get_notification_for_user

        notification = get_notification_for_user(
            notification_id=notification_id,
            user_id=uid,
        )
        if not notification:
            self._redirect("/notifications")
            return

        mark_notification_dismissed(
            notification_id=notification_id,
            user_id=uid,
        )

        self.send_response(302)
        self.send_header("Location", "/notifications")
        self.end_headers()


    # ---- Mark all notifications read (POST)
    def handle_notifications_mark_read_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/notifications",
        ):
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/notifications?error=invalid_csrf")
            return

        from app.services.notifications import mark_all_notifications_read

        mark_all_notifications_read(uid)

        self.send_response(302)
        self.send_header("Location", "/notifications")
        self.end_headers()

    def handle_trials_interest_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/trials/upcoming",
        ):
            return

        round_id = data.get("round_id")

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/trials/upcoming?error=invalid_csrf")
            return

        try:
            round_id_int = int(round_id)
        except (TypeError, ValueError):
            self._redirect("/trials/upcoming")
            return

        from app.services.trial_visibility import get_visible_upcoming_rounds

        visible_round_ids = {
            int(r.get("RoundID") or 0)
            for r in get_visible_upcoming_rounds(uid)
        }
        if round_id_int not in visible_round_ids:
            self._redirect("/trials/upcoming")
            return

        from app.db.project_round_interest import record_round_interest

        record_round_interest(
            user_id=uid,
            round_id=round_id_int
        )

        self.send_response(302)
        self.send_header("Location", "/trials/upcoming")
        self.end_headers()


    def handle_trials_interest_stop_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/trials/upcoming",
        ):
            return

        round_id = data.get("round_id")
        return_to = data.get("return_to") or "/trials/upcoming"

        if return_to not in {"/trials/upcoming", "/my_trials"}:
            return_to = "/trials/upcoming"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/trials/upcoming?error=invalid_csrf")
            return

        try:
            round_id_int = int(round_id)
        except (TypeError, ValueError):
            self._redirect(return_to)
            return

        from app.db.project_round_interest import stop_watching_round

        stop_watching_round(
            user_id=uid,
            round_id=round_id_int,
        )

        self.send_response(302)
        self.send_header("Location", return_to)
        self.end_headers()


    # ---- Selection session init (POST)
    def handle_selection_init_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from urllib.parse import parse_qs
        from app.services.round_access import validate_round_access
        from app.services.selection_service import create_or_get_selection_session

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        try:
            round_id_raw = data.get("round_id", [None])[0]
            round_id = int(round_id_raw)
        except (TypeError, ValueError):
            self._redirect("/dashboard")
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(f"/ut-lead/trials?round_id={round_id}&error=invalid_csrf")
            return

        validated_round = validate_round_access(
            actor_user_id=uid,
            round_id=round_id,
            required_role="ut_lead",
            allow_admin=True,
        )

        if not validated_round:
            self._redirect("/dashboard")
            return

        create_or_get_selection_session(
            validated_round=validated_round,
            user_id=uid,
        )

        self._redirect(f"/trials/selection?round_id={round_id}")

    # ---- Confirm selection (POST)
    def handle_selection_confirm_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from urllib.parse import parse_qs
        from app.services.selection_auth import validate_selection_session_access
        from app.services.selection_service import update_selection_session

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        try:
            session_id_raw = data.get("session_id", [None])[0]
            round_id_raw = data.get("round_id", [None])[0]

            session_id = int(session_id_raw)
            round_id = int(round_id_raw)
        except (TypeError, ValueError):
            self._redirect("/dashboard")
            return

        if not session_id or not round_id:
            self._redirect("/dashboard")
            return

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(f"/trials/selection/confirm?session_id={session_id}&round_id={round_id}&error=invalid_csrf")
            return

        selection_session = validate_selection_session_access(
            actor_user_id=uid,
            session_id=session_id,
            round_id=round_id,
        )

        if not selection_session:
            self._redirect("/dashboard")
            return

        # ✅ Mutation happens here (POST only)
        update_selection_session(
            validated_session=selection_session,
            updates={
                "Status": "selection"
            }
        )

        self._redirect(f"/trials/selection?round_id={round_id}")

    # -------------------------
    # Bonus Survey Structure (Generate + Reset)
    # -------------------------

    def handle_bonus_survey_structure_generate_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/surveys/bonus/structure?error=invalid_request")
            return

        raw_body = post_body["raw_body"]
        form = post_body["form"]

        try:
            bonus_survey_id = int(form.get("survey_id", [0])[0] or 0)
        except (TypeError, ValueError):
            bonus_survey_id = 0

        from app.utils.csrf import validate_csrf_token

        csrf_token = form.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(f"/surveys/bonus/structure?survey_id={bonus_survey_id}&error=invalid_csrf")
            return

        from app.handlers.bonus_survey_structure import (
            handle_bonus_survey_structure_generate_post
        )

        result = handle_bonus_survey_structure_generate_post(
            user_id=uid,
            raw_body=raw_body,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_bonus_survey_structure_reset_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/surveys/bonus/structure?error=invalid_request")
            return

        raw_body = post_body["raw_body"]
        form = post_body["form"]

        try:
            bonus_survey_id = int(form.get("survey_id", [0])[0] or 0)
        except (TypeError, ValueError):
            bonus_survey_id = 0

        from app.utils.csrf import validate_csrf_token

        csrf_token = form.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(f"/surveys/bonus/structure?survey_id={bonus_survey_id}&error=invalid_csrf")
            return

        from app.handlers.bonus_survey_structure import (
            handle_bonus_survey_structure_reset_post
        )

        result = handle_bonus_survey_structure_reset_post(
            user_id=uid,
            raw_body=raw_body,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_bonus_survey_structure_classify_profile_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/surveys/bonus/structure?error=invalid_request")
            return

        raw_body = post_body["raw_body"]
        form = post_body["form"]

        try:
            bonus_survey_id = int(form.get("survey_id", [0])[0] or 0)
        except (TypeError, ValueError):
            bonus_survey_id = 0

        from app.utils.csrf import validate_csrf_token

        csrf_token = form.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(f"/surveys/bonus/structure?survey_id={bonus_survey_id}&error=invalid_csrf")
            return

        from app.handlers.bonus_survey_structure import (
            handle_bonus_survey_structure_classify_profile_post
        )

        result = handle_bonus_survey_structure_classify_profile_post(
            user_id=uid,
            raw_body=raw_body,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_bonus_survey_structure_save_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/surveys/bonus/structure?error=invalid_request")
            return

        raw_body = post_body["raw_body"]
        form = post_body["form"]

        try:
            bonus_survey_id = int(form.get("survey_id", [0])[0] or 0)
        except (TypeError, ValueError):
            bonus_survey_id = 0

        from app.utils.csrf import validate_csrf_token

        csrf_token = form.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(f"/surveys/bonus/structure?survey_id={bonus_survey_id}&error=invalid_csrf")
            return

        from app.handlers.bonus_survey_structure import (
            handle_bonus_survey_structure_save_post
        )

        result = handle_bonus_survey_structure_save_post(
            user_id=uid,
            raw_body=raw_body,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_bonus_survey_section_add_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/surveys/bonus/structure?error=invalid_request")
            return

        raw_body = post_body["raw_body"]
        form = post_body["form"]

        try:
            bonus_survey_id = int(form.get("survey_id", [0])[0] or 0)
        except (TypeError, ValueError):
            bonus_survey_id = 0

        from app.utils.csrf import validate_csrf_token

        csrf_token = form.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(f"/surveys/bonus/structure?survey_id={bonus_survey_id}&error=invalid_csrf")
            return

        from app.handlers.bonus_survey_structure import (
            handle_bonus_survey_section_add_post
        )

        result = handle_bonus_survey_section_add_post(
            user_id=uid,
            raw_body=raw_body,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_bonus_survey_section_rename_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/surveys/bonus/structure?error=invalid_request")
            return

        raw_body = post_body["raw_body"]
        form = post_body["form"]

        try:
            bonus_survey_id = int(form.get("survey_id", [0])[0] or 0)
        except (TypeError, ValueError):
            bonus_survey_id = 0

        from app.utils.csrf import validate_csrf_token

        csrf_token = form.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(f"/surveys/bonus/structure?survey_id={bonus_survey_id}&error=invalid_csrf")
            return

        from app.handlers.bonus_survey_structure import (
            handle_bonus_survey_section_rename_post
        )

        result = handle_bonus_survey_section_rename_post(
            user_id=uid,
            raw_body=raw_body,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_bonus_survey_section_delete_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        post_body = self._read_urlencoded_post_body()

        if not post_body.get("ok"):
            self._redirect("/surveys/bonus/structure?error=invalid_request")
            return

        raw_body = post_body["raw_body"]
        form = post_body["form"]

        try:
            bonus_survey_id = int(form.get("survey_id", [0])[0] or 0)
        except (TypeError, ValueError):
            bonus_survey_id = 0

        from app.utils.csrf import validate_csrf_token

        csrf_token = form.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(f"/surveys/bonus/structure?survey_id={bonus_survey_id}&error=invalid_csrf")
            return

        from app.handlers.bonus_survey_structure import (
            handle_bonus_survey_section_delete_post
        )

        result = handle_bonus_survey_section_delete_post(
            user_id=uid,
            raw_body=raw_body,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()


    # ---- Historical Upload
    def handle_historical_upload_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        from app.handlers.historical import handle_historical_upload_post

        parsed = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=parsed,
            redirect_path="/historical/upload",
        ):
            return

        context_id = parsed.get("context_id")
        if context_id and str(context_id).isdigit():
            csrf_error_redirect = f"/historical/upload?context_id={int(context_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/historical?error=invalid_csrf"

        if not self._validate_parsed_form_csrf(user_id=uid, data=parsed):
            self._redirect(csrf_error_redirect)
            return

        files = parsed.get("files") or {}
        upload_file = files.get("file")

        if upload_file is not None:
            parsed["file"] = {
                "filename": getattr(upload_file, "filename", ""),
                "file": upload_file.getvalue(),
            }

        result = handle_historical_upload_post(
            user_id=uid,
            data=parsed,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_historical_create_context_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/historical/create-context?error=invalid_csrf")
            return

        from app.handlers.historical import handle_historical_create_context_post

        result = handle_historical_create_context_post(data)

        if "error" in result:
            self._redirect(f"/historical/create-context?error={result['error']}")
            return

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_historical_product_publish_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        raw_product_id = data.get("product_id", [None])[0]
        try:
            product_id = int(raw_product_id)
        except (TypeError, ValueError):
            product_id = 0

        csrf_error_redirect = f"/historical/product?product_id={product_id}&error=invalid_csrf" if product_id else "/historical?error=invalid_csrf"

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.historical import handle_historical_product_publish_post

        result = handle_historical_product_publish_post(
            user_id=uid,
            data=data,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_historical_aggregate_report_generate_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/historical",
        ):
            return

        raw_product_id = data.get("product_id")
        raw_round_number = data.get("round_number")

        try:
            product_id = int(raw_product_id)
            round_number = int(raw_round_number)
        except (TypeError, ValueError):
            product_id = 0
            round_number = 0

        csrf_error_redirect = (
            f"/historical/aggregate-report?product_id={product_id}&round_number={round_number}&error=invalid_csrf"
            if product_id and round_number else
            "/historical?error=invalid_csrf"
        )

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.historical import handle_historical_aggregate_report_generate_post

        result = handle_historical_aggregate_report_generate_post(
            user_id=uid,
            data=data,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_historical_aggregate_report_generate_ai_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/historical",
        ):
            return

        raw_product_id = data.get("product_id")
        raw_round_number = data.get("round_number")

        try:
            product_id = int(raw_product_id)
            round_number = int(raw_round_number)
        except (TypeError, ValueError):
            product_id = 0
            round_number = 0

        csrf_error_redirect = (
            f"/historical/aggregate-report?product_id={product_id}&round_number={round_number}&error=invalid_csrf"
            if product_id and round_number else
            "/historical?error=invalid_csrf"
        )

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.historical import handle_historical_aggregate_report_generate_ai_post

        result = handle_historical_aggregate_report_generate_ai_post(
            user_id=uid,
            data=data,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_historical_aggregate_report_publish_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/historical",
        ):
            return

        raw_product_id = data.get("product_id")
        raw_round_number = data.get("round_number")

        try:
            product_id = int(raw_product_id)
            round_number = int(raw_round_number)
        except (TypeError, ValueError):
            product_id = 0
            round_number = 0

        csrf_error_redirect = (
            f"/historical/aggregate-report?product_id={product_id}&round_number={round_number}&error=invalid_csrf"
            if product_id and round_number else
            "/historical?error=invalid_csrf"
        )

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.historical import handle_historical_aggregate_report_publish_post

        result = handle_historical_aggregate_report_publish_post(
            user_id=uid,
            data=data,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_historical_product_access_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        raw_product_id = data.get("product_id", [None])[0]
        try:
            product_id = int(raw_product_id)
        except (TypeError, ValueError):
            product_id = 0

        csrf_error_redirect = f"/historical/product?product_id={product_id}&error=invalid_csrf" if product_id else "/historical?error=invalid_csrf"

        if not self._validate_parsed_form_csrf(user_id=uid, data=data):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.historical import handle_historical_product_access_post

        result = handle_historical_product_access_post(
            user_id=uid,
            data=data,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()


    def handle_generate_section_names_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/historical",
        ):
            return

        context_id = data.get("context_id")

        if context_id and str(context_id).isdigit():
            csrf_error_redirect = f"/historical/context?context_id={int(context_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/historical?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.historical import handle_generate_section_names_post

        result = handle_generate_section_names_post(
            user_id=uid,
            data=data,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_generate_section_summaries_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/historical",
        ):
            return

        context_id = data.get("context_id")

        if context_id and str(context_id).isdigit():
            csrf_error_redirect = f"/historical/context?context_id={int(context_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/historical?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.historical import handle_generate_section_summaries_post

        result = handle_generate_section_summaries_post(
            user_id=uid,
            data=data,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_generate_insights_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        data = self._parse_post_data()
        if self._redirect_on_parse_error(
            data=data,
            redirect_path="/historical",
        ):
            return

        context_id = data.get("context_id")

        if context_id and str(context_id).isdigit():
            csrf_error_redirect = f"/historical/context?context_id={int(context_id)}&error=invalid_csrf"
        else:
            csrf_error_redirect = "/historical?error=invalid_csrf"

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token")
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect(csrf_error_redirect)
            return

        from app.handlers.historical import handle_generate_insights_post

        result = handle_generate_insights_post(
            user_id=uid,
            data=data,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def handle_create_product_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from app.db.user_roles import get_effective_permission_level

        permission_level = get_effective_permission_level(uid)
        if permission_level < 70:
            self._redirect("/dashboard")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        from app.utils.csrf import validate_csrf_token

        csrf_token = data.get("csrf_token", [None])[0]
        if not csrf_token or not validate_csrf_token(uid, csrf_token):
            self._redirect("/products/create?error=invalid_csrf")
            return

        from app.handlers.products import handle_create_product_post

        result = handle_create_product_post(data)

        if "error" in result:
            self._redirect(f"/products/create?error={result['error']}")
            return

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    # -------------------------
    # Helpers
    # -------------------------

    def _get_base_html(self):
        base_html = BASE_TEMPLATE
        return self._inject_nav(base_html)

    def _get_session_id_from_cookie(self) -> str | None:
        raw = self.headers.get("Cookie")
        if not raw:
            return None

        c = cookies.SimpleCookie()
        c.load(raw)

        morsel = c.get("session_id")
        if not morsel:
            return None

        session_id = morsel.value.strip()
        if not session_id:
            return None

        return session_id

    def _get_uid_from_cookie(self) -> str | None:
        session_id = self._get_session_id_from_cookie()
        if not session_id:
            return None

        from app.services.session_service import get_user_from_session
        user_id = get_user_from_session(session_id)
        return user_id

    def _get_display_permission_level(self, user_id: str) -> int:
        """
        Return the permission level used for GET page preview/rendering.

        Real permission remains authoritative inside POST handlers. This helper
        is only for read-only route access previews while admin view mode is active.
        """
        from app.services.permission_context import get_permission_context

        permission_context = get_permission_context(
            user_id=user_id,
            session_id=self._get_session_id_from_cookie(),
        )

        return permission_context["effective_permission_level"]
    
    def _is_logged_in(self) -> bool:
        return bool(self._get_uid_from_cookie())
    
    def _redirect(self, location: str):
        """
        Standard redirect helper to enforce PRG pattern.
        """
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()    

    def _validate_parsed_form_csrf(self, *, user_id: str, data: dict) -> bool:
        """
        Validate a CSRF token from parse_qs-style POST data.

        Supports both:
        - {"csrf_token": ["..."]}
        - {"csrf_token": "..."}
        """
        from app.utils.csrf import validate_csrf_token

        raw_token = data.get("csrf_token")

        if isinstance(raw_token, list):
            csrf_token = raw_token[0] if raw_token else None
        else:
            csrf_token = raw_token

        return bool(csrf_token and validate_csrf_token(user_id, csrf_token))

    def _get_display_name(self, user: dict) -> str:
        first = (user.get("FirstName") or "").strip()
        last = (user.get("LastName") or "").strip()

        if first and last:
            return f"{first} {last}"
        if first:
            return first
        return "Account"

    def _get_query_param(self, key):
        query = urlparse(self.path).query
        return parse_qs(query).get(key, [""])[0]

    def _get_post_param(self, name: str):

        import urllib.parse

        # Read POST body only once
        if not hasattr(self, "_post_params"):
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length).decode("utf-8")
            self._post_params = urllib.parse.parse_qs(post_data)

        value = self._post_params.get(name)

        if not value:
            return None

        return value[0]

    def _send_json_response(self, payload: dict, status_code: int = 200):
        """
        Standardized JSON response helper.

        Expected payload format:
        {
            "ok": bool,
            "error": str | None,
            "data": dict | None
        }
        """

        import json

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def _parse_post_data(self):
        """
        Parse POST bodies.

        Supports:
        - application/x-www-form-urlencoded
        - multipart/form-data (file uploads)

        Returns:
            dict with:
                normal fields as strings
                files under key "files"

        Security behavior:
            Malformed/oversized bodies return a small parse-error dict instead
            of raising raw exceptions from the routing layer.
        """
        from urllib.parse import parse_qs
        from email.parser import BytesParser
        from email.policy import default
        from io import BytesIO

        content_type = self.headers.get("Content-Type", "")

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            return {"_parse_error": "invalid_content_length"}

        if content_length <= 0:
            return {}

        if content_length > MAX_POST_BODY_BYTES:
            return {"_parse_error": "request_body_too_large"}

        try:
            body = self.rfile.read(content_length)
        except Exception:
            return {"_parse_error": "request_body_read_failed"}

        # --------------------------------------------------
        # Multipart (file upload)
        # --------------------------------------------------
        if content_type.startswith("multipart/form-data"):
            data = {}
            files = {}

            # The email parser expects full headers
            full_message = (
                f"Content-Type: {content_type}\r\n"
                f"MIME-Version: 1.0\r\n\r\n"
            ).encode() + body

            try:
                msg = BytesParser(policy=default).parsebytes(full_message)
            except Exception:
                return {"_parse_error": "invalid_multipart"}

            try:
                parts = list(msg.iter_parts())
            except Exception:
                return {"_parse_error": "invalid_multipart"}

            for part in parts:
                content_disposition = part.get("Content-Disposition", "")
                if not content_disposition:
                    continue

                dispositions = {}

                for item in content_disposition.split(";")[1:]:
                    if "=" not in item:
                        continue

                    key, value = item.strip().split("=", 1)
                    dispositions[key.strip()] = value.strip()

                name = dispositions.get("name")
                if not name:
                    continue

                name = name.strip('"')

                filename = dispositions.get("filename")
                payload = part.get_payload(decode=True) or b""

                if filename:
                    filename = filename.strip('"')
                    file_obj = BytesIO(payload)
                    file_obj.filename = filename
                    files[name] = file_obj
                else:
                    value = payload.decode("utf-8", errors="replace")
                    data[name] = value

            if files:
                data["files"] = files

            return data

        # --------------------------------------------------
        # URL Encoded
        # --------------------------------------------------
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            return {"_parse_error": "invalid_encoding"}

        parsed = parse_qs(text, keep_blank_values=True)

        return {
            key: values[0] if len(values) == 1 else values
            for key, values in parsed.items()
        }


    def _redirect_on_parse_error(
        self,
        *,
        data: dict,
        redirect_path: str,
        error_param: str = "error",
    ) -> bool:
        """
        Redirect safely when _parse_post_data() returns a parser error.

        Returns True when a redirect was sent.
        """
        if not isinstance(data, dict):
            self._redirect(f"{redirect_path}?{error_param}=invalid_request")
            return True

        parse_error = data.get("_parse_error")
        if not parse_error:
            return False

        separator = "&" if "?" in redirect_path else "?"
        self._redirect(f"{redirect_path}{separator}{error_param}=invalid_request")
        return True


    def _read_urlencoded_post_body(self) -> dict:
        """
        Safely read a URL-encoded POST body while preserving raw_body.

        Some legacy handlers still need raw_body for downstream parsing, so this
        is separate from _parse_post_data().
        """
        from urllib.parse import parse_qs

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            return {
                "ok": False,
                "error": "invalid_content_length",
                "raw_body": "",
                "form": {},
            }

        if content_length <= 0:
            return {
                "ok": False,
                "error": "empty_request_body",
                "raw_body": "",
                "form": {},
            }

        if content_length > MAX_POST_BODY_BYTES:
            return {
                "ok": False,
                "error": "request_body_too_large",
                "raw_body": "",
                "form": {},
            }

        try:
            raw_body = self.rfile.read(content_length).decode("utf-8")
        except UnicodeDecodeError:
            return {
                "ok": False,
                "error": "invalid_encoding",
                "raw_body": "",
                "form": {},
            }

        return {
            "ok": True,
            "error": None,
            "raw_body": raw_body,
            "form": parse_qs(raw_body, keep_blank_values=True),
        }


    def _render_content_page(self, page):
        content = page["Content"] or ""

        # -------------------------
        # HTML Mode (trusted content)
        # -------------------------
        if "<h" in content or "<p" in content:
            content_html = content

        # -------------------------
        # Text Mode (safe rendering)
        # -------------------------
        else:
            lines = content.splitlines()
            html = []

            for line in lines:
                line = line.rstrip()

                if not line:
                    html.append("<br>")
                elif line.startswith("## "):
                    html.append(f"<h3>{e(line[3:])}</h3>")
                elif line.startswith("- "):
                    html.append(f"<li>{e(line[2:])}</li>")
                else:
                    html.append(f"<p>{e(line)}</p>")

            content_html = "\n".join(html)

            # wrap orphan <li> blocks in <ul>
            content_html = content_html.replace(
                "</p>\n<li>", "</p>\n<ul><li>"
            ).replace(
                "</li>\n<p>", "</li></ul>\n<p>"
            )

        return f"""
            <h2>{e(page['Title'])}</h2>
            {content_html}
        """

    def _build_admin_view_mode_menu_html(self, *, permission_context: dict, csrf_token: str) -> str:
        if not permission_context.get("can_use_admin_view_mode"):
            return ""

        selected_level = permission_context.get("view_as_permission_level")
        options = []

        for row in permission_context.get("admin_view_mode_levels", []):
            level = row.get("permission_level")
            label = row.get("label") or f"Level {level}"
            selected = " selected" if selected_level == level else ""
            options.append(
                f'<option value="{e(str(level))}"{selected}>{e(label)} ({e(str(level))})</option>'
            )

        clear_html = ""
        if permission_context.get("is_viewing_as"):
            clear_html = f"""
            <form method="POST" action="/admin/view-mode/clear" class="admin-view-mode-clear-form">
                <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
                <button type="submit" class="admin-view-mode-clear-button">Exit view mode</button>
            </form>
            """

        return f"""
        <hr>
        <div class="admin-view-mode-menu-block">
            <div class="admin-view-mode-menu-title">View site as</div>
            <form method="POST" action="/admin/view-mode/set" class="admin-view-mode-form">
                <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
                <select name="view_as_permission_level" class="admin-view-mode-select">
                    {''.join(options)}
                </select>
                <button type="submit" class="admin-view-mode-submit">Apply</button>
            </form>
            <div class="admin-view-mode-real-level">
                Real: {e(permission_context.get("real_permission_label", ""))}
                ({e(str(permission_context.get("real_permission_level", "")))})
            </div>
            {clear_html}
        </div>
        """

    def _build_admin_view_mode_banner_html(self, *, permission_context: dict, csrf_token: str) -> str:
        if not permission_context.get("is_viewing_as"):
            return ""

        return f"""
        <section class="admin-view-mode-banner" aria-label="Admin view mode active">
            <div class="layout-container admin-view-mode-banner-inner">
                <div>
                    Viewing site as
                    <strong>
                        {e(permission_context.get("view_as_permission_label", ""))}
                        ({e(str(permission_context.get("view_as_permission_level", "")))})
                    </strong>
                    <span>
                        Real access:
                        {e(permission_context.get("real_permission_label", ""))}
                        ({e(str(permission_context.get("real_permission_level", "")))})
                    </span>
                </div>
                <form method="POST" action="/admin/view-mode/clear">
                    <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
                    <button type="submit">Exit view mode</button>
                </form>
            </div>
        </section>
        """

    def _inject_admin_view_mode_banner(self, *, base_html: str, banner_html: str) -> str:
        if not banner_html:
            return base_html

        if "</header>" not in base_html:
            return base_html

        return base_html.replace("</header>", f"</header>\n{banner_html}", 1)

    def _inject_nav(self, base_html: str, mode: str = "user") -> str:
        uid = self._get_uid_from_cookie()

        home_link = ""
        user_anchor = ""
        role_nav = ""
        admin_view_mode_banner = ""

        if mode == "public":
            base_html = base_html.replace("__HOME_LINK__", "")
            base_html = base_html.replace("__USER_ANCHOR__", "")
            base_html = base_html.replace("__ROLE_NAV__", "")
            return base_html

        if mode == "onboarding":
            home_link = '<a href="/">Home</a>'

            from app.utils.csrf import generate_csrf_token

            logout_csrf_token = generate_csrf_token(uid) if uid else ""

            user_anchor = f"""
            <form method="POST" action="/logout" class="logout-inline-form">
                <input type="hidden" name="csrf_token" value="{e(logout_csrf_token)}">
                <button type="submit" class="logout-link-button">Log out</button>
            </form>
            """
            role_nav = ""

            base_html = base_html.replace("__HOME_LINK__", home_link)
            base_html = base_html.replace("__USER_ANCHOR__", user_anchor)
            base_html = base_html.replace("__ROLE_NAV__", role_nav)

            return base_html

        if uid:
            from app.db.user_pool import get_user_by_userid
            from app.services.permission_context import get_permission_context

            user = get_user_by_userid(uid)
            display_name = self._get_display_name(user) if user else "Account"
            home_link = '<a href="/">Home</a>'

            from app.services.notifications import (
                get_unread_count,
                get_recent_notifications,
            )

            unread_count = get_unread_count(uid)

            from app.utils.csrf import generate_csrf_token

            notification_action_csrf_token = generate_csrf_token(uid)
            notification_mark_read_csrf_token = generate_csrf_token(uid)
            logout_csrf_token = generate_csrf_token(uid)
            admin_view_mode_csrf_token = generate_csrf_token(uid)

            session_id = self._get_session_id_from_cookie()
            permission_context = get_permission_context(
                user_id=uid,
                session_id=session_id,
            )

            try:
                notifications = get_recent_notifications(uid, limit=5)
            except Exception:
                debug("Unable to load bell notifications")
                notifications = []

            badge_html = ""
            if unread_count > 0:
                badge_html = (
                    f'<span class="notification-badge">'
                    f'{unread_count if unread_count < 10 else "9+"}'
                    f'</span>'
                )

            dropdown_items = ""

            for n in notifications:
                notification_id = n.get("notification_id") or ""

                rendered = render_notification({
                    "title": n.get("title"),
                    "payload": n.get("payload", {}),
                    "type_key": n.get("type_key"),
                })

                title = rendered.get("title") or n.get("title") or "Notification"
                message = rendered.get("message") or ""

                actions_html = ""

                for a in rendered.get("actions", []):
                    label = a.get("label", "Open")
                    href = a.get("href", "#")

                    safe_href = href if isinstance(href, str) and href.startswith("/") and not href.startswith("//") else "#"

                    if safe_href == "#":
                        continue

                    if safe_href.startswith("/notifications/"):
                        actions_html += f"""
                        <form method="POST" action="{e(safe_href)}" style="display:inline;">
                            <input type="hidden" name="csrf_token" value="{e(notification_action_csrf_token)}">
                            <input type="hidden" name="notification_id" value="{e(notification_id)}">
                            <button type="submit" class="dropdown-action notification-action-button">
                                {e(label)}
                            </button>
                        </form>
                        """
                    else:
                        actions_html += f"""
                        <form method="POST" action="/notifications/open" style="display:inline;">
                            <input type="hidden" name="csrf_token" value="{e(notification_action_csrf_token)}">
                            <input type="hidden" name="notification_id" value="{e(notification_id)}">
                            <input type="hidden" name="target_url" value="{e(safe_href)}">
                            <button type="submit" class="dropdown-action notification-action-button">
                                {e(label)}
                            </button>
                        </form>
                        """

                dropdown_items += f"""
                <div class="notification-dropdown-item">
                    <div class="notification-dropdown-title">{e(title)}</div>
                    <div class="notification-dropdown-message">{e(message)}</div>
                    <div class="notification-dropdown-actions">
                        {actions_html}
                    </div>
                </div>
                """

            if not dropdown_items:
                dropdown_items = """
                <div class="notification-dropdown-item">
                    <div class="notification-dropdown-message">No new notifications.</div>
                </div>
                """

            notification_dropdown = f"""
            <div class="dropdown notification-menu">
                <a href="#" class="dropdown-trigger notification-bell" data-notification-csrf="{e(notification_mark_read_csrf_token)}">
                    🔔
                    {badge_html}
                </a>

                <div class="dropdown-menu notification-dropdown">
                    {dropdown_items}

                    <div class="notification-dropdown-footer">
                        <a href="/notifications">See all &gt;</a>
                    </div>
                </div>
            </div>
            """

            admin_view_mode_menu_html = self._build_admin_view_mode_menu_html(
                permission_context=permission_context,
                csrf_token=admin_view_mode_csrf_token,
            )

            admin_view_mode_banner = self._build_admin_view_mode_banner_html(
                permission_context=permission_context,
                csrf_token=admin_view_mode_csrf_token,
            )

            user_anchor = f"""
            {notification_dropdown}

            <div class="dropdown user-menu">
                <a href="#" class="dropdown-trigger user-anchor">
                    {e(display_name)} ▾
                </a>

                <div class="dropdown-menu user-dropdown">
                    <a href="/my_trials">My Trials</a>
                    <hr>
                    <a href="/profile">Profile Summary</a>
                    <a href="/settings">Settings</a>
                    {admin_view_mode_menu_html}
                    <hr>
                    <form method="POST" action="/logout" class="logout-menu-form">
                        <input type="hidden" name="csrf_token" value="{e(logout_csrf_token)}">
                        <button type="submit" class="logout-menu-button">Log out</button>
                    </form>
                </div>
            </div>
            """

            from app.navigation.role_nav import build_role_nav

            role_nav = build_role_nav(
                permission_level=permission_context["effective_permission_level"]
            )

        else:
            user_anchor = '<a href="/login">Login</a>'

        base_html = base_html.replace("__HOME_LINK__", home_link)
        base_html = base_html.replace("__USER_ANCHOR__", user_anchor)
        base_html = base_html.replace("__ROLE_NAV__", role_nav)
        base_html = self._inject_admin_view_mode_banner(
            base_html=base_html,
            banner_html=admin_view_mode_banner,
        )

        return base_html

    def _render_register_error(self, message, email=""):
        from app.utils.csrf import generate_csrf_token

        csrf_token = generate_csrf_token("public_register")

        body_html = REGISTER_TEMPLATE
        body_html = body_html.replace("__CSRF_TOKEN__", e(csrf_token))

        body_html = body_html.replace(
            "__ERROR_BLOCK__",
            f'<div class="form-error">{message}</div>'
        )

        # Rehydrate email field only (password should remain blank)
        body_html = body_html.replace(
            "__EMAIL_VALUE__",
            email
        )

        base_html = self._get_base_html()
        html = base_html.replace("__BODY__", body_html)
        self._send_html(html)


    # -------------------------
    # Login Error Renderer
    # -------------------------

    def _render_login_error(self, message: str):
        from app.handlers.auth import render_login_get

        base_html = BASE_TEMPLATE

        result = render_login_get(
            handler=self,
            base_html=base_html,
            login_template_path=LOGIN_TEMPLATE,
            query={"error": message},
        )

        html = self._inject_nav(result["html"])
        self._send_html(html)


    def _send_html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_404(self):
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"404 - Page not found")
    
# -------------------------
# Server
# -------------------------
def run():
    server = ThreadingHTTPServer(("127.0.0.1", 8000), RequestHandler)
    print("Serving User Trials site at http://localhost:8000")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped by user")
        server.server_close()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    run()
