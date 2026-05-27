# app/handlers/dashboard.py

from pathlib import Path

from app.utils.html_escape import escape_html as e
from app.utils.trial_display import get_project_display_name, get_round_display_label


DASHBOARD_TEMPLATE = Path("app/templates/dashboard.html")
DASHBOARD_CARDS_TEMPLATE = Path("app/templates/dashboard_cards.html")


PARTICIPANT_DASHBOARD_LEVELS = {20, 30, 40, 50, 60, 70, 80, 100}
LEGAL_DASHBOARD_LEVELS = {30, 100}
BSC_DASHBOARD_LEVELS = {40, 70, 100}
PRODUCT_TEAM_DASHBOARD_LEVELS = {50, 70, 100}
MANAGEMENT_DASHBOARD_LEVELS = {60, 70, 100}
UT_LEAD_DASHBOARD_LEVELS = {70, 100}
IT_DASHBOARD_LEVELS = {80, 100}
ADMIN_DASHBOARD_LEVELS = {100}


DASHBOARD_CARD_DEFINITIONS = [
    {
        "key": "current_trial",
        "title": "Current Trial",
        "description": "Shows your active trial and the next action you may need to take.",
        "builder": "current_trial",
        "default_order": 10,
        "dismissible": True,
        "allowed_permission_levels": PARTICIPANT_DASHBOARD_LEVELS,
    },
    {
        "key": "upcoming_trials",
        "title": "Upcoming Trials",
        "description": "Shows upcoming trials visible to you.",
        "builder": "upcoming_trials",
        "default_order": 20,
        "dismissible": True,
        "allowed_permission_levels": PARTICIPANT_DASHBOARD_LEVELS,
    },
    {
        "key": "recruiting_trials",
        "title": "Trials Currently Recruiting",
        "description": "Shows trial rounds that are currently open for applications.",
        "builder": "recruiting_trials",
        "default_order": 30,
        "dismissible": True,
        "allowed_permission_levels": PARTICIPANT_DASHBOARD_LEVELS,
    },
    {
        "key": "bonus_surveys_available",
        "title": "Bonus Surveys Available",
        "description": "Shows available bonus surveys that you may be eligible to complete.",
        "builder": "bonus_surveys",
        "default_order": 40,
        "dismissible": True,
        "allowed_permission_levels": PARTICIPANT_DASHBOARD_LEVELS,
    },
    {
        "key": "profile_completion",
        "title": "Profile Completion",
        "description": "Shows whether your profile is complete enough for trial matching.",
        "builder": "profile_completion",
        "default_order": 50,
        "dismissible": False,
        "allowed_permission_levels": PARTICIPANT_DASHBOARD_LEVELS,
    },
    {
        "key": "notifications",
        "title": "Notifications",
        "description": "Shows unread user-specific notifications and alerts.",
        "builder": "notifications",
        "default_order": 60,
        "dismissible": False,
        "allowed_permission_levels": PARTICIPANT_DASHBOARD_LEVELS,
    },
    {
        "key": "site_updates",
        "title": "Site Updates / Announcements",
        "description": "Shows program-wide updates and Logitech User Trials announcements.",
        "builder": "site_updates",
        "default_order": 70,
        "dismissible": True,
        "allowed_permission_levels": PARTICIPANT_DASHBOARD_LEVELS,
    },
    {
        "key": "logitrial_reputation",
        "title": "LogiTrials Reputation",
        "description": "Placeholder for future participation reliability and response quality scoring.",
        "builder": "reputation",
        "default_order": 80,
        "dismissible": True,
        "allowed_permission_levels": PARTICIPANT_DASHBOARD_LEVELS,
    },
    {
        "key": "legal_document_review",
        "title": "Legal Document Review",
        "description": "Shows active legal documents that are overdue, due soon, or never reviewed.",
        "builder": "legal_document_review",
        "default_order": 10,
        "dismissible": False,
        "allowed_permission_levels": LEGAL_DASHBOARD_LEVELS,
    },
]


def _format_date(value):
    if not value:
        return "—"

    try:
        return value.strftime("%Y-%m-%d")
    except Exception:
        return str(value)


def _count_label(count: int, singular: str, plural: str | None = None) -> str:
    safe_count = int(count or 0)
    if safe_count == 1:
        return f"1 {singular}"
    return f"{safe_count} {plural or singular + 's'}"


def _get_form_value(form: dict, key: str) -> str:
    raw_value = form.get(key)

    if isinstance(raw_value, list):
        return str(raw_value[0]).strip() if raw_value else ""

    return str(raw_value or "").strip()


def _safe_permission_level(permission_level: int) -> int:
    try:
        return int(permission_level or 0)
    except (TypeError, ValueError):
        return 0


def _is_definition_available_for_permission(definition: dict, permission_level: int) -> bool:
    safe_permission_level = _safe_permission_level(permission_level)
    allowed_permission_levels = definition.get("allowed_permission_levels")

    if allowed_permission_levels is not None:
        return safe_permission_level in set(allowed_permission_levels)

    return safe_permission_level >= int(definition.get("min_permission_level", 0))


def _get_available_card_definitions(permission_level: int) -> list[dict]:
    return [
        definition
        for definition in DASHBOARD_CARD_DEFINITIONS
        if _is_definition_available_for_permission(definition, permission_level)
    ]


def _get_card_definition(card_key: str, permission_level: int) -> dict | None:
    for definition in _get_available_card_definitions(permission_level):
        if definition["key"] == card_key:
            return definition

    return None


def _is_card_visible(definition: dict, preferences: dict) -> bool:
    card_key = definition["key"]
    preference = preferences.get(card_key)

    if not preference:
        return True

    return bool(preference.get("is_visible"))


def _get_card_sort_order(definition: dict, preferences: dict) -> int:
    card_key = definition["key"]
    preference = preferences.get(card_key) or {}
    sort_order = preference.get("sort_order")

    if sort_order is None:
        return int(definition["default_order"])

    try:
        return int(sort_order)
    except (TypeError, ValueError):
        return int(definition["default_order"])


def _get_visible_card_definitions(*, available_definitions: list[dict], preferences: dict) -> list[dict]:
    visible = [
        definition
        for definition in available_definitions
        if _is_card_visible(definition, preferences)
    ]

    return sorted(
        visible,
        key=lambda definition: _get_card_sort_order(definition, preferences),
    )


def _get_hidden_card_definitions(*, available_definitions: list[dict], preferences: dict) -> list[dict]:
    hidden = [
        definition
        for definition in available_definitions
        if not _is_card_visible(definition, preferences)
    ]

    return sorted(
        hidden,
        key=lambda definition: _get_card_sort_order(definition, preferences),
    )


def _render_dashboard_card(
    *,
    key: str,
    title: str,
    eyebrow: str,
    status: str,
    body_html: str,
    csrf_token: str,
    action_href: str | None = None,
    action_label: str | None = None,
    dismissible: bool = True,
    is_stub: bool = False,
) -> str:
    safe_key = e(key)
    safe_title = e(title)
    safe_eyebrow = e(eyebrow)
    safe_status = e(status)
    safe_csrf_token = e(csrf_token)

    dismiss_html = ""
    if dismissible:
        dismiss_html = f"""
        <form method="post" action="/dashboard/cards/hide" class="dashboard-card-dismiss-form">
            <input type="hidden" name="csrf_token" value="{safe_csrf_token}">
            <input type="hidden" name="card_key" value="{safe_key}">
            <button
                type="submit"
                class="dashboard-card-dismiss"
                aria-label="Hide {safe_title} card"
                title="Hide this dashboard card"
            >×</button>
        </form>
        """

    action_html = ""
    if action_href and action_label:
        action_html = f"""
        <a class="dashboard-card-action" href="{e(action_href)}">
            {e(action_label)}
        </a>
        """

    stub_class = " dashboard-card-stub" if is_stub else ""

    return f"""
    <article id="dashboard-card-{safe_key}" class="dashboard-card{stub_class}" data-card-key="{safe_key}">
        <div class="dashboard-card-topline">
            <span class="dashboard-card-eyebrow">{safe_eyebrow}</span>
            {dismiss_html}
        </div>

        <div class="dashboard-card-header">
            <h2>{safe_title}</h2>
            <span class="dashboard-card-status">{safe_status}</span>
        </div>

        <div class="dashboard-card-body">
            {body_html}
        </div>

        <div class="dashboard-card-footer">
            {action_html}
        </div>
    </article>
    """


def _render_mini_list(items: list[tuple[str, str]], empty_text: str) -> str:
    if not items:
        return f"<p class='dashboard-card-empty'>{e(empty_text)}</p>"

    rows = []
    for label, meta in items:
        rows.append(f"""
        <li>
            <span class="dashboard-mini-list-label">{e(label)}</span>
            <span class="dashboard-mini-list-meta">{e(meta)}</span>
        </li>
        """)

    return f"""
    <ul class="dashboard-mini-list">
        {''.join(rows)}
    </ul>
    """


def _derive_next_active_trial_action(active_context: dict) -> str:
    if active_context.get("nda", {}).get("required") and not active_context.get("nda", {}).get("signed"):
        return "Next action: sign trial NDA."

    if active_context.get("shipping", {}).get("required") and not active_context.get("shipping", {}).get("confirmed"):
        return "Next action: confirm shipping details."

    if not active_context.get("responsibilities", {}).get("accepted"):
        return "Next action: accept trial responsibilities."

    device = active_context.get("device") or {}
    device_state = device.get("state")

    if device_state == "pending":
        return "Device shipment is pending."

    if device_state == "in_transit":
        return "Device is in transit."

    if device_state == "awaiting_confirmation":
        return "Next action: confirm device receipt."

    for survey in active_context.get("surveys") or []:
        if survey.get("available") and not survey.get("completed"):
            label = survey.get("label") or "survey"
            return f"Next action: complete {label}."

    for survey in active_context.get("surveys") or []:
        if not survey.get("completed"):
            return "Waiting for the next survey activation."

    return "No immediate action required."


def _build_current_trial_card(user_id: str, csrf_token: str, definition: dict) -> str:
    from app.db.project_participants import get_active_trials_for_user
    from app.services.active_trial import build_active_trial_context

    rows = get_active_trials_for_user(user_id)

    if not rows:
        return _render_dashboard_card(
            key=definition["key"],
            title=definition["title"],
            eyebrow="Participant",
            status="No active trial",
            body_html="""
                <p class="dashboard-card-empty">
                    You are not currently in an active trial.
                </p>
            """,
            csrf_token=csrf_token,
            action_href="/trials/recruiting",
            action_label="Browse recruiting trials",
            dismissible=definition["dismissible"],
        )

    active = build_active_trial_context(rows[0])
    trial_name = get_project_display_name(active)
    round_label = get_round_display_label(active)
    next_action = _derive_next_active_trial_action(active)
    more_count = max(0, len(rows) - 1)

    extra_html = ""
    if more_count:
        extra_html = f"""
        <p class="dashboard-card-note">
            + {e(str(more_count))} more active trial{'' if more_count == 1 else 's'}.
        </p>
        """

    body_html = f"""
        <p class="dashboard-card-primary">{e(trial_name)}</p>
        <p class="dashboard-card-secondary">{e(round_label)}</p>
        <p class="dashboard-card-note">{e(next_action)}</p>
        {extra_html}
    """

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Participant",
        status="Active",
        body_html=body_html,
        csrf_token=csrf_token,
        action_href="/trials/active",
        action_label="View active trial",
        dismissible=definition["dismissible"],
    )


def _build_upcoming_trials_card(user_id: str, csrf_token: str, definition: dict) -> str:
    from app.services.trial_visibility import get_visible_upcoming_rounds

    rounds = get_visible_upcoming_rounds(user_id=user_id)
    items = []

    for row in rounds[:3]:
        label = get_project_display_name(row)
        meta = f"{get_round_display_label(row)} · Starts {_format_date(row.get('StartDate'))}"
        items.append((label, meta))

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Planning",
        status=_count_label(len(rounds), "trial"),
        body_html=_render_mini_list(items, "No upcoming trials are visible right now."),
        csrf_token=csrf_token,
        action_href="/trials/upcoming",
        action_label="View upcoming trials",
        dismissible=definition["dismissible"],
    )


def _build_recruiting_trials_card(user_id: str, csrf_token: str, definition: dict) -> str:
    from app.services.trial_visibility import get_visible_recruiting_rounds

    rounds = get_visible_recruiting_rounds(user_id=user_id)
    items = []

    for row in rounds[:3]:
        label = get_project_display_name(row)
        meta = f"{get_round_display_label(row)} · Starts {_format_date(row.get('StartDate'))}"
        items.append((label, meta))

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Applications",
        status=_count_label(len(rounds), "open trial", "open trials"),
        body_html=_render_mini_list(items, "No trials are currently recruiting for your profile."),
        csrf_token=csrf_token,
        action_href="/trials/recruiting",
        action_label="Browse recruiting trials",
        dismissible=definition["dismissible"],
    )


def _build_bonus_surveys_card(user_id: str, csrf_token: str, definition: dict) -> str:
    from app.db.surveys import get_eligible_active_bonus_surveys_for_user

    surveys = get_eligible_active_bonus_surveys_for_user(user_id)
    items = []

    for survey in surveys[:3]:
        title = survey.get("survey_title") or "Untitled bonus survey"
        close_date = _format_date(survey.get("close_at"))
        requestor = survey.get("requestor_name") or "Logitech User Trials"
        items.append((title, f"{requestor} · Closes {close_date}"))

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Extra feedback",
        status=_count_label(len(surveys), "survey", "surveys"),
        body_html=_render_mini_list(items, "No bonus surveys are available right now."),
        csrf_token=csrf_token,
        action_href="/surveys/bonus/take",
        action_label="View bonus surveys",
        dismissible=definition["dismissible"],
    )


def _build_profile_completion_card(user_id: str, csrf_token: str, definition: dict) -> str:
    from app.services.profile_state import (
        PROFILE_STATE_ADVANCED,
        PROFILE_STATE_BASIC,
        PROFILE_STATE_COMPLETE,
        PROFILE_STATE_INTERESTS,
        get_profile_state,
    )

    state = get_profile_state(user_id)

    state_map = {
        PROFILE_STATE_INTERESTS: ("Interests needed", 0, "Choose product interests to start matching."),
        PROFILE_STATE_BASIC: ("Basic profile needed", 33, "Add your core participant details."),
        PROFILE_STATE_ADVANCED: ("Advanced profile needed", 66, "Add device, usage, and preference details."),
        PROFILE_STATE_COMPLETE: ("Complete", 100, "Your profile is ready for trial matching."),
    }

    status, percent, note = state_map.get(state, ("Needs review", 0, "Review your profile details."))
    action_href = "/profile" if state == PROFILE_STATE_COMPLETE else "/profile/wizard"
    action_label = "Review profile" if state == PROFILE_STATE_COMPLETE else "Continue profile"

    body_html = f"""
        <div class="dashboard-progress-row">
            <div class="dashboard-progress-track">
                <div class="dashboard-progress-fill" style="width: {int(percent)}%;"></div>
            </div>
            <span>{int(percent)}%</span>
        </div>
        <p class="dashboard-card-note">{e(note)}</p>
    """

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Profile",
        status=status,
        body_html=body_html,
        csrf_token=csrf_token,
        action_href=action_href,
        action_label=action_label,
        dismissible=definition["dismissible"],
    )


def _build_notifications_card(user_id: str, csrf_token: str, definition: dict) -> str:
    from app.services.notifications import get_recent_notifications, get_unread_count

    unread_count = get_unread_count(user_id)
    notifications = get_recent_notifications(user_id, limit=3)

    items = []
    for notification in notifications[:3]:
        title = notification.get("title") or "Notification"
        created_at = _format_date(notification.get("created_at"))
        items.append((title, created_at))

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Attention",
        status=_count_label(unread_count, "unread"),
        body_html=_render_mini_list(items, "You have no unread notifications."),
        csrf_token=csrf_token,
        action_href="/notifications",
        action_label="View notifications",
        dismissible=definition["dismissible"],
    )


def _build_site_updates_card(user_id: str, csrf_token: str, definition: dict) -> str:
    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Program updates",
        status="Stub",
        body_html="""
            <p class="dashboard-card-empty">
                Site-wide updates and Logitech User Trials announcements will appear here.
            </p>
        """,
        csrf_token=csrf_token,
        dismissible=definition["dismissible"],
        is_stub=True,
    )

def _build_legal_document_review_card(user_id: str, csrf_token: str, definition: dict) -> str:
    from app.db.legal_documents import get_legal_review_dashboard_summary

    summary = get_legal_review_dashboard_summary()
    counts = summary.get("counts", {})
    attention_rows = summary.get("attention_rows", [])

    overdue_count = int(counts.get("overdue") or 0)
    due_soon_count = int(counts.get("due_soon") or 0)
    never_reviewed_count = int(counts.get("never_reviewed") or 0)

    if overdue_count:
        status = _count_label(overdue_count, "overdue")
    elif due_soon_count:
        status = _count_label(due_soon_count, "due soon")
    elif never_reviewed_count:
        status = _count_label(never_reviewed_count, "never reviewed")
    else:
        status = "Current"

    items = []
    for row in attention_rows[:4]:
        label = row.get("title") or "Untitled legal document"
        due_at = _format_date(row.get("review_due_at"))
        if row.get("is_overdue"):
            meta = f"Overdue · Due {due_at}"
        elif row.get("is_never_reviewed"):
            meta = f"Never reviewed · Due {due_at}"
        else:
            meta = f"Due soon · Due {due_at}"

        items.append((label, meta))

    if items:
        body_html = _render_mini_list(items, "")
    else:
        body_html = """
            <p class="dashboard-card-empty">
                All active legal documents are current for annual review.
            </p>
        """

    body_html += f"""
        <p class="dashboard-card-note">
            {e(str(counts.get("active") or 0))} active documents ·
            {e(str(overdue_count))} overdue ·
            {e(str(due_soon_count))} due soon ·
            {e(str(never_reviewed_count))} never reviewed
        </p>
    """

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Legal",
        status=status,
        body_html=body_html,
        csrf_token=csrf_token,
        action_href="/legal/documents",
        action_label="Review legal documents",
        dismissible=definition["dismissible"],
    )

def _build_reputation_card(user_id: str, csrf_token: str, definition: dict) -> str:
    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Coming soon",
        status="Stub",
        body_html="""
            <p class="dashboard-card-empty">
                Your reputation will eventually reflect participation reliability,
                survey completion, and response quality.
            </p>
        """,
        csrf_token=csrf_token,
        dismissible=definition["dismissible"],
        is_stub=True,
    )


def _build_card_from_definition(*, user_id: str, csrf_token: str, definition: dict) -> str:
    builder = definition["builder"]

    if builder == "current_trial":
        return _build_current_trial_card(user_id, csrf_token, definition)

    if builder == "upcoming_trials":
        return _build_upcoming_trials_card(user_id, csrf_token, definition)

    if builder == "recruiting_trials":
        return _build_recruiting_trials_card(user_id, csrf_token, definition)

    if builder == "bonus_surveys":
        return _build_bonus_surveys_card(user_id, csrf_token, definition)

    if builder == "profile_completion":
        return _build_profile_completion_card(user_id, csrf_token, definition)

    if builder == "notifications":
        return _build_notifications_card(user_id, csrf_token, definition)

    if builder == "site_updates":
        return _build_site_updates_card(user_id, csrf_token, definition)

    if builder == "reputation":
        return _build_reputation_card(user_id, csrf_token, definition)

    if builder == "legal_document_review":
        return _build_legal_document_review_card(user_id, csrf_token, definition)

    return ""


def _render_add_card_placeholder(hidden_count: int) -> str:
    note = "No hidden cards available"
    if hidden_count:
        note = _count_label(hidden_count, "hidden card")

    return f"""
    <article class="dashboard-add-card-shell" aria-label="Add dashboard card placeholder">
        <a class="dashboard-add-card" href="/dashboard/cards">
            <span class="dashboard-add-plus">+</span>
            <span class="dashboard-add-label">Add dashboard card</span>
            <span class="dashboard-add-note">{e(note)}</span>
        </a>
    </article>
    """


def _render_visible_dashboard_card_row(
    *,
    definition: dict,
    csrf_token: str,
    can_move_up: bool,
    can_move_down: bool,
) -> str:
    safe_key = e(definition["key"])
    safe_csrf_token = e(csrf_token)

    up_disabled = "" if can_move_up else " disabled"
    down_disabled = "" if can_move_down else " disabled"

    return f"""
    <article class="dashboard-picker-card dashboard-picker-card-visible">
        <div>
            <h2>{e(definition["title"])}</h2>
            <p>{e(definition["description"])}</p>
        </div>

        <div class="dashboard-picker-actions">
            <form method="post" action="/dashboard/cards/move-up">
                <input type="hidden" name="csrf_token" value="{safe_csrf_token}">
                <input type="hidden" name="card_key" value="{safe_key}">
                <button type="submit" class="dashboard-order-button"{up_disabled}>
                    Move up
                </button>
            </form>

            <form method="post" action="/dashboard/cards/move-down">
                <input type="hidden" name="csrf_token" value="{safe_csrf_token}">
                <input type="hidden" name="card_key" value="{safe_key}">
                <button type="submit" class="dashboard-order-button"{down_disabled}>
                    Move down
                </button>
            </form>
        </div>
    </article>
    """


def _render_visible_dashboard_card_rows(*, visible_definitions: list[dict], csrf_token: str) -> str:
    if not visible_definitions:
        return """
        <div class="dashboard-picker-empty">
            <p>No dashboard cards are currently visible.</p>
        </div>
        """

    rows = []
    last_index = len(visible_definitions) - 1
    for index, definition in enumerate(visible_definitions):
        rows.append(
            _render_visible_dashboard_card_row(
                definition=definition,
                csrf_token=csrf_token,
                can_move_up=index > 0,
                can_move_down=index < last_index,
            )
        )

    return "".join(rows)


def _render_hidden_dashboard_card(*, definition: dict, csrf_token: str) -> str:
    return f"""
    <article class="dashboard-picker-card">
        <div>
            <h2>{e(definition["title"])}</h2>
            <p>{e(definition["description"])}</p>
        </div>

        <form method="post" action="/dashboard/cards/show">
            <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
            <input type="hidden" name="card_key" value="{e(definition["key"])}">
            <button type="submit" class="dashboard-card-action">
                Add card
            </button>
        </form>
    </article>
    """


def _render_hidden_dashboard_card_rows(*, hidden_definitions: list[dict], csrf_token: str) -> str:
    if not hidden_definitions:
        return """
        <div class="dashboard-picker-empty">
            <p>All available dashboard cards are already visible.</p>
        </div>
        """

    rows = []
    for definition in hidden_definitions:
        rows.append(_render_hidden_dashboard_card(definition=definition, csrf_token=csrf_token))

    return "".join(rows)


def render_dashboard_get(
    *,
    user_id: str,
    permission_level: int,
    base_template: str,
    inject_nav,
    csrf_token: str,
):
    """
    GET /dashboard

    Modular dashboard framework.
    Read-only: this renderer pulls DB-backed summaries and user card preferences.
    """

    from app.db.dashboard_cards import get_user_card_preferences

    dashboard_template = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    preferences = get_user_card_preferences(user_id)
    available_definitions = _get_available_card_definitions(permission_level)

    visible_definitions = _get_visible_card_definitions(
        available_definitions=available_definitions,
        preferences=preferences,
    )
    hidden_definitions = _get_hidden_card_definitions(
        available_definitions=available_definitions,
        preferences=preferences,
    )

    cards = []
    for definition in visible_definitions:
        cards.append(
            _build_card_from_definition(
                user_id=user_id,
                csrf_token=csrf_token,
                definition=definition,
            )
        )

    cards.append(_render_add_card_placeholder(len(hidden_definitions)))

    body = dashboard_template.replace("__DASHBOARD_CARDS__", "".join(cards))

    html = inject_nav(base_template)
    html = html.replace("__BODY_CLASS__", "dashboard-page-body")
    html = html.replace("{{ title }}", "Dashboard")
    html = html.replace("__BODY__", body)

    return {"html": html}


def render_dashboard_cards_get(
    *,
    user_id: str,
    permission_level: int,
    base_template: str,
    inject_nav,
    csrf_token: str,
):
    """
    GET /dashboard/cards

    Curated dashboard card picker.
    Read-only: this page lists hidden cards that the user can add back.
    """

    from app.db.dashboard_cards import get_user_card_preferences

    dashboard_cards_template = DASHBOARD_CARDS_TEMPLATE.read_text(encoding="utf-8")
    preferences = get_user_card_preferences(user_id)
    available_definitions = _get_available_card_definitions(permission_level)
    visible_definitions = _get_visible_card_definitions(
        available_definitions=available_definitions,
        preferences=preferences,
    )
    hidden_definitions = _get_hidden_card_definitions(
        available_definitions=available_definitions,
        preferences=preferences,
    )

    visible_rows = _render_visible_dashboard_card_rows(
        visible_definitions=visible_definitions,
        csrf_token=csrf_token,
    )
    hidden_rows = _render_hidden_dashboard_card_rows(
        hidden_definitions=hidden_definitions,
        csrf_token=csrf_token,
    )

    body = dashboard_cards_template.replace("__VISIBLE_DASHBOARD_CARD_ROWS__", visible_rows)
    body = body.replace("__HIDDEN_DASHBOARD_CARD_ROWS__", hidden_rows)

    html = inject_nav(base_template)
    html = html.replace("__BODY_CLASS__", "dashboard-page-body")
    html = html.replace("{{ title }}", "Dashboard Cards")
    html = html.replace("__BODY__", body)

    return {"html": html}


def handle_dashboard_card_hide_post(*, user_id: str, permission_level: int, form: dict) -> dict:
    """
    POST /dashboard/cards/hide

    Mutates only the authenticated user's dashboard card visibility.
    """

    card_key = _get_form_value(form, "card_key")
    definition = _get_card_definition(card_key, permission_level)

    if not definition:
        return {"ok": False, "error": "unknown_card"}

    if not definition.get("dismissible"):
        return {"ok": False, "error": "card_not_dismissible"}

    from app.db.dashboard_cards import set_dashboard_card_visibility

    set_dashboard_card_visibility(
        user_id=user_id,
        card_key=card_key,
        is_visible=False,
    )

    return {"ok": True}


def handle_dashboard_card_show_post(*, user_id: str, permission_level: int, form: dict) -> dict:
    """
    POST /dashboard/cards/show

    Mutates only the authenticated user's dashboard card visibility.
    """

    card_key = _get_form_value(form, "card_key")
    definition = _get_card_definition(card_key, permission_level)

    if not definition:
        return {"ok": False, "error": "unknown_card"}

    from app.db.dashboard_cards import set_dashboard_card_visibility

    set_dashboard_card_visibility(
        user_id=user_id,
        card_key=card_key,
        is_visible=True,
    )

    return {"ok": True}

def handle_dashboard_card_move_post(
    *,
    user_id: str,
    permission_level: int,
    form: dict,
    direction: str,
) -> dict:
    """
    POST /dashboard/cards/move-up
    POST /dashboard/cards/move-down

    Mutates only the authenticated user's dashboard card sort order.
    The handler recomputes available/visible cards from DB preferences and the
    curated card registry instead of trusting the browser for order state.
    """

    card_key = _get_form_value(form, "card_key")
    definition = _get_card_definition(card_key, permission_level)

    if not definition:
        return {"ok": False, "error": "unknown_card"}

    if direction not in {"up", "down"}:
        return {"ok": False, "error": "invalid_direction"}

    from app.db.dashboard_cards import (
        get_user_card_preferences,
        set_dashboard_card_sort_orders,
    )

    preferences = get_user_card_preferences(user_id)
    available_definitions = _get_available_card_definitions(permission_level)
    visible_definitions = _get_visible_card_definitions(
        available_definitions=available_definitions,
        preferences=preferences,
    )

    visible_keys = [row["key"] for row in visible_definitions]

    if card_key not in visible_keys:
        return {"ok": False, "error": "card_not_visible"}

    current_index = visible_keys.index(card_key)
    target_index = current_index - 1 if direction == "up" else current_index + 1

    if target_index < 0 or target_index >= len(visible_keys):
        return {"ok": True}

    visible_keys[current_index], visible_keys[target_index] = (
        visible_keys[target_index],
        visible_keys[current_index],
    )

    set_dashboard_card_sort_orders(
        user_id=user_id,
        ordered_card_keys=visible_keys,
    )

    return {"ok": True}