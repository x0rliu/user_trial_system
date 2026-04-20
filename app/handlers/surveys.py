# app/handlers/surveys.py

from pathlib import Path
from app.cache.surveys_cache import list_bonus_drafts_for_user
from app.cache.surveys_cache import (
    create_bonus_draft,
    get_bonus_draft,
)
from app.utils.html_escape import escape_html as e
from app.services.bonus_survey_summary import get_bonus_survey_summary
from app.services.bonus_survey_analysis import generate_bonus_survey_analysis
from app.services.bonus_survey_analysis_builder import build_bonus_survey_analysis_payload
from app.services.bonus_survey_insights_ai import generate_segment_insights


def _render_bonus_wizard_status(*, current_step: str, completed_steps: set[str], draft_id: str):
    """
    Render bonus survey drafting status nav.
    Render-only. No persistence. No inference.
    """

    if current_step == "submitted":
        return ""

    steps = [
        ("basics", "Basic Information", f"/surveys/bonus/create?draft={draft_id}"),
        ("template", "Survey Creation", f"/surveys/bonus/create/template?draft={draft_id}"),
        ("targeting", "Target Audience", f"/surveys/bonus/create/targeting?draft={draft_id}"),
        ("review", "Review", f"/surveys/bonus/create/review?draft={draft_id}"),
    ]

    items = []

    for key, label, href in steps:
        safe_href = e(href)
        safe_label = e(label)

        if key == current_step:
            items.append(
                f'<li class="wizard-step current">{safe_label}</li>'
            )
        elif key in completed_steps:
            items.append(
                f'<li class="wizard-step completed">'
                f'<a href="{safe_href}">{safe_label}</a>'
                f'</li>'
            )
        else:
            items.append(
                f'<li class="wizard-step future">{safe_label}</li>'
            )

    return f"""
    <nav class="wizard-status" aria-label="Bonus survey drafting progress">
        <ol>
            {''.join(items)}
        </ol>
    </nav>
    """

def render_bonus_surveys_get(*, user_id, base_template, inject_nav):
    """
    GET /surveys/bonus
    """
    try:
        bonus_base = Path(
            "app/templates/surveys/base_bonus_surveys.html"
        ).read_text(encoding="utf-8")

        bonus_layout = Path(
            "app/templates/surveys/bonus_layout.html"
        ).read_text(encoding="utf-8")

        from app.cache.surveys_cache import get_bonus_draft
        from app.db.surveys import (
            get_pending_bonus_surveys_for_user,
            get_active_bonus_surveys_for_user,
        )

        draft_ids = list_bonus_drafts_for_user(user_id)

        items = []

        if not draft_ids:
            drafting_html = (
                "<span class='rail-empty rail-item'>"
                "No drafts"
                "</span>"
            )
        else:
            for draft_id in draft_ids:
                draft = get_bonus_draft(user_id, draft_id)
                if not draft:
                    continue

                basics = draft.get("basics", {})
                display_name = basics.get("survey_name") or "Untitled Survey"

                safe_name = e(display_name)
                safe_href = e(f"/surveys/bonus/create/template?draft={draft_id}")

                items.append(
                    f"<a class='rail-item' href='{safe_href}'>"
                    f"{safe_name}"
                    f"</a>"
                )

            drafting_html = "".join(items)

        # -----------------------------
        # Pending Approval (DB-backed)
        # -----------------------------
        pending_surveys = get_pending_bonus_surveys_for_user(user_id)

        items = []

        if not pending_surveys:
            pending_html = (
                "<span class='rail-empty rail-item'>"
                "No surveys pending approval"
                "</span>"
            )
        else:
            for survey in pending_surveys:
                label = survey["survey_title"]
                survey_id = survey["bonus_survey_id"]

                safe_label = e(label)
                safe_href = e(f"/surveys/bonus/pending?survey_id={survey_id}")

                items.append(
                    f"<a class='rail-item' href='{safe_href}'>"
                    f"{safe_label}"
                    f"</a>"
                )

            pending_html = "".join(items)

        # -----------------------------
        # Active Surveys
        # -----------------------------
        active_surveys = get_active_bonus_surveys_for_user(user_id)

        if not active_surveys:
            active_html = (
                "<span class='rail-empty rail-item'>"
                "No active surveys"
                "</span>"
            )
        else:
            items = []
            for survey in active_surveys:
                label = survey["survey_title"]
                survey_id = survey["bonus_survey_id"]

                safe_label = e(label)
                safe_href = e(f"/surveys/bonus/active?survey_id={survey_id}")

                items.append(
                    f"<a class='rail-item' href='{safe_href}'>"
                    f"{safe_label}"
                    f"</a>"
                )

            active_html = "".join(items)

        bonus_content = """
        <h2>Bonus Surveys</h2>

        <div class="bonus-drafting">
            <p class="muted">
            Bonus Surveys are a fast way to send targeted surveys without setting up a full user trial.
            They’re ideal for quick questions, concept checks, or lightweight feedback.
            Create a draft, submit it for approval, and once approved your survey will be sent automatically.
            </p>
            <p class="muted small">
            Start here to create a new bonus survey.
            As you work, you’ll see your surveys move from drafting to pending approval and, once approved, to active.
            </p>
            <p class="muted small">
            This panel shows a live summary of your survey as you work through the setup steps.
            Your selections appear here automatically, and you can revise anything until the survey is submitted for approval.
            </p>
        </div>
        """

        body = bonus_layout.replace(
            "{{ BONUS_CONTENT }}",
            bonus_content,
        )
        body = body.replace("{{ WIZARD_STATUS }}", "")
        body = body.replace("{{ BONUS_DRAFTING }}", drafting_html)

        # Right rail summary (default state)
        default_summary = """
        <div class="bonus-summary">
            <h3>Summary</h3>
            <p class="muted small">
                Create or select a survey to see details.
            </p>
        </div>
        """

        # Support BOTH placeholders (prevents drift issues)
        body = body.replace("{{ BONUS_ACTIVE_SUMMARY }}", default_summary)
        body = body.replace("{{ BONUS_SUMMARY }}", default_summary)

        body = body.replace("{{ BONUS_PENDING }}", pending_html)
        body = body.replace("{{ BONUS_ACTIVE }}", active_html)

        html = bonus_base.replace("__BODY__", body)
        html = inject_nav(html)

        return {"html": html}

    except Exception as e_err:
        print("[ERROR] render_bonus_surveys_get failed:", repr(e_err))
        return {
            "html": f"""
            <html>
              <body style="font-family: system-ui; padding: 24px;">
                <h1>Bonus Surveys (Error)</h1>
                <pre>{e(repr(e_err))}</pre>
              </body>
            </html>
            """
        }

def render_bonus_survey_create_get(
    *,
    user_id,
    base_template,
    inject_nav,
    query_params: dict,
):
    from app.db.surveys import (
        get_pending_bonus_surveys_for_user,
        get_active_bonus_surveys_for_user,
    )

    # =====================================================
    # Templates
    # =====================================================
    bonus_base = Path(
        "app/templates/surveys/base_bonus_surveys.html"
    ).read_text(encoding="utf-8")

    bonus_layout = Path(
        "app/templates/surveys/bonus_layout.html"
    ).read_text(encoding="utf-8")

    basics_html = Path(
        "app/templates/surveys/bonus_create_basics.html"
    ).read_text(encoding="utf-8")

    # =====================================================
    # Draft context (HARD REQUIREMENT)
    # =====================================================
    draft_id = query_params.get("draft", [None])[0]

    if not draft_id:
        return {"redirect": "/surveys/bonus"}

    draft = get_bonus_draft(user_id, draft_id)
    if draft is None:
        return {"redirect": "/surveys/bonus"}

    basics = draft.get("basics", {}) or {}

    # =====================================================
    # Left rail — Drafting (cache)
    # =====================================================
    draft_ids = list_bonus_drafts_for_user(user_id)
    items = []

    if not draft_ids:
        drafting_html = (
            "<span class='rail-empty rail-item'>"
            "No drafts"
            "</span>"
        )
    else:
        for d in draft_ids:
            drow = get_bonus_draft(user_id, d)
            if not drow:
                continue

            d_basics = drow.get("basics", {}) or {}
            display_name = d_basics.get("survey_name") or "Untitled Survey"

            safe_name = e(display_name)
            safe_href = e(f"/surveys/bonus/create?draft={d}")

            items.append(
                f"<a class='rail-item' href='{safe_href}'>"
                f"{safe_name}"
                f"</a>"
            )

        drafting_html = "".join(items) if items else (
            "<span class='rail-empty rail-item'>"
            "No drafts"
            "</span>"
        )

    # =====================================================
    # Left rail — Pending Approval (DB)
    # =====================================================
    pending_surveys = get_pending_bonus_surveys_for_user(user_id)
    items = []

    if not pending_surveys:
        pending_html = (
            "<span class='rail-empty rail-item'>"
            "No surveys pending approval"
            "</span>"
        )
    else:
        for survey in pending_surveys:
            safe_label = e(survey["survey_title"])
            safe_href = e(f"/surveys/bonus/pending?survey_id={survey['bonus_survey_id']}")

            items.append(
                f"<a class='rail-item' href='{safe_href}'>"
                f"{safe_label}"
                f"</a>"
            )

        pending_html = "".join(items)

    # =====================================================
    # Left rail — Active (DB)
    # =====================================================
    active_surveys = get_active_bonus_surveys_for_user(user_id)
    items = []

    if not active_surveys:
        active_html = (
            "<span class='rail-empty rail-item'>"
            "No active surveys"
            "</span>"
        )
    else:
        for survey in active_surveys:
            safe_label = e(survey["survey_title"])
            safe_href = e(f"/surveys/bonus/active?survey_id={survey['bonus_survey_id']}")

            items.append(
                f"<a class='rail-item' href='{safe_href}'>"
                f"{safe_label}"
                f"</a>"
            )

        active_html = "".join(items)

    # =====================================================
    # Wizard + Summary
    # =====================================================
    wizard_status = _render_bonus_wizard_status(
        current_step="basics",
        completed_steps=set(),
        draft_id=draft_id,
    )

    summary_data = _project_bonus_summary_from_draft(draft)
    summary_html = _render_bonus_summary(summary_data)

    # =====================================================
    # Content — Hydrate Basics (CRITICAL: escape values)
    # =====================================================
    hydrated_basics = basics_html
    hydrated_basics = hydrated_basics.replace("{{ DRAFT_ID }}", e(draft_id))
    hydrated_basics = hydrated_basics.replace(
        "{{ SURVEY_NAME }}",
        e(basics.get("survey_name", ""))
    )
    hydrated_basics = hydrated_basics.replace(
        "{{ START_DATE }}",
        e(basics.get("start_date", ""))
    )
    hydrated_basics = hydrated_basics.replace(
        "{{ END_DATE }}",
        e(basics.get("end_date", ""))
    )
    hydrated_basics = hydrated_basics.replace(
        "{{ PURPOSE }}",
        e(basics.get("purpose", ""))
    )

    # =====================================================
    # Final Render
    # =====================================================
    body = bonus_layout.replace("{{ BONUS_CONTENT }}", hydrated_basics)
    body = body.replace("{{ WIZARD_STATUS }}", wizard_status)
    body = body.replace("{{ BONUS_DRAFTING }}", drafting_html)
    body = body.replace("{{ BONUS_PENDING }}", pending_html)
    body = body.replace("{{ BONUS_ACTIVE }}", active_html)
    body = body.replace("{{ BONUS_SUMMARY }}", summary_html)

    html = bonus_base.replace("__BODY__", body)
    html = inject_nav(html)

    return {"html": html}



def render_bonus_survey_template_get(
    *,
    user_id,
    base_template,
    inject_nav,
    query_params: dict,
):
    """
    GET /surveys/bonus/create/template
    Render-only instructional step for Google Forms template usage.
    """

    try:
        bonus_base = Path(
            "app/templates/surveys/base_bonus_surveys.html"
        ).read_text(encoding="utf-8")

        bonus_layout = Path(
            "app/templates/surveys/bonus_layout.html"
        ).read_text(encoding="utf-8")

        template_html = Path(
            "app/templates/surveys/bonus_create_template.html"
        ).read_text(encoding="utf-8")

        # --------------------------------------------------
        # Draft resolution (MUST happen first)
        # --------------------------------------------------
        draft_id = query_params.get("draft", [None])[0]
        if not draft_id:
            return {"redirect": "/surveys/bonus"}

        draft = get_bonus_draft(user_id, draft_id)
        if draft is None:
            return {"redirect": "/surveys/bonus"}

        # --------------------------------------------------
        # Wizard + summary
        # --------------------------------------------------
        wizard_status = _render_bonus_wizard_status(
            current_step="template",
            completed_steps={"basics"},
            draft_id=draft_id,
        )

        summary_data = _project_bonus_summary_from_draft(draft)
        summary_html = _render_bonus_summary(summary_data)

        # --------------------------------------------------
        # Left rail – Drafting
        # --------------------------------------------------
        from app.cache.surveys_cache import list_bonus_drafts_for_user
        from app.db.surveys import (
            get_pending_bonus_surveys_for_user,
            get_active_bonus_surveys_for_user,
        )

        draft_ids = list_bonus_drafts_for_user(user_id)
        items = []

        if not draft_ids:
            drafting_html = (
                "<span class='rail-empty rail-item'>"
                "No drafts"
                "</span>"
            )
        else:
            for d in draft_ids:
                drow = get_bonus_draft(user_id, d)
                if not drow:
                    continue

                basics = drow.get("basics", {}) or {}
                display_name = basics.get("survey_name") or "Untitled Survey"

                safe_name = e(display_name)
                safe_href = e(f"/surveys/bonus/create?draft={d}")

                items.append(
                    f"<a class='rail-item' href='{safe_href}'>"
                    f"{safe_name}"
                    f"</a>"
                )

            drafting_html = "".join(items)

        # --------------------------------------------------
        # Left rail – Pending Approval
        # --------------------------------------------------
        pending_surveys = get_pending_bonus_surveys_for_user(user_id)
        items = []

        if not pending_surveys:
            pending_html = (
                "<span class='rail-empty rail-item'>"
                "No surveys pending approval"
                "</span>"
            )
        else:
            for survey in pending_surveys:
                safe_label = e(survey["survey_title"])
                safe_href = e(f"/surveys/bonus/pending?survey_id={survey['bonus_survey_id']}")

                items.append(
                    f"<a class='rail-item' href='{safe_href}'>"
                    f"{safe_label}"
                    f"</a>"
                )

            pending_html = "".join(items)

        # --------------------------------------------------
        # Left rail – Active
        # --------------------------------------------------
        active_surveys = get_active_bonus_surveys_for_user(user_id)

        if not active_surveys:
            active_html = (
                "<span class='rail-empty rail-item'>"
                "No active surveys"
                "</span>"
            )
        else:
            items = []
            for survey in active_surveys:
                safe_label = e(survey["survey_title"])
                safe_href = e(f"/surveys/bonus/active?survey_id={survey['bonus_survey_id']}")

                items.append(
                    f"<a class='rail-item' href='{safe_href}'>"
                    f"{safe_label}"
                    f"</a>"
                )

            active_html = "".join(items)

        # --------------------------------------------------
        # Template hydration (CRITICAL FIX)
        # --------------------------------------------------
        template_html = template_html.replace(
            "{{ DRAFT_ID }}",
            e(draft_id),
        )

        template_data = draft.get("template", {}) or {}
        survey_link = template_data.get("survey_link", "")

        template_html = template_html.replace(
            "{{ SURVEY_LINK }}",
            e(survey_link or ""),
        )

        # --------------------------------------------------
        # Final render
        # --------------------------------------------------
        body = bonus_layout.replace(
            "{{ BONUS_CONTENT }}",
            template_html,
        )
        body = body.replace("{{ WIZARD_STATUS }}", wizard_status)
        body = body.replace("{{ BONUS_DRAFTING }}", drafting_html)
        body = body.replace("{{ BONUS_SUMMARY }}", summary_html)
        body = body.replace("{{ BONUS_PENDING }}", pending_html)
        body = body.replace("{{ BONUS_ACTIVE }}", active_html)

        html = bonus_base.replace("__BODY__", body)
        html = inject_nav(html)

        return {"html": html}

    except Exception as e_err:
        print("[ERROR] render_bonus_survey_template_get failed:", repr(e_err))
        return {
            "html": f"""
            <html>
              <body style="font-family: system-ui; padding: 24px;">
                <h1>Bonus Survey – Template (Error)</h1>
                <pre>{e(repr(e_err))}</pre>
              </body>
            </html>
            """
        }


def render_ut_surveys_get(*, user_id, base_template, inject_nav):
    from app.db.user_roles import get_effective_permission_level

    permission_level = get_effective_permission_level(user_id)

    if permission_level < 70:
        content = """
        <h1>User Trial Surveys</h1>
        <p class="muted">You do not have access to manage User Trial survey uploads.</p>
        """
    else:
        content = """
        <h1>User Trial Surveys</h1>

        <section class="card" style="max-width: 920px;">
          <h2>Upload Survey Results (Google Forms CSV)</h2>
          <p class="muted">
            This ingests the CSV into the database and stores a SHA256 hash for duplicate protection.
            The raw CSV file is not stored on the server.
          </p>

          <form action="/surveys/ut/upload-results" method="post" enctype="multipart/form-data">
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <label>
                <div>Project ID</div>
                <input name="project_id" type="text" placeholder="ProjectID" required>
              </label>

              <label>
                <div>Round ID</div>
                <input name="round_id" type="number" placeholder="1" required>
              </label>
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px;">
              <label>
                <div>Survey Type ID</div>
                <input name="survey_type_id" type="text" placeholder="UTSurveyType0001" required>
              </label>

              <label>
                <div>Survey Title (optional)</div>
                <input name="survey_title" type="text" placeholder="Fujian – Final Usage – Survey 2">
              </label>
            </div>

            <div style="margin-top: 12px;">
              <label>
                <div>CSV File</div>
                <input name="csv_file" type="file" accept=".csv" required>
              </label>
            </div>

            <div style="margin-top: 16px;">
              <button type="submit">Upload and Ingest</button>
            </div>
          </form>
        </section>
        """

    html = base_template.replace(
        "__BODY__",
        content,
    )

    html = inject_nav(html)

    return {"html": html}


def render_recruitment_surveys_get(*, user_id, base_template, inject_nav):
    """
    Static page.
    No user data.
    No escaping required.
    """

    content = """
    <h1>Recruitment Surveys</h1>
    <p>This section will manage recruitment surveys.</p>
    """

    html = base_template.replace("__BODY__", content)
    html = inject_nav(html)

    return {"html": html}

def render_bonus_survey_review_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict,
) -> dict:
    """
    GET /surveys/bonus/create/review
    Wizard Step 4: Review (render-only).
    """

    try:
        bonus_base = Path(
            "app/templates/surveys/base_bonus_surveys.html"
        ).read_text(encoding="utf-8")

        bonus_layout = Path(
            "app/templates/surveys/bonus_layout.html"
        ).read_text(encoding="utf-8")

        review_html = Path(
            "app/templates/surveys/bonus_create_review.html"
        ).read_text(encoding="utf-8")

        # --------------------------------------------------
        # Draft resolution
        # --------------------------------------------------
        draft_id = query_params.get("draft", [None])[0]
        if not draft_id:
            return {"redirect": "/surveys/bonus"}

        draft = get_bonus_draft(user_id, draft_id)
        if draft is None:
            return {"redirect": "/surveys/bonus"}

        review_html = review_html.replace(
            "{{ DRAFT_ID }}",
            e(draft_id),
        )

        # --------------------------------------------------
        # Hydrate review content
        # --------------------------------------------------
        basics = draft.get("basics", {}) or {}
        template = draft.get("template", {}) or {}

        summary_data = _project_bonus_summary_from_draft(draft)

        review_html = review_html.replace(
            "class=\"value survey-name\">—",
            f"class=\"value survey-name\">{e(basics.get('survey_name', '—'))}",
        )

        review_html = review_html.replace(
            "class=\"value start-date\">—",
            f"class=\"value start-date\">{e(basics.get('start_date', '—'))}",
        )

        review_html = review_html.replace(
            "class=\"value end-date\">—",
            f"class=\"value end-date\">{e(basics.get('end_date', '—'))}",
        )

        review_html = review_html.replace(
            "class=\"value purpose\">—",
            f"class=\"value purpose\">{e(basics.get('purpose', '—'))}",
        )

        review_html = review_html.replace(
            "{{ SURVEY_LINK }}",
            e(template.get("survey_link", "—")),
        )

        review_html = review_html.replace(
            "class=\"value targeting-summary\">—",
            f"class=\"value targeting-summary\">{e(summary_data.get('targeting_summary', '—'))}",
        )

        # --------------------------------------------------
        # Wizard + summary
        # --------------------------------------------------
        wizard_status = _render_bonus_wizard_status(
            current_step="review",
            completed_steps={"basics", "template", "targeting"},
            draft_id=draft_id,
        )

        summary_html = _render_bonus_summary(summary_data)

        # --------------------------------------------------
        # Left rail – Drafting
        # --------------------------------------------------
        from app.db.surveys import (
            get_pending_bonus_surveys_for_user,
            get_active_bonus_surveys_for_user,
        )

        draft_ids = list_bonus_drafts_for_user(user_id)
        items = []

        if not draft_ids:
            drafting_html = (
                "<span class='rail-empty rail-item'>"
                "No drafts"
                "</span>"
            )
        else:
            for d in draft_ids:
                drow = get_bonus_draft(user_id, d)
                if not drow:
                    continue

                d_basics = drow.get("basics", {}) or {}
                display_name = d_basics.get("survey_name") or "Untitled Survey"

                safe_name = e(display_name)
                safe_href = e(f"/surveys/bonus/create/review?draft={d}")

                items.append(
                    f"<a class='rail-item' href='{safe_href}'>"
                    f"{safe_name}"
                    f"</a>"
                )

            drafting_html = "".join(items)

        # --------------------------------------------------
        # Left rail – Pending
        # --------------------------------------------------
        pending_surveys = get_pending_bonus_surveys_for_user(user_id)
        items = []

        if not pending_surveys:
            pending_html = (
                "<span class='rail-empty rail-item'>"
                "No surveys pending approval"
                "</span>"
            )
        else:
            for survey in pending_surveys:
                safe_label = e(survey["survey_title"])
                safe_href = e(f"/surveys/bonus/pending?survey_id={survey['bonus_survey_id']}")

                items.append(
                    f"<a class='rail-item' href='{safe_href}'>"
                    f"{safe_label}"
                    f"</a>"
                )

            pending_html = "".join(items)

        # --------------------------------------------------
        # Left rail – Active
        # --------------------------------------------------
        active_surveys = get_active_bonus_surveys_for_user(user_id)

        if not active_surveys:
            active_html = (
                "<span class='rail-empty rail-item'>"
                "No active surveys"
                "</span>"
            )
        else:
            items = []
            for survey in active_surveys:
                safe_label = e(survey["survey_title"])
                safe_href = e(f"/surveys/bonus/active?survey_id={survey['bonus_survey_id']}")

                items.append(
                    f"<a class='rail-item' href='{safe_href}'>"
                    f"{safe_label}"
                    f"</a>"
                )

            active_html = "".join(items)

        # --------------------------------------------------
        # Final render
        # --------------------------------------------------
        body = bonus_layout.replace("{{ BONUS_CONTENT }}", review_html)
        body = body.replace("{{ WIZARD_STATUS }}", wizard_status)
        body = body.replace("{{ BONUS_DRAFTING }}", drafting_html)
        body = body.replace("{{ BONUS_SUMMARY }}", "")
        body = body.replace("{{ BONUS_PENDING }}", pending_html)
        body = body.replace("{{ BONUS_ACTIVE }}", active_html)

        html = bonus_base.replace("__BODY__", body)
        html = inject_nav(html)

        return {"html": html}

    except Exception as e_err:
        print("[ERROR] render_bonus_survey_review_get failed:", repr(e_err))
        return {
            "html": f"""
            <html>
              <body style="font-family: system-ui; padding: 24px;">
                <h1>Bonus Survey – Review (Error)</h1>
                <pre>{e(repr(e_err))}</pre>
              </body>
            </html>
            """
        }

def render_bonus_survey_submitted_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict,
) -> dict:
    """
    GET /surveys/bonus/submitted
    Read-only receipt view rendered from DB.
    """

    from app.cache.surveys_cache import get_bonus_draft
    from app.db.surveys import (
        get_bonus_survey_by_id,
        get_bonus_survey_targeting_rules,
        get_pending_bonus_surveys_for_user,
    )

    try:
        bonus_base = Path(
            "app/templates/surveys/base_bonus_surveys.html"
        ).read_text(encoding="utf-8")

        bonus_layout = Path(
            "app/templates/surveys/bonus_layout.html"
        ).read_text(encoding="utf-8")

        submitted_html = Path(
            "app/templates/surveys/bonus_create_submitted.html"
        ).read_text(encoding="utf-8")

        # --------------------------------------------------
        # Resolve draft → DB survey
        # --------------------------------------------------
        draft_id = query_params.get("draft", [None])[0]
        if not draft_id:
            return {"redirect": "/surveys/bonus"}

        draft = get_bonus_draft(user_id, draft_id)
        if draft is None:
            return {"redirect": "/surveys/bonus"}

        bonus_survey_id = draft.get("bonus_survey_id")
        if not bonus_survey_id:
            raise RuntimeError("Submitted survey missing bonus_survey_id")

        survey = get_bonus_survey_by_id(bonus_survey_id)
        if not survey:
            raise RuntimeError(
                f"BonusSurveyID {bonus_survey_id} not found in DB"
            )

        rules = get_bonus_survey_targeting_rules(bonus_survey_id)

        # --------------------------------------------------
        # Targeting reconstruction
        # --------------------------------------------------
        targeting = {}

        for r in rules:
            criterion = r["Criterion"]
            value = r["Value"]
            operator = r["Operator"]

            if criterion == "age":
                if operator == ">=":
                    targeting["age_min"] = value
                elif operator == "<=":
                    targeting["age_max"] = value

            elif criterion == "region":
                targeting.setdefault("regions", []).append(value)

            elif criterion == "job_function":
                targeting.setdefault("job_functions", []).append(value)

            elif criterion == "primary_os":
                targeting.setdefault("primary_os", []).append(value)

            elif criterion == "phone_os":
                targeting.setdefault("phone_os", []).append(value)

            elif criterion == "gender":
                targeting.setdefault("genders", []).append(value)

        summary_data = {
            "survey_name": survey["survey_title"],
            "start_date": str(survey["open_at"]) if survey["open_at"] else "—",
            "end_date": str(survey["close_at"]) if survey["close_at"] else "—",
            "purpose": survey["response_destination"] or "—",
            "survey_url": survey["survey_link"],
            "targeting_summary": _project_bonus_summary_from_draft(
                {"targeting": targeting}
            ).get("targeting_summary", "All users"),
        }

        # --------------------------------------------------
        # Hydrate template (ESCAPED)
        # --------------------------------------------------
        submitted_html = submitted_html.replace(
            'class="value survey-name">—',
            f'class="value survey-name">{e(summary_data["survey_name"])}',
        )

        submitted_html = submitted_html.replace(
            'class="value start-date">—',
            f'class="value start-date">{e(summary_data["start_date"])}',
        )

        submitted_html = submitted_html.replace(
            'class="value end-date">—',
            f'class="value end-date">{e(summary_data["end_date"])}',
        )

        submitted_html = submitted_html.replace(
            'class="value purpose">—',
            f'class="value purpose">{e(summary_data["purpose"])}',
        )

        submitted_html = submitted_html.replace(
            'class="value form-url">—',
            f'class="value form-url">{e(summary_data["survey_url"])}',
        )

        submitted_html = submitted_html.replace(
            'class="value targeting-summary">—',
            f'class="value targeting-summary">{e(summary_data["targeting_summary"])}',
        )

        # --------------------------------------------------
        # Wizard status
        # --------------------------------------------------
        wizard_status = _render_bonus_wizard_status(
            current_step="submitted",
            completed_steps={
                "basics",
                "template",
                "targeting",
                "review",
                "submitted",
            },
            draft_id=draft_id,
        )

        # --------------------------------------------------
        # Pending rail (ESCAPED)
        # --------------------------------------------------
        pending_surveys = get_pending_bonus_surveys_for_user(user_id)

        pending_html = (
            "<span class='rail-empty rail-item'>"
            "No surveys pending approval"
            "</span>"
        )

        if pending_surveys:
            items = []
            current_id = str(bonus_survey_id)

            for s in pending_surveys:
                is_current = str(s["bonus_survey_id"]) == current_id

                safe_label = e(s["survey_title"])
                safe_href = e(f"/surveys/bonus/pending?survey_id={s['bonus_survey_id']}")

                if is_current:
                    safe_label = f"<strong>{safe_label}</strong>"

                items.append(
                    f"<a class='rail-item' href='{safe_href}'>"
                    f"{safe_label}"
                    f"</a>"
                )

            pending_html = "".join(items)

        # --------------------------------------------------
        # Final render
        # --------------------------------------------------
        body = bonus_layout.replace("{{ BONUS_CONTENT }}", submitted_html)
        body = body.replace("{{ WIZARD_STATUS }}", wizard_status)
        body = body.replace(
            "{{ BONUS_DRAFTING }}",
            "<span class='rail-empty rail-item'>No drafts</span>",
        )
        body = body.replace("{{ BONUS_SUMMARY }}", "")
        body = body.replace("{{ BONUS_PENDING }}", pending_html)
        body = body.replace(
            "{{ BONUS_ACTIVE }}",
            "<span class='rail-empty rail-item'>No active surveys</span>",
        )

        html = bonus_base.replace("__BODY__", body)
        html = inject_nav(html)

        return {"html": html}

    except Exception as e_err:
        print("[ERROR] render_bonus_survey_submitted_get failed:", repr(e_err))
        return {
            "html": f"""
            <html>
              <body style="font-family: system-ui; padding: 24px;">
                <h1>Bonus Survey – Submitted (Error)</h1>
                <pre>{e(repr(e_err))}</pre>
              </body>
            </html>
            """
        }


def _render_bonus_summary(summary: dict) -> str:
    template = Path(
        "app/templates/surveys/bonus_summary.html"
    ).read_text(encoding="utf-8")

    fields = [
        "survey_name",
        "start_date",
        "end_date",
        "purpose",
        "survey_url",
        "targeting_summary",
    ]

    for field in fields:
        raw_value = summary.get(field) or "—"
        safe_value = e(str(raw_value))

        template = template.replace(
            f"{{{{ {field} }}}}",
            safe_value
        )

    return template


def handle_bonus_survey_basics_post(*, user_id: str, data: dict) -> dict:

    from app.cache.surveys_cache import (
        update_bonus_draft,
        get_bonus_draft,
    )

    survey_name = data.get("survey_name", [""])[0].strip()
    start_date = data.get("start_date", [""])[0]
    end_date = data.get("end_date", [""])[0]
    purpose = data.get("purpose", [""])[0].strip()

    draft_id = data.get("draft_id", [None])[0]

#    print("[DEBUG basics_save drafts_for_user]", list_bonus_drafts_for_user(user_id))
#    print("[DEBUG basics_save draft_id]", draft_id)
#    print("[DEBUG POST data]", data)
#    print("[DEBUG basics_save user_id]", user_id)

    if not isinstance(draft_id, str):
        raise RuntimeError("draft_id must be a string")

    # 🔐 HARD REQUIREMENT
    if not draft_id:
        raise RuntimeError("Missing draft_id in basics save")

    draft = get_bonus_draft(user_id, draft_id)
    if draft is None:
        raise RuntimeError("Draft not found")

    status = draft.get("status", "draft")
    if status != "draft":
        raise RuntimeError("Draft is locked and cannot be modified")

    update_bonus_draft(
        user_id,
        draft_id,
        {
            "basics": {
                "survey_name": survey_name,
                "start_date": start_date,
                "end_date": end_date,
                "purpose": purpose,
            }
        },
    )

    return {
        "redirect": f"/surveys/bonus/create/template?draft={draft_id}"
    }


def handle_bonus_survey_template_post(*, user_id: str, data: dict) -> dict:
    from app.cache.surveys_cache import update_bonus_draft, get_bonus_draft

    draft_id = data.get("draft_id")
    if not isinstance(draft_id, str) or not draft_id:
        raise RuntimeError("Missing or invalid draft_id in template save")
    
    survey_link = data.get("survey_link", "").strip()

    if not draft_id:
        raise RuntimeError("Missing draft_id in template save")

    draft = get_bonus_draft(user_id, draft_id)
    if draft is None:
        raise RuntimeError("Draft not found")

    status = draft.get("status", "draft")
    if status != "draft":
        raise RuntimeError("Draft is locked and cannot be modified")

    if not survey_link:
        raise RuntimeError("Missing survey_link")

    update_bonus_draft(
        user_id,
        draft_id,
        {
            "template": {
                "survey_link": survey_link,
            }
        },
    )

    return {"success": True}


def _project_bonus_summary_from_draft(draft: dict) -> dict:
    """
    Project draft data into flat summary fields.
    Draft remains canonical. This is read-only projection.
    """

    basics = draft.get("basics", {}) or {}
    template = draft.get("template", {}) or {}
    targeting = draft.get("targeting", {}) or {}

    # ---- Survey link (Step 2) ----
    survey_url = template.get("survey_link", "—")

    targeting_parts = []

    # ---- Age range ----
    age_min = targeting.get("age_min")
    age_max = targeting.get("age_max")
    if age_min or age_max:
        targeting_parts.append(
            f"Age {age_min or '—'}–{age_max or '—'}"
        )

    # ---- Regions ----
    regions = targeting.get("regions") or []
    if regions:
        targeting_parts.append("Regions: " + ", ".join(regions))

    # ---- Job functions ----
    job_functions = targeting.get("job_functions") or []
    if job_functions:
        targeting_parts.append("Roles: " + ", ".join(job_functions))

    # ---- Primary OS ----
    primary_os = targeting.get("primary_os") or []
    if primary_os:
        targeting_parts.append("OS: " + ", ".join(primary_os))

    # ---- Phone OS ----
    phone_os = targeting.get("phone_os") or []
    if phone_os:
        targeting_parts.append("Phone: " + ", ".join(phone_os))

    # ---- User type ----
    user_types = targeting.get("user_types") or []
    if user_types:
        targeting_parts.append("Users: " + ", ".join(user_types))

    # ---- Gender ----
    genders = targeting.get("genders") or []
    if genders:
        targeting_parts.append("Gender: " + ", ".join(genders))

    targeting_summary = (
        "; ".join(targeting_parts)
        if targeting_parts
        else "All users"
    )

    return {
        "survey_name": basics.get("survey_name", ""),
        "start_date": basics.get("start_date", ""),
        "end_date": basics.get("end_date", ""),
        "purpose": basics.get("purpose", ""),
        "survey_url": survey_url,
        "targeting_summary": targeting_summary,
    }


def render_bonus_survey_targeting_get(
    *,
    user_id,
    base_template,
    inject_nav,
    query_params: dict,
):
    """
    GET /surveys/bonus/create/targeting
    Intended audience definition step.
    """

    try:
        from pathlib import Path
        from app.cache.surveys_cache import get_bonus_draft, list_bonus_drafts_for_user
        from app.db.surveys import (
            get_pending_bonus_surveys_for_user,
            get_active_bonus_surveys_for_user,
        )

        bonus_base = Path(
            "app/templates/surveys/base_bonus_surveys.html"
        ).read_text(encoding="utf-8")

        bonus_layout = Path(
            "app/templates/surveys/bonus_layout.html"
        ).read_text(encoding="utf-8")

        targeting_html = Path(
            "app/templates/surveys/bonus_create_targeting.html"
        ).read_text(encoding="utf-8")

        draft_id = query_params.get("draft", [None])[0]
        if not draft_id:
            return {"redirect": "/surveys/bonus"}

        draft = get_bonus_draft(user_id, draft_id)
        if draft is None:
            return {"redirect": "/surveys/bonus"}

        targeting_html = targeting_html.replace(
            "{{ DRAFT_ID }}",
            e(draft_id),
        )

        wizard_status = _render_bonus_wizard_status(
            current_step="targeting",
            completed_steps={"basics", "template"},
            draft_id=draft_id,
        )

        summary_data = _project_bonus_summary_from_draft(draft)
        summary_html = _render_bonus_summary(summary_data)

        draft_ids = list_bonus_drafts_for_user(user_id)

        if not draft_ids:
            drafting_html = (
                "<span class='rail-empty rail-item'>"
                "No drafts"
                "</span>"
            )
        else:
            items = []

            for d in draft_ids:
                d_draft = get_bonus_draft(user_id, d)
                if not d_draft:
                    continue

                basics = d_draft.get("basics", {}) or {}
                name = basics.get("survey_name")

                label = (
                    name.strip()
                    if isinstance(name, str) and name.strip()
                    else f"Draft {d[:8]}"
                )

                safe_label = e(label)
                safe_href = e(f"/surveys/bonus/create?draft={d}")

                items.append(
                    f"<a class='rail-item' href='{safe_href}'>"
                    f"{safe_label}"
                    f"</a>"
                )

            drafting_html = "".join(items)

        pending_surveys = get_pending_bonus_surveys_for_user(user_id)

        if not pending_surveys:
            pending_html = (
                "<span class='rail-empty rail-item'>"
                "No surveys pending approval"
                "</span>"
            )
        else:
            items = []

            for s in pending_surveys:
                safe_label = e(s["survey_title"])
                safe_href = e(
                    f"/surveys/bonus/pending?survey_id={s['bonus_survey_id']}"
                )

                items.append(
                    f"<a class='rail-item' href='{safe_href}'>"
                    f"{safe_label}"
                    f"</a>"
                )

            pending_html = "".join(items)

        active_surveys = get_active_bonus_surveys_for_user(user_id)

        if not active_surveys:
            active_html = (
                "<span class='rail-empty rail-item'>"
                "No active surveys"
                "</span>"
            )
        else:
            items = []

            for s in active_surveys:
                safe_label = e(s["survey_title"])
                safe_href = e(
                    f"/surveys/bonus/active?survey_id={s['bonus_survey_id']}"
                )

                items.append(
                    f"<a class='rail-item' href='{safe_href}'>"
                    f"{safe_label}"
                    f"</a>"
                )

            active_html = "".join(items)

        body = bonus_layout.replace("{{ BONUS_CONTENT }}", targeting_html)
        body = body.replace("{{ WIZARD_STATUS }}", wizard_status)
        body = body.replace("{{ BONUS_DRAFTING }}", drafting_html)
        body = body.replace("{{ BONUS_SUMMARY }}", summary_html)
        body = body.replace("{{ BONUS_PENDING }}", pending_html)
        body = body.replace("{{ BONUS_ACTIVE }}", active_html)

        html = bonus_base.replace("__BODY__", body)
        html = inject_nav(html)

        return {"html": html}

    except Exception as e_err:
        print("[ERROR] render_bonus_survey_targeting_get failed:", repr(e_err))
        return {
            "html": f"""
            <html>
              <body style="font-family: system-ui; padding: 24px;">
                <h1>Bonus Survey – Targeting (Error)</h1>
                <pre>{e(repr(e_err))}</pre>
              </body>
            </html>
            """
        }


def handle_bonus_survey_targeting_post(*, user_id: str, data: dict) -> dict:
    from app.cache.surveys_cache import update_bonus_draft, get_bonus_draft

    draft_id = data.get("draft_id")
    if not isinstance(draft_id, str):
        raise RuntimeError("draft_id must be a string")
    
    if not draft_id:
        raise RuntimeError("Missing draft_id in targeting save")

    # 1. Load draft FIRST
    draft = get_bonus_draft(user_id, draft_id)
    if draft is None:
        raise RuntimeError("Draft not found")

    # 2. Normalize status AFTER draft exists
    status = draft.get("status", "draft")

    # 3. Lock check
    if status != "draft":
        raise RuntimeError("Draft is locked and cannot be modified")

    targeting = {
        "age_min": data.get("age_min"),
        "age_max": data.get("age_max"),
        "regions": data.get("regions", []),
        "job_functions": data.get("job_functions", []),
        "primary_os": data.get("primary_os", []),
        "phone_os": data.get("phone_os", []),
        "user_types": data.get("user_types", []),
        "genders": data.get("genders", []),
        "distribution_mode": data.get("distribution_mode", "open"),
    }

    update_bonus_draft(
        user_id,
        draft_id,
        {
            "targeting": targeting,
        },
    )

    return {"success": True}




def handle_bonus_survey_submit_post(*, user_id: str, data: dict) -> dict:
    """
    POST /surveys/bonus/create/submit
    Persist bonus survey + targeting rules, then mark pending approval.
    """

    from datetime import datetime
    from app.cache.surveys_cache import get_bonus_draft, update_bonus_draft
    from app.db.surveys import (
        create_bonus_survey,
        insert_bonus_survey_targeting_rules,
    )

    draft_id = data.get("draft_id", [None])[0]
    if not isinstance(draft_id, str):
        raise RuntimeError("draft_id must be a string")

    if not draft_id:
        return {"redirect": "/surveys/bonus"}

    draft = get_bonus_draft(user_id, draft_id)
    if draft is None:
        return {"redirect": "/surveys/bonus"}

    status = draft.get("status", "draft")

    # Idempotency guard
    if status == "pending_approval":
        return {
            "redirect": f"/surveys/bonus/submitted?draft={draft_id}"
        }

    if status != "draft":
        raise RuntimeError(
            f"Cannot submit bonus survey in state '{status}'"
        )

    # -----------------------------
    # Persist survey (DB)
    # -----------------------------
    basics = draft.get("basics", {}) or {}
    template = draft.get("template", {}) or {}
    targeting = draft.get("targeting", {}) or {}

    bonus_survey_id = create_bonus_survey(
        created_by_user_id=user_id,
        survey_name=basics.get("survey_name", ""),
        survey_link=template.get("survey_link", ""),
        purpose=basics.get("purpose"),
        start_date=basics.get("start_date"),
        end_date=basics.get("end_date"),
        status="pending_approval",
    )

    # -----------------------------
    # Create approval tracker
    # -----------------------------
    from app.db.bonus_survey_tracker import (
        create_tracker_for_bonus_survey,
        add_tracker_entry_submitted,
    )

    tracker_id = create_tracker_for_bonus_survey(
        bonus_survey_id=bonus_survey_id
    )

    add_tracker_entry_submitted(
        tracker_id=tracker_id,
        actor_user_id=user_id,
    )

    # -----------------------------
    # Build targeting rules
    # -----------------------------
    rules: list[dict] = []

    def add_rule(
        *,
        criterion: str,
        operator: str,
        value,
        value_type: str,
        description: str | None = None,
    ):
        if value is None:
            return

        if isinstance(value, list):
            for v in value:
                rules.append(
                    {
                        "criterion": criterion,
                        "operator": operator,
                        "value": str(v),
                        "value_type": value_type,
                        "description": description,
                    }
                )
        else:
            rules.append(
                {
                    "criterion": criterion,
                    "operator": operator,
                    "value": str(value),
                    "value_type": value_type,
                    "description": description,
                }
            )

    add_rule(
        criterion="age",
        operator=">=",
        value=targeting.get("age_min"),
        value_type="int",
        description="Minimum age",
    )

    add_rule(
        criterion="age",
        operator="<=",
        value=targeting.get("age_max"),
        value_type="int",
        description="Maximum age",
    )

    add_rule(
        criterion="region",
        operator="IN",
        value=targeting.get("regions"),
        value_type="enum",
        description="User region",
    )
    add_rule(
        criterion="job_function",
        operator="IN",
        value=targeting.get("job_functions"),
        value_type="enum",
        description="Job function",
    )
    add_rule(
        criterion="primary_os",
        operator="IN",
        value=targeting.get("primary_os"),
        value_type="enum",
        description="Primary operating system",
    )
    add_rule(
        criterion="phone_os",
        operator="IN",
        value=targeting.get("phone_os"),
        value_type="enum",
        description="Primary phone OS",
    )
    add_rule(
        criterion="gender",
        operator="IN",
        value=targeting.get("genders"),
        value_type="enum",
        description="Self-reported gender",
    )
    insert_bonus_survey_targeting_rules(
        bonus_survey_id=bonus_survey_id,
        created_by_user_id=user_id,
        rules=rules,
    )


    # -----------------------------
    # Update cache (state only)
    # -----------------------------
    update_bonus_draft(
        user_id,
        draft_id,
        {
            "status": "pending_approval",
            "submitted_at": datetime.utcnow().isoformat(),
            "bonus_survey_id": bonus_survey_id,
        },
    )

    # --------------------------------------------------
    # Notification: Bonus survey pending approval
    # --------------------------------------------------
    from app.db.notifications import (
        create_notification,
        add_notification_recipient,
    )

    notification_id = create_notification(
        type_key="bonus_survey_pending_approval",
        payload={
            "bonus_survey_id": bonus_survey_id,
            "survey_title": basics.get("survey_name"),
            "submitted_by": user_id,
        },
        created_by=user_id,
    )

    # Phase 0: notify UT Lead only
    REVIEWER_USER_IDS = ["userid_4fec82c7eea61"]  # replace with real ID

    for reviewer_id in REVIEWER_USER_IDS:
        add_notification_recipient(
            notification_id=notification_id,
            user_id=reviewer_id,
        )

    return {
        "redirect": f"/surveys/bonus/submitted?draft={draft_id}"
    }


def render_bonus_survey_pending_view_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict,
) -> dict:
    """
    GET /surveys/bonus/pending
    Read-only view for BSC after submission.
    DB is authoritative. Draft is ignored.
    """

    from pathlib import Path
    from app.db.surveys import (
        get_bonus_survey_by_id,
        get_bonus_survey_targeting_rules,
        get_pending_bonus_surveys_for_user,
        get_active_bonus_surveys_for_user,
    )
    from app.cache.surveys_cache import (
        get_bonus_draft,
        list_bonus_drafts_for_user,
    )

    survey_id = query_params.get("survey_id", [None])[0]
    if not survey_id:
        return {"redirect": "/surveys/bonus"}

    survey = get_bonus_survey_by_id(survey_id)
    if not survey:
        return {"redirect": "/surveys/bonus"}

    if survey["created_by_user_id"] != user_id:
        return {"redirect": "/surveys/bonus"}

    if survey["status"] != "pending_approval":
        return {"redirect": "/surveys/bonus"}

    bonus_base = Path(
        "app/templates/surveys/base_bonus_surveys.html"
    ).read_text(encoding="utf-8")

    bonus_layout = Path(
        "app/templates/surveys/bonus_layout.html"
    ).read_text(encoding="utf-8")

    view_html = Path(
        "app/templates/surveys/bonus_submitted_pending_approval.html"
    ).read_text(encoding="utf-8")

    rules = get_bonus_survey_targeting_rules(survey_id)

    targeting = {}
    for r in rules:
        criterion = r["Criterion"]
        value = r["Value"]
        operator = r["Operator"]

        if criterion == "age":
            if operator == ">=":
                targeting["age_min"] = value
            elif operator == "<=":
                targeting["age_max"] = value
        elif criterion == "region":
            targeting.setdefault("regions", []).append(value)
        elif criterion == "job_function":
            targeting.setdefault("job_functions", []).append(value)
        elif criterion == "primary_os":
            targeting.setdefault("primary_os", []).append(value)
        elif criterion == "phone_os":
            targeting.setdefault("phone_os", []).append(value)
        elif criterion == "gender":
            targeting.setdefault("genders", []).append(value)

    summary = _project_bonus_summary_from_draft(
        {"targeting": targeting}
    )

    view_html = view_html.replace(
        'class="value survey-name">—',
        f'class="value survey-name">{e(survey["survey_title"])}',
    )
    view_html = view_html.replace(
        'class="value start-date">—',
        f'class="value start-date">{e(str(survey["open_at"] or "—"))}',
    )
    view_html = view_html.replace(
        'class="value end-date">—',
        f'class="value end-date">{e(str(survey["close_at"] or "—"))}',
    )
    view_html = view_html.replace(
        'class="value purpose">—',
        f'class="value purpose">{e(survey.get("response_destination") or "—")}',
    )
    view_html = view_html.replace(
        'class="value form-url">—',
        f'class="value form-url">{e(survey["survey_link"] or "—")}',
    )
    view_html = view_html.replace(
        'class="value targeting-summary">—',
        f'class="value targeting-summary">{e(summary["targeting_summary"])}',
    )

    draft_ids = list_bonus_drafts_for_user(user_id)

    if not draft_ids:
        drafting_html = (
            "<span class='rail-empty rail-item'>"
            "No drafts"
            "</span>"
        )
    else:
        items = []
        for d in draft_ids:
            d_draft = get_bonus_draft(user_id, d)
            if not d_draft:
                continue

            basics = d_draft.get("basics", {}) or {}
            name = basics.get("survey_name")

            label = (
                name.strip()
                if isinstance(name, str) and name.strip()
                else f"Draft {d[:8]}"
            )

            safe_label = e(label)
            safe_href = e(f"/surveys/bonus/create?draft={d}")

            items.append(
                f"<a class='rail-item' href='{safe_href}'>"
                f"{safe_label}"
                f"</a>"
            )

        drafting_html = "".join(items)

    pending_surveys = get_pending_bonus_surveys_for_user(user_id)

    if not pending_surveys:
        pending_html = (
            "<span class='rail-empty rail-item'>"
            "No surveys pending approval"
            "</span>"
        )
    else:
        items = []
        for s in pending_surveys:
            safe_label = e(s["survey_title"])
            safe_href = e(
                f"/surveys/bonus/pending?survey_id={s['bonus_survey_id']}"
            )
            items.append(
                f"<a class='rail-item' href='{safe_href}'>"
                f"{safe_label}"
                f"</a>"
            )
        pending_html = "".join(items)

    active_surveys = get_active_bonus_surveys_for_user(user_id)

    if not active_surveys:
        active_html = (
            "<span class='rail-empty rail-item'>"
            "No active surveys"
            "</span>"
        )
    else:
        items = []
        for s in active_surveys:
            safe_label = e(s["survey_title"])
            safe_href = e(
                f"/surveys/bonus/active?survey_id={s['bonus_survey_id']}"
            )
            items.append(
                f"<a class='rail-item' href='{safe_href}'>"
                f"{safe_label}"
                f"</a>"
            )
        active_html = "".join(items)

    body = bonus_layout.replace("{{ BONUS_CONTENT }}", view_html)
    body = body.replace("{{ WIZARD_STATUS }}", "")
    body = body.replace(
        "{{ BONUS_DRAFTING }}",
        "<span class='rail-empty rail-item'>No drafts</span>",
    )
    body = body.replace("{{ BONUS_SUMMARY }}", "")
    body = body.replace("{{ BONUS_PENDING }}", pending_html)
    body = body.replace("{{ BONUS_ACTIVE }}", active_html)

    html = bonus_base.replace("__BODY__", body)
    html = inject_nav(html)

    return {"html": html}

def render_bonus_survey_active_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict,
):
    """
    GET /surveys/bonus/active?survey_id=#
    Active survey detail view.
    """

    from pathlib import Path
    from app.cache.surveys_cache import (
        list_bonus_drafts_for_user,
        get_bonus_draft,
    )
    from app.db.surveys import (
        get_bonus_survey_by_id,
        get_pending_bonus_surveys_for_user,
        get_active_bonus_surveys_for_user,
        get_eligible_active_bonus_surveys_for_user,
    )

    bonus_base = Path(
        "app/templates/surveys/base_bonus_surveys.html"
    ).read_text(encoding="utf-8")

    bonus_layout = Path(
        "app/templates/surveys/bonus_layout_active.html"
    ).read_text(encoding="utf-8")

    survey_id = query_params.get("survey_id", [None])[0]
    if not survey_id:
        return {"redirect": "/surveys/bonus"}

    toast_flag = query_params.get("toast", [None])[0]

    survey = get_bonus_survey_by_id(survey_id)
    if not survey:
        return {"redirect": "/surveys/bonus"}

    if survey.get("created_by_user_id") != user_id:
        return {"redirect": "/surveys/bonus"}

    if survey.get("status") not in ("active", "closed"):
        return {"redirect": "/surveys/bonus"}

    # ✅ NOW it's safe to calculate engagement
    from app.db.surveys import get_bonus_survey_engagement

    eng = get_bonus_survey_engagement(
        survey_id=int(survey_id)
    )

    from app.services.bonus_survey_summary import get_bonus_survey_summary

    summary = get_bonus_survey_summary(int(survey["bonus_survey_id"]))

    if not isinstance(summary, dict):
        summary = {
            "responses": 0,
            "questions": 0,
            "avg_answers": 0,
            "consistency": 0,
        }

    # ==================================================
    # NEW: Explicit state detection (NO GUESSING)
    # ==================================================
    from app.services.bonus_survey_analysis_builder import build_bonus_survey_analysis_payload
    from app.db.bonus_survey_reports import get_bonus_survey_report

    payload = build_bonus_survey_analysis_payload(
        int(survey["bonus_survey_id"])
    )

    has_data = bool(payload.get("responses"))

    report_result = get_bonus_survey_report(
        bonus_survey_id=int(survey["bonus_survey_id"])
    )

    report = report_result.get("report")

    has_report = bool(report)

    # -------------------------
    # STATE MACHINE
    # -------------------------
    if not has_data:
        render_state = "no_data"
    elif has_data and not has_report:
        render_state = "data_uploaded"
    else:
        render_state = "analysis_ready"

    print("[DEBUG] render_state =", render_state)

    draft_ids = list_bonus_drafts_for_user(user_id)
    if not draft_ids:
        drafting_html = (
            "<span class='rail-empty rail-item'>"
            "No drafts"
            "</span>"
        )
    else:
        items = []
        for draft_id in draft_ids:
            draft = get_bonus_draft(user_id, draft_id)
            if not draft:
                continue

            basics = draft.get("basics", {}) or {}
            display_name = basics.get("survey_name") or "Untitled Survey"

            safe_name = e(display_name)
            safe_href = e(f"/surveys/bonus/create?draft={draft_id}")

            items.append(
                f"<a class='rail-item' href='{safe_href}'>"
                f"{safe_name}"
                f"</a>"
            )

        drafting_html = "".join(items) if items else (
            "<span class='rail-empty rail-item'>No drafts</span>"
        )

    pending_surveys = get_pending_bonus_surveys_for_user(user_id)
    if not pending_surveys:
        pending_html = (
            "<span class='rail-empty rail-item'>"
            "No surveys pending approval"
            "</span>"
        )
    else:
        items = []
        for s in pending_surveys:
            safe_label = e(s["survey_title"])
            safe_href = e(
                f"/surveys/bonus/pending?survey_id={s['bonus_survey_id']}"
            )
            items.append(
                f"<a class='rail-item' href='{safe_href}'>"
                f"{safe_label}"
                f"</a>"
            )
        pending_html = "".join(items)

    active_surveys = get_active_bonus_surveys_for_user(user_id)
    if not active_surveys:
        active_html = (
            "<span class='rail-empty rail-item'>"
            "No active surveys"
            "</span>"
        )
    else:
        items = []
        current_id = str(survey.get("bonus_survey_id"))

        for s in active_surveys:
            sid = str(s["bonus_survey_id"])
            label = e(s["survey_title"])
            if sid == current_id:
                label = f"<strong>{label}</strong>"

            safe_href = e(
                f"/surveys/bonus/active?survey_id={s['bonus_survey_id']}"
            )

            items.append(
                f"<a class='rail-item' href='{safe_href}'>"
                f"{label}"
                f"</a>"
            )

        active_html = "".join(items)

    raw_status = (survey.get("status") or "").strip().lower()
    display_status = raw_status.title() if raw_status else "—"

    safe_title = e(survey["survey_title"])
    safe_status = e(display_status)

    open_date = _format_date(survey.get("open_at"))
    close_date = _format_date(survey.get("close_at"))
    if open_date != "—" and close_date != "—":
        duration_text = f"{open_date} → {close_date}"
    elif open_date != "—":
        duration_text = open_date
    elif close_date != "—":
        duration_text = close_date
    else:
        duration_text = "—"

    safe_duration = e(duration_text)
    safe_link = e(survey.get("survey_link") or "")
    safe_purpose = e(survey.get("response_destination") or "—")

    status_text = (
        "This bonus survey is active and collecting responses."
        if raw_status == "active"
        else "This bonus survey is closed and no longer accepting responses."
    )

    is_open = survey.get("is_open", 1)

    close_button_label = (
        "Survey Closed"
        if not is_open
        else "Close Survey"
    )

    from app.db.bonus_survey_reports import get_bonus_survey_report

    report_result = get_bonus_survey_report(
        bonus_survey_id=int(survey["bonus_survey_id"])
    )

    analysis_html = ""

    report = report_result.get("report")

    if report:

        summary = report.get("summary", {})
        sections = report.get("sections", [])
        segments = report.get("segments", [])

        # -------------------------
        # SUMMARY
        # -------------------------
        analysis_html += f"""
        <div class="analysis-block">
            <h4>Overall</h4>
            <div><strong>Responses:</strong> {summary.get("response_count", "")}</div>
        </div>
        """

        # -------------------------
        # SECTIONS
        # -------------------------
        analysis_html += "<h4>Sections</h4>"

        for s in sections:
            section_name = s.get("section_name", "")
            avg = s.get("average_score")

            key_findings = s.get("key_findings", [])
            qualitative = s.get("qualitative_insights", [])
            quotes = s.get("notable_quotes", [])

            findings_html = "".join(f"<li>{e(x)}</li>" for x in key_findings)
            qualitative_html = "".join(f"<li>{e(x)}</li>" for x in qualitative)
            quotes_html = "".join(f"<li>{e(x)}</li>" for x in quotes)

            analysis_html += f"""
            <div class="analysis-theme">
                <div class="analysis-theme-header">
                    <strong>{e(section_name)}</strong>
                </div>

                <div class="analysis-body">
                    <div><strong>Section Score:</strong> {avg if avg is not None else "—"}</div>

                    <div style="margin-top:8px;">
                        <strong>Key Findings:</strong>
                        <ul>{findings_html}</ul>
                    </div>

                    <div style="margin-top:8px;">
                        <strong>Qualitative Insights:</strong>
                        <ul>{qualitative_html}</ul>
                    </div>

                    <div style="margin-top:8px;">
                        <strong>Notable Quotes:</strong>
                        <ul>{quotes_html}</ul>
                    </div>
                </div>
            </div>
            """

        # -------------------------
        # SEGMENTS (Comparisons)
        # -------------------------
        analysis_html += "<h4>Comparisons</h4>"

        for seg in segments:
            label = seg.get("segment", "")
            insights = seg.get("insights", [])

            insights_html = "".join(f"<li>{e(x)}</li>" for x in insights)

            analysis_html += f"""
            <div class="analysis-theme">
                <strong>{e(label)}</strong>
                <ul>{insights_html}</ul>
            </div>
            """

    else:
        analysis_html = "<div class='muted'>Analysis unavailable</div>"

    survey_id = int(survey["bonus_survey_id"])

    # ==================================================
    # RESULTS (STATE-DRIVEN)
    # ==================================================
    results_html = ""

    if render_state == "no_data":

        results_html = f"""
        <div class="content-card">
            <h3>Survey Results</h3>

            <div class="muted" style="margin-bottom:16px;">
                No data uploaded yet.
            </div>

            <a class="btn btn-primary"
            href="/surveys/bonus/upload?survey_id={survey_id}">
                Upload Results
            </a>
        </div>
        """

    elif render_state == "data_uploaded":

        from app.services.bonus_survey_structure_service import build_structured_results

        structured = build_structured_results(
            bonus_survey_id=int(survey["bonus_survey_id"])
        )

        sections_html = ""

        for s in structured["sections"]:
            section_html = f"<h4>{e(s['section_name'])}</h4>"

            if s["section_avg"] is not None:
                section_html += f"<div class='muted'>Section Avg: {round(s['section_avg'], 2)}</div>"

            for q in s["questions"]:
                avg = (
                    f"{round(q['avg'], 2)}"
                    if q["avg"] is not None
                    else "-"
                )

                section_html += f"""
                <div style="margin-left:12px; padding:2px 0;">
                    {e(q['question_text'])} → {avg}
                </div>
                """

            sections_html += f"""
            <div class="results-section">
                {section_html}
            </div>
            """

        results_html = f"""
        <div class="content-card">
            <h3>Survey Results</h3>

            <div class="results-section">
                <div class="results-title">Summary</div>

                <div>Responses: {summary.get('response_count', '—')}</div>

                <div style="margin-top:10px;">
                    <strong>Key Patterns:</strong>
                    <ul>
                        {"".join(f"<li>{e(x)}</li>" for x in summary.get("key_patterns", []))}
                    </ul>
                </div>
            </div>

            {sections_html}

            <div class="results-section">
                <form method="POST" action="/surveys/bonus/analyze">
                    <input type="hidden" name="survey_id" value="{survey_id}">
                    <button type="submit" class="btn btn-primary">
                        Generate Insights
                    </button>
                </form>
            </div>
        </div>
        """

    elif render_state == "analysis_ready":

        from app.services.bonus_survey_structure_service import build_structured_results

        structured = build_structured_results(
            bonus_survey_id=int(survey["bonus_survey_id"])
        )

        sections_html = ""

        for s in structured["sections"]:
            section_html = f"<h4>{e(s['section_name'])}</h4>"

            if s["section_avg"] is not None:
                section_html += f"<div class='muted'>Section Avg: {round(s['section_avg'], 2)}</div>"

            for q in s["questions"]:
                avg = (
                    f"{round(q['avg'], 2)}"
                    if q["avg"] is not None
                    else "-"
                )

                section_html += f"""
                <div style="margin-left:12px; padding:2px 0;">
                    {e(q['question_text'])} → {avg}
                </div>
                """

            sections_html += f"""
            <div class="results-section">
                {section_html}
            </div>
            """

        results_html = f"""
        <div class="content-card">
            <h3>Survey Results</h3>

            <div class="results-section">
                <div class="results-title">Summary</div>

                <div>Responses: {summary.get('response_count', '—')}</div>

                <div style="margin-top:10px;">
                    <strong>Key Patterns:</strong>
                    <ul>
                        {"".join(f"<li>{e(x)}</li>" for x in summary.get("key_patterns", []))}
                    </ul>
                </div>
            </div>

            {sections_html}

            <div class="results-section">
                <div class="results-title">Analysis</div>
                {analysis_html}
            </div>

            <div class="results-section">
                <form method="POST" action="/surveys/bonus/analyze">
                    <input type="hidden" name="survey_id" value="{survey_id}">
                    <button type="submit" class="btn btn-primary">
                        Re-Generate Insights
                    </button>
                </form>
            </div>

            <div class="results-section">
                <a class="btn btn-secondary"
                href="/surveys/bonus/upload?survey_id={survey_id}">
                    Upload New Results
                </a>
            </div>
        </div>
        """

    content_html = f"""
    <h2>{safe_title}</h2>

    <!-- TOP CONTROL -->
    <div class="content-card control-card">
        <div class="survey-control">

            <form method="POST" action="/surveys/bonus/close" style="margin:0;">
                <input type="hidden" name="survey_id" value="{int(survey['bonus_survey_id'])}">
                <button type="submit" class="btn btn-secondary" {"disabled" if not is_open else ""}>
                    {close_button_label}
                </button>
            </form>

            <a class="btn btn-secondary"
            href="/surveys/bonus/finalize?survey_id={survey['bonus_survey_id']}">
                Finalize Results
            </a>

            <!-- 🔥 NEW: STRUCTURE LINK -->
            <a class="btn btn-secondary"
            href="/surveys/bonus/structure?survey_id={survey['bonus_survey_id']}">
                Manage Structure
            </a>

        </div>
    </div>

    <p class="muted">
        {status_text}
    </p>

    <!-- SURVEY INFO -->
    <div class="content-card">
        <div class="info-grid">
            <div class="info-row"><strong>Status:</strong> {safe_status}</div>
            <div class="info-row"><strong>Duration:</strong> {safe_duration}</div>
            <div class="info-row"><strong>Purpose:</strong> {safe_purpose}</div>
            <div class="info-row">
                <strong>Survey Link:</strong>
                <a href="{safe_link}" target="_blank">LINK</a>
            </div>
        </div>
    </div>

    {results_html}
    
    <!-- BOTTOM CONTROL -->
    <div class="content-card control-card">
        <div class="survey-control">

            <form method="POST" action="/surveys/bonus/close" style="margin:0;">
                <input type="hidden" name="survey_id" value="{int(survey['bonus_survey_id'])}">
                <button type="submit" class="btn btn-secondary" {"disabled" if not is_open else ""}>
                    {close_button_label}
                </button>
            </form>

            <a class="btn btn-secondary"
            href="/surveys/bonus/finalize?survey_id={survey['bonus_survey_id']}">
                Finalize Results
            </a>

        </div>
    </div>

    <!-- LOADING OVERLAY -->
    <div id="analysis-loading-overlay" style="display:none;">
        <div class="loading-card">
            <div class="spinner"></div>
            <div id="loading-message">Generating insights...</div>
        </div>
    </div>
    """

    active_summary_html = f"""
    <h3>Engagement</h3>

    <p class="muted small">
        Stats for <strong>{safe_title}</strong>
    </p>

    <div class="rail-divider"></div>

    <div class="muted small">
        <div><strong>Survey clicks:</strong> {eng['clicks']}</div>
        <div><strong>Form opens:</strong> {eng['opens']}</div>
        <div><strong>Responses:</strong> {eng['responses']}</div>
        <div><strong>Completion rate:</strong> {eng['completion_rate']}%</div>
    </div>
    """

    body = bonus_layout
    body = body.replace("{{ BONUS_DRAFTING }}", drafting_html)
    body = body.replace("{{ BONUS_PENDING }}", pending_html)
    body = body.replace("{{ BONUS_ACTIVE }}", active_html)
    body = body.replace("{{ WIZARD_STATUS }}", "")
    body = body.replace("{{ BONUS_CONTENT }}", content_html)
    body = body.replace("{{ BONUS_ACTIVE_SUMMARY }}", active_summary_html)

    html = bonus_base.replace("__BODY__", body)
    html = inject_nav(html)

    if toast_flag == "closed":
        html = html.replace(
            "<body class=\"__BODY_CLASS__\">",
            "<body class=\"__BODY_CLASS__\" data-toast=\"closed\">"
        )

    return {"html": html}

from datetime import datetime, date

def _format_date(value) -> str:
    if not value:
        return "—"

    # MySQL connector may already return datetime objects
    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    # Fallback for string input
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date().isoformat()
        except Exception:
            return value.split(" ")[0]

    # Absolute last-resort fallback
    return str(value)


def render_bonus_survey_take_get(*, user_id, base_template, inject_nav):
    from app.db.surveys import get_eligible_active_bonus_surveys_for_user

    surveys = get_eligible_active_bonus_surveys_for_user(user_id)

    rows = []
    for s in surveys:
        open_date = _format_date(s.get("open_at"))
        close_date = _format_date(s.get("close_at"))

        safe_title = e(s["survey_title"])
        safe_requestor = e(s.get("requestor_name", s["created_by_user_id"]))
        safe_open = e(open_date)
        safe_close = e(close_date)
        safe_purpose = e(s.get("purpose") or "—")
        safe_href = e(f"/surveys/bonus/take/open?survey_id={s['bonus_survey_id']}")

        rows.append(f"""
        <tr>
            <td class="col-survey">{safe_title}</td>
            <td class="col-requestor">{safe_requestor}</td>
            <td class="col-date">{safe_open}</td>
            <td class="col-date">{safe_close}</td>
            <td class="col-purpose">{safe_purpose}</td>
            <td class="col-action">
                <a href="{safe_href}"
                   target="_blank"
                   rel="noopener noreferrer">
                    Open survey
                </a>
            </td>
        </tr>
        """)

    body = f"""
    <h2>Available Bonus Surveys</h2>

    <table class="data-table">
        <thead>
            <tr>
                <th>Survey</th>
                <th>Requestor</th>
                <th>Open</th>
                <th>Close</th>
                <th>Purpose</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows) or '<tr><td colspan="6">No active surveys.</td></tr>'}
        </tbody>
    </table>
    """

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Bonus Surveys")
    html = html.replace("__BODY__", body)

    return {"html": html}

def resolve_bonus_survey_redirect(*, user_id: str, survey_id: int) -> str:
    """
    Resolves the final survey redirect URL for bonus surveys.
    """

    from urllib.parse import urlparse

    # -------------------------
    # 1. Get survey
    # -------------------------
    from app.db.surveys import get_bonus_survey_by_id

    survey = get_bonus_survey_by_id(survey_id)

    if not survey:
        raise ValueError("Survey not found")

    raw_link = (survey.get("survey_link") or "").strip()
    if not raw_link:
        raise ValueError("Survey link not configured")

    # -------------------------
    # 2. Validate URL (CRITICAL)
    # -------------------------
    parsed = urlparse(raw_link)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Invalid survey link scheme")

    if not parsed.netloc:
        raise ValueError("Invalid survey link")

    # -------------------------
    # 3. Validate placeholder
    # -------------------------
    placeholder = "user_token_here"

    if raw_link.count(placeholder) != 1:
        raise ValueError("Survey link must contain exactly one 'user_token_here' placeholder")

    # -------------------------
    # 4. Get participation (ONLY token source)
    # -------------------------
    from app.db.surveys import (
        get_or_create_participation,
        mark_participation_started,
    )

    participation = get_or_create_participation(
        bonus_survey_id=survey_id,
        user_id=user_id,
    )

    token = participation["participation_token"]

    if not token:
        raise RuntimeError("Missing participation token")

    # -------------------------
    # 5. Inject token
    # -------------------------
    final_link = raw_link.replace(placeholder, token)

    # -------------------------
    # 6. Mark started
    # -------------------------
    mark_participation_started(
        bonus_survey_id=survey_id,
        user_id=user_id,
    )

    return final_link

def render_bonus_survey_upload_get(*, user_id, base_template, inject_nav, query_params):
    from app.db.surveys import get_bonus_survey_by_id
    from app.utils.html_escape import escape_html as e

    survey_id = query_params.get("survey_id", [None])[0]

    if not survey_id or not str(survey_id).isdigit():
        return {"redirect": "/surveys/bonus"}

    survey = get_bonus_survey_by_id(int(survey_id))
    if not survey:
        return {"redirect": "/surveys/bonus"}

    if survey["created_by_user_id"] != user_id:
        return {"redirect": "/surveys/bonus"}

    content_html = f"""
    <div class="content-card">
        <h1>Upload Results Snapshot</h1>
        <p class="muted">
            Upload a CSV export to update the current response counts for this survey.
            This does not finalize the survey.
        </p>

        <div class="form-row">
            <div class="label"><strong>Survey</strong></div>
            <div class="value">{e(survey["survey_title"])}</div>
        </div>

        <form method="POST" action="/surveys/bonus/upload" enctype="multipart/form-data" style="margin-top: 20px;">
            <input type="hidden" name="survey_id" value="{int(survey["bonus_survey_id"])}">

            <div class="form-row">
                <label for="results_file"><strong>Results File (CSV)</strong></label><br>
                <input type="file" id="results_file" name="results_file" accept=".csv" required>
            </div>

            <div class="form-actions" style="margin-top: 16px;">
                <button type="submit" class="btn btn-primary">Upload / Update Results</button>
                <a class="btn btn-secondary" href="/surveys/bonus/active?survey_id={int(survey["bonus_survey_id"])}">Cancel</a>
            </div>
        </form>
    </div>
    """

    body = base_template.replace("__BODY__", content_html)
    body = body.replace("{{ BONUS_ACTIVE_SUMMARY }}", "")
    body = inject_nav(body)

    return {"html": body}

def handle_bonus_survey_upload_post(*, user_id, handler):

    import re
    from app.db.surveys import get_bonus_survey_by_id
    from app.utils.html_escape import escape_html as e

    # -------------------------
    # Read raw request
    # -------------------------
    content_type = handler.headers.get("Content-Type", "")
    content_length = int(handler.headers.get("Content-Length", "0"))

    raw = handler.rfile.read(content_length)

    # -------------------------
    # Extract boundary
    # -------------------------
    match = re.search(r"boundary=(.+)", content_type)
    if not match:
        return {"redirect": "/surveys/bonus"}

    boundary = match.group(1).encode()
    parts = raw.split(b"--" + boundary)

    survey_id = None
    file_bytes = None
    filename = None

    # -------------------------
    # Parse multipart parts
    # -------------------------
    for part in parts:
        if b"Content-Disposition" not in part:
            continue

        if b'name="survey_id"' in part:
            value = part.split(b"\r\n\r\n", 1)[1].strip()
            survey_id = value.decode("utf-8")

        if b'name="results_file"' in part:
            header, body = part.split(b"\r\n\r\n", 1)

            filename_match = re.search(b'filename="([^"]+)"', header)
            if filename_match:
                filename = filename_match.group(1).decode("utf-8")

            file_bytes = body.rstrip(b"\r\n")

    # -------------------------
    # Validate survey_id
    # -------------------------
    if not survey_id or not str(survey_id).isdigit():
        return {"redirect": "/surveys/bonus"}

    survey_id = int(survey_id)

    survey = get_bonus_survey_by_id(survey_id)
    if not survey:
        return {"redirect": "/surveys/bonus"}

    if survey["created_by_user_id"] != user_id:
        return {"redirect": "/surveys/bonus"}

    if not file_bytes:
        return {"redirect": f"/surveys/bonus/upload?survey_id={survey_id}"}

    filename = filename or "upload.csv"

    # -------------------------
    # Save + ingest
    # -------------------------
    from app.services.bonus_survey_results import save_bonus_results_upload

    try:
        save_bonus_results_upload(
            survey_id=survey_id,
            uploaded_by_user_id=user_id,
            filename=filename,
            file_bytes=file_bytes,
        )
    except Exception as e_err:
        return {
            "html": f"""
            <html>
              <body style="font-family: system-ui; padding: 24px;">
                <h1>Bonus Survey Upload Error</h1>
                <p>Upload failed while processing the CSV.</p>
                <pre>{e(str(e_err))}</pre>
                <p>
                  <a href="/surveys/bonus/upload?survey_id={survey_id}">Back to upload</a>
                </p>
              </body>
            </html>
            """
        }

    # ==================================================
    # NEW: Generate sections (AI) immediately after upload
    # ==================================================
    try:
        from app.services.bonus_survey_analysis_builder import (
            build_bonus_survey_analysis_payload,
        )
        from app.services.bonus_survey_section_generator import (
            generate_bonus_survey_sections,
        )
        from app.db.surveys import save_bonus_survey_sections

        payload = build_bonus_survey_analysis_payload(survey_id)

        if payload and payload.get("responses"):
            section_payload = generate_bonus_survey_sections(payload)

            save_bonus_survey_sections(
                bonus_survey_id=survey_id,
                section_payload=section_payload,
            )

    except Exception as e_err:
        # IMPORTANT:
        # Do NOT fail upload if section generation fails
        # Upload is primary, sections are secondary
        print("[WARN] Section generation failed:", str(e_err))

    # -------------------------
    # Redirect
    # -------------------------
    return {"redirect": f"/surveys/bonus/active?survey_id={survey_id}"}

def handle_bonus_survey_close_post(*, user_id, handler):
    import urllib.parse

    # -------------------------
    # Parse POST body
    # -------------------------
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8")
    data = urllib.parse.parse_qs(raw)

    survey_id = data.get("survey_id", [None])[0]

    if not survey_id or not str(survey_id).isdigit():
        return {"redirect": "/surveys/bonus"}

    survey_id = int(survey_id)

    # -------------------------
    # Fetch survey
    # -------------------------
    from app.db.surveys import get_bonus_survey_by_id, update_bonus_survey_status

    survey = get_bonus_survey_by_id(survey_id)
    if not survey:
        return {"redirect": "/surveys/bonus"}

    # -------------------------
    # Ownership check
    # -------------------------
    if survey.get("created_by_user_id") != user_id:
        return {"redirect": "/surveys/bonus"}

    # -------------------------
    # State guard
    # -------------------------
    current_status = (survey.get("status") or "").strip().lower()

    if current_status == "closed":
        # Already closed → no-op
        return {"redirect": f"/surveys/bonus/active?survey_id={survey_id}"}

    if current_status != "active":
        return {"redirect": f"/surveys/bonus/active?survey_id={survey_id}"}

    # -------------------------
    # Update state
    # -------------------------
    from app.db.surveys import update_bonus_survey_open_state

    update_bonus_survey_open_state(
        bonus_survey_id=survey_id,
        is_open=0,
    )

    # -------------------------
    # Redirect back
    # -------------------------
    return {"redirect": f"/surveys/bonus/active?survey_id={survey_id}&toast=closed"}

def handle_bonus_survey_analyze_post(*, user_id, handler):
    """
    Generate insights report (AI) and persist to DB.
    """

    # -------------------------
    # Parse form data (match upload pattern)
    # -------------------------
    length = int(handler.headers.get("Content-Length", 0))
    body = handler.rfile.read(length).decode("utf-8")

    from urllib.parse import parse_qs
    form = parse_qs(body)

    survey_id = form.get("survey_id", [None])[0]

    if not survey_id:
        return {"redirect": "/surveys/bonus"}

    survey_id = int(survey_id)

    # -------------------------
    # Build + generate report
    # -------------------------
    from app.services.bonus_survey_analysis import generate_bonus_survey_analysis
    from app.db.bonus_survey_reports import upsert_bonus_survey_report

    report_result = generate_bonus_survey_analysis(survey_id)

    # -------------------------
    # Persist
    # -------------------------
    if report_result.get("success"):
        upsert_bonus_survey_report(
            bonus_survey_id=survey_id,
            report=report_result["analysis"]
        )

    # -------------------------
    # Redirect back
    # -------------------------
    return {
        "redirect": f"/surveys/bonus/active?survey_id={survey_id}"
    }

def handle_generate_bonus_survey_insights_get(user_id: str, query_params: dict):
    """
    Generate AI insights for a bonus survey.

    Expects:
    /surveys/insights?bonus_survey_id=XX
    """

    bonus_survey_id = query_params.get("bonus_survey_id")

    if not bonus_survey_id:
        return "Missing bonus_survey_id", 400

    try:
        bonus_survey_id = int(bonus_survey_id)
    except ValueError:
        return "Invalid bonus_survey_id", 400

    # -------------------------
    # Build payload
    # -------------------------
    payload = build_bonus_survey_analysis_payload(bonus_survey_id)

    # -------------------------
    # Force survey segmentation
    # -------------------------
    payload["segmentation_mode"] = "survey"

    # -------------------------
    # Generate insights
    # -------------------------
    result = generate_segment_insights(payload)

    # -------------------------
    # Return raw JSON (for now)
    # -------------------------
    import json
    return json.dumps(result, ensure_ascii=False), 200

def handle_bonus_survey_generate_sections_post(user_id: str, data: dict):
    """
    Generate and persist AI-derived section structure for a bonus survey.

    POST only.
    Mutates DB.
    Must redirect.
    """

    bonus_survey_id = data.get("bonus_survey_id")

    if not bonus_survey_id:
        return {"redirect": "/surveys/bonus", "error": "missing_id"}

    try:
        bonus_survey_id = int(bonus_survey_id)
    except ValueError:
        return {"redirect": "/surveys/bonus", "error": "invalid_id"}

    # -------------------------
    # Build payload (source of truth = DB)
    # -------------------------
    from app.services.bonus_survey_analysis_builder import (
        build_bonus_survey_analysis_payload,
    )

    payload = build_bonus_survey_analysis_payload(bonus_survey_id)

    if not payload or not payload.get("responses"):
        return {
            "redirect": f"/surveys/bonus/pending?bonus_survey_id={bonus_survey_id}",
            "error": "no_data",
        }

    # -------------------------
    # Generate sections (AI - minimal structural)
    # -------------------------
    from app.services.bonus_survey_section_generator import (
        generate_bonus_survey_sections,
    )

    try:
        section_payload = generate_bonus_survey_sections(payload)
    except Exception:
        return {
            "redirect": f"/surveys/bonus/pending?bonus_survey_id={bonus_survey_id}",
            "error": "section_generation_failed",
        }

    # -------------------------
    # Persist sections
    # -------------------------
    from app.db.surveys import save_bonus_survey_sections

    try:
        save_bonus_survey_sections(
            bonus_survey_id=bonus_survey_id,
            section_payload=section_payload,
        )
    except Exception:
        return {
            "redirect": f"/surveys/bonus/pending?bonus_survey_id={bonus_survey_id}",
            "error": "db_write_failed",
        }

    # -------------------------
    # Redirect (POST must redirect)
    # -------------------------
    return {
        "redirect": f"/surveys/bonus/pending?bonus_survey_id={bonus_survey_id}&sections=generated"
    }