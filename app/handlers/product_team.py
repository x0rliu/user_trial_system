# app/handlers/product_team.py

from pathlib import Path
from app.db.user_roles import get_effective_permission_level
from app.cache.simple_cache import cache
from app.cache.product_cache import TRIAL_PROJECT_PREFIX
from app.cache.product_cache import get_trial_project
from app.db.user_pool_country_codes import get_country_codes
from app.handlers import users

PRODUCT_WIZARD_STEPS = [
    ("basics", "Project Basics"),
    ("timing", "Timing & Scope"),
    ("stakeholders", "Stakeholders"),
    ("review", "Review & Submit"),
]


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
        name = p.get("basics", {}).get("project_name", "Untitled Trial")

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
                {p["ProjectName"]}
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
            # Not a Product Team–owned request state
            continue

        action_required_items.append(
            f"""
            <a class="rail-item rail-status-{status}"
            href="{href}">
                {p["ProjectName"]}
            </a>
            """
        )

    left_rail_html = f"""
    <h2>User Trials</h2>

    <div class="rail-section">
        <form method="post" action="/product/request-trial/create">
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
    <h2>Request a User Trial</h2>

    <p class="muted">
        This wizard starts the User Trial planning process with the UT team.
        You’ll define the basics needed to kick off discussion and scheduling.
    </p>

    <p class="muted small">
        This request does <strong>not</strong> finalize scope, recruiting, or surveys.
        Those are defined collaboratively after submission.
    </p>

    <p class="muted small">
        Begin by outlining the project basics.
    </p>
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

    html = product_base.replace("{{ body }}", body)
    html = inject_nav(html)

    return {"html": html}


def _render_product_wizard_status(
    *,
    current_step: str,
    wizard_state: dict,
    project_id: str,
):
    step_keys = [k for k, _ in PRODUCT_WIZARD_STEPS]

    def step_index(step):
        return step_keys.index(step)

    completed_steps = [
        step for step, completed in wizard_state.items() if completed
    ]

    max_completed_step = completed_steps[-1] if completed_steps else None

    max_index = (
        step_index(max_completed_step)
        if max_completed_step in step_keys
        else -1
    )

    items = []

    for idx, (key, label) in enumerate(PRODUCT_WIZARD_STEPS):
        href = f"/product/request-trial/wizard/{key}?project_id={project_id}"

        if key == current_step:
            item = f'<strong><a href="{href}">{label}</a></strong>'
        elif idx <= max_index:
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

    from app.cache.product_cache import get_trial_project, save_trial_project
    from datetime import datetime

    project_id_list = data.get("project_id")
    if not project_id_list:
        return {"error": "missing_project_id"}

    project_id = project_id_list[0]

    project = get_trial_project(project_id)
    if not project:
        return {"error": "project_not_found"}

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
    from app.cache.product_cache import get_trial_project, save_trial_project
    from datetime import datetime

    project_id = data.get("project_id", [None])[0]
    if not project_id:
        return {"error": "missing_project_id"}

    project = get_trial_project(project_id)
    if not project:
        return {"error": "project_not_found"}

    countries = data.get("countries[]", [])

    project["timing_scope"] = {
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



def render_section(items, empty_text):
    if items:
        return "\n".join(items)
    return f"""
    <span class="rail-empty rail-item">
        {empty_text}
    </span>
    """

def handle_product_request_trial_wizard_stakeholders_post(
    *,
    user_id: str,
    data: dict,
):
    """
    Saves Stakeholders into the trial project draft.
    Requires at least one stakeholder role.
    """

    from app.cache.product_cache import get_trial_project, save_trial_project
    from datetime import datetime

    project_id_list = data.get("project_id")
    if not project_id_list:
        return {"error": "missing_project_id"}

    project_id = project_id_list[0]

    project = get_trial_project(project_id)
    if not project:
        return {"error": "project_not_found"}

    # --------------------------------------------------
    # Normalize stakeholders (dynamic multi-row version)
    # --------------------------------------------------
    stakeholders = []

    names = data.get("stakeholder_name[]", [])
    roles = data.get("stakeholder_role[]", [])
    notes = data.get("notes", [""])[0].strip()

    for name, role in zip(names, roles):

        name = (name or "").strip()
        role = (role or "").strip()

        if name and role:
            stakeholders.append({
                "name": name,
                "role": role,
            })
    # --------------------------------------------------
    # Validation: require at least one role
    # --------------------------------------------------
    if not stakeholders:
        return {
            "redirect": (
                f"/product/request-trial/wizard/stakeholders"
                f"?project_id={project_id}&error=missing_roles"
            )
        }


    # --------------------------------------------------
    # Persist
    # --------------------------------------------------
    project["stakeholders"] = {
        "roles": stakeholders,
        "notes": notes,
    }

    project["updated_at"] = datetime.utcnow().isoformat()

    save_trial_project(project_id, project)

    return {
        "redirect": f"/product/request-trial/wizard/review?project_id={project_id}"
    }


def handle_product_request_trial_submit_post(
    *,
    user_id: str,
    data: dict,
):
    """
    Final submission of a Product Team trial request.
    Delegates ALL DB writes to project_rounds.
    """

    from datetime import datetime
    from app.cache.product_cache import get_trial_project, delete_trial_project
    from app.db.project_rounds import create_project_from_request

    project_id = data.get("project_id")
    if not project_id:
        return {"error": "missing_project_id"}

    project = get_trial_project(project_id)
    if not project:
        return {"error": "project_not_found"}

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
    # Cache eviction: draft lifecycle ends here
    # --------------------------------------------------
    delete_trial_project(project_id)

    # --------------------------------------------------
    # Notification: Product trial pending UT approval
    # --------------------------------------------------
    from app.db.notifications import (
        create_notification,
        add_notification_recipient,
    )

    basics = project.get("basics", {})
    timing = project.get("timing_scope", {})

    notification_id = create_notification(
        type_key="product_trial_pending_approval",
        payload={
            # Identity
            "project_id": project_id,
            "project_name": basics.get("project_name"),
            "requested_by": user_id,

            # Classification
            "trial_type": "ut_trial",
            "product_category": basics.get("product_category"),
            "business_group": basics.get("business_group"),

            # Timing (nullable but explicit)
            "estimated_start_date": timing.get("shipping_date"),
            "estimated_end_date": basics.get("gate_x_date"),

            # Capacity (future, safe to be None)
            "user_amount": project.get("user_amount"),
        },
        created_by=user_id,
    )



    # Phase 0: explicit UT reviewers (no role magic yet)
    REVIEWER_USER_IDS = [
        "userid_4fec82c7eea61",   # TODO: replace in the future with smarter code
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
        name = p.get("basics", {}).get("project_name", "Untitled Trial")

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
                {p["ProjectName"]}
            </a>
            """
        )

    # Active Trials (DB)
    # for p in active_projects:
    #    action_required_items.append(
    #        f"""
    #        <a class="rail-item"
    #           href="/product/trials/{p["RoundID"]}">
    #            {p["ProjectName"]}
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
                {p["ProjectName"]}
            </a>
            """
        )


    return f"""
    <h2>User Trials</h2>

    <div class="rail-section">
        <form method="post" action="/product/request-trial/create">
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
            <h4 class="summary-title">Project Summary</h4>
            <div class="muted small">
                Project summary will appear here as you complete each step.
            </div>
        </div>
        """

    # --------------------------------------------------
    # Render
    # --------------------------------------------------
    return f"""
    <div class="summary-block">
        <h4 class="summary-title">Project Summary</h4>
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

    product_base, product_layout = _load_product_team_templates()
    left_rail_html = _render_product_left_rail_for_user(user_id=user_id)

    wizard_state = derive_wizard_state(project)
    wizard_status_html = _render_product_wizard_status(
        current_step="basics",
        wizard_state=wizard_state,
        project_id=project_id,
    )

    basics = project.get("basics", {})

    main_content_html = f"""
    <h2>Project Basics</h2>

    <form method="post" action="/product/request-trial/wizard/basics">
        <input type="hidden" name="project_id" value="{project_id}" />

        <div class="form-group">
            <label>Project Name</label>
            <input
                type="text"
                name="project_name"
                value="{basics.get('project_name', '')}"
                required
            />
        </div>

        <div class="form-group">
            <label>Market Name</label>
            <input
                type="text"
                name="market_name"
                value="{basics.get('market_name', '')}"
            />
        </div>

        <div class="form-group">
            <label>Business Group</label>
            <input
                type="text"
                name="business_group"
                value="{basics.get('business_group', '')}"
                required
            />
        </div>

        <div class="form-group">
            <label>Product Category / Type</label>
            <input
                type="text"
                name="product_category"
                value="{basics.get('product_category', '')}"
                required
            />
        </div>

        <div class="form-group">
            <label>User Scope</label>
            <select name="user_scope">
                <option value="Internal" {"selected" if basics.get("user_scope") == "Internal" else ""}>Internal (Employees Only)</option>
                <option value="External" {"selected" if basics.get("user_scope") == "External" else ""}>External (Participants Only)</option>
                <option value="Hybrid" {"selected" if basics.get("user_scope","Hybrid") == "Hybrid" else ""}>Hybrid (Employees + Participants)</option>
            </select>
        </div>

        <div class="form-group">
            <label>Purpose / Additional Context</label>
            <textarea name="purpose" rows="4">{basics.get('purpose', '')}</textarea>
        </div>

        <div class="form-actions">
            <button type="submit" class="primary">
                Save & Continue
            </button>
        </div>
    </form>
    """

    summary_html = _render_project_summary_right_rail(
        project=project, wizard_state=wizard_state
    )

    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", wizard_status_html)
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", summary_html)

    html = product_base.replace("{{ body }}", body)
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

    product_base, product_layout = _load_product_team_templates()
    left_rail_html = _render_product_left_rail_for_user(user_id=user_id)

    wizard_state = derive_wizard_state(project)
    wizard_status_html = _render_product_wizard_status(
        current_step="timing",
        wizard_state=wizard_state,
        project_id=project_id,
    )

    timing = project.get("timing_scope", {})

    # --------------------------------------------------
    # Load country list from DB
    # --------------------------------------------------
    countries = get_country_codes()

    country_options = ""
    for c in countries:
        code = c["CountryCode"]
        name = c["CountryName"]
        country_options += f'<option value="{code}">{name}</option>'

    main_content_html = f"""
    <h2>Timing & Scope</h2>

    <form method="post" action="/product/request-trial/wizard/timing">
        <input type="hidden" name="project_id" value="{project_id}" />

        <div class="form-group">
            <label>Target Shipping Date</label>
            <input
                type="date"
                name="shipping_date"
                value="{timing.get('shipping_date', '')}"
                required
            />
            <p class="muted small">
                Date when units are expected to ship (tracking numbers available).
            </p>
        </div>

        <div class="form-group">
            <label>Gate X / Decision Date</label>
            <input
                type="date"
                name="gate_x_date"
                value="{timing.get('gate_x_date', '')}"
            />
            <p class="muted small">
                Date by which results are needed for a go / no-go decision.
            </p>
        </div>

        <div class="form-group">
            <label>Target Countries</label>

            <div id="country-container">

                <div class="country-row">
                    <select name="countries[]" required onchange="lockCountrySelection(this)">
                        <option value="">Select Country</option>
                        <option value="GLOBAL">All Countries / Global</option>
                        {country_options}
                    </select>
                </div>

            </div>

            <div style="margin-top:8px;">
                <button type="button" onclick="addCountryRow()">
                    + Add Country
                </button>
            </div>

            <!-- Hidden template used for new country rows -->
            <div id="country-template" style="display:none;">
                <select name="countries[]">
                    <option value="">Select Country</option>
                    <option value="GLOBAL">All Countries / Global</option>
                    {country_options}
                </select>
            </div>

        </div>

        <div class="form-group">
            <label>Timing & Scope Notes</label>
            <textarea name="notes" rows="3">{timing.get('notes', '')}</textarea>
        </div>

        <div class="form-actions">
            <button type="submit" class="primary">
                Save & Continue
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
            '<button type="button" onclick="removeCountry(this)">Remove</button>';

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
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", wizard_status_html)
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", summary_html)

    html = product_base.replace("{{ body }}", body)
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

    # --------------------------------------------------
    # Normalize stakeholders for rendering
    # --------------------------------------------------
    if not roles:
        roles = [{"name": "", "role": ""}]
    else:
        roles = roles + [{"name": "", "role": ""}]

    role_options = ["", "GPM", "PQA", "PM", "Other"]

    stakeholder_rows_html = ""

    for r in roles:
        name_val = r.get("name", "")
        role_val = r.get("role", "")

        options_html = ""
        for opt in role_options:
            label = "Select Role" if opt == "" else opt
            selected = "selected" if opt == role_val else ""
            options_html += f'<option value="{opt}" {selected}>{label}</option>'

        stakeholder_rows_html += f"""
            <div class="stakeholder-row">
                <input
                    type="text"
                    name="stakeholder_name[]"
                    placeholder="First and Last Name"
                    value="{name_val}"
                    />

                <select name="stakeholder_role[]">
                    {options_html}
                </select>
            </div>
        """

    main_content_html = f"""
    <h2>Stakeholders</h2>

    <form method="post" action="/product/request-trial/wizard/stakeholders" novalidate>
        <input type="hidden" name="project_id" value="{project_id}" />

        <div id="stakeholder-container">
            {stakeholder_rows_html}
        </div>

        <div style="margin-top: 8px;">
            <button type="button" onclick="addStakeholderRow()">
                + Add Stakeholder
            </button>
        </div>

        <div class="form-group">
            <label>Additional Notes</label>
            <textarea name="notes" rows="3">{notes_val}</textarea>
        </div>

        <div class="form-actions">
            <button type="submit" class="primary">
                Save & Continue
            </button>
        </div>
    </form>

    """

    summary_html = _render_project_summary_right_rail(
        project=project, wizard_state=wizard_state
    )

    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", wizard_status_html)
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", summary_html)

    html = product_base.replace("{{ body }}", body)
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

    stakeholder_rows_html = ""
    roles = stakeholders.get("roles", []) if isinstance(stakeholders, dict) else []

    for role in roles:
        stakeholder_rows_html += f"""
        <tr>
            <td>{role.get("name", "—")}</td>
            <td>—</td>
            <td>{role.get("role", "—")}</td>
        </tr>
        """

    if not stakeholder_rows_html:
        stakeholder_rows_html = """
        <tr>
            <td colspan="3">—</td>
        </tr>
        """

    main_content_html = f"""
    <h2>Review & Submit</h2>

    <p class="muted">
        This is how your request will be reviewed by the User Trials team.
        Please confirm all details below are accurate.
    </p>

    <section class="review-section">
        <h3>Project Overview</h3>
        <dl class="review-grid">
            <dt>Project Name</dt>
            <dd>{basics.get("project_name", "—")}</dd>

            <dt>Market Name</dt>
            <dd>{basics.get("market_name", "—")}</dd>

            <dt>Business Group</dt>
            <dd>{basics.get("business_group", "—")}</dd>

            <dt>Product Category</dt>
            <dd>{basics.get("product_category", "—")}</dd>
        </dl>
    </section>

    <section class="review-section">
        <h3>Timing & Scope</h3>
        <dl class="review-grid">
            <dt>Target Shipping Date</dt>
            <dd>{timing.get("shipping_date", "—")}</dd>

            <dt>Gate X</dt>
            <dd>{timing.get("gate_x_date", "—")}</dd>

            <dt>Regions</dt>
            <dd>{timing.get("regions", "—")}</dd>
        </dl>

        <p class="muted small">
            Final timelines are confirmed by the UT Lead based on capacity,
            holidays, and trial complexity.
        </p>
    </section>

    <section class="review-section">
        <h3>Stakeholders</h3>

        <table class="review-table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                </tr>
            </thead>
            <tbody>
                {stakeholder_rows_html}
            </tbody>
        </table>
    </section>

    <section class="review-section">
        <h3>Additional Context</h3>
        <div class="review-notes">
            {basics.get("purpose", "—")}
        </div>
    </section>

    <form method="post" action="/product/request-trial/submit">
        <input type="hidden" name="project_id" value="{project_id}" />

        <div class="form-actions">
            <button class="primary">
                Submit for UT Review
            </button>

            <p class="muted small">
                After submission, this request will be locked for UT review.
            </p>
        </div>
    </form>
    """

    # Review page: no right rail summary (your current behavior)
    summary_html = ""

    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", wizard_status_html)
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", summary_html)

    html = product_base.replace("{{ body }}", body)
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

    Canonical, DB-backed view of a submitted User Trial request
    awaiting UT approval.
    """

    from pathlib import Path
    from app.db.user_roles import get_effective_permission_level
    from app.db.project_rounds import get_project_with_latest_round

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    permission_level = get_effective_permission_level(user_id)
    if permission_level < 50:
        return {"redirect": "/dashboard"}

    if not project_id:
        return {"redirect": "/product/request-trial"}
    
    # --------------------------------------------------
    # Load project + latest round from DB (authoritative)
    # --------------------------------------------------
    result = get_project_with_latest_round(project_id=project_id)
    if not result:
        return {"redirect": "/product/request-trial"}

    project_row, round_row = result

    from app.db.project_rounds import get_round_stakeholders

    stakeholders = get_round_stakeholders(
        round_id=round_row["RoundID"]
    ) or []

    # --------------------------------------------------
    # Templates
    # --------------------------------------------------
    product_base = Path(
        "app/templates/product_team/base_product_team.html"
    ).read_text(encoding="utf-8")

    product_layout = Path(
        "app/templates/product_team/product_layout.html"
    ).read_text(encoding="utf-8")

    # --------------------------------------------------
    # LEFT RAIL — Pending Approval
    # --------------------------------------------------
    left_rail_html = _render_product_left_rail_for_user(user_id=user_id)


    # --------------------------------------------------
    # MAIN CONTENT — read-only snapshot
    # Render stakeholders
    # --------------------------------------------------

    stakeholder_rows = ""

    for s in stakeholders:
        stakeholder_rows += f"""
        <tr>
            <td>{s.get("DisplayName","—")}</td>
            <td>{s.get("StakeholderRole","—")}</td>
        </tr>
        """

    if not stakeholder_rows:
        stakeholder_rows = """
        <tr>
            <td colspan="2" class="muted">No stakeholders submitted</td>
        </tr>
        """

    # --------------------------------------------------
    # MAIN CONTENT
    # --------------------------------------------------

    main_content_html = f"""
    <h2>Pending UT Approval</h2>

    <p class="muted">
        Your User Trial request has been submitted successfully
        and is currently under review by the User Trials team.
    </p>

    <section class="review-section">
        <h3>Project Overview</h3>
        <dl class="review-grid">
            <dt>Project Name</dt>
            <dd>{project_row.get("ProjectName", "—")}</dd>

            <dt>Market Name</dt>
            <dd>{project_row.get("MarketName", "—")}</dd>

            <dt>Business Group</dt>
            <dd>{project_row.get("BusinessGroup", "—")}</dd>

            <dt>Product Category</dt>
            <dd>{project_row.get("ProductType", "—")}</dd>
        </dl>
    </section>

    <section class="review-section">
        <h3>Timing & Scope</h3>
        <dl class="review-grid">
            <dt>Target Shipping Date</dt>
            <dd>{round_row.get("StartDate", "—")}</dd>

            <dt>Gate X</dt>
            <dd>{project_row.get("GateX_Date", "—")}</dd>

            <dt>Regions</dt>
            <dd>{round_row.get("Region", "—")}</dd>
        </dl>
    </section>

    <section class="review-section">
        <h3>Stakeholders</h3>

        <table class="review-table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Role</th>
                </tr>
            </thead>

            <tbody>
                {stakeholder_rows}
            </tbody>
        </table>
    </section>

    <div class="muted small" style="margin-top: 24px;">
        This request is locked while pending UT approval.
    </div>
    """


    # --------------------------------------------------
    # Assemble layout (standard contract)
    # --------------------------------------------------
    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", "")
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", "")

    html = product_base.replace("{{ body }}", body)
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

    main_content_html = f"""
    <h2>Information Requested</h2>

    <p class="muted">
        The User Trials team needs additional information before proceeding.
    </p>

    <section class="review-section">
        <h3>Request from User Trials</h3>
        <div class="callout warning">
            {request_action.get("ReasonText", "—")}
        </div>
    </section>

    <form method="post" action="/product/request-trial/info-requested/respond">
        <input type="hidden" name="project_id" value="{project_id}" />

        <div class="form-group">
            <label>Your Response</label>
            <textarea name="response_text" rows="5" required></textarea>
            <p class="muted small">
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

    html = product_base.replace("{{ body }}", body)
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
    round_id = round_["RoundID"]  # ✅ DEFINE IT EXPLICITLY


    change_action = get_latest_change_request_action(round_id=round_["RoundID"])
    if round_["Status"] != "change_requested":
        return {"redirect": "/product/request-trial"}


    product_base = Path(
        "app/templates/product_team/base_product_team.html"
    ).read_text(encoding="utf-8")

    product_layout = Path(
        "app/templates/product_team/product_layout.html"
    ).read_text(encoding="utf-8")

    left_rail_html = _render_product_left_rail_for_user(user_id=user_id)

    main_content_html = f"""
    <h2>Change Requested</h2>

    <p class="muted">
        The User Trials team has proposed a change to proceed with this request.
    </p>

    <section class="review-section">
        <h3>Proposed Change</h3>
        <div class="callout warning">
            {change_action.get("ReasonText", "—")}
        </div>
    </section>

    <form method="post" action="/product/request-trial/change-requested/respond">
        <input type="hidden" name="round_id" value="{round_id}" />
        <input type="hidden" name="decision" value="" />

        <div class="form-group">
            <label>If you want to counter, explain your constraints</label>
            <textarea
                name="detail_text"
                rows="4"
                placeholder="Explain what you can and cannot change…"
            ></textarea>
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

    html = product_base.replace("{{ body }}", body)
    html = inject_nav(html)

    return {"html": html}

def handle_product_request_trial_info_requested_respond_post(
    *,
    user_id: str,
    data: dict,
):
    from app.db.project_rounds import (
        get_project_with_latest_round,
        mark_project_round_pending_ut_review,
    )
    from app.db.approval_actions import insert_approval_action
    from app.services.notifications import notify_user

    project_id = data.get("project_id")
    info_text = (data.get("response_text") or "").strip()

    if not project_id or not info_text:
        return {"error": "missing_required_fields"}

    result = get_project_with_latest_round(project_id=project_id)
    if not result:
        return {"redirect": "/product/request-trial"}

    project, round_ = result

    # --------------------------------------------------
    # 1️⃣ Append approval action (history, not state)
    # --------------------------------------------------
    insert_approval_action(
        approval_type="product_trial",
        approval_id=round_["RoundID"],
        action_type="info_provided",     # ✅ ENUM
        reason_category="clarification",   # ✅ REQUIRED
        reason_text=info_text,
        assigned_ut_lead_id=None,
        action_by_user_id=user_id,
    )

    # --------------------------------------------------
    # 2️⃣ Authoritative lifecycle transition
    # --------------------------------------------------
    mark_project_round_pending_ut_review(
        project_id=project_id
    )

    # --------------------------------------------------
    # 3️⃣ Notify UT (event, not logic)
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

    round_id = data.get("round_id")
    decision = data.get("decision")

    if not round_id or not decision:
        return {"error": "Missing required fields", "status": 400}

    detail_text = (data.get("detail_text") or "").strip()

    from app.db.project_rounds import (
        get_project_with_latest_round,
        set_project_round_status,
    )
    from app.db.approval_actions import insert_approval_action
    from app.services.notifications import notify_user

    # --------------------------------------------------
    # Load authoritative project + round (for UT lead)
    # --------------------------------------------------
    result = get_project_with_latest_round(round_id=int(round_id))
    if not result:
        return {"redirect": "/product/request-trial"}

    project, round_ = result
    ut_lead_id = round_.get("UTLead_UserID")

    if not ut_lead_id:
        from app.db.user_roles import get_users_with_permission_levels

        admins = get_users_with_permission_levels([100])
        ut_lead_id = admins[0]["user_id"] if admins else None

    # --------------------------------------------------
    # Decision handling
    # --------------------------------------------------

    if decision == "accept":
        insert_approval_action(
            approval_type="product_trial",
            approval_id=int(round_id),
            action_type="change_accepted",
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
            action_type="withdrawn_by_requestor",
            reason_text=detail_text or None,
            assigned_ut_lead_id=None,
            action_by_user_id=user_id,
        )

        set_project_round_status(
            round_id=int(round_id),
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

    # --------------------------------------------------
    # Return round to UT review (accept / counter only)
    # --------------------------------------------------
    set_project_round_status(
        round_id=int(round_id),
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
        get_project_round_by_id,
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

    # --------------------------------------------------
    # Detail view (single round)
    # --------------------------------------------------
    if round_id:
        round_row = get_project_round_by_id(round_id=round_id)
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
        main_content_html = f"""
        <h2>Current Trial</h2>

        <section class="review-section">
            <h3>{round_row.get("ProjectName", "—")}</h3>
            {render_grid(core_rows)}
        </section>

        <div class="muted small" style="margin-top:10px;">
            Project details are managed by the assigned UT Lead.
        </div>

        <section class="review-section" style="margin-top:24px;">
            <h3>Trial Execution</h3>

            <div style="margin-top:16px;">
                <h4>User Profile</h4>

                {render_grid([
                    ("Age Range", age_display),
                    ("Region", region_display),
                    ("Target Users", round_row.get("TargetUsers") or "—")
                ])}

                <div style="margin-top:12px;">
                    <div class="muted small" style="margin-bottom:6px;">
                        Profile Criteria
                    </div>

                    <div class="kv-grid">
                        {criteria_html}
                    </div>
                </div>
            </div>

            <div style="margin-top:20px;">
                <h4>Recruiting</h4>
                {render_grid([
                    ("Status", '<span class="muted">Not configured</span>'),
                    ("Notes", '<span class="muted small">Opens once profile is defined</span>')
                ])}
            </div>

            <div style="margin-top:20px;">
                <h4>Participants</h4>
                <div class="empty-state">
                    No users selected yet.
                </div>
            </div>

            <div style="margin-top:20px;">
                <h4>Surveys</h4>
                {survey_table_html}
            </div>

            <div style="margin-top:20px;">
                <h4>Report an Issue</h4>
                <div class="muted small">
                    Available once the trial begins.
                </div>
            </div>

        </section>
        """

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

        print("DEBUG USER SAMPLE:", users[:1])

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
            status_raw = (r.get("Status") or "").lower()

            if status_raw == "closed":
                status_display = "Completed"
            elif status_raw == "running":
                status_display = "In Progress"
            elif status_raw == "recruiting":
                status_display = "Recruiting"
            elif status_raw == "approved":
                status_display = "Preparing"
            else:
                status_display = "—"

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
                        {r.get("ProjectName")}
                    </a>
                </td>
                <td>{status_display}</td>
                <td>{ut_lead_display}</td>
                <td>{r.get("StartDate") or "—"}</td>
                <td>{region_display}</td>
            </tr>
            """

        if not rows_html:
            rows_html = """
            <tr>
                <td colspan="5">No current trials</td>
            </tr>
            """

        main_content_html = f"""
        <h2>My Current Trials</h2>

        <table class="data-table">
            <thead>
                <tr>
                    <th>Project</th>
                    <th>Status</th>
                    <th>User Trial Lead</th>
                    <th>Start Date</th>
                    <th>Region</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        """

    # --------------------------------------------------
    # Assemble layout
    # --------------------------------------------------
    body = product_layout
    body = body.replace("{{ PRODUCT_LEFT_RAIL }}", left_rail_html)
    body = body.replace("{{ PRODUCT_WIZARD_STATUS }}", "")
    body = body.replace("{{ PRODUCT_CONTENT }}", main_content_html)
    body = body.replace("{{ PRODUCT_SUMMARY }}", "")

    html = product_base.replace("{{ body }}", body)
    html = inject_nav(html)

    return {"html": html}
