from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from os import path
from pathlib import Path
from unittest import result
from urllib.parse import urlparse, parse_qs

from app.db.content_pages import get_page_by_slug
from app.services.registration import register_user, RegistrationInput
from app.config.config import DEBUG as CONFIG_DEBUG
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
from app.handlers.my_trials import render_past_trials_get
from app.handlers.legal_download import render_download_document
from app.db.user_pool import mark_email_verified
from app.services.notifications import get_all_notifications
from app.handlers.notifications import render_notification



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

# -------------------------
# Debug flag
# -------------------------
DEBUG = CONFIG_DEBUG  # flip via .env if needed


def debug(*args):
    if DEBUG:
        print("[DEBUG]", *args)


def render_profile_summary_html(full_summary: dict) -> str:
    html = []

    # -------------------------
    # Demographics
    # -------------------------
    demo = full_summary.get("demographics", {})
    html.append("<section class='profile-summary demographics'>")
    html.append(f"<h2>{demo.get('title')}</h2>")

    for item in demo.get("items", []):
        html.append(
            f"<div class='summary-row'>"
            f"<span class='label'>{item['label']}</span>: "
            f"<span class='value'>{item['value']}</span>"
            f"</div>"
        )
    html.append("</section>")

    # -------------------------
    # Interests / Basic / Advanced
    # -------------------------
    def render_sections(title, sections):
        html.append(f"<section class='profile-summary'><h2>{title}</h2>")

        for s in sections:
            html.append("<details>")
            html.append(
                f"<summary>{s['title']} ({s['completed']} / {s['total']})</summary>"
            )

            # Child sections (Product Types)
            if "children" in s:
                for child in s["children"]:
                    html.append(
                        f"<div class='summary-child'>"
                        f"<strong>{child['title']}</strong>"
                        f"</div>"
                    )
                    for cat in child.get("categories", []):
                        html.append(f"<div>{cat['category_name']}: "
                                    f"{', '.join(cat['values'])}</div>")
            else:
                for cat in s.get("categories", []):
                    html.append(
                        f"<div>{cat['category_name']}: "
                        f"{', '.join(cat['values'])}</div>"
                    )

            if s.get("missing", 0) > 0:
                html.append(
                    f"<div class='missing'>{s['missing']} not specified</div>"
                )

            html.append("</details>")

        html.append("</section>")

    render_sections("Interests", full_summary.get("interests", []))
    render_sections("Basic Profile", full_summary.get("basic_profile", []))
    render_sections("Advanced Profile", full_summary.get("advanced_profile", []))

    return "\n".join(html)




class RequestHandler(BaseHTTPRequestHandler):
    # -------------------------
    # Static assets
    # -------------------------
    def _serve_static(self):
        static_path = Path("app") / self.path.lstrip("/")
        if not static_path.exists():
            self._send_404()
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/css")
        self.end_headers()
        self.wfile.write(static_path.read_bytes())

    def _serve_image(self):
        image_path = Path("app") / self.path.lstrip("/")

        if not image_path.exists():
            debug("Image not found:", image_path)
            self._send_404()
            return

        self.send_response(200)
        self.send_header("Content-Type", "image/png")
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
        if path == "logout":
            self._handle_logout()
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
        if path == "trials/recruiting":
            self._render_trials_recruiting()
            return
        if path == "trials/interest":
            self._render_trials_interest()
            return
        if path == "admin/users":
            self._render_admin_users()
            return
        # ---- Legal routes
        if path == "legal/nda":
            self._render_legal_nda()
            return
        if path.startswith("legal/download/"):
            self._render_legal_download(path)
            return
        if path.startswith("legal/signed/"):
            self._render_signed_legal_document(path)
            return
        if path == "legal/documents":
            self._render_legal_documents_index()
            return
        if path.startswith("legal/documents/"):
            doc_id = path.replace("legal/documents/", "", 1)
            self._render_legal_documents_index(doc_id=doc_id)
            return
        if path.startswith("legal/"):
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
        
        if path == "admin/approvals":
            self._render_admin_approvals()
            return

        if path == "admin/approvals/view":
            self._render_admin_approval_view()
            return

        if path == "surveys/bonus/active":
            self._render_bonus_survey_active()
            return
        if path == "surveys/bonus/take":
            self._render_bonus_survey_take()
            return
        if path == "surveys/bonus/take/open":
            self._render_bonus_survey_take_open()
            return

        # ---- Notifcations
        if path == "notifications":
            self._render_notifications()
            return
        if path == "notifications/view":
            self._render_notification_view()
            return
        if path == "notifications/dismiss":
            self._dismiss_notification()
            return
        if path == "notifications/mark-read":
            self._mark_notifications_read()
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
        if path == "product/current-trials":
            self._render_product_current_trials()
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
        # ---- Catch-all for unhandled GET routes

        self._render_guest_content(path)

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

    # ---- Logout
    def _handle_logout(self):
        from app.handlers.auth import handle_logout_get
        handle_logout_get(self)


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

        html = self._inject_nav(BASE_TEMPLATE, mode="onboarding")
        html = html.replace("{{ body }}", result["html"])
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
        html = html.replace("{{ body }}", result["html"])
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
        html = html.replace("{{ body }}", body)

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
        html = html.replace("{{ body }}", result["html"])
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

        from app.handlers.settings import render_settings_get

        base_html = BASE_TEMPLATE

        result = render_settings_get(
            user_id=uid,
            base_template=base_html,
            inject_nav=self._inject_nav,
        )

        self._send_html(result["html"])

    # ---- Settings: Demographics fragment (GET)
    def _render_settings_demographics_fragment(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._send_401()
            return

        from app.handlers.settings import render_demographics_form

        fragment = render_demographics_form(uid)

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

    # ---- Dashboard (dummy for now)
    def _render_dashboard(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.dashboard import render_dashboard_get

        result = render_dashboard_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
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
        html = html.replace("{{ body }}", body)

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
        html = html.replace("{{ body }}", body)

        self._send_html(html)

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
        html = html.replace("{{ body }}", body)

        self._send_html(html)


    # ---- Upcoming Trials interest (GET)
    def _render_trials_interest(self):

        # --------------------------------------------------
        # Authentication
        # --------------------------------------------------

        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # --------------------------------------------------
        # Parse round_id
        # --------------------------------------------------

        round_id = self._get_query_param("round_id")

        if not round_id:
            self.send_response(302)
            self.send_header("Location", "/trials/upcoming")
            self.end_headers()
            return

        # --------------------------------------------------
        # Record interest
        # --------------------------------------------------

        from app.db.project_round_interest import record_round_interest

        record_round_interest(
            user_id=uid,
            round_id=int(round_id)
        )

        # --------------------------------------------------
        # Redirect back
        # --------------------------------------------------

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
        html = html.replace("{{ body }}", body)

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
        from app.db.notifications import mark_notification_read

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)
        notification_id = query_params.get("notification_id", [None])[0]

        if not notification_id:
            self.send_response(302)
            self.send_header("Location", "/notifications")
            self.end_headers()
            return

        # Mark read (NOT dismissed)
        mark_notification_read(
            notification_id=notification_id,
            user_id=uid,
        )

        body = render_notification_view(
            user_id=uid,
            notification_id=notification_id,
        )

        html = BASE_TEMPLATE
        html = self._inject_nav(html)
        html = html.replace("{{ title }}", "Notification")
        html = html.replace("{{ body }}", body)

        self._send_html(html)


    # ---- Dismiss Notifications (GET)
    def _dismiss_notification(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from urllib.parse import parse_qs, urlparse
        from app.db.notifications import mark_notification_dismissed

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)
        notification_id = query_params.get("notification_id", [None])[0]

        if notification_id:
            mark_notification_dismissed(
                notification_id=notification_id,
                user_id=uid,
            )

        self.send_response(302)
        self.send_header("Location", "/notifications")
        self.end_headers()

    # ---- Mark all notifications read (GET)
    def _mark_notifications_read(self):
        uid = self._get_uid_from_cookie()

        if not uid:
            self.send_response(401)
            self.end_headers()
            return

        try:
            from app.services.notifications import mark_all_notifications_read
            mark_all_notifications_read(uid)
        except Exception as e:
            print("ERROR marking notifications read:", e)

        # respond OK but no page
        self.send_response(204)
        self.end_headers()

    # ---- Legal NDA page (GET)
    def _render_legal_nda(self):

        uid = self._get_uid_from_cookie()

        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.legal_public import render_public_legal_document

        result = render_public_legal_document(
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
        html = html.replace("{{ body }}", result["html"])

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
        html = html.replace("{{ body }}", result["html"])

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
        html = html.replace("{{ body }}", result["html"])

        self._send_html(html)

    # ---- Legal documents editor index (GET)
    def _render_legal_documents_index(self, doc_id=None):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.legal_documents import render_legal_documents_index

        result = render_legal_documents_index(
            user_id=uid,
            doc_id=doc_id,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        html = BASE_LEGAL
        html = self._inject_nav(html)
        html = html.replace("{{ body }}", result["html"])

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

        # Send file
        self.send_response(200)
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
    # Admin Approval (GET)
    # -------------------------

    def _render_admin_approvals(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
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

    def _render_bonus_survey_active(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
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

        survey_id = self._get_query_param("survey_id")
        if not survey_id:
            self.send_error(400, "Missing survey_id")
            return

        from app.handlers.surveys import resolve_bonus_survey_redirect

        try:
            redirect_url = resolve_bonus_survey_redirect(
                user_id=uid,
                survey_id=int(survey_id),
            )
        except ValueError:
            self.send_error(404, "Survey not found")
            return
        except Exception as e:
            self.send_error(500, str(e))
            return

        self.send_response(302)
        self.send_header("Location", redirect_url)
        self.end_headers()



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
    # Product Team – My Current Trials (GET)
    # -------------------------
    def _render_product_current_trials(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.product_team import render_product_current_trials_get

        result = render_product_current_trials_get(
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
    # Product Team – My Past Trials (GET)
    # -------------------------
    def _render_product_past_trials(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.product_team import render_product_past_trials_get

        result = render_product_past_trials_get(
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
    # Product Team – Reports and Summaries (GET)
    # -------------------------

    def _render_product_reports(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.product_team import render_product_reports_get

        result = render_product_reports_get(
            user_id=uid,
            base_template=BASE_TEMPLATE,
            inject_nav=self._inject_nav,
        )

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

        project_id = self._get_query_param("project_id")
        if not project_id:
            self.send_error(400, "Missing project_id")
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

        project_id = self._get_query_param("project_id")
        if not project_id:
            self.send_error(400, "Missing project_id")
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

        project_id = self._get_query_param("project_id")
        if not project_id:
            self.send_error(400, "Missing project_id")
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

        project_id = self._get_query_param("project_id")
        if not project_id:
            self.send_error(400, "Missing project_id")
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

        from app.handlers.user_trial_lead import render_ut_lead_trials_get

        result = render_ut_lead_trials_get(
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

    def _render_ut_lead_project(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
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

    # -------------------------
    # Profile Levels API (GET)
    # -------------------------
    def _render_api_profile_levels(self):

        from urllib.parse import parse_qs, urlparse
        import json
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
            body = body.replace(
                "{{CONTACT_FORM}}",
                CONTACT_FORM_HTML
            )

        html = BASE_TEMPLATE
        html = self._inject_nav(html)
        html = html.replace("{{ body }}", body)

        self._send_html(html)


    # -------------------------
    # POST requests
    # -------------------------
    def do_POST(self):
        if self.path == "/register":
            self._handle_register()
            return
        if self.path == "/verify-email":
            self._handle_verify_email()
            return
        if self.path == "/demographics":
            self._handle_demographics()
            return
        if self.path == "/login":
            self._handle_login()
            return
        if self.path == "/nda":
            self._handle_nda()
            return
        if self.path == "/participation-guidelines":
            self._handle_guidelines()
            return
        if self.path == "/profile/interests":
            self._handle_profile_interests()
            return
        if self.path == "/profile/basic":
            self._handle_profile_basic()
            return
        if self.path == "/profile/advanced":
            self._handle_profile_advanced()
            return  
        if self.path == "/welcome":
            self._handle_welcome()
            return
        if self.path == "/settings":
            self._handle_settings_page()
            return
        if self.path == "/settings/demographics/save":
            self._handle_settings_demographics_save()
            return
        if self.path == "/admin/users/update-permission":
            self._handle_update_user_permission()
            return
        if self.path == "/contact-us":
            self._handle_contact_us()
            return
        if self.path == "/legal/documents/save":
            self._handle_legal_document_save()
            return
        if self.path == "/legal/documents/publish":
            self._handle_legal_document_publish()
            return
        if self.path == "/surveys/bonus/create/save-basics":
            self._handle_bonus_survey_basics_save()
            return
        if self.path == "/surveys/bonus/create/new":
            self._handle_bonus_survey_create_new()
            return
        if self.path == "/surveys/bonus/create/save-template":
            self._handle_bonus_survey_template_save()
            return
        if self.path == "/surveys/bonus/create/save-targeting":
            self._handle_bonus_survey_targeting_save()
            return
        if self.path == "/surveys/bonus/take":
            self._handle_bonus_survey_take_post()
            return

        # -----------------------------
        # Bonus Approval actions (POST)
        # -----------------------------
        
        if self.path == "/surveys/bonus/approve":
            self._handle_bonus_survey_approve()
            return
        if self.path == "/surveys/bonus/request-changes":
            self._handle_bonus_survey_request_changes()
            return
        if self.path == "/surveys/bonus/request-info":
            self._handle_bonus_survey_request_info()
            return
        if self.path == "/surveys/bonus/create/submit":
            self._handle_bonus_survey_submit()
            return
        
        # -----------------------------
        # Product Team Request Trial (POST)
        # -----------------------------

        if self.path == "/product/request-trial/create":
            self._handle_request_trial_create()
            return
        if self.path == "/product/request-trial/wizard/basics":
            self._handle_product_request_trial_wizard_basics()
            return
        if self.path == "/product/request-trial/wizard/timing":
            self._handle_product_request_trial_wizard_timing()
            return
        if self.path == "/product/request-trial/wizard/stakeholders":
            self._handle_product_request_trial_wizard_stakeholders_post()
            return
        if self.path == "/product/request-trial/submit":
            self._handle_product_request_trial_submit_post()
            return
        if self.path == "/admin/approvals/submit":
            self._handle_admin_approval_post()
            return
        if self.path == "/admin/approvals/bonus/submit":
            self._handle_admin_approval_post()
            return
        if self.path == "/product/request-trial/info-requested/respond":
            self._handle_product_request_trial_info_requested_respond_post()
            return
        if self.path == "/product/request-trial/change-requested/respond":
            self._handle_product_request_trial_change_requested_respond_post()
            return
        if self.path == "/admin/approval":
            self._handle_admin_approval_post()
            return
        
        # -----------------------------
        # UT Lead (POST)
        # -----------------------------

        if self.path == "/ut-lead/project":
            self._handle_ut_lead_project_post()
            return

        # -----------------------------
        # User Application to UT (POST)
        # -----------------------------

        if self.path == "/trials/apply":
            self._handle_trial_apply()
            return

        if self.path == "/trials/withdraw":
            self._handle_trial_withdraw()
            return
        # -----------------------------
        # No path exists (POST)
        # -----------------------------

        self._send_404()

    # -------------------------
    # Register handler
    # -------------------------
    def _handle_register(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

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

    def _handle_verify_email(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        token = data.get("token", [None])[0]

        from app.handlers.auth import handle_verify_email_post

        result = handle_verify_email_post(token)

        if "error" in result:
            self.send_response(400)
            self._send_html(f"<p>{result['error']}</p>")
            return

        user = result["user"]

        # ---- set session cookie immediately after verification ----
        c = cookies.SimpleCookie()
        c["uid"] = user["user_id"]
        c["uid"]["path"] = "/"
        c["uid"]["httponly"] = True
        c["uid"]["samesite"] = "Lax"

        # ---- determine next onboarding step ----
        onboarding_state = get_onboarding_state(user)

        self.send_response(302)
        self.send_header("Set-Cookie", c["uid"].OutputString())

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

    def _handle_login(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        from app.handlers.auth import handle_login_post

        # ----------------------------------------
        # REAL CLIENT IP (nginx-aware) + DEBUG
        # ----------------------------------------

        x_real_ip = self.headers.get("X-Real-IP")
        x_forwarded_for = self.headers.get("X-Forwarded-For")

        if x_real_ip:
            ip = x_real_ip
            source = "X-Real-IP"
        elif x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
            source = "X-Forwarded-For"
        else:
            ip = self.client_address[0]
            source = "client_address"

        # ---- DEBUG OUTPUT ----
        print("\n[LOGIN DEBUG]")
        print(f"  extracted_ip={ip}")
        print(f"  source={source}")
        print(f"  X-Real-IP={x_real_ip}")
        print(f"  X-Forwarded-For={x_forwarded_for}")
        print(f"  client_address={self.client_address}")
        print(f"  email_attempt={data.get('email', [''])[0]}")
        print("[END LOGIN DEBUG]\n")

        result = handle_login_post(data, ip)

        if "error" in result:
            print(f"[LOGIN RESULT] FAILURE ip={ip} error={result['error']}")
            self._render_login_error(result["error"])
            return

        user = result["user"]
        onboarding_state = result["onboarding_state"]

        print(f"[LOGIN RESULT] SUCCESS ip={ip} user_id={user.get('user_id')}")

        # ---- set session cookie ----
        c = cookies.SimpleCookie()
        c["uid"] = user["user_id"]
        c["uid"]["path"] = "/"
        c["uid"]["httponly"] = True
        c["uid"]["samesite"] = "Lax"

        self.send_response(302)
        self.send_header("Set-Cookie", c["uid"].OutputString())

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
    # Logout handler
    # -------------------------

    def _handle_logout(self):
        c = cookies.SimpleCookie()
        c["uid"] = ""
        c["uid"]["path"] = "/"
        c["uid"]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        c["uid"]["max-age"] = 0

        self.send_response(302)
        self.send_header("Set-Cookie", c["uid"].OutputString())
        self.send_header("Location", "/login")
        self.end_headers()


    # -------------------------
    # Demographics handler (POST)
    # -------------------------

    def _handle_demographics(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

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
    def _handle_guidelines(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.onboarding import handle_guidelines_post

        result = handle_guidelines_post(uid)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()


    # -------------------------
    # Interests handler
    # -------------------------
    def _handle_profile_interests(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")

        from app.handlers.profile import handle_profile_interests_post
        result = handle_profile_interests_post(uid, raw_body)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()


    # -------------------------
    # Basic Profile handler
    # -------------------------
    def _handle_profile_basic(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")

        from app.handlers.profile import handle_profile_basic_post
        result = handle_profile_basic_post(uid, raw_body)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()


    # -------------------------
    # Advanced Profile handler
    # -------------------------
    def _handle_profile_advanced(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")

        from app.handlers.profile import handle_profile_advanced_post
        result = handle_profile_advanced_post(uid, raw_body)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    # -------------------------
    # Welcome handler
    # -------------------------

    def _handle_welcome(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.onboarding import handle_welcome_post

        result = handle_welcome_post(uid)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    # -------------------------
    # NDA handler
    # -------------------------

    def _handle_nda(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        form = parse_qs(post_data)

        from app.handlers.onboarding import handle_nda_post

        result = handle_nda_post(uid, form)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()


    # -------------------------
    # Settings Handler: Settings Page
    # -------------------------

    def _handle_settings_page(self):
        user_id = self._get_uid_from_cookie()
        if not user_id:
            self._send_401()
            return

        from app.db.user_pool import get_user_by_userid
        user = get_user_by_userid(user_id)

        render_template(
            "settings.html",
            {
                "user": user,
            }
        )

    # -------------------------
    # Settings Handler: Update Demographics
    # -------------------------

    def _handle_settings_demographics_save(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._send_401()
            return

        import json
        from app.handlers.settings import save_demographics_inline

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        data = json.loads(raw) if raw else {}

        response = save_demographics_inline(uid, data)
        self._send_response_object(response)

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
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, status=400)


    # -------------------------
    # Update Permissions Handler
    # -------------------------

    def _handle_update_user_permission(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._send_401()
            return

        import json
        from app.handlers.users import handle_update_user_permission

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        data = json.loads(raw) if raw else {}

        response = handle_update_user_permission(uid, data)
        self._send_response_object(response)

    # -------------------------
    # Legal Save & Publish handler (POST)
    # -------------------------

    def _handle_legal_document_save(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        from app.handlers.legal_documents import handle_save_legal_draft

        result = handle_save_legal_draft(
            user_id=self._get_uid_from_cookie(),
            data=data,
        )

        self.send_response(200 if result["ok"] else 400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode("utf-8"))

    def _handle_legal_document_publish(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        from app.handlers.legal_documents import handle_publish_legal_document

        result = handle_publish_legal_document(
            user_id=self._get_uid_from_cookie(),
            data=data,
        )

        self.send_response(200 if result["ok"] else 400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode("utf-8"))

    # -------------------------
    # Contact Us handler (POST)
    # -------------------------
    def _handle_contact_us(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        uid = self._get_uid_from_cookie()  # may be None
        actor_ip = self.client_address[0] if self.client_address else ""

        from app.handlers.contact import handle_contact_post

        result = handle_contact_post(
            actor_uid=uid,
            form=data,
            actor_ip=actor_ip,
        )

        # handler returns either {"error": "..."} or {"success": True}
        if "error" in result:
            self.send_response(result.get("status", 400))
            self.end_headers()
            self.wfile.write(result["error"].encode("utf-8"))
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    # -------------------------
    # Bonus Survey Basics Save
    # -------------------------
    def _handle_bonus_survey_basics_save(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        from app.handlers.surveys import handle_bonus_survey_basics_post

        result = handle_bonus_survey_basics_post(
            user_id=uid,
            data=data,
        )

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def _handle_bonus_survey_create_new(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
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
    # Bonus Survey Template Save (AJAX)
    # -------------------------
    def _handle_bonus_survey_template_save(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(401)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length).decode("utf-8")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error":"Invalid JSON"}')
            return

        from app.handlers.surveys import handle_bonus_survey_template_post

        result = handle_bonus_survey_template_post(
            user_id=uid,
            data=data,
        )

        # Always return JSON for AJAX saves
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        self.wfile.write(json.dumps(result).encode("utf-8"))

    # -------------------------
    # Bonus Survey Targeting Save
    # -------------------------
    def _handle_bonus_survey_targeting_save(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(401)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = json.loads(body)

        from app.handlers.surveys import handle_bonus_survey_targeting_post

        result = handle_bonus_survey_targeting_post(
            user_id=uid,
            data=data,
        )

        # IMPORTANT: JSON response (not redirect)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode("utf-8"))

    # -------------------------
    # Bonus Survey Submit (POST)
    # -------------------------
    def _handle_bonus_survey_submit(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

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

    # -------------------------
    # Bonus Survey Approval (POST)
    # -------------------------
    def _handle_bonus_survey_approve(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        tracker_id = data.get("tracker_id", [None])[0]
        if not tracker_id:
            raise RuntimeError("tracker_id is required")

        from app.db.bonus_survey_tracker import add_tracker_entry_approved
        from app.db.surveys import set_bonus_survey_status_by_tracker

        add_tracker_entry_approved(
            tracker_id=int(tracker_id),
            actor_user_id=uid,
        )

        set_bonus_survey_status_by_tracker(
            tracker_id=int(tracker_id),
            new_status="active",
        )


        self.send_response(302)
        self.send_header("Location", "/surveys/bonus/pending")
        self.end_headers()

    # -------------------------
    # Bonus Survey Request Info (POST)
    # -------------------------

    def _handle_bonus_survey_request_info(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        tracker_id = data.get("tracker_id", [None])[0]
        detail_text = data.get("detail_text", [""])[0]

        if not tracker_id or not detail_text:
            raise RuntimeError("tracker_id and detail_text are required")

        from app.db.bonus_survey_tracker import (
            add_tracker_entry_info_requested,
        )

        add_tracker_entry_info_requested(
            tracker_id=int(tracker_id),
            actor_user_id=uid,
            detail_text=detail_text,
        )

        self.send_response(302)
        self.send_header("Location", "/surveys/bonus/pending")
        self.end_headers()

    # -------------------------
    # Bonus Survey Request Changes (POST)
    # -------------------------

    def _handle_bonus_survey_request_changes(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        tracker_id = data.get("tracker_id", [None])[0]
        detail_text = data.get("detail_text", [""])[0]

        if not tracker_id or not detail_text:
            raise RuntimeError("tracker_id and detail_text are required")

        from app.db.bonus_survey_tracker import (
            add_tracker_entry_changes_requested,
        )

        add_tracker_entry_changes_requested(
            tracker_id=int(tracker_id),
            actor_user_id=uid,
            detail_text=detail_text,
        )

        self.send_response(302)
        self.send_header("Location", "/surveys/bonus/pending")
        self.end_headers()

    def _handle_bonus_survey_take_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        params = urllib.parse.parse_qs(body)

        survey_id = params.get("survey_id", [None])[0]
        if not survey_id:
            self.send_response(302)
            self.send_header("Location", "/surveys/bonus/take")
            self.end_headers()
            return

        from app.db.bonus_survey_participation import (
            get_or_create_participation,
            mark_participation_seen,
        )
        from app.db.surveys import get_bonus_survey_by_id

        survey = get_bonus_survey_by_id(int(survey_id))
        if not survey or survey["status"] != "active":
            self.send_response(302)
            self.send_header("Location", "/surveys/bonus/take")
            self.end_headers()
            return

        participation = get_or_create_participation(
            bonus_survey_id=int(survey_id),
            user_id=uid,
        )

        mark_participation_seen(
            bonus_survey_id=int(survey_id),
            user_id=uid,
        )

        token = participation["participation_token"]

        survey_link = survey["survey_link"]
        join_char = "&" if "?" in survey_link else "?"
        redirect_url = f"{survey_link}{join_char}user_token={token}"

        self.send_response(302)
        self.send_header("Location", redirect_url)
        self.end_headers()

    # -------------------------
    # Product Team Request Trial (POST)
    # -------------------------

    def _handle_request_trial_create(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
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

    def _handle_product_request_trial_wizard_basics(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        from app.handlers.product_team import handle_product_request_trial_wizard_basics_post

        result = handle_product_request_trial_wizard_basics_post(
            user_id=uid,
            data=data,
        )

        if "error" in result:
            # placeholder – wire error rendering later
            self.send_response(400)
            self.end_headers()
            return

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    # -------------------------
    # Product Request Trial – Timing (POST)
    # -------------------------

    def _handle_product_request_trial_wizard_timing(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        from app.handlers.product_team import (
            handle_product_request_trial_wizard_timing_post,
        )

        result = handle_product_request_trial_wizard_timing_post(
            user_id=uid,
            data=data,
        )

        if "error" in result:
            self.send_response(400)
            self.end_headers()
            return

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def _handle_product_request_trial_wizard_stakeholders_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length).decode("utf-8")

        from urllib.parse import parse_qs
        data = parse_qs(raw)

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

        self._redirect("/product/request-trial")

    def _handle_product_request_trial_submit_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()

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

        self.send_error(400, result.get("error", "submission_failed"))

    def _handle_admin_approval_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()

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

        self.send_error(400, result.get("error", "approval_failed"))

    def _handle_product_request_trial_change_requested_respond_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()

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

        self._send_error(400, result.get("error", "submission_failed"))

    def _handle_product_request_trial_info_requested_respond_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()

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

        self.send_error(400, result.get("error", "submission_failed"))

    # -------------------------
    # UT Lead – Project Save (POST)
    # -------------------------

    def _handle_ut_lead_project_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()

        print("🔥 UT LEAD PROJECT POST HIT")
        print("ACTION:", data.get("action"))
        print("ROUND ID RAW:", data.get("round_id"))

        from app.handlers.user_trial_lead_project import (
            handle_ut_lead_project_post,
        )

        result = handle_ut_lead_project_post(
            user_id=uid,
            data=data,
        )

        print("🔁 POST RESULT:", result)

        if result and "redirect" in result:
            print("➡️ REDIRECTING TO:", result["redirect"])

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_error(400)

    # -------------------------
    # Trial Application Handler (POST)
    # -------------------------

    def _handle_trial_apply(self):

        uid = self._get_uid_from_cookie()

        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        round_id = int(self._get_post_param("round_id"))
        motivation = self._get_post_param("motivation_text")

        if not round_id:
            self.send_response(302)
            self.send_header("Location", "/trials/recruiting")
            self.end_headers()
            return

        from app.db.project_applicants import apply_for_trial

        apply_for_trial(
            user_id=uid,
            round_id=int(round_id),
            motivation=motivation
        )

        self.send_response(302)
        self.send_header("Location", "/trials/recruiting")
        self.end_headers()

    def _handle_trial_withdraw(self):

        uid = self._get_uid_from_cookie()

        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        round_id = int(self._get_post_param("round_id"))

        if not round_id:
            self.send_response(302)
            self.send_header("Location", "/trials/recruiting")
            self.end_headers()
            return

        from app.db.project_applicants import withdraw_application

        withdraw_application(
            user_id=uid,
            round_id=round_id
        )

        self.send_response(302)
        self.send_header("Location", "/trials/recruiting")
        self.end_headers()

    # -------------------------
    # Helpers
    # -------------------------

    def _get_base_html(self):
        base_html = BASE_TEMPLATE
        return self._inject_nav(base_html)

    def _get_uid_from_cookie(self) -> str | None:
        raw = self.headers.get("Cookie")
        if not raw:
            return None

        c = cookies.SimpleCookie()
        c.load(raw)

        morsel = c.get("uid")
        if not morsel:
            return None

        uid = morsel.value.strip()
        return uid or None
    
    def _is_logged_in(self) -> bool:
        return bool(self._get_uid_from_cookie())
    
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
        """
        from urllib.parse import parse_qs
        from email.parser import BytesParser
        from email.policy import default
        from io import BytesIO

        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))

        if content_length <= 0:
            return {}

        body = self.rfile.read(content_length)

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

            msg = BytesParser(policy=default).parsebytes(full_message)

            for part in msg.iter_parts():
                content_disposition = part.get("Content-Disposition", "")
                if not content_disposition:
                    continue

                dispositions = dict(
                    item.strip().split("=")
                    for item in content_disposition.split(";")[1:]
                    if "=" in item
                )

                name = dispositions.get("name")
                if not name:
                    continue

                name = name.strip('"')

                filename = dispositions.get("filename")
                payload = part.get_payload(decode=True)

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
        text = body.decode("utf-8")
        parsed = parse_qs(text)

        return {
            key: values[0] if len(values) == 1 else values
            for key, values in parsed.items()
        }

    def _render_content_page(self, page):
        lines = page["Content"].splitlines()
        html = []


        for line in lines:
            line = line.rstrip()

            if not line:
                html.append("<br>")
            elif line.startswith("## "):
                html.append(f"<h3>{line[3:]}</h3>")
            elif line.startswith("- "):
                html.append(f"<li>{line[2:]}</li>")
            else:
                html.append(f"<p>{line}</p>")

        content_html = "\n".join(html)

        # wrap orphan <li> blocks in <ul>
        content_html = content_html.replace(
            "</p>\n<li>", "</p>\n<ul><li>"
        ).replace(
            "</li>\n<p>", "</li></ul>\n<p>"
        )

        return f"""
            <h2>{page['Title']}</h2>
            {content_html}
        """

    def _inject_nav(self, base_html: str, mode: str = "user") -> str:
        print("NAV MODE CALLED:", mode)
        uid = self._get_uid_from_cookie()

        home_link = ""
        user_anchor = ""
        role_nav = ""

        # -------------------------
        # Mode: PUBLIC
        # -------------------------
        if mode == "public":
            base_html = base_html.replace("__HOME_LINK__", "")
            base_html = base_html.replace("__USER_ANCHOR__", "")
            base_html = base_html.replace("__ROLE_NAV__", "")
            return base_html

        # -------------------------
        # Mode: ONBOARDING
        # -------------------------
        if mode == "onboarding":
            home_link = '<a href="/">Home</a>'
            user_anchor = '<a href="/logout">Log out</a>'
            role_nav = ""

            base_html = base_html.replace("__HOME_LINK__", home_link)
            base_html = base_html.replace("__USER_ANCHOR__", user_anchor)
            base_html = base_html.replace("__ROLE_NAV__", role_nav)

            return base_html


        # -------------------------
        # Mode: AUTHENTICATED USER
        # -------------------------
        if uid:
            from app.db.user_pool import get_user_by_userid
            user = get_user_by_userid(uid)

            display_name = self._get_display_name(user) if user else "Account"

            home_link = '<a href="/">Home</a>'

            # ---- Notification scaffold ----
            from app.services.notifications import (
                get_unread_count,
                get_recent_notifications,
            )

            unread_count = get_unread_count(uid)
            notifications = get_recent_notifications(uid, limit=5)

            badge_html = ""
            if unread_count > 0:
                badge_html = (
                    f'<span class="notification-badge">'
                    f'{unread_count if unread_count < 10 else "9+"}'
                    f'</span>'
                )

            notifications = []

            try:
                notifications = get_all_notifications(uid, limit=5)
            except Exception as e:
                print("ERROR loading bell notifications:", e)

            dropdown_items = ""

            for n in notifications:

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

                    actions_html += f"""
                    <a class="dropdown-action" href="{href}">
                        {label}
                    </a>
                    """

                dropdown_items += f"""
                <div class="notification-dropdown-item">
                    <div class="notification-dropdown-title">{title}</div>
                    <div class="notification-dropdown-message">{message}</div>
                    <div class="notification-dropdown-actions">
                        {actions_html}
                    </div>
                </div>
                """

            notification_dropdown = f"""
            <div class="dropdown notification-menu">
                <a href="#" class="dropdown-trigger notification-bell">
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

            user_anchor = f"""
            {notification_dropdown}

            <div class="dropdown user-menu">
                <a href="#" class="dropdown-trigger user-anchor">
                    {display_name} ▾
                </a>

                <div class="dropdown-menu user-dropdown">
                    <a href="/my_trials">My Trials</a>
                    <hr>
                    <a href="/profile">Profile Summary</a>
                    <a href="/settings">Settings</a>
                    <hr>
                    <a href="/logout">Log out</a>
                </div>
            </div>
            """

            from app.db.user_roles import get_effective_permission_level
            from app.navigation.role_nav import build_role_nav

            permission_level = get_effective_permission_level(uid)
            role_nav = build_role_nav(permission_level=permission_level)

        else:
            user_anchor = '<a href="/login">Login</a>'


        base_html = base_html.replace("__HOME_LINK__", home_link)
        base_html = base_html.replace("__USER_ANCHOR__", user_anchor)
        base_html = base_html.replace("__ROLE_NAV__", role_nav)

        return base_html

    def _render_register_error(self, message, email=""):
        body_html = REGISTER_TEMPLATE

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
        html = base_html.replace("{{ body }}", body_html)
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
    
    def _send_response_object(self, response):
        """
        Accepts (status, headers, body) tuples.
        """
        status, headers, body = response

        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()

        if body:
            self.wfile.write(body.encode("utf-8"))

# -------------------------
# Server
# -------------------------
def run():
    server = ThreadingHTTPServer(("0.0.0.0", 8000), RequestHandler)
    print("Serving User Trials site at http://localhost:8000")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped by user")
        server.server_close()

if __name__ == "__main__":
    run()
