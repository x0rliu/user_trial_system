# app/handlers/product_team.py

from pathlib import Path
from app.db.user_roles import get_effective_permission_level
from app.cache.simple_cache import cache
from app.cache.product_cache import TRIAL_PROJECT_PREFIX
from app.cache.product_cache import get_trial_project, save_trial_project
from app.db.user_pool_country_codes import get_country_codes
from app.handlers import users
from datetime import datetime
from app.utils.csrf import generate_csrf_token
from app.cache.product_cache import get_trial_project, delete_trial_project
from app.db.project_rounds import create_project_from_request
from app.db.notifications import (
    create_notification,
    add_notification_recipient,
)
from app.db.project_rounds import (
    get_project_with_latest_round,
    mark_project_round_pending_ut_review,
)
from app.db.approval_actions import insert_approval_action
from app.services.notifications import notify_user
from app.utils.html_escape import escape_html as e

PRODUCT_WIZARD_STEPS = [
    ("basics", "Project Basics"),
    ("timing", "Timing & Scope"),
    ("stakeholders", "Stakeholders"),
    ("review", "Review & Submit"),
]


def _can_access_product_request(*, user_id: str, project: dict | None) -> bool:
    if not user_id or not project:
        return False

    owner_id = (
        project.get("created_by")
        or project.get("CreatedBy")
        or project.get("requested_by_user_id")
    )

    if bool(owner_id) and str(owner_id) == str(user_id):
        return True

    # Drafts stay requestor-only. Stakeholder access begins only after
    # the request is submitted and project_stakeholders exists in the DB.
    if project.get("status") == "draft":
        return False

    project_id = project.get("ProjectID") or project.get("project_id")
    if not project_id:
        return False

    from app.db.project_rounds import user_can_access_project_request

    return user_can_access_project_request(
        user_id=user_id,
        project_id=project_id,
    )


def _normalize_stakeholder_email(raw_email: str) -> str:
    return (raw_email or "").strip().lower()


def _is_logitech_email(email: str) -> bool:
    if not email or "@" not in email:
        return False

    local_part, domain = email.rsplit("@", 1)
    return bool(local_part.strip()) and domain.strip().lower() == "logitech.com"


def _build_stakeholder_from_email(*, email: str, role: str) -> dict:
    from app.db.user_pool import get_user_by_email

    normalized_email = _normalize_stakeholder_email(email)
    user = get_user_by_email(normalized_email)

    display_name = normalized_email
    linked_user_id = None

    if user:
        first_name = (user.get("FirstName") or "").strip()
        last_name = (user.get("LastName") or "").strip()
        full_name = f"{first_name} {last_name}".strip()

        display_name = full_name or normalized_email
        linked_user_id = user.get("user_id")

    return {
        "email": normalized_email,
        "display_name": display_name,
        "user_id": linked_user_id,
        "role": role,
    }


def render_product_request_trial_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict | None = None,
):
    """
    GET /product/request-trial

    Product Team (50+) entry point.
    Render-only shell for the Request Trial wizard.
    No cache creation. No DB writes. No inference.
    """

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    permission_level = get_effective_permission_level(user_id)
    if permission_level < 50:
        return {"redirect": "/dashboard"}

    # --------------------------------------------------
    # Templates
    # --------------------------------------------------
    product_base = Path(
        "app/templates/product_team/base_product_team.html"
    ).read_text(encoding="utf-8")

    product_layout = Path(
        "app/templates/product_team/product_layout.html"
    ).read_text(encoding="utf-8")

    # ==================================================
    # Left rail — Product Trials (Draft = cache, others = DB)
    # ==================================================
    from app.cache.product_cache import list_trial_projects_for_user
    from app.db.project_rounds import (
        get_pending_project_rounds_for_user,
        get_active_project_rounds_for_user,
        get_action_required_project_rounds_for_user,
    )

    draft_projects = list_trial_projects_for_user(user_id=user_id)
    pending_projects = get_pending_project_rounds_for_user(user_id=user_id)
    # active_projects = get_active_project_rounds_for_user(user_id=user_id)
    action_required_projects = get_action_required_project_rounds_for_user(user_id=user_id)


    draft_items = []
    pending_items = []
    # active_items = []
    action_required_items = []

    # -----------------------------
    # Drafts (CACHE)
    # -----------------------------
    for p in draft_projects:
        pid = p["project_id"]
        name = e(p.get("basics", {}).get("project_name", "Untitled Trial"))

        draft_items.append(
            f"""
            <a class="rail-item"
            href="/product/request-trial/wizard/basics?project_id={pid}">
                {name}
            </a>
            """
        )


    # -----------------------------
    # Pending UT Review (DB)
    # -----------------------------
    for p in pending_projects:
        pending_items.append(
            f"""
            <a class="rail-item"
            href="/product/request-trial/pending?project_id={p["ProjectID"]}">
                {e(p["ProjectName"])}
            </a>
            """
        )


    # -----------------------------
    # User Trial Requests (DB — Product Team action required)
    # -----------------------------
    for p in action_required_projects:
        status = (p.get("Status") or "").lower()
        project_id = p.get("ProjectID")

        if status == "info_requested":
            href = (
                "/product/request-trial/info-requested"
                f"?project_id={project_id}"
            )
        elif status == "change_requested":
            href = (
                "/product/request-trial/change-requested"
                f"?project_id={project_id}"
            )
        else:
            continue

        action_required_items.append(
            f"""
            <a class="rail-item rail-status-{status}"
            href="{href}">
                {e(p["ProjectName"])}
            </a>
            """
        )

    create_csrf_token = generate_csrf_token(user_id)

    left_rail_html = f"""
    <h2>User Trials</h2>

    <div class="rail-section">
        <form method="post" action="/product/request-trial/create">
            <input type="hidden" name="csrf_token" value="{e(create_csrf_token)}">
            <button class="rail-item rail-primary" type="submit">
                + Request a Trial
            </button>
        </form>
    </div>

    <div class="rail-divider"></div>

    <div class="rail-group">
        <button class="rail-header rail-toggle" type="button">
            Drafting
            <span class="rail-chevron">▾</span>
        </button>
        <div class="rail-section">
            {render_section(draft_items, "No drafts")}
        </div>
    </div>

    <div class="rail-group">
        <button class="rail-header rail-toggle" type="button">
            Pending UT Review
            <span class="rail-chevron">▾</span>
        </button>
        <div class="rail-section">
            {render_section(pending_items, "No trials pending review")}
        </div>
    </div>

    <div class="rail-group">
        <button class="rail-header rail-toggle" type="button">
            User Trial Requests
            <span class="rail-chevron">▾</span>
        </button>
        <div class="rail-section">
            {render_section(action_required_items, "No trial requests")}
        </div>
    </div>
    """

    # --------------------------------------------------
    # Main content (intro only)
    # --------------------------------------------------
    main_content_html = """
    <div class="page-header">
        <p class="page-kicker">Product Team</p>
        <h2 class="page-title">Request a User Trial</h2>
        <p class="page-description">
            Start the User Trial planning process with the UT team by defining
            the basic project details needed for discussion and scheduling.
        </p>
    </div>

    <section>
        <h3 class="section-title">Before you begin</h3>
        <p class="section-description">
            This request does <strong>not</strong> finalize scope, recruiting, or surveys.
            Those details are defined collaboratively after submission.
        </p>
        <p class="field-hint">
            Begin by outlining the project basics.
        </p>
    </section>
    """

    # --------------------------------------------------
    # Right rail (summary — placeholder)
    # --------------------------------------------------
    summary_html = """
    <div class="muted small">
        Project summary will appear here as you proceed.
    </div>
    """

    # --------------------------------------------------
    # Assemble layout
    # --------------------------------------------------
    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", "")
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", summary_html)

    html = product_base.replace("__BODY__", body)
    html = inject_nav(html)

    return {"html": html}


def _render_product_wizard_status(
    *,
    current_step: str,
    wizard_state: dict,
    project_id: str,
):
    """
    Render Product Team wizard step navigation.

    Access rule:
    - Basics is always reachable for an existing draft.
    - Timing is reachable once Basics is complete.
    - Stakeholders is reachable once Basics + Timing are complete.
    - Review is reachable once Basics + Timing + Stakeholders are complete.

    This lets a requester return to Review after editing an earlier step
    without being forced through the wizard path again.
    """

    basics_complete = bool(wizard_state.get("basics"))
    timing_complete = bool(wizard_state.get("timing"))
    stakeholders_complete = bool(wizard_state.get("stakeholders"))

    accessible_steps = {
        "basics": True,
        "timing": basics_complete,
        "stakeholders": basics_complete and timing_complete,
        "review": basics_complete and timing_complete and stakeholders_complete,
    }

    items = []

    for key, label in PRODUCT_WIZARD_STEPS:
        href = f"/product/request-trial/wizard/{key}?project_id={project_id}"

        if key == current_step:
            item = f'<strong><a href="{href}">{label}</a></strong>'
        elif accessible_steps.get(key):
            item = f'<a href="{href}">{label}</a>'
        else:
            item = f'<span class="wizard-future">{label}</span>'

        items.append(item)

    return f"""
    <nav class="wizard-status">
        {' &nbsp;→&nbsp; '.join(items)}
    </nav>
    """



def handle_product_request_trial_wizard_basics_post(
    *,
    user_id: str,
    data: dict,
):
    """
    Saves Project Basics into the trial project draft.
    Business logic only. No HTTP concerns.
    """

    # --------------------------------------------------
    # CSRF protection
    # --------------------------------------------------
    # Validated in app/main.py before handler delegation.

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    # --------------------------------------------------
    # Project ID extraction
    # --------------------------------------------------
    project_id_list = data.get("project_id")
    if not project_id_list:
        return {"error": "missing_project_id"}

    project_id = project_id_list[0]

    project = get_trial_project(project_id)
    if not project:
        return {"error": "project_not_found"}

    # --------------------------------------------------
    # Ownership validation (IDOR protection)
    # --------------------------------------------------
    if project.get("created_by") != user_id:
        return {"redirect": "/product/request-trial"}

    # --------------------------------------------------
    # Persist basics
    # --------------------------------------------------
    project["basics"] = {
        "project_name": data.get("project_name", [""])[0].strip(),
        "market_name": data.get("market_name", [""])[0].strip() or None,
        "gate_x_date": data.get("gate_x_date", [""])[0].strip() or None,
        "business_group": data.get("business_group", [""])[0].strip(),
        "product_category": data.get("product_category", [""])[0].strip(),
        "purpose": data.get("purpose", [""])[0].strip(),
    }

    project["updated_at"] = datetime.utcnow().isoformat()

    save_trial_project(project_id, project)

    return {
        "redirect": f"/product/request-trial/wizard/timing?project_id={project_id}"
    }


def derive_wizard_state(project: dict) -> dict:
    """
    Derive wizard completion state from project data.

    Returns a dict keyed by step name with boolean completion.
    This function is the single source of truth for wizard state.
    """

    basics = project.get("basics", {})
    timing = project.get("timing_scope", {})
    stakeholders = project.get("stakeholders", {})

    return {
        "basics": bool(
            basics.get("project_name")
            and basics.get("business_group")
            and basics.get("product_category")
        ),
        "timing": bool(
            timing.get("shipping_date")
            and timing.get("countries")
        ),

        "stakeholders": bool(stakeholders.get("roles")),
        # review is derived, never directly "completed"
    }

def handle_product_request_trial_wizard_timing_post(
    *,
    user_id: str,
    data: dict,
):
    # --------------------------------------------------
    # CSRF protection
    # --------------------------------------------------
    # Validated in app/main.py before handler delegation.

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    # --------------------------------------------------
    # Project ID extraction
    # --------------------------------------------------
    project_id = data.get("project_id", [None])[0]
    if not project_id:
        return {"error": "missing_project_id"}

    project = get_trial_project(project_id)
    if not project:
        return {"error": "project_not_found"}

    # --------------------------------------------------
    # Ownership validation (IDOR protection)
    # --------------------------------------------------
    if project.get("created_by") != user_id:
        return {"redirect": "/product/request-trial"}

    # --------------------------------------------------
    # Persist timing scope
    # --------------------------------------------------
    existing_timing = project.get("timing_scope", {})

    submitted_countries = data.get("countries[]", [])
    countries = [
        country.strip()
        for country in submitted_countries
        if country and country.strip()
    ]

    # If no country inputs were submitted, preserve the existing draft value.
    # This prevents accidental data loss when revisiting the step.
    # Explicit country removal should be handled by a dedicated UI action later.
    if not countries:
        countries = existing_timing.get("countries", []) or []

    project["timing_scope"] = {
        **existing_timing,
        "shipping_date": data.get("shipping_date", [""])[0].strip(),
        "gate_x_date": data.get("gate_x_date", [""])[0].strip(),
        "countries": countries,
        "notes": data.get("notes", [""])[0].strip(),
    }

    project["updated_at"] = datetime.utcnow().isoformat()
    save_trial_project(project_id, project)

    return {
        "redirect": f"/product/request-trial/wizard/stakeholders?project_id={project_id}"
    }


def handle_product_request_trial_wizard_stakeholders_post(
    *,
    user_id: str,
    data: dict,
):
    """
    Saves Product Team request stakeholders into the trial project draft.
    Business logic only. No HTTP rendering.
    """

    # --------------------------------------------------
    # CSRF protection
    # --------------------------------------------------
    # Validated in app/main.py before handler delegation.

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    # --------------------------------------------------
    # Project ID extraction
    # --------------------------------------------------
    project_id = data.get("project_id", [None])[0]
    if not project_id:
        return {"error": "missing_project_id"}

    project = get_trial_project(project_id)
    if not project:
        return {"error": "project_not_found"}

    # --------------------------------------------------
    # Ownership validation
    # --------------------------------------------------
    if project.get("created_by") != user_id:
        return {"redirect": "/product/request-trial"}

    # --------------------------------------------------
    # Normalize stakeholder rows
    # --------------------------------------------------
    emails = data.get("stakeholder_email[]", [])
    roles = data.get("stakeholder_role[]", [])

    if isinstance(emails, str):
        emails = [emails]

    if isinstance(roles, str):
        roles = [roles]

    stakeholder_roles = []
    seen_emails = set()

    for index, raw_email in enumerate(emails):
        email = _normalize_stakeholder_email(raw_email)
        role = (roles[index] if index < len(roles) else "").strip()

        if not email and not role:
            continue

        if not _is_logitech_email(email):
            return {"error": "invalid_stakeholder_email", "project_id": project_id}

        if email in seen_emails:
            continue

        seen_emails.add(email)
        stakeholder_roles.append(
            _build_stakeholder_from_email(
                email=email,
                role=role or "Other",
            )
        )

    # --------------------------------------------------
    # Persist stakeholders
    # --------------------------------------------------
    project["stakeholders"] = {
        "roles": stakeholder_roles,
        "notes": data.get("notes", [""])[0].strip(),
    }

    project["updated_at"] = datetime.utcnow().isoformat()

    save_trial_project(project_id, project)

    return {
        "redirect": f"/product/request-trial/wizard/review?project_id={project_id}"
    }


def handle_product_request_trial_cancel_post(
    *,
    user_id: str,
    data: dict,
):
    """
    Cancels a Product Team trial request draft.
    Business logic only. No HTTP rendering.
    """

    # --------------------------------------------------
    # CSRF protection
    # --------------------------------------------------
    # Validated in app/main.py before handler delegation.

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    # --------------------------------------------------
    # Project ID extraction
    # --------------------------------------------------
    project_id = data.get("project_id", [None])[0]
    if not project_id:
        return {"error": "missing_project_id"}

    project = get_trial_project(project_id)
    if not project:
        return {"redirect": "/product/request-trial"}

    # --------------------------------------------------
    # Ownership validation
    # --------------------------------------------------
    if project.get("created_by") != user_id:
        return {"redirect": "/product/request-trial"}

    # --------------------------------------------------
    # Draft-only deletion
    # --------------------------------------------------
    if project.get("status") != "draft":
        return {"redirect": "/product/request-trial"}

    delete_trial_project(project_id)

    return {"redirect": "/product/request-trial?notice=request_cancelled"}


def render_section(items, empty_text):
    if items:
        return "\n".join(items)
    return f"""
    <span class="rail-empty">
        {empty_text}
    </span>
    """

def handle_product_request_trial_submit_post(
    *,
    user_id: str,
    data: dict,
):
    """
    Final submission of a Product Team trial request.
    Delegates ALL DB writes to project_rounds.
    """

    # --------------------------------------------------
    # CSRF protection
    # --------------------------------------------------
    # Validated in app/main.py before handler delegation.

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    # --------------------------------------------------
    # Project ID extraction
    # --------------------------------------------------
    project_id_list = data.get("project_id")
    if not project_id_list:
        return {"error": "missing_project_id"}

    project_id = project_id_list[0]

    project = get_trial_project(project_id)
    if not project:
        return {"error": "project_not_found"}

    # --------------------------------------------------
    # Ownership validation (IDOR protection)
    # --------------------------------------------------
    if project.get("created_by") != user_id:
        return {"redirect": "/product/request-trial"}

    # --------------------------------------------------
    # Wizard completeness check
    # --------------------------------------------------
    wizard_state = derive_wizard_state(project)
    if not all((
        wizard_state.get("basics"),
        wizard_state.get("timing"),
        wizard_state.get("stakeholders"),
    )):
        return {"error": "incomplete_project"}

    now = datetime.utcnow()

    # --------------------------------------------------
    # Explicit authority handoff: CACHE → DB
    # --------------------------------------------------
    project["_authority"] = {
        "sot": "database",
        "cache_authoritative_from": project.get("created_at"),
        "cache_authoritative_until": now.isoformat(),
        "handoff_reason": "submitted_for_ut_review",
        "handoff_by": user_id,
    }

    # --------------------------------------------------
    # Single authoritative DB call
    # --------------------------------------------------
    create_project_from_request(
        project_id=project_id,
        created_by=user_id,
        project_snapshot=project,
        submitted_at=now,
    )

    # --------------------------------------------------
    # Cache eviction
    # --------------------------------------------------
    delete_trial_project(project_id)

    # --------------------------------------------------
    # Notification
    # --------------------------------------------------
    basics = project.get("basics", {})
    timing = project.get("timing_scope", {})

    notification_id = create_notification(
        type_key="product_trial_pending_approval",
        payload={
            "project_id": project_id,
            "project_name": basics.get("project_name"),
            "requested_by": user_id,
            "trial_type": "ut_trial",
            "product_category": basics.get("product_category"),
            "business_group": basics.get("business_group"),
            "estimated_start_date": timing.get("shipping_date"),
            "estimated_end_date": basics.get("gate_x_date"),
            "user_amount": project.get("user_amount"),
        },
        created_by=user_id,
    )

    REVIEWER_USER_IDS = [
        "userid_4fec82c7eea61",
    ]

    for reviewer_id in REVIEWER_USER_IDS:
        add_notification_recipient(
            notification_id=notification_id,
            user_id=reviewer_id,
        )

    return {
        "redirect": (
            "/product/request-trial/pending"
            f"?project_id={project_id}"
        )
    }

def _load_product_team_templates():
    product_base = Path(
        "app/templates/product_team/base_product_team.html"
    ).read_text(encoding="utf-8")

    product_layout = Path(
        "app/templates/product_team/product_layout.html"
    ).read_text(encoding="utf-8")

    return product_base, product_layout


def _render_product_left_rail_for_user(*, user_id: str) -> str:
    """
    Left rail used across Product Team request-trial pages.
    Drafting = CACHE
    Pending/Active = DB
    """

    from app.cache.product_cache import list_trial_projects_for_user
    from app.db.project_rounds import (
        get_pending_project_rounds_for_user,
        get_active_project_rounds_for_user,
        get_action_required_project_rounds_for_user,
    )

    draft_projects = list_trial_projects_for_user(user_id=user_id)
    pending_projects = get_pending_project_rounds_for_user(user_id=user_id)
    # active_projects = get_active_project_rounds_for_user(user_id=user_id)
    action_required_projects = get_action_required_project_rounds_for_user(user_id=user_id)


    draft_items = []
    pending_items = []
    # active_items = []
    action_required_items = []

    # Drafts (CACHE)
    for p in draft_projects:
        pid = p["project_id"]
        name = e(p.get("basics", {}).get("project_name", "Untitled Trial"))

        draft_items.append(
            f"""
            <a class="rail-item"
               href="/product/request-trial/wizard/basics?project_id={pid}">
                {name}
            </a>
            """
        )

    # Pending UT Review (DB)
    for p in pending_projects:
        pending_items.append(
            f"""
            <a class="rail-item"
               href="/product/request-trial/pending?project_id={p["ProjectID"]}">
                {e(p["ProjectName"])}
            </a>
            """
        )

    # Active Trials (DB)
    # for p in active_projects:
    #    action_required_items.append(
    #        f"""
    #        <a class="rail-item"
    #           href="/product/trials/{p["RoundID"]}">
    #            {e(p["ProjectName"])}
    #        </a>
    #        """
    #    )


    # User Trial Requests (DB — Product Team action required)
    for p in action_required_projects:
        status = (p.get("Status") or "").lower()
        project_id = p.get("ProjectID")

        if status == "info_requested":
            href = (
                "/product/request-trial/info-requested"
                f"?project_id={project_id}"
            )

        elif status == "change_requested":
            href = (
                "/product/request-trial/change-requested"
                f"?project_id={project_id}"
            )

        else:
            # Not a Product Team–owned request state
            continue

        action_required_items.append(
            f"""
            <a class="rail-item rail-status-{status}"
            href="{href}">
                {e(p["ProjectName"])}
            </a>
            """
        )


    create_csrf_token = generate_csrf_token(user_id)

    draft_group_state = "" if draft_items else " collapsed"
    pending_group_state = "" if pending_items else " collapsed"
    action_required_group_state = "" if action_required_items else " collapsed"

    return f"""
    <h2>User Trials</h2>

    <div class="rail-section">
        <form method="post" action="/product/request-trial/create">
            <input type="hidden" name="csrf_token" value="{e(create_csrf_token)}">
            <button class="rail-item rail-primary" type="submit">
                + Request a Trial
            </button>
        </form>
    </div>

    <div class="rail-divider"></div>

    <div class="rail-group{draft_group_state}">
        <button class="rail-header rail-toggle" type="button">
            Drafting
            <span class="rail-chevron">▾</span>
        </button>
        <div class="rail-section">
            {render_section(draft_items, "No drafts")}
        </div>
    </div>

    <div class="rail-group{pending_group_state}">
        <button class="rail-header rail-toggle" type="button">
            Pending UT Review
            <span class="rail-chevron">▾</span>
        </button>
        <div class="rail-section">
            {render_section(pending_items, "No trials pending review")}
        </div>
    </div>

    <div class="rail-group{action_required_group_state}">
        <button class="rail-header rail-toggle" type="button">
            User Trial Requests
            <span class="rail-chevron">▾</span>
        </button>
        <div class="rail-section">
            {render_section(action_required_items, "No trial requests")}
        </div>
    </div>
    """


def _render_project_summary_right_rail(*, project: dict, wizard_state: dict) -> str:
    basics = project.get("basics", {})
    timing = project.get("timing_scope", {})

    summary_rows = []

    # --------------------------------------------------
    # Basics
    # --------------------------------------------------
    if wizard_state.get("basics"):
        summary_rows.append(f"""
            <dt>Project</dt>
            <dd>{basics.get("project_name", "—")}</dd>

            <dt>Market</dt>
            <dd>{basics.get("market_name", "—")}</dd>

            <dt>Category</dt>
            <dd>{basics.get("product_category", "—")}</dd>
        """)

    # --------------------------------------------------
    # Timing
    # --------------------------------------------------
    if wizard_state.get("timing"):

        countries = timing.get("countries") or []
        if isinstance(countries, list):
            country_str = ", ".join(countries) if countries else "—"
        else:
            country_str = countries

        summary_rows.append(f"""
            <dt>Shipping</dt>
            <dd>{timing.get("shipping_date", "—")}</dd>

            <dt>Gate X</dt>
            <dd>{timing.get("gate_x_date", "—")}</dd>

            <dt>Countries</dt>
            <dd>{country_str}</dd>
        """)

    # --------------------------------------------------
    # Empty state
    # --------------------------------------------------
    if not summary_rows:
        return """
        <div class="summary-block">
            <h4 class="summary-title">Request Summary</h4>
            <div class="muted small">
                Request summary will appear here as you complete each step.
            </div>
        </div>
        """

    # --------------------------------------------------
    # Render
    # --------------------------------------------------
    return f"""
    <div class="summary-block">
        <h4 class="summary-title">Request Summary</h4>
        <dl class="summary-list">
            {''.join(summary_rows)}
        </dl>
    </div>
    """

# --------------------------------------------------
# NEW: explicit GET renderers (one per step)
# Routes these are meant to back:
#   GET /product/request-trial/wizard/basics?project_id=...
#   GET /product/request-trial/wizard/timing?project_id=...
#   GET /product/request-trial/wizard/stakeholders?project_id=...
#   GET /product/request-trial/wizard/review?project_id=...
# --------------------------------------------------

def render_product_request_trial_wizard_basics_get(
    *,
    user_id: str,
    project_id: str,
    base_template: str,
    inject_nav,
    query_params: dict | None = None,
):
    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    project = get_trial_project(project_id)
    if not project or project.get("status") != "draft":
        return {"redirect": "/product/request-trial"}

    if not _can_access_product_request(user_id=user_id, project=project):
        return {"redirect": "/product/request-trial"}

    product_base, product_layout = _load_product_team_templates()
    left_rail_html = _render_product_left_rail_for_user(user_id=user_id)

    wizard_state = derive_wizard_state(project)
    wizard_status_html = _render_product_wizard_status(
        current_step="basics",
        wizard_state=wizard_state,
        project_id=project_id,
    )

    basics = project.get("basics", {})

    # --------------------------------
    # CSRF TOKEN
    # --------------------------------
    csrf_token = generate_csrf_token(user_id)

    project_name = e(basics.get("project_name", ""))
    market_name = e(basics.get("market_name", ""))
    business_group = e(basics.get("business_group", ""))
    product_category = e(basics.get("product_category", ""))
    purpose = e(basics.get("purpose", ""))

    user_scope = basics.get("user_scope", "Hybrid")

    main_content_html = f"""
    <div class="page-header">
        <p class="page-kicker">Product Trial Request</p>
        <h2 class="page-title">Project Basics</h2>
        <p class="page-description">
            Define the product identity and high-level purpose for this trial request.
        </p>
    </div>

    {wizard_status_html}

    <form method="post" action="/product/request-trial/wizard/basics">
        <input type="hidden" name="csrf_token" value="{csrf_token}" />
        <input type="hidden" name="project_id" value="{project_id}" />

        <div class="form-group">
            <label class="field-label">Project Name</label>
            <input
                type="text"
                name="project_name"
                value="{project_name}"
                required
            />
        </div>

        <div class="form-group">
            <label class="field-label">Market Name</label>
            <input
                type="text"
                name="market_name"
                value="{market_name}"
            />
        </div>

        <div class="form-group">
            <label class="field-label">Business Group</label>
            <input
                type="text"
                name="business_group"
                value="{business_group}"
                required
            />
        </div>

        <div class="form-group">
            <label class="field-label">Product Category / Type</label>
            <input
                type="text"
                name="product_category"
                value="{product_category}"
                required
            />
        </div>

        <div class="form-group">
            <label class="field-label">User Scope</label>
            <select name="user_scope">
                <option value="Internal" {"selected" if user_scope == "Internal" else ""}>Internal (Employees Only)</option>
                <option value="External" {"selected" if user_scope == "External" else ""}>External (Participants Only)</option>
                <option value="Hybrid" {"selected" if user_scope == "Hybrid" else ""}>Hybrid (Employees + Participants)</option>
            </select>
        </div>

        <div class="form-group">
            <label class="field-label">Purpose / Additional Context</label>
            <textarea name="purpose" rows="4">{purpose}</textarea>
        </div>

        <div class="form-actions">
            <button type="submit" class="primary">
                Save & Continue
            </button>

            <button
                type="submit"
                class="secondary request-cancel-button"
                formaction="/product/request-trial/cancel"
                formmethod="post"
                formnovalidate
            >
                Cancel Request
            </button>
        </div>
    </form>
    """

    summary_html = _render_project_summary_right_rail(
        project=project, wizard_state=wizard_state
    )

    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", "")
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", summary_html)

    html = product_base.replace("__BODY__", body)
    html = inject_nav(html)

    return {"html": html}


def render_product_request_trial_wizard_timing_get(
    *,
    user_id: str,
    project_id: str,
    base_template: str,
    inject_nav,
    query_params: dict | None = None,
):
    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    project = get_trial_project(project_id)
    if not project or project.get("status") != "draft":
        return {"redirect": "/product/request-trial"}

    if not _can_access_product_request(user_id=user_id, project=project):
        return {"redirect": "/product/request-trial"}

    product_base, product_layout = _load_product_team_templates()
    left_rail_html = _render_product_left_rail_for_user(user_id=user_id)

    wizard_state = derive_wizard_state(project)
    wizard_status_html = _render_product_wizard_status(
        current_step="timing",
        wizard_state=wizard_state,
        project_id=project_id,
    )

    timing = project.get("timing_scope", {})

    # --------------------------------
    # CSRF TOKEN
    # --------------------------------
    csrf_token = generate_csrf_token(user_id)

    # --------------------------------
    # ESCAPED VALUES
    # --------------------------------
    shipping_date = e(timing.get("shipping_date", ""))
    gate_x_date = e(timing.get("gate_x_date", ""))
    notes = e(timing.get("notes", ""))

    # --------------------------------------------------
    # Load country list from DB
    # --------------------------------------------------
    countries = get_country_codes()

    country_name_lookup = {
        str(c["CountryCode"]): str(c["CountryName"])
        for c in countries
    }

    country_options = ""
    for c in countries:
        code = e(c["CountryCode"])
        name = e(c["CountryName"])
        country_options += f'<option value="{code}">{name}</option>'

    selected_countries = timing.get("countries", []) or []
    if isinstance(selected_countries, str):
        selected_countries = [selected_countries]

    selected_country_rows_html = ""

    for country_code in selected_countries:
        if not country_code:
            continue

        country_code_raw = str(country_code)
        country_code_html = e(country_code_raw)

        if country_code_raw == "GLOBAL":
            country_label = "All Countries / Global"
        else:
            country_label = country_name_lookup.get(country_code_raw, country_code_raw)

        selected_country_rows_html += f"""
                <div class="country-row">
                    <span class="country-label">{e(country_label)}</span>
                    <input type="hidden" name="countries[]" value="{country_code_html}">
                    <button type="button" class="product-danger-lite-button" onclick="removeCountry(this)">Remove</button>
                </div>
        """

    if not selected_country_rows_html:
        selected_country_rows_html = f"""
                <div class="country-row">
                    <select name="countries[]" required onchange="lockCountrySelection(this)">
                        <option value="">Select Country</option>
                        <option value="GLOBAL">All Countries / Global</option>
                        {country_options}
                    </select>
                </div>
        """

    main_content_html = f"""
    <div class="page-header">
        <p class="page-kicker">Product Trial Request</p>
        <h2 class="page-title">Timing & Scope</h2>
        <p class="page-description">
            Define the target shipping window, decision timing, and country scope for this trial request.
        </p>
    </div>

    {wizard_status_html}

    <form method="post" action="/product/request-trial/wizard/timing">
        <input type="hidden" name="csrf_token" value="{csrf_token}" />
        <input type="hidden" name="project_id" value="{project_id}" />

        <div class="form-group">
            <label class="field-label">Target Shipping Date</label>
            <input
                type="date"
                name="shipping_date"
                value="{shipping_date}"
                required
            />
            <p class="field-hint">
                Date when units are expected to ship, or when tracking numbers are expected to become available.
            </p>
        </div>

        <div class="form-group">
            <label class="field-label">Gate X / Decision Date</label>
            <input
                type="date"
                name="gate_x_date"
                value="{gate_x_date}"
            />
            <p class="field-hint">
                Date by which results are needed for a go / no-go decision.
            </p>
        </div>

        <div class="form-group">
            <label class="field-label">Target Countries</label>

            <div id="country-container">
                {selected_country_rows_html}
            </div>

            <div style="margin-top:8px;">
                <button type="button" class="product-add-row-button" onclick="addCountryRow()">
                    + Add Country
                </button>
            </div>

            <div id="country-template" style="display:none;">
                <select name="countries[]">
                    <option value="">Select Country</option>
                    <option value="GLOBAL">All Countries / Global</option>
                    {country_options}
                </select>
            </div>

        </div>

        <div class="form-group">
            <label class="field-label">Timing & Scope Notes</label>
            <textarea name="notes" rows="3">{notes}</textarea>
            <p class="field-hint">
                Add any timing constraints, sample-size assumptions, or regional requirements the UT team should know.
            </p>
        </div>

        <div class="form-actions">
            <button type="submit" class="primary">
                Save & Continue
            </button>

            <button
                type="submit"
                class="secondary request-cancel-button"
                formaction="/product/request-trial/cancel"
                formmethod="post"
                formnovalidate
            >
                Cancel Request
            </button>
        </div>
    </form>

    <script>
    function lockCountrySelection(selectEl) {{
        var row = selectEl.parentElement;
        var value = selectEl.value;
        var text = selectEl.options[selectEl.selectedIndex].text;
        if (!value) return;

        row.innerHTML =
            '<span class="country-label">' + text + '</span>' +
            '<input type="hidden" name="countries[]" value="' + value + '">' +
            '<button type="button" class="product-danger-lite-button" onclick="removeCountry(this)">Remove</button>';
    }}

    function addCountryRow() {{
        var container = document.getElementById("country-container");
        var template = document.getElementById("country-template");

        var row = document.createElement("div");
        row.className = "country-row";

        var select = template.querySelector("select").cloneNode(true);
        select.setAttribute("onchange", "lockCountrySelection(this)");

        row.appendChild(select);
        container.appendChild(row);
    }}

    function removeCountry(btn) {{
        btn.parentElement.remove();
    }}
    </script>
    """

    summary_html = _render_project_summary_right_rail(
        project=project, wizard_state=wizard_state
    )

    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", "")
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", summary_html)

    html = product_base.replace("__BODY__", body)
    html = inject_nav(html)

    return {"html": html}


def render_product_request_trial_wizard_stakeholders_get(
    *,
    user_id: str,
    project_id: str,
    base_template: str,
    inject_nav,
    query_params: dict | None = None,
):
    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    project = get_trial_project(project_id)
    if not project or project.get("status") != "draft":
        return {"redirect": "/product/request-trial"}

    if not _can_access_product_request(user_id=user_id, project=project):
        return {"redirect": "/product/request-trial"}

    product_base, product_layout = _load_product_team_templates()
    left_rail_html = _render_product_left_rail_for_user(user_id=user_id)

    wizard_state = derive_wizard_state(project)
    wizard_status_html = _render_product_wizard_status(
        current_step="stakeholders",
        wizard_state=wizard_state,
        project_id=project_id,
    )

    stakeholders = project.get("stakeholders", {})
    roles = stakeholders.get("roles", []) if isinstance(stakeholders, dict) else []
    notes_val = stakeholders.get("notes", "") if isinstance(stakeholders, dict) else ""

    # --------------------------------
    # CSRF TOKEN
    # --------------------------------
    csrf_token = generate_csrf_token(user_id)

    error_key = ""
    if query_params:
        error_key = query_params.get("error", [""])[0]

    error_html = ""
    if error_key == "invalid_stakeholder_email":
        error_html = """
        <div class="product-form-alert product-form-alert-error">
            Stakeholder emails must be valid @logitech.com addresses.
        </div>
        """

    # --------------------------------------------------
    # Normalize stakeholders for rendering
    # --------------------------------------------------
    if not roles:
        roles = [{"email": "", "role": ""}]
    else:
        roles = roles + [{"email": "", "role": ""}]

    role_options = ["", "GPM", "PQA", "PM", "Other"]

    stakeholder_rows_html = ""

    for r in roles:
        email_val = e(r.get("email") or "")
        role_val = r.get("role", "")
        linked_user_id = r.get("user_id")

        options_html = ""
        for opt in role_options:
            label = "Select Role" if opt == "" else opt
            selected = "selected" if opt == role_val else ""
            options_html += f'<option value="{opt}" {selected}>{label}</option>'

        registration_notice_html = ""
        if email_val and not linked_user_id:
            registration_notice_html = """
                <div class="stakeholder-registration-warning">
                    Not currently registered in UTS. They will gain access after registration or SSO linking.
                </div>
            """

        stakeholder_rows_html += f"""
            <div class="stakeholder-row-group">
                <div class="stakeholder-row">
                    <input
                        type="email"
                        name="stakeholder_email[]"
                        placeholder="name@logitech.com"
                        pattern="^[^@]+@logitech[.]com$"
                        value="{email_val}"
                    />

                    <select name="stakeholder_role[]">
                        {options_html}
                    </select>

                    <button
                        type="button"
                        class="product-danger-lite-button stakeholder-remove-button"
                        onclick="removeStakeholderRow(this)"
                    >
                        Remove
                    </button>
                </div>
                {registration_notice_html}
            </div>
        """

    notes_html = e(notes_val)

    main_content_html = f"""
    <div class="page-header">
        <p class="page-kicker">Product Trial Request</p>
        <h2 class="page-title">Stakeholders</h2>
        <p class="page-description">
            Identify the key Product Team contacts who should be associated with this trial request.
        </p>
    </div>

    {wizard_status_html}

    {error_html}

    <form method="post" action="/product/request-trial/wizard/stakeholders" novalidate>
        <input type="hidden" name="csrf_token" value="{csrf_token}" />
        <input type="hidden" name="project_id" value="{project_id}" />

        <section>
            <h3 class="section-title">Product Team Contacts</h3>
            <p class="section-description">
                Add the primary stakeholders for this request by Logitech email address. This keeps
                stakeholder access compatible with future SSO linking.
            </p>

            <div id="stakeholder-container">
                {stakeholder_rows_html}
            </div>

            <div style="margin-top: 8px;">
                <button type="button" class="product-add-row-button" onclick="addStakeholderRow()">
                    + Add Stakeholder
                </button>
            </div>
        </section>

        <div class="form-group">
            <label class="field-label">Additional Notes</label>
            <textarea name="notes" rows="3">{notes_html}</textarea>
            <p class="field-hint">
                Add any stakeholder context, escalation notes, or communication preferences the UT team should know.
            </p>
        </div>

        <div class="form-actions">
            <button type="submit" class="primary">
                Save & Continue
            </button>

            <button
                type="submit"
                class="secondary request-cancel-button"
                formaction="/product/request-trial/cancel"
                formmethod="post"
                formnovalidate
            >
                Cancel Request
            </button>
        </div>
    </form>
    """

    summary_html = _render_project_summary_right_rail(
        project=project, wizard_state=wizard_state
    )

    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", "")
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", summary_html)

    html = product_base.replace("__BODY__", body)
    html = inject_nav(html)

    return {"html": html}


def render_product_request_trial_wizard_review_get(
    *,
    user_id: str,
    project_id: str,
    base_template: str,
    inject_nav,
    query_params: dict | None = None,
):
    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    project = get_trial_project(project_id)
    if not project or project.get("status") != "draft":
        return {"redirect": "/product/request-trial"}

    if not _can_access_product_request(user_id=user_id, project=project):
        return {"redirect": "/product/request-trial"}

    product_base, product_layout = _load_product_team_templates()
    left_rail_html = _render_product_left_rail_for_user(user_id=user_id)

    wizard_state = derive_wizard_state(project)
    wizard_status_html = _render_product_wizard_status(
        current_step="review",
        wizard_state=wizard_state,
        project_id=project_id,
    )

    basics = project.get("basics", {})
    timing = project.get("timing_scope", {})
    stakeholders = project.get("stakeholders", {})

    # --------------------------------
    # CSRF TOKEN
    # --------------------------------
    csrf_token = generate_csrf_token(user_id)

    # --------------------------------
    # ESCAPED VALUES
    # --------------------------------
    project_name = e(basics.get("project_name", "—"))
    market_name = e(basics.get("market_name", "—"))
    business_group = e(basics.get("business_group", "—"))
    product_category = e(basics.get("product_category", "—"))
    purpose = e(basics.get("purpose", "—"))

    shipping_date = e(timing.get("shipping_date", "—"))
    gate_x_date = e(timing.get("gate_x_date", "—"))
    regions = e(", ".join(timing.get("countries", [])) or "—")
    
    stakeholder_rows_html = ""
    unregistered_stakeholder_count = 0
    roles = stakeholders.get("roles", []) if isinstance(stakeholders, dict) else []

    for role in roles:
        display_name = e(
            role.get("display_name")
            or role.get("name")
            or role.get("email")
            or "—"
        )
        email = e(role.get("email") or "")
        role_name = e(role.get("role", "—"))
        linked_user_id = role.get("user_id")

        if email:
            role_detail = f"{role_name} · {email}"
        else:
            role_detail = role_name

        registration_badge_html = ""
        if email and not linked_user_id:
            unregistered_stakeholder_count += 1
            registration_badge_html = """
            <div class="product-review-person-warning">
                Not registered in UTS yet
            </div>
            """

        stakeholder_rows_html += f"""
        <div class="product-review-person">
            <div class="product-review-person-name">{display_name}</div>
            <div class="product-review-person-role">{role_detail}</div>
            {registration_badge_html}
        </div>
        """

    if not stakeholder_rows_html:
        stakeholder_rows_html = """
        <p class="product-review-empty">No stakeholders listed.</p>
        """

    stakeholder_registration_alert_html = ""
    if unregistered_stakeholder_count:
        stakeholder_registration_alert_html = f"""
        <div class="product-form-alert product-form-alert-warning">
            {unregistered_stakeholder_count} stakeholder(s) are not registered in UTS yet.
            They will not be able to view this request until their account is registered or linked through SSO.
        </div>
        """

    main_content_html = f"""
    <div class="page-header">
        <p class="page-kicker">Product Trial Request</p>
        <h2 class="page-title">Review & Submit</h2>
        <p class="page-description">
            Review the request details that will be submitted to the User Trials team.
            Confirm that the project, timing, scope, and stakeholder information are accurate.
        </p>
    </div>

    {wizard_status_html}

    {stakeholder_registration_alert_html}

    <div class="product-review-grid">
        <section class="product-review-card">
            <h3 class="section-title">Project Overview</h3>
            <dl class="product-review-list">
                <dt>Project Name</dt>
                <dd>{project_name}</dd>

                <dt>Market Name</dt>
                <dd>{market_name}</dd>

                <dt>Business Group</dt>
                <dd>{business_group}</dd>

                <dt>Product Category</dt>
                <dd>{product_category}</dd>
            </dl>
        </section>

        <section class="product-review-card">
            <h3 class="section-title">Timing & Scope</h3>
            <dl class="product-review-list">
                <dt>Target Shipping Date</dt>
                <dd>{shipping_date}</dd>

                <dt>Gate X</dt>
                <dd>{gate_x_date}</dd>

                <dt>Regions</dt>
                <dd>{regions}</dd>
            </dl>

            <p class="field-hint">
                Final timelines are confirmed by the UT Lead based on capacity,
                holidays, and trial complexity.
            </p>
        </section>

        <section class="product-review-card">
            <h3 class="section-title">Stakeholders</h3>
            <div class="product-review-people">
                {stakeholder_rows_html}
            </div>
        </section>

        <section class="product-review-card">
            <h3 class="section-title">Additional Context</h3>
            <p class="product-review-note">
                {purpose}
            </p>
        </section>

        <form class="review-submit-form product-review-actions" method="post" action="/product/request-trial/submit">
            <input type="hidden" name="csrf_token" value="{csrf_token}" />
            <input type="hidden" name="project_id" value="{project_id}" />

            <button class="primary review-submit-button">
                Submit for UT Review
            </button>

            <button
                type="submit"
                class="secondary request-cancel-button"
                formaction="/product/request-trial/cancel"
                formmethod="post"
                formnovalidate
            >
                Cancel Request
            </button>

            <p class="field-hint">
                After submission, this request will be locked for UT review.
                Cancel deletes this draft request and removes it from Drafting.
            </p>
        </form>
    </div>
    """

    summary_html = _render_project_summary_right_rail(
        project=project, wizard_state=wizard_state
    )

    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", "")
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", summary_html)

    html = product_base.replace("__BODY__", body)
    html = inject_nav(html)

    return {"html": html}

def render_product_request_trial_pending_get(
    *,
    user_id: str,
    project_id: str,
    base_template: str,
    inject_nav,
):
    """
    GET /product/request-trial/pending
    """

    from pathlib import Path
    from app.db.user_roles import get_effective_permission_level
    from app.db.project_rounds import get_project_with_latest_round

    permission_level = get_effective_permission_level(user_id)
    if permission_level < 50:
        return {"redirect": "/dashboard"}

    if not project_id:
        return {"redirect": "/product/request-trial"}
    
    result = get_project_with_latest_round(project_id=project_id)
    if not result:
        return {"redirect": "/product/request-trial"}

    project_row, round_row = result

    if not _can_access_product_request(user_id=user_id, project=project_row):
        return {"redirect": "/product/request-trial"}

    from app.db.project_rounds import get_round_stakeholders

    stakeholders = get_round_stakeholders(
        round_id=round_row["RoundID"]
    ) or []

    product_base = Path(
        "app/templates/product_team/base_product_team.html"
    ).read_text(encoding="utf-8")

    product_layout = Path(
        "app/templates/product_team/product_layout.html"
    ).read_text(encoding="utf-8")

    left_rail_html = _render_product_left_rail_for_user(user_id=user_id)

    # --------------------------------
    # ESCAPE VALUES
    # --------------------------------
    project_name = e(project_row.get("ProjectName", "—"))
    market_name = e(project_row.get("MarketName", "—"))
    business_group = e(project_row.get("BusinessGroup", "—"))
    product_type = e(project_row.get("ProductType", "—"))

    shipping_date = e(str(round_row.get("StartDate", "—")))
    gate_x = e(str(project_row.get("GateX_Date", "—")))
    regions = e(str(round_row.get("Region", "—")))

    # --------------------------------
    # Stakeholders
    # --------------------------------
    stakeholder_rows = ""

    for s in stakeholders:
        name = e(s.get("DisplayName", "—"))
        role = e(s.get("StakeholderRole", "—"))

        stakeholder_rows += f"""
        <div class="product-review-person">
            <div class="product-review-person-name">{name}</div>
            <div class="product-review-person-role">{role}</div>
        </div>
        """

    if not stakeholder_rows:
        stakeholder_rows = """
        <p class="product-review-empty">No stakeholders submitted.</p>
        """

    # --------------------------------
    # MAIN CONTENT
    # --------------------------------
    main_content_html = f"""
    <div class="page-header">
        <p class="page-kicker">Product Trial Request</p>
        <h2 class="page-title">Pending UT Approval</h2>
        <p class="page-description">
            Your User Trial request has been submitted successfully and is currently
            under review by the User Trials team.
        </p>
    </div>

    <div class="product-review-grid">
        <section class="product-review-card">
            <h3 class="section-title">Project Overview</h3>
            <dl class="product-review-list">
                <dt>Project Name</dt>
                <dd>{project_name}</dd>

                <dt>Market Name</dt>
                <dd>{market_name}</dd>

                <dt>Business Group</dt>
                <dd>{business_group}</dd>

                <dt>Product Category</dt>
                <dd>{product_type}</dd>
            </dl>
        </section>

        <section class="product-review-card">
            <h3 class="section-title">Timing & Scope</h3>
            <dl class="product-review-list">
                <dt>Target Shipping Date</dt>
                <dd>{shipping_date}</dd>

                <dt>Gate X</dt>
                <dd>{gate_x}</dd>

                <dt>Regions</dt>
                <dd>{regions}</dd>
            </dl>
        </section>

        <section class="product-review-card">
            <h3 class="section-title">Stakeholders</h3>
            <div class="product-review-people">
                {stakeholder_rows}
            </div>
        </section>

        <section class="product-review-card">
            <h3 class="section-title">Current Status</h3>
            <p class="product-review-note">
                This request is locked while pending UT approval.
            </p>
        </section>

        <div class="product-review-actions">
            <button
                type="button"
                class="secondary review-withdraw-button"
                disabled
                title="Withdraw request wiring will be added in a later pass."
            >
                Withdraw Request (FPO)
            </button>

            <p class="field-hint">
                Withdraw request behavior will be wired in a later pass.
            </p>
        </div>
    </div>
    """

    summary_html = f"""
    <div class="summary-block">
        <h4 class="summary-title">Request Summary</h4>
        <dl class="summary-list">
            <dt>Project</dt>
            <dd>{project_name}</dd>

            <dt>Market</dt>
            <dd>{market_name}</dd>

            <dt>Category</dt>
            <dd>{product_type}</dd>

            <dt>Shipping</dt>
            <dd>{shipping_date}</dd>

            <dt>Gate X</dt>
            <dd>{gate_x}</dd>

            <dt>Countries</dt>
            <dd>{regions}</dd>
        </dl>
    </div>
    """

    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", "")
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", summary_html)

    html = product_base.replace("__BODY__", body)
    html = inject_nav(html)

    return {"html": html}

def render_product_request_trial_info_requested_get(
    *,
    user_id: str,
    project_id: str,
    base_template: str,
    inject_nav,
):
    from pathlib import Path
    from app.db.user_roles import get_effective_permission_level
    from app.db.project_rounds import get_project_with_latest_round
    from app.db.approval_actions import get_latest_request_info_action

    # Permission gate
    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    result = get_project_with_latest_round(project_id=project_id)
    if not result:
        return {"redirect": "/product/request-trial"}

    project, round_ = result

    if not _can_access_product_request(user_id=user_id, project=project):
        return {"redirect": "/product/request-trial"}

    # Explicit state gate
    if round_["Status"] != "info_requested":
        return {"redirect": "/product/request-trial"}

    request_action = get_latest_request_info_action(round_id=round_["RoundID"])
    if not request_action:
        return {"redirect": "/product/request-trial"}

    product_base = Path(
        "app/templates/product_team/base_product_team.html"
    ).read_text(encoding="utf-8")

    product_layout = Path(
        "app/templates/product_team/product_layout.html"
    ).read_text(encoding="utf-8")

    left_rail_html = _render_product_left_rail_for_user(user_id=user_id)

    # --------------------------------
    # CSRF TOKEN
    # --------------------------------
    csrf_token = generate_csrf_token(user_id)

    # --------------------------------
    # ESCAPED VALUES
    # --------------------------------
    reason_text = e(request_action.get("ReasonText", "—"))

    main_content_html = f"""
    <div class="page-header">
        <p class="page-kicker">Product Trial Request</p>
        <h2 class="page-title">Information Requested</h2>
        <p class="page-description">
            The User Trials team needs additional information before proceeding with this request.
        </p>
    </div>

    <section class="review-section">
        <h3 class="section-title">Request from User Trials</h3>
        <div class="callout warning">
            {reason_text}
        </div>
    </section>

    <form method="post" action="/product/request-trial/info-requested/respond">
        <input type="hidden" name="csrf_token" value="{csrf_token}" />
        <input type="hidden" name="project_id" value="{project_id}" />

        <div class="form-group">
            <label class="field-label">Your Response</label>
            <textarea name="response_text" rows="5" required></textarea>
            <p class="field-hint">
                The UT team will update the request directly based on this information.
            </p>
        </div>

        <div class="form-actions">
            <button class="primary">Submit Information</button>
        </div>
    </form>
    """

    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", "")
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", "")

    html = product_base.replace("__BODY__", body)
    html = inject_nav(html)

    return {"html": html}

def render_product_request_trial_change_requested_get(
    *,
    user_id: str,
    project_id: str,
    base_template: str,
    inject_nav,
):
    from pathlib import Path
    from app.db.user_roles import get_effective_permission_level
    from app.db.project_rounds import get_project_with_latest_round
    from app.db.approval_actions import get_latest_change_request_action

    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    result = get_project_with_latest_round(project_id=project_id)
    if not result:
        return {"redirect": "/product/request-trial"}

    project, round_ = result
    round_id = round_["RoundID"]

    if not _can_access_product_request(user_id=user_id, project=project):
        return {"redirect": "/product/request-trial"}

    if round_["Status"] != "change_requested":
        return {"redirect": "/product/request-trial"}

    change_action = get_latest_change_request_action(round_id=round_id)

    product_base = Path(
        "app/templates/product_team/base_product_team.html"
    ).read_text(encoding="utf-8")

    product_layout = Path(
        "app/templates/product_team/product_layout.html"
    ).read_text(encoding="utf-8")

    left_rail_html = _render_product_left_rail_for_user(user_id=user_id)

    # --------------------------------
    # CSRF TOKENS (TWO FORMS)
    # --------------------------------
    csrf_token_main = generate_csrf_token(user_id)
    csrf_token_admin = generate_csrf_token(user_id)

    # --------------------------------
    # ESCAPED VALUES
    # --------------------------------
    reason_text = e(change_action.get("ReasonText", "—"))

    main_content_html = f"""
    <div class="page-header">
        <p class="page-kicker">Product Trial Request</p>
        <h2 class="page-title">Change Requested</h2>
        <p class="page-description">
            The User Trials team has proposed a change before this request can proceed.
        </p>
    </div>

    <section class="review-section">
        <h3 class="section-title">Proposed Change</h3>
        <div class="callout warning">
            {reason_text}
        </div>
    </section>

    <form method="post" action="/product/request-trial/change-requested/respond">
        <input type="hidden" name="csrf_token" value="{csrf_token_main}" />
        <input type="hidden" name="round_id" value="{round_id}" />
        <input type="hidden" name="decision" value="" />

        <div class="form-group">
            <label class="field-label">Counter Proposal Details</label>
            <textarea
                name="detail_text"
                rows="4"
                placeholder="Explain what you can and cannot change…"
            ></textarea>
            <p class="field-hint">
                Add constraints or alternatives only if you plan to counter the proposed change.
            </p>
        </div>

        <div class="form-actions">
            <button
                type="submit"
                class="primary"
                onclick="this.form.decision.value='accept';"
            >
                Accept Proposed Change
            </button>

            <button
                type="submit"
                class="secondary"
                onclick="this.form.decision.value='counter';"
            >
                Counter Proposal
            </button>
        </div>
    </form>

    <form
        method="post"
        action="/admin/approval"
        onsubmit="return confirm('Are you sure you want to withdraw this trial request?');"
        style="margin-top: 2rem;"
    >
        <input type="hidden" name="csrf_token" value="{csrf_token_admin}" />
        <input type="hidden" name="approval_type" value="product_trial" />
        <input type="hidden" name="approval_id" value="{round_id}" />
        <input type="hidden" name="action" value="withdraw" />

        <button type="submit" class="danger">
            Withdraw Trial Request
        </button>
    </form>
    """

    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", "")
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", "")

    html = product_base.replace("__BODY__", body)
    html = inject_nav(html)

    return {"html": html}

def handle_product_request_trial_info_requested_respond_post(
    *,
    user_id: str,
    data: dict,
):
    # --------------------------------------------------
    # CSRF protection
    # --------------------------------------------------
    # Validated in app/main.py before handler delegation.

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    # --------------------------------------------------
    # Input extraction
    # --------------------------------------------------
    project_id_list = data.get("project_id")
    project_id = project_id_list[0] if project_id_list else None

    info_text = (data.get("response_text", [""])[0] or "").strip()

    if not project_id or not info_text:
        return {"error": "missing_required_fields"}

    result = get_project_with_latest_round(project_id=project_id)
    if not result:
        return {"redirect": "/product/request-trial"}

    project, round_ = result

    # --------------------------------------------------
    # Ownership validation (IDOR protection)
    # --------------------------------------------------
    if not _can_access_product_request(user_id=user_id, project=project):
        return {"redirect": "/product/request-trial"}

    # --------------------------------------------------
    # 1️⃣ Append approval action
    # --------------------------------------------------
    insert_approval_action(
        approval_type="product_trial",
        approval_id=round_["RoundID"],
        action_type="info_provided",
        reason_category=None,
        reason_text=info_text,
        assigned_ut_lead_id=None,
        action_by_user_id=user_id,
    )

    # --------------------------------------------------
    # 2️⃣ Lifecycle transition
    # --------------------------------------------------
    mark_project_round_pending_ut_review(
        project_id=project_id
    )

    # --------------------------------------------------
    # 3️⃣ Notify UT
    # --------------------------------------------------
    if round_.get("UTLead_UserID"):
        notify_user(
            user_id=round_["UTLead_UserID"],
            type_key="product_trial_info_provided",
            context={
                "project_id": project_id,
                "round_id": round_["RoundID"],
                "round_name": round_["RoundName"],
            },
            created_by=user_id,
        )

    return {"redirect": "/product/request-trial"}

def handle_product_request_trial_change_requested_respond_post(
    *,
    user_id: str,
    data: dict,
):
    """
    Product Team response to UT 'request changes'.
    Returns round to pending_ut_review.
    """

    # --------------------------------------------------
    # CSRF protection
    # --------------------------------------------------
    # Validated in app/main.py before handler delegation.

    round_id = data.get("round_id", [None])[0]
    decision = data.get("decision", [""])[0]

    if not round_id or not decision:
        return {"error": "Missing required fields", "status": 400}

    if decision not in {"accept", "counter", "withdraw"}:
        return {"error": "invalid_decision", "status": 400}

    try:
        round_id = int(round_id)
    except:
        return {"redirect": "/dashboard"}

    from app.services.round_access import validate_round_access

    validated_round = validate_round_access(
        actor_user_id=user_id,
        round_id=round_id,
        required_role="product",
        allow_admin=True,
    )

    if not validated_round:
        return {"redirect": "/dashboard"}

    detail_text = (data.get("detail_text", [""])[0] or "").strip()

    from app.db.project_rounds import (
        get_project_with_latest_round,
        set_project_round_status,
    )
    from app.db.approval_actions import insert_approval_action
    from app.services.notifications import notify_user

    result = get_project_with_latest_round(round_id=validated_round["RoundID"])
    if not result:
        return {"redirect": "/product/request-trial"}

    project, round_ = result
    ut_lead_id = round_.get("UTLead_UserID")

    if not ut_lead_id:
        from app.db.user_roles import get_users_with_permission_levels

        admins = get_users_with_permission_levels([100])
        ut_lead_id = admins[0]["user_id"] if admins else None

    if decision == "accept":
        insert_approval_action(
            approval_type="product_trial",
            approval_id=int(round_id),
            action_type="change_accepted",
            reason_category=None,
            reason_text=None,
            assigned_ut_lead_id=None,
            action_by_user_id=user_id,
        )

        if ut_lead_id:
            notify_user(
                user_id=ut_lead_id,
                type_key="product_trial_change_accepted",
                context={
                    "project_id": project.get("ProjectID"),
                    "round_id": round_id,
                },
                created_by=user_id,
            )

    elif decision == "counter":
        if not detail_text:
            return {
                "error": "Counter proposal requires explanation",
                "status": 400,
            }

        insert_approval_action(
            approval_type="product_trial",
            approval_id=int(round_id),
            action_type="change_countered",
            reason_category=None,
            reason_text=detail_text,
            assigned_ut_lead_id=None,
            action_by_user_id=user_id,
        )

        if ut_lead_id:
            notify_user(
                user_id=ut_lead_id,
                type_key="product_trial_change_countered",
                context={
                    "project_id": project.get("ProjectID"),
                    "round_id": round_id,
                    "reason": detail_text,
                },
                created_by=user_id,
            )

    elif decision == "withdraw":
        insert_approval_action(
            approval_type="product_trial",
            approval_id=int(round_id),
            action_type="withdraw_request",
            reason_category=None,
            reason_text=detail_text or None,
            assigned_ut_lead_id=None,
            action_by_user_id=user_id,
        )

        set_project_round_status(
            round_id=validated_round["RoundID"],
            status="withdrawn",
        )

        if ut_lead_id:
            notify_user(
                user_id=ut_lead_id,
                type_key="product_trial_withdrawn_by_requestor",
                context={
                    "project_id": project.get("ProjectID"),
                    "round_id": round_id,
                },
                created_by=user_id,
            )

        return {"redirect": "/product/request-trial"}

    else:
        return {"error": f"Invalid decision: {decision}", "status": 400}

    set_project_round_status(
        round_id=validated_round["RoundID"],
        status="pending_ut_review",
    )

    return {"redirect": "/product/request-trial"}

def render_product_current_trials_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict | None = None,
):
    """
    GET /product/current-trials
    GET /product/current-trials?round_id=...

    Read-only Product Team view of approved User Trials.
    """

    from pathlib import Path
    from app.db.user_roles import get_effective_permission_level
    from app.db.user_roles import get_users_with_permission_levels
    from app.db.user_pool_country_codes import get_country_codes
    from app.db.project_rounds import (
        get_current_project_rounds_for_user,
        get_project_round_by_id_for_user,
    )

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    round_id = None
    if query_params:
        round_id = query_params.get("round_id", [None])[0]

    # --------------------------------------------------
    # Templates
    # --------------------------------------------------
    product_base = Path(
        "app/templates/product_team/base_product_team.html"
    ).read_text(encoding="utf-8")

    product_layout = Path(
        "app/templates/product_team/product_layout.html"
    ).read_text(encoding="utf-8")

    left_rail_html = _render_product_left_rail_for_user(user_id=user_id)
    product_context_html = ""

    def display_value(value):
        if value in (None, ""):
            return "—"

        raw = str(value)

        if raw.lower() == "none":
            return "—"

        return e(raw)

    def status_label(value):
        raw = (str(value or "")).lower()

        status_map = {
            "approved": "Preparing",
            "running": "In Progress",
            "recruiting": "Recruiting",
            "closed": "Completed",
            "pending_ut_review": "Pending UT Review",
            "info_requested": "Information Requested",
            "change_requested": "Change Requested",
        }

        return status_map.get(raw, "—")

    def render_review_list(rows):
        parts = []

        for label, value in rows:
            parts.append(f"""
                <dt>{e(label)}</dt>
                <dd>{value}</dd>
            """)

        return f"""
        <dl class="product-review-list">
            {''.join(parts)}
        </dl>
        """

    def render_summary_block(title, rows):
        parts = []

        for label, value in rows:
            parts.append(f"""
                <dt>{e(label)}</dt>
                <dd>{value}</dd>
            """)

        return f"""
        <div class="summary-block">
            <h4 class="summary-title">{e(title)}</h4>
            <dl class="summary-list">
                {''.join(parts)}
            </dl>
        </div>
        """

    # --------------------------------------------------
    # Detail view (single round)
    # --------------------------------------------------
    if round_id:
        round_row = get_project_round_by_id_for_user(
            user_id=user_id,
            round_id=round_id,
        )
        if not round_row:
            return {"redirect": "/product/current-trials"}

        # --------------------------------------------------
        # Load supporting data
        # --------------------------------------------------
        from app.db.user_pool_country_codes import get_country_codes
        from app.db.user_trial_lead import get_round_surveys  # <-- confirm this exists

        # Country lookup
        countries = get_country_codes()
        country_lookup = {c["CountryCode"]: c["CountryName"] for c in countries}

        region_raw = round_row.get("Region") or ""
        region_names = []

        for code in region_raw.split(","):
            code = code.strip()
            if code:
                region_names.append(country_lookup.get(code, code))

        region_display = ", ".join(region_names) if region_names else "—"

        # --------------------------------------------------
        # Survey Data
        # --------------------------------------------------
        round_surveys = get_round_surveys(round_id=round_id)

        consolidated_link_html = '<span class="muted small">—</span>'

        for s in round_surveys or []:
            survey_type = (s.get("SurveyTypeName") or "").lower()
            survey_link = s.get("SurveyLink")

            # Only show if edit link exists (your rule)
            if survey_type == "consolidated" and survey_link:
                consolidated_link_html = f"""
                <a href="{survey_link}" target="_blank" rel="noopener noreferrer">
                    View Survey
                </a>
                """

        # --------------------------------------------------
        # Layout Helpers (LOCAL)
        # --------------------------------------------------
        def render_grid(rows):
            items = []
            for label, value in rows:
                items.append(f"""
                    <dt style="font-weight:600;color:#555;">{label}</dt>
                    <dd>{value}</dd>
                """)
            return f"""
            <dl style="
                display:grid;
                grid-template-columns:200px 1fr;
                gap:10px 20px;
                align-items:start;
                margin:0;
            ">
                {''.join(items)}
            </dl>
            """

        # --------------------------------------------------
        # Country Expansion
        # --------------------------------------------------
        from app.db.user_pool_country_codes import get_country_codes
        countries = get_country_codes()
        country_lookup = {c["CountryCode"]: c["CountryName"] for c in countries}

        region_raw = round_row.get("Region") or ""
        region_names = []

        for code in region_raw.split(","):
            code = code.strip()
            if code:
                region_names.append(country_lookup.get(code, code))

        region_display = ", ".join(region_names) if region_names else "—"

        # --------------------------------------------------
        # Survey Data
        # --------------------------------------------------
        from app.db.user_trial_lead import get_round_surveys
        round_surveys = get_round_surveys(round_id=round_id)

        consolidated_link_html = '<span class="muted small">—</span>'

        for s in round_surveys or []:
            survey_type = (s.get("SurveyTypeName") or "").lower()
            survey_link = s.get("SurveyLink")

            if survey_type == "consolidated" and survey_link:
                consolidated_link_html = f"""
                <a href="{survey_link}" target="_blank" rel="noopener noreferrer">
                    View Survey
                </a>
                """

        # --------------------------------------------------
        # Core Rows
        # --------------------------------------------------
        core_rows = [
            ("Status", round_row.get("Status", "—")),
            ("Shipping Date", round_row.get("StartDate") or "—"),
            ("Gate X", round_row.get("GateX_Date") or "—"),
            ("Countries", region_display),
        ]

        # -------------------------
        # User Profile Data Prep
        # -------------------------

        from app.db.user_trial_lead import get_round_profile_criteria
        from app.db.user_pool_country_codes import get_country_codes

        # Country mapping
        countries = get_country_codes()
        country_lookup = {
            c["CountryCode"]: c["CountryName"]
            for c in countries
        }

        region_raw = round_row.get("Region") or ""
        region_names = []

        for code in region_raw.split(","):
            code = code.strip()
            if code:
                region_names.append(country_lookup.get(code, code))

        region_display = ", ".join(region_names) if region_names else "—"

        # Age
        min_age = round_row.get("MinAge")
        max_age = round_row.get("MaxAge")

        if min_age and max_age:
            age_display = f"{min_age} – {max_age}"
        else:
            age_display = "—"

        # Profile Criteria
        criteria_rows = get_round_profile_criteria(int(round_row["RoundID"]))

        criteria_html_parts = []

        if criteria_rows:
            for c in criteria_rows:
                criteria_html_parts.append(
                    f"""
                    <div class="kv-row">
                        <div class="kv-label">{c['Operator']}</div>
                        <div class="kv-value">
                            {c['CategoryName']} → {c['LevelDescription']}
                        </div>
                    </div>
                    """
                )
        else:
            criteria_html_parts.append("""
                <div class="kv-row">
                    <div class="kv-label">Profile</div>
                    <div class="kv-value muted small">Not defined</div>
                </div>
            """)

        criteria_html = "".join(criteria_html_parts)

        # --------------------------------------------------
        # Build Survey Display (NEW)
        # --------------------------------------------------

        survey_rows_html = ""

        for s in round_surveys or []:

            survey_type = s.get("SurveyTypeName") or "—"
            edit_link = s.get("SurveyLink")
            dist_link = s.get("DistributionLink")

            # Edit link display
            if edit_link:
                edit_html = f"""
                <a href="{edit_link}" target="_blank" rel="noopener noreferrer">
                    Internal Link
                </a>
                """
            else:
                edit_html = '<span class="muted small">—</span>'

            # Distribution link display
            if dist_link:
                dist_html = f"""
                <a href="{dist_link}" target="_blank" rel="noopener noreferrer">
                    Participant Link
                </a>
                """
            else:
                dist_html = '<span class="muted small">—</span>'

            survey_rows_html += f"""
            <tr>
                <td>{survey_type}</td>
                <td>{edit_html}</td>
                <td>{dist_html}</td>
            </tr>
            """

        if not survey_rows_html:
            survey_rows_html = """
            <tr>
                <td colspan="3" class="muted small">
                    No surveys configured yet.
                </td>
            </tr>
            """

        survey_table_html = f"""
        <table class="data-table">
            <thead>
                <tr>
                    <th>Type</th>
                    <th>Internal</th>
                    <th>Participant</th>
                </tr>
            </thead>
            <tbody>
                {survey_rows_html}
            </tbody>
        </table>
        """

        # --------------------------------------------------
        # Render
        # --------------------------------------------------
        project_name_display = display_value(round_row.get("ProjectName"))
        status_display = status_label(round_row.get("Status"))
        shipping_date_display = display_value(
            round_row.get("ShipDate") or round_row.get("StartDate")
        )
        gate_x_display = display_value(round_row.get("GateX_Date"))
        countries_display = display_value(region_display)
        target_users_display = display_value(round_row.get("TargetUsers"))

        product_context_html = ""

        main_content_html = f"""
        <div class="page-header">
            <div class="product-title-row">
                <h2 class="page-title">Current Trial - {project_name_display}</h2>

                <a class="product-back-link" href="/product/current-trials">
                    ← Back to Current Trials
                </a>
            </div>

            <p class="page-description">
                Review the current Product Trial status, execution setup, surveys,
                and participant-facing resources.
            </p>
        </div>

        <div class="product-review-grid product-current-grid">
            <section class="product-review-card">
                <h3 class="section-title">Trial Overview</h3>
                {render_review_list([
                    ("Status", display_value(status_display)),
                    ("Shipping Date", shipping_date_display),
                    ("Gate X", gate_x_display),
                    ("Countries", countries_display),
                ])}
            </section>

            <section class="product-review-card">
                <h3 class="section-title">User Profile</h3>
                {render_review_list([
                    ("Age Range", display_value(age_display)),
                    ("Region", countries_display),
                    ("Target Users", target_users_display),
                ])}

                <div class="product-current-subsection">
                    <div class="summary-label">Profile Criteria</div>
                    <div class="product-current-criteria">
                        {criteria_html}
                    </div>
                </div>
            </section>

            <section class="product-review-card">
                <h3 class="section-title">Recruiting</h3>
                {render_review_list([
                    ("Status", '<span class="muted">Not configured</span>'),
                    ("Notes", '<span class="muted small">Opens once profile is defined</span>'),
                ])}
            </section>

            <section class="product-review-card">
                <h3 class="section-title">Participants</h3>
                <div class="empty-state product-current-empty">
                    <p class="empty-state-description">
                        No users selected yet.
                    </p>
                </div>
            </section>

            <section class="product-review-card product-current-wide-card">
                <h3 class="section-title">Surveys</h3>
                {survey_table_html}
            </section>

            <section class="product-review-card product-current-wide-card">
                <h3 class="section-title">Report an Issue</h3>
                <p class="product-review-note">
                    Available once the trial begins.
                </p>
            </section>
        </div>
        """

        summary_html = render_summary_block(
            "Trial Summary",
            [
                ("Project", project_name_display),
                ("Status", display_value(status_display)),
                ("Shipping", shipping_date_display),
                ("Gate X", gate_x_display),
                ("Countries", countries_display),
            ],
        )

    # --------------------------------------------------
    # List view (all current trials)
    # --------------------------------------------------
    else:
        rounds = get_current_project_rounds_for_user(user_id=user_id)

        # -------------------------
        # UT Lead lookup
        # -------------------------
        from app.db.user_pool import get_all_users

        users = get_all_users()

        ut_lookup = {}

        for u in users:
            name = f"{u.get('FirstName','')} {u.get('LastName','')}".strip()

            if not name:
                name = u.get("Email") or "—"   # fallback

            ut_lookup[u["user_id"]] = name
        # -------------------------
        # Country lookup
        # -------------------------
        countries = get_country_codes()
        country_lookup = {
            c["CountryCode"]: c["CountryName"]
            for c in countries
        }

        rows_html = ""

        for r in rounds:

            # -------------------------
            # Status Mapping
            # -------------------------
            status_display = status_label(r.get("Status"))

            # -------------------------
            # UT Lead
            # -------------------------
            ut_lead_id = r.get("UTLead_UserID")
            ut_lead_display = ut_lookup.get(ut_lead_id) or "—"

            # -------------------------
            # Region expansion
            # -------------------------
            region_raw = r.get("Region") or ""
            region_names = []

            for code in region_raw.split(","):
                code = code.strip()
                if code:
                    region_names.append(country_lookup.get(code, code))

            region_display = ", ".join(region_names) if region_names else "—"

            # -------------------------
            # Row render
            # -------------------------
            rows_html += f"""
            <tr>
                <td>
                    <a href="/product/current-trials?round_id={r["RoundID"]}">
                        {e(r.get("ProjectName", "—"))}
                    </a>
                </td>
                <td>{e(status_display)}</td>
                <td>{e(ut_lead_display)}</td>
                <td>{display_value(r.get("ShipDate") or r.get("StartDate"))}</td>
                <td>{e(region_display)}</td>
            </tr>
            """

        if not rows_html:
            rows_html = """
            <tr>
                <td colspan="5">No current trials</td>
            </tr>
            """

        main_content_html = f"""
        <div class="page-header">
            <h2 class="page-title">Current Trials</h2>
            <p class="page-description">
                View Product Trials that are approved, preparing, recruiting, or currently running.
            </p>
        </div>

        <section class="product-current-table-card">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Project</th>
                        <th>Status</th>
                        <th>User Trial Lead</th>
                        <th>Shipping Date</th>
                        <th>Region</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </section>
        """

        summary_html = """
        <div class="summary-block">
            <h4 class="summary-title">Current Trials</h4>
            <p class="muted small">
                Select a trial from the table to view its setup, surveys, recruiting status,
                and participant-facing resources.
            </p>
        </div>
        """

    # --------------------------------------------------
    # Assemble layout
    # --------------------------------------------------
    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", product_context_html)
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", summary_html)

    html = product_base.replace("__BODY__", body)
    html = inject_nav(html)

    return {"html": html}

def render_product_past_trials_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict | None = None,
):
    """
    GET /product/past-trials
    GET /product/past-trials?round_id=...

    Product Team archive view for closed trials and delivered artifacts.
    """

    from app.db.user_roles import get_effective_permission_level
    from app.db.project_rounds import (
        get_past_project_rounds_for_user,
        get_past_project_round_by_id_for_user,
    )
    from app.db.user_pool_country_codes import get_country_codes
    from app.db.user_trial_lead import get_round_surveys
    from pathlib import Path

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    round_id = None
    if query_params:
        round_id = query_params.get("round_id", [None])[0]

    # --------------------------------------------------
    # Templates
    # --------------------------------------------------
    product_base = Path(
        "app/templates/product_team/base_product_team.html"
    ).read_text(encoding="utf-8")

    product_layout = Path(
        "app/templates/product_team/product_layout.html"
    ).read_text(encoding="utf-8")

    left_rail_html = _render_product_left_rail_for_user(user_id=user_id)

    # --------------------------------------------------
    # Display helpers
    # --------------------------------------------------
    def display_value(value):
        if value in (None, ""):
            return "—"

        raw = str(value)

        if raw.lower() == "none":
            return "—"

        return e(raw)

    def display_date(value):
        if value in (None, ""):
            return "—"

        raw = str(value)

        if raw.lower() == "none":
            return "—"

        if " " in raw:
            raw = raw.split(" ", 1)[0]

        if "T" in raw:
            raw = raw.split("T", 1)[0]

        return e(raw)

    def pluralize_report_count(value):
        try:
            count = int(value or 0)
        except (TypeError, ValueError):
            count = 0

        if count == 1:
            return "1 report"

        return f"{count} reports"

    def expand_region(region_raw):
        countries = get_country_codes()
        country_lookup = {
            c["CountryCode"]: c["CountryName"]
            for c in countries
        }

        if not region_raw:
            return "—"

        names = []
        for code in str(region_raw).split(","):
            code = code.strip()
            if not code:
                continue
            names.append(country_lookup.get(code, code))

        return e(", ".join(names)) if names else "—"

    def render_review_list(rows):
        parts = []

        for label, value in rows:
            parts.append(f"""
                <dt>{e(label)}</dt>
                <dd>{value}</dd>
            """)

        return f"""
        <dl class="product-review-list">
            {''.join(parts)}
        </dl>
        """

    def render_summary_block(title, rows):
        parts = []

        for label, value in rows:
            parts.append(f"""
                <dt>{e(label)}</dt>
                <dd>{value}</dd>
            """)

        return f"""
        <div class="summary-block">
            <h4 class="summary-title">{e(title)}</h4>
            <dl class="summary-list">
                {''.join(parts)}
            </dl>
        </div>
        """

    # --------------------------------------------------
    # Detail view
    # --------------------------------------------------
    if round_id:
        try:
            round_id_int = int(round_id)
        except (TypeError, ValueError):
            return {"redirect": "/product/past-trials"}

        round_row = get_past_project_round_by_id_for_user(
            user_id=user_id,
            round_id=round_id_int,
        )

        if not round_row:
            return {"redirect": "/product/past-trials"}

        project_name_display = display_value(round_row.get("ProjectName"))
        product_type_display = display_value(round_row.get("ProductType"))
        ut_lead_display = display_value(
            round_row.get("UTLeadName") or round_row.get("UTLead_UserID")
        )
        start_date_display = display_date(
            round_row.get("StartDate") or round_row.get("ShipDate")
        )
        end_date_display = display_date(
            round_row.get("CompletedAt") or round_row.get("EndDate")
        )
        countries_display = expand_region(round_row.get("Region"))
        round_label = f"Round {round_row.get('RoundNumber') or 1}"

        artifacts = get_round_surveys(round_id_int) or []
        artifact_rows = []
        report_count = 0

        for artifact in artifacts:
            survey_type = artifact.get("SurveyTypeName") or "Report"
            survey_type_display = e(str(survey_type).replace("_", " "))
            internal_link = artifact.get("SurveyLink")
            participant_link = artifact.get("DistributionLink")
            created_at = display_date(artifact.get("CreatedAt"))

            if survey_type not in ("Recruiting", "Report_Issue"):
                report_count += 1

            link_parts = []
            if internal_link:
                link_parts.append(
                    f'<a href="{e(internal_link)}" target="_blank" rel="noopener noreferrer">Internal</a>'
                )
            if participant_link:
                link_parts.append(
                    f'<a href="{e(participant_link)}" target="_blank" rel="noopener noreferrer">Participant</a>'
                )

            links_html = " · ".join(link_parts) if link_parts else "—"

            artifact_rows.append(f"""
                <div class="product-artifact-row">
                    <div>
                        <div class="product-artifact-title">{survey_type_display}</div>
                        <div class="product-artifact-meta">Added {created_at}</div>
                    </div>
                    <div class="product-artifact-links">
                        {links_html}
                    </div>
                </div>
            """)

        if not artifact_rows:
            artifact_rows.append("""
                <div class="empty-state product-current-empty">
                    <p class="empty-state-description">
                        No reports or artifacts are attached to this trial yet.
                    </p>
                </div>
            """)

        report_count_display = pluralize_report_count(report_count)

        main_content_html = f"""
        <div class="page-header">
            <div class="product-title-row">
                <h2 class="page-title">Past Trial - {project_name_display}</h2>

                <a class="product-back-link" href="/product/past-trials">
                    ← Back to Past Trials
                </a>
            </div>

            <p class="page-description">
                Review the completed trial packet, delivered reports, and archived trial artifacts.
            </p>
        </div>

        <div class="product-review-grid product-past-grid">
            <section class="product-review-card">
                <h3 class="section-title">Trial Summary</h3>
                {render_review_list([
                    ("Project", project_name_display),
                    ("Round", display_value(round_label)),
                    ("Product Type", product_type_display),
                    ("UT Lead", ut_lead_display),
                ])}
            </section>

            <section class="product-review-card">
                <h3 class="section-title">Timeline</h3>
                {render_review_list([
                    ("Start Date", start_date_display),
                    ("End Date", end_date_display),
                    ("Countries", countries_display),
                    ("Reports", display_value(report_count_display)),
                ])}
            </section>

            <section class="product-review-card product-current-wide-card">
                <h3 class="section-title">Delivered Reports & Artifacts</h3>
                <div class="product-artifact-list">
                    {''.join(artifact_rows)}
                </div>
            </section>

            <section class="product-review-card product-current-wide-card">
                <h3 class="section-title">Reports & Insights</h3>
                <p class="product-review-note">
                    Cross-trial comparisons and deeper product-type insights will be added in a later version.
                </p>
            </section>
        </div>
        """

        summary_html = render_summary_block(
            "Past Trial",
            [
                ("Project", project_name_display),
                ("Round", display_value(round_label)),
                ("UT Lead", ut_lead_display),
                ("End Date", end_date_display),
                ("Reports", display_value(report_count_display)),
            ],
        )

    # --------------------------------------------------
    # List view
    # --------------------------------------------------
    else:
        past_rounds = get_past_project_rounds_for_user(user_id=user_id)
        rows_html = ""

        for row in past_rounds:
            project_name = display_value(row.get("ProjectName"))
            round_id_value = e(row.get("RoundID"))
            ut_lead = display_value(row.get("UTLeadName") or row.get("UTLead_UserID"))
            start_date = display_date(row.get("StartDate") or row.get("ShipDate"))
            end_date = display_date(row.get("CompletedAt") or row.get("EndDate"))
            reports = display_value(pluralize_report_count(row.get("ReportCount")))

            rows_html += f"""
            <tr>
                <td>
                    <a href="/product/past-trials?round_id={round_id_value}">
                        {project_name}
                    </a>
                </td>
                <td>{ut_lead}</td>
                <td>{start_date}</td>
                <td>{end_date}</td>
                <td>{reports}</td>
            </tr>
            """

        if not rows_html:
            rows_html = """
            <tr>
                <td colspan="5">
                    <div class="empty-state product-current-empty">
                        <p class="empty-state-description">
                            No past trials are available yet.
                        </p>
                    </div>
                </td>
            </tr>
            """

        main_content_html = f"""
        <div class="page-header">
            <h2 class="page-title">Past Trials</h2>
            <p class="page-description">
                View closed Product Trials and open the completed trial packet for delivered reports and artifacts.
            </p>
        </div>

        <section class="product-current-table-card product-past-table-card">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Project</th>
                        <th>UT Lead</th>
                        <th>Start Date</th>
                        <th>End Date</th>
                        <th>Reports</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </section>
        """

        summary_html = """
        <div class="summary-block">
            <h4 class="summary-title">Past Trials</h4>
            <p class="muted small">
                Past Trials is the archive for closed Product Trials and delivered trial artifacts.
            </p>
        </div>
        """

    # --------------------------------------------------
    # Assemble layout
    # --------------------------------------------------
    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", "")
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", summary_html)

    html = product_base.replace("__BODY__", body)
    html = inject_nav(html)

    return {"html": html}

def render_product_reports_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict | None = None,
):
    """
    GET /product/reports

    Placeholder until reports view is implemented.
    """

    from app.db.user_roles import get_effective_permission_level
    from pathlib import Path

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    if get_effective_permission_level(user_id) < 50:
        return {"redirect": "/dashboard"}

    # --------------------------------------------------
    # Templates
    # --------------------------------------------------
    product_base = Path(
        "app/templates/product_team/base_product_team.html"
    ).read_text(encoding="utf-8")

    product_layout = Path(
        "app/templates/product_team/product_layout.html"
    ).read_text(encoding="utf-8")

    left_rail_html = _render_product_left_rail_for_user(user_id=user_id)

    # --------------------------------------------------
    # TEMP content
    # --------------------------------------------------
    main_content_html = """
    <h2>Reports</h2>

    <div class="muted">
        Reports view is not implemented yet.
    </div>
    """

    # --------------------------------------------------
    # Assemble layout
    # --------------------------------------------------
    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", "")
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", "")

    html = product_base.replace("__BODY__", body)
    html = inject_nav(html)

    return {"html": html}