from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from os import path
from pathlib import Path
from unittest import result
from urllib.parse import urlparse, parse_qs
import multiprocessing

from app.db.content_pages import get_page_by_slug
from app.services.registration import register_user, RegistrationInput
from app.config.config import DEBUG as CONFIG_DEBUG
from app.config.config import SESSION_COOKIE_SECURE
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
from app.handlers.survey_upload import (
    render_survey_upload_get,
    handle_survey_upload_post,
)
from app.handlers.responsibilities import (
    render_responsibilities,
    handle_responsibilities,
)
from app.utils.html_escape import escape_html as e

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
        if path == "trials/nda":
            self._render_trial_nda()
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
        if path == "surveys/bonus/take":
            self._render_bonus_survey_take()
            return
        if path == "surveys/bonus/take/open":
            self._render_bonus_survey_take_open()
            return

        # ---- Notifcations
        if path == "/notifications":
            self._render_notifications()
            return
        if path == "/notifications/view":
            self._render_notification_view()
            return
        if path == "/notifications/dismiss":
            self._render_notifications()
            return
        if path == "/notifications/mark-read":
            self._render_notifications()
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
        if path == "trials/selection":
            self._render_user_selection()
            return
        if path == "trials/selection/confirm":
            self._render_user_selection_confirm()
            return
        if path.startswith("survey/upload"):
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
            self._debug_selection_test()
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
        # ---- Historical Create Context
        if path == "historical/create-context":
            self._render_historical_create_context()
            return
        # ---- Historical Context
        if path == "historical/context":
            self._render_historical_context()
            return
        # ---- Historical Raw Data
        if path == "historical/raw":
            self._render_historical_raw()
            return
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
    # Bonus Survey Upload View (GET)
    # -------------------------
    def _render_bonus_survey_upload(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
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

    def _render_admin_approval_project(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
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
    # UT Lead – All Trials Overview (GET)
    # -------------------------
    def _render_ut_lead_trials(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
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

        from urllib.parse import urlparse, parse_qs
        from app.handlers.user_selection import handle_user_selection_confirm_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        result = handle_user_selection_confirm_get(
            user_id=uid,
            query_params=query_params,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        # Fallback safety (should not happen)
        self._redirect("/trials/selection")

    def _render_survey_upload(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
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
    # Bonus Survey Structure (GET)
    # -------------------------

    def _render_bonus_survey_structure(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
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
        from app.handlers.historical import render_historical_context_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        context_id = int(query_params.get("context_id", [0])[0])

        if not context_id:
            self.send_response(302)
            self.send_header("Location", "/historical")
            self.end_headers()
            return

        result = render_historical_context_get(
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

    def _render_historical_create_context(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
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

        from urllib.parse import urlparse, parse_qs
        from app.handlers.historical import render_historical_raw_get

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        context_id = query_params.get("context_id", [None])[0]
        dataset_id = query_params.get("dataset_id", [None])[0]

        if not dataset_id:
            self.send_response(302)
            self.send_header("Location", "/historical")
            self.end_headers()
            return

        try:
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
            body = body.replace(
                "{{CONTACT_FORM}}",
                CONTACT_FORM_HTML
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

        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/register":
            self._handle_register()
            return
        if path == "/verify-email":
            self._handle_verify_email()
            return
        if path == "/demographics":
            self._handle_demographics()
            return
        if path == "/login":
            self._handle_login()
            return
        if path == "/nda":
            self._handle_nda()
            return
        if path == "/participation-guidelines":
            self._handle_guidelines()
            return
        if path == "/profile/interests":
            self._handle_profile_interests()
            return
        if path == "/profile/basic":
            self._handle_profile_basic()
            return
        if path == "/profile/advanced":
            self._handle_profile_advanced()
            return  
        if path == "/welcome":
            self._handle_welcome()
            return
        if path == "/settings":
            self._handle_settings_page()
            return
        if path == "/settings/password/change":
            self._handle_settings_password_change()
            return
        if path == "/settings/demographics/save":
            self._handle_settings_demographics_save()
            return
        if path == "/admin/users/update-permission":
            self._handle_update_user_permission()
            return
        if path == "/contact-us":
            self._handle_contact_us()
            return
        if path == "/legal/documents/save":
            self._handle_legal_document_save()
            return
        if path == "/legal/documents/publish":
            self._handle_legal_document_publish()
            return
        if path == "/surveys/bonus/create/save-basics":
            self._handle_bonus_survey_basics_save()
            return
        if path == "/surveys/bonus/create/new":
            self._handle_bonus_survey_create_new()
            return
        if path == "/surveys/bonus/create/save-template":
            self._handle_bonus_survey_template_save()
            return
        if path == "/surveys/bonus/create/save-targeting":
            self._handle_bonus_survey_targeting_save()
            return
        if path == "/surveys/bonus/take/open":
            self._handle_bonus_survey_take_open_post()
            return

        # -----------------------------
        # Bonus Approval actions (POST)
        # -----------------------------
        
        if path == "/surveys/bonus/approve":
            self._handle_bonus_survey_approve()
            return
        if path == "/surveys/bonus/request-changes":
            self._handle_bonus_survey_request_changes()
            return
        if path == "/surveys/bonus/request-info":
            self._handle_bonus_survey_request_info()
            return
        if path == "/surveys/bonus/create/submit":
            self._handle_bonus_survey_submit()
            return
        if path.startswith("/surveys/bonus/upload"):
            self._handle_bonus_survey_upload_post()
            return
        if path.startswith("/surveys/bonus/analyze"):
            self._handle_bonus_survey_analyze_post()
            return
        if path.startswith("/surveys/bonus/close"):
            self._handle_bonus_survey_close_post()
            return
        if path == "surveys/bonus/generate-sections":
            self._handle_bonus_survey_generate_sections_post()
            return
        # -----------------------------
        # Product Team Request Trial (POST)
        # -----------------------------

        if path == "/product/request-trial/create":
            self._handle_request_trial_create()
            return
        if path == "/product/request-trial/wizard/basics":
            self._handle_product_request_trial_wizard_basics()
            return
        if path == "/product/request-trial/wizard/timing":
            self._handle_product_request_trial_wizard_timing()
            return
        if path == "/product/request-trial/wizard/stakeholders":
            self._handle_product_request_trial_wizard_stakeholders_post()
            return
        if path == "/product/request-trial/submit":
            self._handle_product_request_trial_submit_post()
            return
        if path == "/admin/approvals/submit":
            self._handle_admin_approval_post()
            return
        if path == "/admin/approvals/bonus/submit":
            self._handle_admin_approval_post()
            return
        if path == "/product/request-trial/info-requested/respond":
            self._handle_product_request_trial_info_requested_respond_post()
            return
        if path == "/product/request-trial/change-requested/respond":
            self._handle_product_request_trial_change_requested_respond_post()
            return
        if path == "/admin/approval":
            self._handle_admin_approval_post()
            return

        # -----------------------------
        # UT Lead (POST)
        # -----------------------------

        if path == "/ut-lead/project":
            self._handle_ut_lead_project_post()
            return

        if path == "/trials/selection":
            self._handle_user_selection_post()
            return
        
        if path.startswith("/survey/upload"):
            self._handle_survey_upload_post()
            return
        # -----------------------------
        # User Application to UT (POST)
        # -----------------------------

        if path == "/trials/apply":
            self._handle_trial_apply()
            return

        if path == "/trials/withdraw":
            self._handle_trial_withdraw()
            return
        
        if path == "/trials/end-recruiting":
            self._handle_end_recruiting()
            return
        
        if path == "/trials/nda":
            self._handle_trial_nda_post()
            return
        
        # -----------------------------
        # User project round onboarding (POST)
        # -----------------------------

        if path == "/trials/confirm-shipping":
            self._handle_confirm_shipping()
            return
        if path == "/trials/responsibilities":
            self._handle_responsibilities()
            return
        if path == "/trials/save-shipping":
            self._handle_save_shipping()
            return


        # -----------------------------
        # Notifications (POST)
        # -----------------------------

        if path == "/notifications/view":
            self._handle_notification_view_post()
            return
        if path == "/notifications/dismiss":
            self._handle_dismiss_notification_post()
            return
        if path == "/notifications/mark-read":
            self._handle_mark_notifications_read_post()
            return

        # -----------------------------
        # Trials interest (POST)
        # -----------------------------
        if path == "/trials/interest":
            self._handle_trials_interest_post()
            return

        # -----------------------------
        # Trial Welcome (POST)
        # -----------------------------

        if path == "/welcome":
            self._handle_welcome_post()
            return
        
        # -----------------------------
        # Trial Selection Init (POST)
        # -----------------------------
        #         
        if path == "/trials/selection/init":
            self._handle_selection_init_post()
            return

        if path == "/trials/selection/confirm":
            self._handle_selection_confirm_post()
            return

        if path == "/trials/selection/confirm/post-bridge":
            self._render_selection_confirm_post_bridge()
            return
        
        # -----------------------------
        # Bonus Survey Structure (POST)
        # -----------------------------        
        if path == "/surveys/bonus/structure/generate":
            self._handle_bonus_survey_structure_generate()
            return
       
        if path == "/surveys/bonus/structure/reset":
            self._handle_bonus_survey_structure_reset()
            return
        
        if path == "/surveys/bonus/structure/classify-profile":
            self._handle_bonus_survey_structure_classify_profile()
            return

        if path == "/surveys/bonus/structure/save":
            self._handle_bonus_survey_structure_save()
            return
        
        if path == "/surveys/bonus/section/add":
            self._handle_bonus_survey_section_add()
            return

        if path == "/surveys/bonus/section/rename":
            self._handle_bonus_survey_section_rename()
            return

        if path == "/surveys/bonus/section/delete":
            self._handle_bonus_survey_section_delete()
            return

        # ---- Historical Upload
        if self.path == "/historical/upload":
            self._handle_historical_upload_post()
            return
        # ---- Historical Create Context
        if self.path == "/historical/create-context":
            self._handle_historical_create_context_post()
            return
        if self.path == "/products/create":
            self._handle_create_product()
            return
        # ---- Historical Generate Section Names
        if self.path == "/historical/generate-section-names":
            self._handle_generate_section_names_post()
            return
        # ---- Historical Generate Section Summaries
        if self.path == "/historical/generate-section-summaries":
            self._handle_generate_section_summaries_post()
            return
        # ---- Historical Generate Insights
        if self.path == "/historical/generate-insights":
            self._handle_generate_insights_post()
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

        result = handle_login_post(data, ip)

        if "error" in result:
            print(f"[LOGIN RESULT] FAILURE ip={ip} error={result['error']}")
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
    # Logout handler
    # -------------------------

    def _handle_logout(self):
        from app.services.session_service import delete_session

        raw = self.headers.get("Cookie")
        session_id = None
        if raw:
            parsed = cookies.SimpleCookie()
            parsed.load(raw)
            morsel = parsed.get("session_id")
            if morsel:
                session_id = morsel.value.strip() or None

        if session_id is not None:
            delete_session(session_id)

        c = cookies.SimpleCookie()
        c["session_id"] = ""
        c["session_id"]["path"] = "/"
        c["session_id"]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        c["session_id"]["max-age"] = 0
        c["session_id"]["samesite"] = "Lax"
        if SESSION_COOKIE_SECURE:
            c["session_id"]["secure"] = True

        self.send_response(302)
        self.send_header("Set-Cookie", c["session_id"].OutputString())
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
    # Settings Handler: Change Password
    # -------------------------

    def _handle_settings_password_change(self):
        user_id = self._get_uid_from_cookie()
        if not user_id:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()

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
        except Exception as e_err:
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

        response = {
            "ok": result.get("ok", False),
            "error": result.get("error"),
            "data": result if result.get("ok") else None,
        }

        self._send_json_response(
            response,
            status_code=200 if response["ok"] else 400
        )

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

        # Standardized JSON response

        if "error" in result:
            response = {
                "ok": False,
                "error": result.get("error"),
                "data": None,
            }

            self._send_json_response(
                response,
                status_code=result.get("status", 400)
            )
            return

        response = {
            "ok": True,
            "error": None,
            "data": result,
        }

        self._send_json_response(
            response,
            status_code=200
        )

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
    # Bonus Survey Template Save
    # -------------------------
    def _handle_bonus_survey_template_save(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

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
    def _handle_bonus_survey_targeting_save(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

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

    def _handle_bonus_survey_take_open_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        params = urllib.parse.parse_qs(body)

        survey_id = params.get("survey_id", [None])[0]
        if not survey_id or not str(survey_id).isdigit():
            self.send_response(302)
            self.send_header("Location", "/surveys/bonus/take")
            self.end_headers()
            return

        from app.handlers.surveys import handle_bonus_survey_take_open_post

        try:
            result = handle_bonus_survey_take_open_post(
                user_id=uid,
                survey_id=int(survey_id),
            )
        except Exception as err:
            print("[BONUS SURVEY OPEN ERROR]", err)
            result = {"redirect": "/surveys/bonus/take"}

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    # -------------------------
    # Bonus Survey Upload (POST)
    # -------------------------
    def _handle_bonus_survey_upload_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.surveys import handle_bonus_survey_upload_post

        result = handle_bonus_survey_upload_post(
            user_id=uid,
            handler=self,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # -------------------------
    # Bonus Survey Analyze (POST)
    # -------------------------
    def _handle_bonus_survey_analyze_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.surveys import handle_bonus_survey_analyze_post

        result = handle_bonus_survey_analyze_post(
            user_id=uid,
            handler=self,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        self._send_html(result["html"])

    # -------------------------
    # Bonus Survey Close (POST)
    # -------------------------
    def _handle_bonus_survey_close_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.surveys import handle_bonus_survey_close_post

        result = handle_bonus_survey_close_post(
            user_id=uid,
            handler=self,
        )

        if "redirect" in result:
            self.send_response(302)
            self.send_header("Location", result["redirect"])
            self.end_headers()
            return

        if "html" in result:
            self._send_html(result["html"])
            return

    # -------------------------
    # Bonus Survey Section Generator
    # -------------------------

    def _handle_bonus_survey_generate_sections_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()

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

        self._send_error(400)

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
    # UT Lead – User Selection (POST)
    # -------------------------

    def _handle_user_selection_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()

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

        self._send_404()

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

        # FIXED: do NOT cast here
        round_id_raw = self._get_post_param("round_id")
        motivation = self._get_post_param("motivation_text")

        if not round_id_raw:
            self.send_response(302)
            self.send_header("Location", "/trials/recruiting")
            self.end_headers()
            return

        try:
            round_id = int(round_id_raw)
        except ValueError:
            self.send_response(302)
            self.send_header("Location", "/trials/recruiting")
            self.end_headers()
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

            self.send_response(302)
            self.send_header("Location", survey_url)
            self.end_headers()
            return

        # 4. Fallback
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

    def _handle_end_recruiting(self):

        uid = self._get_uid_from_cookie()

        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        round_id_raw = self._get_post_param("round_id")

        try:
            round_id = int(round_id_raw)
        except:
            self.send_response(302)
            self.send_header("Location", "/dashboard")
            self.end_headers()
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

    def _handle_trial_nda_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()

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

    def _handle_survey_upload_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        data = self._parse_post_data()

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

        self._send_error(400)

    # -------------------------
    # Active Trials
    # -------------------------

    def _handle_confirm_shipping(self):
        user_id = self._get_uid_from_cookie()

        if not user_id:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        round_id_raw = self._get_post_param("round_id")

        if not round_id_raw:
            self.send_response(302)
            self.send_header("Location", "/trials/active")
            self.end_headers()
            return

        try:
            round_id = int(round_id_raw)
        except ValueError:
            self.send_response(302)
            self.send_header("Location", "/trials/active")
            self.end_headers()
            return

        from app.db.project_participants import confirm_shipping_address

        confirm_shipping_address(user_id=user_id, round_id=round_id)

        self.send_response(302)
        self.send_header("Location", f"/trials/active?round_id={round_id}")
        self.end_headers()

    def _handle_responsibilities(self):

        uid = self._get_uid_from_cookie()

        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # -------------------------
        # 🔥 Build data payload
        # -------------------------
        data = {
            "round_id": self._get_post_param("round_id"),
            "action": self._get_post_param("action") or self._get_post_param("decline_action"),
            "confirm_pickup": self._get_post_param("confirm_pickup"),
            "confirm_tracking": self._get_post_param("confirm_tracking"),
            "confirm_surveys": self._get_post_param("confirm_surveys"),
            "confirm_participation": self._get_post_param("confirm_participation"),
        }

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

    def _handle_save_shipping(self):

        user_id = self._get_uid_from_cookie()

        if not user_id:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # -------------------------
        # Collect POST data ONLY
        # -------------------------
        data = {
            "round_id": self._get_post_param("round_id"),
            "delivery_type": self._get_post_param("delivery_type"),
            "save_globally": self._get_post_param("save_globally"),
            "line1": self._get_post_param("line1"),
            "line2": self._get_post_param("line2"),
            "city": self._get_post_param("city"),
            "state": self._get_post_param("state"),
            "postal": self._get_post_param("postal"),
            "country": self._get_post_param("country"),
            "office_id": self._get_post_param("office_id"),

            # 🔥 NEW FIELDS
            "first_name": self._get_post_param("first_name"),
            "last_name": self._get_post_param("last_name"),
            "country_code": self._get_post_param("country_code"),
            "area_code": self._get_post_param("area_code"),
            "phone_number": self._get_post_param("phone_number"),
        }

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

    # ---- Mark notification read (POST)
    def _handle_notification_view_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from urllib.parse import parse_qs
        from app.db.notifications import mark_notification_read

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)
        notification_id = data.get("notification_id", [None])[0]

        if notification_id:
            mark_notification_read(
                notification_id=notification_id,
                user_id=uid,
            )

        target = f"/notifications/view?notification_id={notification_id}" if notification_id else "/notifications"
        self.send_response(302)
        self.send_header("Location", target)
        self.end_headers()


    # ---- Dismiss notification (POST)
    def _handle_dismiss_notification_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from urllib.parse import parse_qs
        from app.db.notifications import mark_notification_dismissed

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)
        notification_id = data.get("notification_id", [None])[0]

        if notification_id:
            mark_notification_dismissed(
                notification_id=notification_id,
                user_id=uid,
            )

        self.send_response(302)
        self.send_header("Location", "/notifications")
        self.end_headers()


    # ---- Mark all notifications read (POST)
    def _handle_mark_notifications_read_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.services.notifications import mark_all_notifications_read

        mark_all_notifications_read(uid)

        self.send_response(302)
        self.send_header("Location", "/notifications")
        self.end_headers()

    # ---- Record trial interest (POST)
    def _handle_trials_interest_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from urllib.parse import parse_qs
        from app.db.project_round_interest import record_round_interest

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        round_id = data.get("round_id", [None])[0]

        if round_id:
            record_round_interest(
                user_id=uid,
                round_id=int(round_id)
            )

        self.send_response(302)
        self.send_header("Location", "/trials/upcoming")
        self.end_headers()

    # ---- Welcome acknowledge (POST)
    def _handle_welcome_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # --------------------------------------------------
        # Correct imports (from your actual DB layer)
        # --------------------------------------------------
        from app.db.user_pool import mark_welcome_seen, get_user_by_userid
        from app.services.user_context import build_user_context

        # --------------------------------------------------
        # Mutate state (POST only)
        # --------------------------------------------------
        mark_welcome_seen(uid)

        # --------------------------------------------------
        # Resolve next step
        # --------------------------------------------------
        user = get_user_by_userid(uid)
        ctx = build_user_context(user)

        from urllib.parse import parse_qs

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        target = data.get("next", [ctx["routing"]["landing_path"]])[0]

        self.send_response(302)
        self.send_header("Location", target)
        self.end_headers()

    # ---- Selection session init (POST)
    def _handle_selection_init_post(self):

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
    def _handle_selection_confirm_post(self):

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

    def _render_selection_confirm_post_bridge(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self._redirect("/login")
            return

        from urllib.parse import urlparse, parse_qs
        from app.handlers.user_selection import render_selection_confirm_post_bridge

        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        try:
            session_id_raw = query_params.get("session_id", [None])[0]
            round_id_raw = query_params.get("round_id", [None])[0]

            session_id = int(session_id_raw)
            round_id = int(round_id_raw)
        except (TypeError, ValueError):
            self._redirect("/dashboard")
            return

        result = render_selection_confirm_post_bridge(
            session_id=session_id,
            round_id=round_id,
        )

        self._send_html(result["html"])

    # -------------------------
    # Bonus Survey Structure (Generate + Reset)
    # -------------------------

    def _handle_bonus_survey_structure_generate(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")

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

    def _handle_bonus_survey_structure_reset(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")

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

    def _handle_bonus_survey_structure_classify_profile(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")

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

    def _handle_bonus_survey_structure_save(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")

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

    def _handle_bonus_survey_section_add(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")

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

    def _handle_bonus_survey_section_rename(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")

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

    def _handle_bonus_survey_section_delete(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")

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
    def _handle_historical_upload_post(self):
        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        from app.handlers.historical import handle_historical_upload_post

        content_length = int(self.headers.get("Content-Length", 0))
        content_type = self.headers.get("Content-Type", "")

        raw_body = self.rfile.read(content_length)

        # -------------------------
        # MULTIPART PARSE
        # -------------------------
        if "multipart/form-data" in content_type:
            boundary = content_type.split("boundary=")[-1].encode()
            parts = raw_body.split(b"--" + boundary)

            parsed = {}

            for part in parts:
                if b"Content-Disposition" not in part:
                    continue

                headers, _, body = part.partition(b"\r\n\r\n")

                headers_str = headers.decode(errors="ignore")

                # Extract name
                import re
                name_match = re.search(r'name="([^"]+)"', headers_str)
                if not name_match:
                    continue

                name = name_match.group(1)

                # File field
                filename_match = re.search(r'filename="([^"]*)"', headers_str)

                if filename_match:
                    filename = filename_match.group(1)

                    parsed[name] = {
                        "filename": filename,
                        "file": body.rstrip(b"\r\n")
                    }
                else:
                    raw_value = body.decode(errors="ignore")

                    # 🔥 HARD CUT at first CRLF (actual field value ends here)
                    value = raw_value.split("\r\n")[0].strip()

                    parsed[name] = value

        else:
            # fallback (non-file POST)
            from urllib.parse import parse_qs
            parsed = {k: v[0] for k, v in parse_qs(raw_body.decode()).items()}

        result = handle_historical_upload_post(parsed)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def _handle_historical_create_context_post(self):

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

        from app.handlers.historical import handle_historical_create_context_post

        result = handle_historical_create_context_post(data)

        if "error" in result:
            self._redirect(f"/historical/create-context?error={result['error']}")
            return

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def _handle_generate_section_names_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()

        from app.handlers.historical import handle_generate_section_names_post

        result = handle_generate_section_names_post(data)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def _handle_generate_section_summaries_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()

        from app.handlers.historical import handle_generate_section_summaries_post

        result = handle_generate_section_summaries_post(data)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def _handle_generate_insights_post(self):

        uid = self._get_uid_from_cookie()
        if not uid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        data = self._parse_post_data()

        from app.handlers.historical import handle_generate_insights_post

        result = handle_generate_insights_post(data)

        self.send_response(302)
        self.send_header("Location", result["redirect"])
        self.end_headers()

    def _handle_create_product(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = parse_qs(body)

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

    def _get_uid_from_cookie(self) -> str | None:
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

        from app.services.session_service import get_user_from_session
        user_id = get_user_from_session(session_id)
        return user_id
    
    def _is_logged_in(self) -> bool:
        return bool(self._get_uid_from_cookie())
    
    def _redirect(self, location: str):
        """
        Standard redirect helper to enforce PRG pattern.
        """
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()    

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

    def _inject_nav(self, base_html: str, mode: str = "user") -> str:
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
            except Exception as e_err:
                print("ERROR loading bell notifications:", e_err)

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

                    safe_href = e(href) if href.startswith("/") else "#"

                    actions_html += f"""
                    <a class="dropdown-action" href="{safe_href}">
                        {e(label)}
                    </a>
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
                    {e(display_name)} ▾
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
