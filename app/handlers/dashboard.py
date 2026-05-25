# app/handlers/dashboard.py

from pathlib import Path

from app.utils.html_escape import escape_html as e
from app.utils.trial_display import get_project_display_name, get_round_display_label


DASHBOARD_TEMPLATE = Path("app/templates/dashboard.html")


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


def _render_dashboard_card(
    *,
    key: str,
    title: str,
    eyebrow: str,
    status: str,
    body_html: str,
    action_href: str | None = None,
    action_label: str | None = None,
    dismissible: bool = True,
    is_stub: bool = False,
) -> str:
    safe_key = e(key)
    safe_title = e(title)
    safe_eyebrow = e(eyebrow)
    safe_status = e(status)

    dismiss_html = ""
    if dismissible:
        dismiss_html = f"""
        <button
            type="button"
            class="dashboard-card-dismiss"
            aria-label="Hide {safe_title} card"
            title="Dashboard card hiding will be wired in the next dashboard persistence pass."
            disabled
        >×</button>
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
    <article class="dashboard-card{stub_class}" data-card-key="{safe_key}">
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


def _build_current_trial_card(user_id: str) -> str:
    from app.db.project_participants import get_active_trials_for_user
    from app.services.active_trial import build_active_trial_context

    rows = get_active_trials_for_user(user_id)

    if not rows:
        return _render_dashboard_card(
            key="current_trial",
            title="Current Trial",
            eyebrow="Participant",
            status="No active trial",
            body_html="""
                <p class="dashboard-card-empty">
                    You are not currently in an active trial.
                </p>
            """,
            action_href="/trials/recruiting",
            action_label="Browse recruiting trials",
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
        key="current_trial",
        title="Current Trial",
        eyebrow="Participant",
        status="Active",
        body_html=body_html,
        action_href="/trials/active",
        action_label="View active trial",
    )


def _build_upcoming_trials_card(user_id: str) -> str:
    from app.services.trial_visibility import get_visible_upcoming_rounds

    rounds = get_visible_upcoming_rounds(user_id=user_id)
    items = []

    for row in rounds[:3]:
        label = get_project_display_name(row)
        meta = f"{get_round_display_label(row)} · Starts {_format_date(row.get('StartDate'))}"
        items.append((label, meta))

    return _render_dashboard_card(
        key="upcoming_trials",
        title="Upcoming Trials",
        eyebrow="Planning",
        status=_count_label(len(rounds), "trial"),
        body_html=_render_mini_list(items, "No upcoming trials are visible right now."),
        action_href="/trials/upcoming",
        action_label="View upcoming trials",
    )


def _build_recruiting_trials_card(user_id: str) -> str:
    from app.services.trial_visibility import get_visible_recruiting_rounds

    rounds = get_visible_recruiting_rounds(user_id=user_id)
    items = []

    for row in rounds[:3]:
        label = get_project_display_name(row)
        meta = f"{get_round_display_label(row)} · Starts {_format_date(row.get('StartDate'))}"
        items.append((label, meta))

    return _render_dashboard_card(
        key="recruiting_trials",
        title="Trials Currently Recruiting",
        eyebrow="Applications",
        status=_count_label(len(rounds), "open trial", "open trials"),
        body_html=_render_mini_list(items, "No trials are currently recruiting for your profile."),
        action_href="/trials/recruiting",
        action_label="Browse recruiting trials",
    )


def _build_bonus_surveys_card(user_id: str) -> str:
    from app.db.surveys import get_eligible_active_bonus_surveys_for_user

    surveys = get_eligible_active_bonus_surveys_for_user(user_id)
    items = []

    for survey in surveys[:3]:
        title = survey.get("survey_title") or "Untitled bonus survey"
        close_date = _format_date(survey.get("close_at"))
        requestor = survey.get("requestor_name") or "Logitech User Trials"
        items.append((title, f"{requestor} · Closes {close_date}"))

    return _render_dashboard_card(
        key="bonus_surveys_available",
        title="Bonus Surveys Available",
        eyebrow="Extra feedback",
        status=_count_label(len(surveys), "survey", "surveys"),
        body_html=_render_mini_list(items, "No bonus surveys are available right now."),
        action_href="/surveys/bonus/take",
        action_label="View bonus surveys",
    )


def _build_profile_completion_card(user_id: str) -> str:
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
        key="profile_completion",
        title="Profile Completion",
        eyebrow="Profile",
        status=status,
        body_html=body_html,
        action_href=action_href,
        action_label=action_label,
        dismissible=False,
    )


def _build_notifications_card(user_id: str) -> str:
    from app.services.notifications import get_recent_notifications, get_unread_count

    unread_count = get_unread_count(user_id)
    notifications = get_recent_notifications(user_id, limit=3)

    items = []
    for notification in notifications[:3]:
        title = notification.get("title") or "Notification"
        created_at = _format_date(notification.get("created_at"))
        items.append((title, created_at))

    return _render_dashboard_card(
        key="notifications",
        title="Notifications",
        eyebrow="Attention",
        status=_count_label(unread_count, "unread"),
        body_html=_render_mini_list(items, "You have no unread notifications."),
        action_href="/notifications",
        action_label="View notifications",
        dismissible=False,
    )


def _build_site_updates_card() -> str:
    return _render_dashboard_card(
        key="site_updates",
        title="Site Updates / Announcements",
        eyebrow="Program updates",
        status="Stub",
        body_html="""
            <p class="dashboard-card-empty">
                Site-wide updates and Logitech User Trials announcements will appear here.
            </p>
        """,
        is_stub=True,
    )


def _build_reputation_card() -> str:
    return _render_dashboard_card(
        key="logitrial_reputation",
        title="LogiTrial Reputation",
        eyebrow="Coming soon",
        status="Stub",
        body_html="""
            <p class="dashboard-card-empty">
                Your reputation will eventually reflect participation reliability,
                survey completion, and response quality.
            </p>
        """,
        is_stub=True,
    )


def _render_add_card_placeholder() -> str:
    return """
    <article class="dashboard-add-card-shell" aria-label="Add dashboard card placeholder">
        <button
            type="button"
            class="dashboard-add-card"
            title="Dashboard card picker will be wired after dashboard card persistence exists."
            disabled
        >
            <span class="dashboard-add-plus">+</span>
            <span class="dashboard-add-label">Add dashboard card</span>
            <span class="dashboard-add-note">Curated card picker coming next</span>
        </button>
    </article>
    """


def render_dashboard_get(*, user_id: str, base_template: str, inject_nav):
    """
    GET /dashboard

    Modular dashboard framework.
    Read-only: this renderer pulls DB-backed summaries and does not mutate state.
    """

    dashboard_template = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")

    cards = [
        _build_current_trial_card(user_id),
        _build_upcoming_trials_card(user_id),
        _build_recruiting_trials_card(user_id),
        _build_bonus_surveys_card(user_id),
        _build_profile_completion_card(user_id),
        _build_notifications_card(user_id),
        _build_site_updates_card(),
        _build_reputation_card(),
        _render_add_card_placeholder(),
    ]

    body = dashboard_template.replace("__DASHBOARD_CARDS__", "".join(cards))

    html = inject_nav(base_template)
    html = html.replace("__BODY_CLASS__", "dashboard-page-body")
    html = html.replace("{{ title }}", "Dashboard")
    html = html.replace("__BODY__", body)

    return {"html": html}