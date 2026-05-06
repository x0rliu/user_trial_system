# app/handlers/admin.py

from pathlib import Path

from app.db.user_roles import get_effective_permission_level

# approval aggregation
from app.services.approvals import get_pending_approvals

# approval block renderers
from app.handlers.admin_approval_blocks import APPROVAL_BLOCK_RENDERERS

# detail view dependencies
from app.db.bonus_survey_tracker import (
    get_tracker_by_id,
    get_tracker_entries,
)
from app.db.surveys import get_bonus_survey_by_id
from app.db.user_pool import get_display_name_by_user_id
from app.utils.html_escape import escape_html as e
from app.services.gender_values import canonicalize_gender_value

# --------------------------------------------------
# Permission Gate
# --------------------------------------------------

def _require_ut_lead(user_id: str):
    permission_level = get_effective_permission_level(user_id)
    if permission_level < 70:
        return {"redirect": "/dashboard"}
    return None


# --------------------------------------------------
# Admin Approvals Landing
# --------------------------------------------------

def render_admin_approvals_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
):
    """
    Admin approvals landing page.
    Chronological list of approval blocks.
    """

    denied = _require_ut_lead(user_id)
    if denied:
        return denied

    from app.services.approvals import get_pending_approvals
    from app.handlers.admin_approval_blocks import (
        render_product_trial_approval_block,
        render_bonus_survey_approval_block,
    )

    approvals = get_pending_approvals()

    grouped = {
        "product_trial": [],
        "bonus_survey": [],
    }

    for a in approvals:
        grouped[a["approval_type"]].append(a)

    blocks = []

    # Newest tables first
    if grouped["product_trial"]:
        blocks.append(render_product_trial_approval_block(grouped["product_trial"]))

    if grouped["bonus_survey"]:
        blocks.append(render_bonus_survey_approval_block(grouped["bonus_survey"]))

    body_html = "\n".join(blocks) or "<p>No items pending approval.</p>"

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Admin Approvals")
    html = html.replace("__BODY__", body_html)

    return {"html": html}


# --------------------------------------------------
# Bonus Survey Approval Presentation Helpers
# --------------------------------------------------

def _format_admin_date(value) -> str:
    """
    Format date/datetime values for approval review.
    Render-only.
    """

    if not value:
        return "—"

    raw = str(value)

    if " " in raw:
        return raw.split(" ", 1)[0]

    if "T" in raw:
        return raw.split("T", 1)[0]

    return raw


def _build_bonus_targeting_review_from_rules(rules: list[dict]) -> dict:
    """
    Read-only projection of DB targeting rules into reviewer-friendly groups.
    DB remains the source of truth.
    """

    targeting = {}

    for rule in rules:
        criterion = rule.get("Criterion")
        operator = rule.get("Operator")
        value = rule.get("Value")

        if value is None:
            continue

        if criterion == "age":
            if operator == ">=":
                targeting["age_min"] = value
            elif operator == "<=":
                targeting["age_max"] = value

        elif criterion == "region":
            targeting.setdefault("regions", []).append(value)

        elif criterion == "country":
            targeting.setdefault("country_codes", []).append(value)

        elif criterion == "office":
            targeting.setdefault("office_ids", []).append(value)

        elif criterion == "job_function":
            targeting.setdefault("job_functions", []).append(value)

        elif criterion == "primary_os":
            targeting.setdefault("primary_os", []).append(value)

        elif criterion == "phone_os":
            targeting.setdefault("phone_os", []).append(value)

        elif criterion == "gender":
            canonical_gender = canonicalize_gender_value(value)
            if canonical_gender:
                targeting.setdefault("genders", []).append(canonical_gender)

        elif criterion == "user_type":
            targeting.setdefault("user_types", []).append(value)

        elif criterion == "distribution_mode":
            targeting["distribution_mode"] = value

    distribution_mode = targeting.get("distribution_mode") or "open"

    rows: list[dict] = []

    rows.append({
        "label": "Distribution",
        "values": [
            "Direct invite"
            if distribution_mode == "direct"
            else "Open invitation"
        ],
        "style": "primary",
    })

    age_min = targeting.get("age_min")
    age_max = targeting.get("age_max")

    if age_min or age_max:
        rows.append({
            "label": "Age Range",
            "values": [f"{age_min or '—'} – {age_max or '—'}"],
            "style": "default",
        })

    criteria_map = [
        ("regions", "Regions"),
        ("country_codes", "Countries"),
        ("office_ids", "Offices"),
        ("job_functions", "Job Functions"),
        ("primary_os", "Primary OS"),
        ("phone_os", "Phone OS"),
        ("user_types", "User Types"),
        ("genders", "Gender"),
    ]

    for key, label in criteria_map:
        values = targeting.get(key) or []

        if values:
            rows.append({
                "label": label,
                "values": values,
                "style": "default",
            })

    if len(rows) == 1 and distribution_mode != "direct":
        rows.append({
            "label": "Audience",
            "values": ["All eligible users"],
            "style": "default",
        })

    return {
        "distribution_mode": distribution_mode,
        "rows": rows,
    }


def _render_admin_review_field(
    *,
    label: str,
    value_html: str,
) -> str:
    """
    Render one approval review row.
    value_html must already be escaped or intentionally generated as safe HTML.
    """

    return f"""
    <div class="admin-review-row">
        <div class="admin-review-label">{e(label)}</div>
        <div class="admin-review-value">{value_html}</div>
    </div>
    """


def _render_targeting_criteria_rows(targeting_review: dict) -> str:
    """
    Render targeting criteria as readable rows/chips.
    """

    rows = targeting_review.get("rows") or []

    if not rows:
        return """
        <div class="admin-criteria-empty">
            No targeting criteria saved.
        </div>
        """

    rendered_rows = []

    for row in rows:
        label = e(row.get("label") or "Criteria")
        values = row.get("values") or []
        style = row.get("style") or "default"

        chips = "".join(
            f'<span class="admin-criteria-chip {e(style)}">{e(str(value))}</span>'
            for value in values
        )

        rendered_rows.append(
            f"""
            <div class="admin-criteria-row">
                <div class="admin-criteria-label">{label}</div>
                <div class="admin-criteria-values">{chips}</div>
            </div>
            """
        )

    return "\n".join(rendered_rows)


def _hydrate_bonus_submitted_review_html(
    *,
    survey: dict,
    targeting_review: dict,
) -> str:
    """
    Admin-specific review presentation for a submitted bonus survey.
    Render-only. No state mutation.
    """

    survey_title = e(survey.get("survey_title") or "—")
    start_date = e(_format_admin_date(survey.get("open_at")))
    end_date = e(_format_admin_date(survey.get("close_at")))
    purpose = e(survey.get("response_destination") or "—")
    survey_link = str(survey.get("survey_link") or "").strip()

    if survey_link:
        safe_survey_link = e(survey_link)
        survey_link_html = f"""
        <a href="{safe_survey_link}" target="_blank" rel="noopener noreferrer">
            Participant Form
        </a>
        """
    else:
        survey_link_html = "—"

    targeting_html = _render_targeting_criteria_rows(targeting_review)

    direct_invite_note = ""

    if targeting_review.get("distribution_mode") == "direct":
        direct_invite_note = """
        <div class="admin-review-note">
            Direct invite recipient details are not shown here yet because the submitted-survey approval view
            does not currently receive the direct-invite recipient source. We should wire that in as the next
            DB-backed pass.
        </div>
        """

    return f"""
    <section class="admin-review-hero">
        <div>
            <div class="admin-review-kicker">Bonus Survey Approval</div>
            <h1>Bonus Survey Submitted for UT Approval</h1>
            <p>
                This bonus survey has been submitted and is pending UT approval.
                You are viewing the exact information the reviewer will use for approval.
            </p>
        </div>
    </section>

    <div class="admin-review-overview-grid">

        <section class="content-card admin-review-card">
            <div class="content-card-header">
                <h2>Basics</h2>
            </div>

            <div class="content-card-body">
                {_render_admin_review_field(label="Survey Name", value_html=survey_title)}
                {_render_admin_review_field(label="Start Date", value_html=start_date)}
                {_render_admin_review_field(label="End Date", value_html=end_date)}
                {_render_admin_review_field(label="Purpose", value_html=purpose)}
            </div>
        </section>

        <section class="content-card admin-review-card">
            <div class="content-card-header">
                <h2>Survey Template</h2>
            </div>

            <div class="content-card-body">
                {_render_admin_review_field(label="Google Form Link", value_html=survey_link_html)}
                {_render_admin_review_field(label="Token Validation", value_html='<span class="admin-status-good">Enabled</span>')}
            </div>
        </section>

    </div>

    <section class="content-card admin-review-card">
        <div class="content-card-header">
            <h2>Targeting Criteria</h2>
        </div>

        <div class="content-card-body">
            <div class="admin-criteria-list">
                {targeting_html}
            </div>
            {direct_invite_note}
        </div>
    </section>

    <div class="admin-review-back">
        <a href="/admin/approvals">Back to Approvals</a>
    </div>
    """


def _render_bonus_admin_action_controls(
    *,
    tracker_id: int,
    current_state: str,
) -> str:
    """
    Render admin-only approval controls.
    POST forms mutate state elsewhere and must redirect.
    """

    safe_tracker_id = e(str(tracker_id))
    safe_current_state = e(current_state or "—")

    return f"""
    <section class="content-card approval-decision-panel">
        <div class="content-card-header">
            <h2>Approval Decision</h2>
            <span class="approval-state-pill">{safe_current_state}</span>
        </div>

        <div class="content-card-body">
            <div class="approval-decision-options" data-admin-approval-decisions>

                <label class="approval-decision-option">
                    <input
                        type="radio"
                        name="admin_approval_decision"
                        value="approve"
                        checked
                    >
                    <span>
                        <strong>Approve</strong>
                        <em>Move this bonus survey out of review and make it active.</em>
                    </span>
                </label>

                <label class="approval-decision-option">
                    <input
                        type="radio"
                        name="admin_approval_decision"
                        value="request-info"
                    >
                    <span>
                        <strong>Request more information</strong>
                        <em>Ask the requestor for clarification without rejecting the survey.</em>
                    </span>
                </label>

                <label class="approval-decision-option">
                    <input
                        type="radio"
                        name="admin_approval_decision"
                        value="request-changes"
                    >
                    <span>
                        <strong>Request changes</strong>
                        <em>Send the requestor specific changes required before approval.</em>
                    </span>
                </label>

                <label class="approval-decision-option disabled">
                    <input
                        type="radio"
                        name="admin_approval_decision"
                        value="deny"
                        disabled
                    >
                    <span>
                        <strong>Deny</strong>
                        <em>Deny is not wired yet. Needs its own POST route and DB state decision.</em>
                    </span>
                </label>

            </div>

            <div class="approval-decision-panels">

                <div class="approval-decision-panel-body" data-decision-panel="approve">
                    <form method="post" action="/surveys/bonus/approve">
                        <input type="hidden" name="tracker_id" value="{safe_tracker_id}">
                        <button type="submit" class="btn btn-primary">
                            Approve Bonus Survey
                        </button>
                    </form>
                </div>

                <div class="approval-decision-panel-body hidden" data-decision-panel="request-info">
                    <form method="post" action="/surveys/bonus/request-info">
                        <input type="hidden" name="tracker_id" value="{safe_tracker_id}">

                        <label for="request-info-detail">
                            Information needed
                        </label>

                        <textarea
                            id="request-info-detail"
                            name="detail_text"
                            required
                            disabled
                            placeholder="Explain what information is needed before this can be approved."
                        ></textarea>

                        <button type="submit" class="btn btn-secondary">
                            Send Information Request
                        </button>
                    </form>
                </div>

                <div class="approval-decision-panel-body hidden" data-decision-panel="request-changes">
                    <form method="post" action="/surveys/bonus/request-changes">
                        <input type="hidden" name="tracker_id" value="{safe_tracker_id}">

                        <label for="request-changes-detail">
                            Required changes
                        </label>

                        <textarea
                            id="request-changes-detail"
                            name="detail_text"
                            required
                            disabled
                            placeholder="Describe the specific changes required."
                        ></textarea>

                        <button type="submit" class="btn btn-secondary">
                            Send Change Request
                        </button>
                    </form>
                </div>

            </div>
        </div>
    </section>
    """

def _render_bonus_approval_history(entries: list[dict]) -> str:
    """
    Render approval tracker history.
    Render-only. No state mutation.
    """

    if not entries:
        return """
        <section class="content-card">
            <div class="content-card-header">
                <h2>Approval History</h2>
            </div>
            <div class="content-card-body">
                <p class="muted">No approval history has been recorded.</p>
            </div>
        </section>
        """

    rows = []

    for entry in entries:
        raw_actor_user_id = entry.get("actor_user_id") or ""

        if raw_actor_user_id:
            actor_display_name = get_display_name_by_user_id(raw_actor_user_id)
        else:
            actor_display_name = "—"

        if not actor_display_name:
            actor_display_name = raw_actor_user_id or "—"

        entry_type_raw = str(entry.get("entry_type") or "—").replace("_", " ")
        entry_type_label = entry_type_raw.title()

        safe_actor_display_name = e(actor_display_name)
        safe_entry_type = e(entry_type_label)
        safe_detail_text = e(entry.get("detail_text") or "")
        safe_created_at = e(str(entry.get("created_at") or "—"))

        detail_html = ""

        if safe_detail_text:
            detail_html = f"""
            <div class="tracker-detail">
                {safe_detail_text}
            </div>
            """

        rows.append(
            f"""
            <div class="tracker-entry">
                <div class="tracker-entry-main">
                    <div>
                        <strong>{safe_entry_type}</strong>
                        <div class="muted small">By {safe_actor_display_name}</div>
                        {detail_html}
                    </div>
                    <div class="tracker-time">
                        {safe_created_at}
                    </div>
                </div>
            </div>
            """
        )

    return f"""
    <section class="content-card">
        <div class="content-card-header">
            <h2>Approval History</h2>
        </div>
        <div class="content-card-body">
            <div class="tracker-log">
                {''.join(rows)}
            </div>
        </div>
    </section>
    """

# --------------------------------------------------
# Admin Approval Detail View
# --------------------------------------------------

def render_admin_approval_view_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict,
):
    """
    Admin approval detail view.
    GET renders only.
    POST actions remain separate and mutate state elsewhere.
    """

    denied = _require_ut_lead(user_id)
    if denied:
        return denied

    tracker_id = query_params.get("tracker_id", [None])[0]
    if not tracker_id:
        return {"redirect": "/admin/approvals"}

    if not str(tracker_id).isdigit():
        return {"redirect": "/admin/approvals"}

    tracker_id_int = int(tracker_id)

    tracker = get_tracker_by_id(tracker_id_int)
    if not tracker:
        return {"redirect": "/admin/approvals"}

    survey = get_bonus_survey_by_id(tracker["bonus_survey_id"])
    if not survey:
        return {"redirect": "/admin/approvals"}

    from app.db.surveys import get_bonus_survey_targeting_rules

    rules = get_bonus_survey_targeting_rules(
        survey["bonus_survey_id"]
    )

    targeting_review = _build_bonus_targeting_review_from_rules(
        rules
    )

    entries = get_tracker_entries(tracker_id_int)

    review_html = _hydrate_bonus_submitted_review_html(
        survey=survey,
        targeting_review=targeting_review,
    )

    history_html = _render_bonus_approval_history(entries)

    controls_html = _render_bonus_admin_action_controls(
        tracker_id=tracker_id_int,
        current_state=tracker.get("current_state") or "—",
    )

    body_html = f"""
    <div class="admin-approval-detail">
        {review_html}

        {history_html}

        {controls_html}
    </div>
    """

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Review Approval")
    html = html.replace("__BODY__", body_html)
    html = html.replace(
        "</head>",
        '<link rel="stylesheet" href="/static/admin.css">\n</head>',
    )

    return {"html": html}