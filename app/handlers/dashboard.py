# app/handlers/dashboard.py

from pathlib import Path

from app.utils.html_escape import escape_html as e
from app.utils.trial_display import get_project_display_name, get_round_display_label


DASHBOARD_TEMPLATE = Path("app/templates/dashboard.html")
DASHBOARD_CARDS_TEMPLATE = Path("app/templates/dashboard_cards.html")


PARTICIPANT_DASHBOARD_LEVELS = {20, 30, 40, 50, 60, 70, 80, 100}
LEGAL_DASHBOARD_LEVELS = {30, 100}
BSC_DASHBOARD_LEVELS = {40, 100}
PRODUCT_TEAM_DASHBOARD_LEVELS = {50, 100}
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
        "default_visible": False,
        "dismissible": True,
        "show_when_profile_incomplete": True,
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
        "key": "bsc_bonus_survey_workflow",
        "title": "Bonus Survey Workflow",
        "description": "Shows your Bonus Survey drafts, pending approvals, active surveys, and recently closed surveys.",
        "builder": "bsc_bonus_survey_workflow",
        "default_order": 15,
        "dismissible": False,
        "allowed_permission_levels": BSC_DASHBOARD_LEVELS,
    },
    {
        "key": "product_team_trial_requests",
        "title": "Product Trial Requests",
        "description": "Shows Product Team draft requests, UT follow-up requests, pending review, and current trials.",
        "builder": "product_team_trial_requests",
        "default_order": 16,
        "dismissible": False,
        "allowed_permission_levels": PRODUCT_TEAM_DASHBOARD_LEVELS,
    },
    {
        "key": "management_reporting_insights",
        "title": "Reporting & Insights",
        "description": "Shows published reports, product-type coverage, and business-group coverage for management review.",
        "builder": "management_reporting_insights",
        "default_order": 17,
        "dismissible": False,
        "allowed_permission_levels": MANAGEMENT_DASHBOARD_LEVELS,
    },
    {
        "key": "ut_lead_my_current_trials",
        "title": "My Current Trials",
        "description": "Shows current trials assigned to you, with progress and the current action.",
        "builder": "ut_lead_my_current_trials",
        "default_order": 18,
        "dismissible": False,
        "allowed_permission_levels": UT_LEAD_DASHBOARD_LEVELS,
    },
    {
        "key": "ut_lead_my_planning_queue",
        "title": "My Planning Queue",
        "description": "Shows planning-stage trials assigned to you, including assigned Product Team requests.",
        "builder": "ut_lead_my_planning_queue",
        "default_order": 19,
        "dismissible": False,
        "allowed_permission_levels": UT_LEAD_DASHBOARD_LEVELS,
    },
    {
        "key": "ut_lead_my_upcoming_trials",
        "title": "My Upcoming Trials",
        "description": "Shows assigned upcoming trials that are scheduled but not yet in the planning window.",
        "builder": "ut_lead_my_upcoming_trials",
        "default_order": 20,
        "dismissible": False,
        "allowed_permission_levels": UT_LEAD_DASHBOARD_LEVELS,
    },
    {
        "key": "ut_lead_team_current_trials",
        "title": "UT Team Current Trials",
        "description": "Shows current trials across the UT team, with progress and current actions.",
        "builder": "ut_lead_team_current_trials",
        "default_order": 21,
        "dismissible": False,
        "allowed_permission_levels": UT_LEAD_DASHBOARD_LEVELS,
    },
    {
        "key": "ut_lead_team_planning_queue",
        "title": "UT Team Planning Queue",
        "description": "Shows planning-stage trials across the UT team, including unassigned planning work.",
        "builder": "ut_lead_team_planning_queue",
        "default_order": 22,
        "dismissible": False,
        "allowed_permission_levels": UT_LEAD_DASHBOARD_LEVELS,
    },
    {
        "key": "ut_lead_assigned_bsc_surveys",
        "title": "My Assigned BSC Surveys",
        "description": "Shows Bonus Surveys assigned to you, with response progress and the current action.",
        "builder": "ut_lead_assigned_bsc_surveys",
        "default_order": 23,
        "dismissible": True,
        "allowed_permission_levels": UT_LEAD_DASHBOARD_LEVELS,
    },
    {
        "key": "admin_site_overview",
        "title": "Site Overview",
        "description": "Shows sitewide users, recent logins, trial volume, and report activity.",
        "builder": "admin_site_overview",
        "default_order": 1,
        "dismissible": True,
        "allowed_permission_levels": ADMIN_DASHBOARD_LEVELS,
    },
    {
        "key": "admin_user_pool_stats",
        "title": "User Pool Stats",
        "description": "Shows real registered users, profile completion, recent logins, countries, and elevated access.",
        "builder": "admin_user_pool_stats",
        "default_order": 2,
        "dismissible": True,
        "allowed_permission_levels": ADMIN_DASHBOARD_LEVELS,
    },
    {
        "key": "admin_trial_stats",
        "title": "Trial Stats",
        "description": "Shows current, planning, upcoming, and recently completed Product Trial volume.",
        "builder": "admin_trial_stats",
        "default_order": 3,
        "dismissible": True,
        "allowed_permission_levels": ADMIN_DASHBOARD_LEVELS,
    },
    {
        "key": "admin_ut_lead_stats",
        "title": "UT Lead Stats",
        "description": "Shows UT Lead assignment coverage, active leads, and unassigned planning work.",
        "builder": "admin_ut_lead_stats",
        "default_order": 4,
        "dismissible": True,
        "allowed_permission_levels": ADMIN_DASHBOARD_LEVELS,
    },
    {
        "key": "admin_bg_product_stats",
        "title": "BG / Product Stats",
        "description": "Shows Business Group and product-type coverage across real Product Trial data.",
        "builder": "admin_bg_product_stats",
        "default_order": 5,
        "dismissible": True,
        "allowed_permission_levels": ADMIN_DASHBOARD_LEVELS,
    },
    {
        "key": "admin_reporting_stats",
        "title": "Reporting Stats",
        "description": "Shows published historical reports, generated Product Trial reports, BSC reports, and missing readouts.",
        "builder": "admin_reporting_stats",
        "default_order": 6,
        "dismissible": True,
        "allowed_permission_levels": ADMIN_DASHBOARD_LEVELS,
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


def _is_profile_completion_incomplete(user_id: str) -> bool:
    from app.services.profile_state import PROFILE_STATE_COMPLETE, get_profile_state

    return get_profile_state(user_id) != PROFILE_STATE_COMPLETE


def _is_card_force_visible(*, definition: dict, user_id: str) -> bool:
    if not definition.get("show_when_profile_incomplete"):
        return False

    if definition.get("key") != "profile_completion":
        return False

    return _is_profile_completion_incomplete(user_id)


def _is_card_visible(*, definition: dict, preferences: dict, user_id: str) -> bool:
    if _is_card_force_visible(definition=definition, user_id=user_id):
        return True

    card_key = definition["key"]
    preference = preferences.get(card_key)

    if preference:
        return bool(preference.get("is_visible"))

    return bool(definition.get("default_visible", True))


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


def _get_visible_card_definitions(
    *,
    available_definitions: list[dict],
    preferences: dict,
    user_id: str,
) -> list[dict]:
    visible = [
        definition
        for definition in available_definitions
        if _is_card_visible(
            definition=definition,
            preferences=preferences,
            user_id=user_id,
        )
    ]

    return sorted(
        visible,
        key=lambda definition: _get_card_sort_order(definition, preferences),
    )


def _get_hidden_card_definitions(
    *,
    available_definitions: list[dict],
    preferences: dict,
    user_id: str,
) -> list[dict]:
    hidden = [
        definition
        for definition in available_definitions
        if not _is_card_visible(
            definition=definition,
            preferences=preferences,
            user_id=user_id,
        )
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


def _build_profile_archetype(user_id: str, profile_state: str) -> dict:
    from app.services.profile_state import PROFILE_STATE_COMPLETE

    default_archetype = {
        "label": "Everyday Gear Explorer",
        "description": "Your profile is ready for a broad mix of Logitech user trials.",
        "chips": ["General trials", "Product feedback", "Trial matching"],
    }

    if profile_state != PROFILE_STATE_COMPLETE:
        return {
            "label": "Almost-Ready Explorer",
            "description": "Finish the remaining profile steps to unlock better trial matching.",
            "chips": ["Interests", "Profile details", "Matching setup"],
        }

    try:
        from app.config.profile_layout import (
            ADVANCED_PROFILE_SECTIONS,
            BASIC_PROFILE_SECTIONS,
            INTEREST_PROFILE_SECTIONS,
        )
        from app.db.user_interest_map import get_user_interest_uids
        from app.db.user_interests import get_interests_by_category_ids
        from app.db.user_profile_map import get_user_profile_uids
        from app.db.user_profiles import get_profiles_by_category_ids
    except Exception:
        return default_archetype

    def _section_category_ids(sections: list[dict]) -> list[int]:
        category_ids = []
        for section in sections:
            for category_id in section.get("categories") or []:
                try:
                    category_ids.append(int(category_id))
                except (TypeError, ValueError):
                    continue
        return sorted(set(category_ids))

    try:
        selected_interest_uids = {
            str(row.get("InterestUID"))
            for row in get_user_interest_uids(user_id)
            if row.get("InterestUID")
        }
        selected_profile_uids = {
            str(row.get("ProfileUID"))
            for row in get_user_profile_uids(user_id)
            if row.get("ProfileUID")
        }

        interest_categories = _section_category_ids(INTEREST_PROFILE_SECTIONS)
        profile_categories = _section_category_ids(BASIC_PROFILE_SECTIONS + ADVANCED_PROFILE_SECTIONS)

        interest_rows = [
            row for row in get_interests_by_category_ids(interest_categories)
            if str(row.get("InterestUID")) in selected_interest_uids
        ]
        profile_rows = [
            row for row in get_profiles_by_category_ids(profile_categories)
            if str(row.get("ProfileUID")) in selected_profile_uids
        ]
    except Exception:
        return default_archetype

    selected_interest_categories = {
        int(row.get("CategoryID"))
        for row in interest_rows
        if row.get("CategoryID") is not None
    }
    selected_profile_categories = {
        int(row.get("CategoryID"))
        for row in profile_rows
        if row.get("CategoryID") is not None
    }
    selected_product_codes = {
        str(row.get("InterestCode") or "")
        for row in interest_rows
        if int(row.get("CategoryID") or 0) == 102
    }
    selected_profile_codes = {
        str(row.get("ProfileCode") or "")
        for row in profile_rows
    }

    has_keyboard = (
        "PT102a" in selected_product_codes
        or bool(selected_interest_categories & {201, 202, 203})
        or 13 in selected_profile_categories
    )
    has_mouse = (
        "PT102b" in selected_product_codes
        or bool(selected_interest_categories & {301, 302, 303})
        or 20 in selected_profile_categories
    )
    has_headset = (
        "PT102c" in selected_product_codes
        or bool(selected_interest_categories & {401, 402, 403, 404, 405})
        or 15 in selected_profile_categories
    )
    has_webcam = (
        "PT102g" in selected_product_codes
        or bool(selected_interest_categories & {801, 802, 803})
        or 18 in selected_profile_categories
    )
    has_microphone = (
        "PT102f" in selected_product_codes
        or bool(selected_interest_categories & {701, 702, 703})
        or 17 in selected_profile_categories
    )
    has_creator = (
        "PT102h" in selected_product_codes
        or bool(selected_interest_categories & {901, 902})
        or bool(selected_profile_codes & {"03a", "03b", "03c", "04a", "04b", "04c"})
    )
    has_gaming = bool(selected_profile_codes & {"01a", "01b", "01c", "02a", "02b", "02c"})
    has_mobile = bool(selected_interest_categories & {1001})
    has_meetings = bool(selected_profile_codes & {"26a", "26b"})

    if has_keyboard and has_mouse:
        return {
            "label": "Desk Setup Maestro",
            "description": "Your profile is tuned for hands-on workspace and productivity gear trials.",
            "chips": ["Keyboards", "Mice", "Work setup"],
        }

    if has_keyboard:
        return {
            "label": "Keyboard Ninja",
            "description": "Your profile is primed for keyboard, typing, and workflow-focused trials.",
            "chips": ["Keyboards", "Typing feel", "Productivity"],
        }

    if has_meetings and (has_webcam or has_headset or has_microphone):
        return {
            "label": "Camera-On Collaborator",
            "description": "Your profile is ready for meeting, video, and collaboration gear trials.",
            "chips": ["Video calls", "Audio gear", "Collaboration"],
        }

    if has_creator:
        return {
            "label": "Creative Multitasker",
            "description": "Your profile fits trials for creating, streaming, and multi-tool workflows.",
            "chips": ["Creator gear", "Streaming", "Workflow"],
        }

    if has_gaming:
        return {
            "label": "Gaming Gear Explorer",
            "description": "Your profile is ready for play-focused gear and entertainment trials.",
            "chips": ["Gaming", "Entertainment", "Gear feedback"],
        }

    if has_mobile:
        return {
            "label": "Mobile Workstyle Scout",
            "description": "Your profile fits trials for flexible, mobile, and on-the-go setups.",
            "chips": ["Mobility", "Flexible setup", "Everyday use"],
        }

    return default_archetype


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
    archetype = _build_profile_archetype(user_id, state)

    chip_html = "".join(
        f'<span class="dashboard-profile-chip">{e(str(chip))}</span>'
        for chip in archetype.get("chips", [])[:3]
    )

    body_html = f"""
        <div class="dashboard-profile-completion">
            <div class="dashboard-profile-hero">
                <span class="dashboard-profile-hero-number">{int(percent)}%</span>
                <span class="dashboard-profile-hero-label">Profile ready</span>
                <div class="dashboard-progress-row dashboard-profile-progress-row">
                    <div class="dashboard-progress-track">
                        <div class="dashboard-progress-fill" style="width: {int(percent)}%;"></div>
                    </div>
                </div>
                <p class="dashboard-card-note dashboard-profile-note">{e(note)}</p>
            </div>

            <div class="dashboard-profile-archetype">
                <span class="dashboard-profile-archetype-label">Trial profile</span>
                <strong>{e(str(archetype.get("label") or "Everyday Gear Explorer"))}</strong>
                <p>{e(str(archetype.get("description") or "Your profile is ready for a broad mix of Logitech user trials."))}</p>
            </div>

            <div class="dashboard-profile-chip-row">
                {chip_html}
            </div>
        </div>
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
        dismissible=definition["dismissible"] and state == PROFILE_STATE_COMPLETE,
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

def _build_bsc_bonus_survey_workflow_card(user_id: str, csrf_token: str, definition: dict) -> str:
    from app.db.surveys import get_bonus_survey_dashboard_summary

    summary = get_bonus_survey_dashboard_summary(user_id)
    counts = summary.get("counts", {})

    draft_count = int(counts.get("drafts") or 0)
    pending_count = int(counts.get("pending") or 0)
    active_count = int(counts.get("active") or 0)
    recently_closed_count = int(counts.get("recently_closed") or 0)

    if draft_count:
        status = _count_label(draft_count, "draft")
    elif pending_count:
        status = _count_label(pending_count, "pending")
    elif active_count:
        status = _count_label(active_count, "active survey", "active surveys")
    elif recently_closed_count:
        status = _count_label(recently_closed_count, "closed survey", "closed surveys")
    else:
        status = "Ready"

    items = []

    for row in (summary.get("drafts") or [])[:2]:
        title = row.get("title") or "Untitled draft"
        updated_at = _format_date(row.get("updated_at"))
        items.append((title, f"Draft · Updated {updated_at}"))

    for row in (summary.get("pending") or [])[:2]:
        title = row.get("survey_title") or "Untitled survey"
        created_at = _format_date(row.get("created_at"))
        items.append((title, f"Pending approval · Submitted {created_at}"))

    for row in (summary.get("active") or [])[:2]:
        title = row.get("survey_title") or "Untitled survey"
        close_at = _format_date(row.get("close_at"))
        items.append((title, f"Active · Closes {close_at}"))

    for row in (summary.get("recently_closed") or [])[:2]:
        title = row.get("survey_title") or "Untitled survey"
        close_at = _format_date(row.get("close_at") or row.get("updated_at"))
        items.append((title, f"Closed · Results follow-up {close_at}"))

    body_html = _render_mini_list(
        items[:4],
        "No Bonus Survey work is waiting right now.",
    )

    body_html += f"""
        <p class="dashboard-card-note">
            {e(str(draft_count))} drafts ·
            {e(str(pending_count))} pending ·
            {e(str(active_count))} active ·
            {e(str(recently_closed_count))} closed
        </p>
    """

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="BSC",
        status=status,
        body_html=body_html,
        csrf_token=csrf_token,
        action_href="/surveys/bonus",
        action_label="Open Bonus Surveys",
        dismissible=definition["dismissible"],
    )


def _product_team_status_label(status: str | None) -> str:
    status_map = {
        "info_requested": "Info requested",
        "change_requested": "Changes requested",
        "pending_ut_review": "Pending UT review",
        "approved": "Approved",
        "recruiting": "Recruiting",
        "screening": "Screening",
        "active": "Active",
        "running": "In progress",
        "completed": "Completed",
    }

    return status_map.get((status or "").lower(), "Current")


def _build_product_team_trial_requests_card(user_id: str, csrf_token: str, definition: dict) -> str:
    from app.cache.product_cache import list_trial_projects_for_user
    from app.db.project_rounds import (
        get_action_required_project_rounds_for_user,
        get_current_project_rounds_for_user,
        get_pending_project_rounds_for_user,
    )

    draft_projects = list_trial_projects_for_user(user_id=user_id)
    action_required = get_action_required_project_rounds_for_user(user_id=user_id)
    pending_review = get_pending_project_rounds_for_user(user_id=user_id)
    current_rounds = get_current_project_rounds_for_user(user_id=user_id)

    active_statuses = {"approved", "recruiting", "screening", "active", "running", "completed"}
    active_rounds = [
        row
        for row in current_rounds
        if (row.get("Status") or "").lower() in active_statuses
    ]

    draft_count = len(draft_projects)
    action_count = len(action_required)
    pending_count = len(pending_review)
    active_count = len(active_rounds)

    if action_count:
        status = _count_label(action_count, "action needed", "actions needed")
    elif draft_count:
        status = _count_label(draft_count, "draft")
    elif pending_count:
        status = _count_label(pending_count, "pending review", "pending reviews")
    elif active_count:
        status = _count_label(active_count, "current trial")
    else:
        status = "Ready"

    items = []

    for row in action_required[:2]:
        title = row.get("ProjectName") or row.get("RoundName") or "Untitled trial request"
        status_label = _product_team_status_label(row.get("Status"))
        updated_at = _format_date(row.get("UpdatedAt"))
        items.append((title, f"{status_label} · Updated {updated_at}"))

    for project in draft_projects[:2]:
        title = project.get("basics", {}).get("project_name") or "Untitled draft"
        updated_at = _format_date(project.get("updated_at"))
        items.append((title, f"Draft · Updated {updated_at}"))

    for row in pending_review[:2]:
        title = row.get("ProjectName") or row.get("RoundName") or "Untitled trial request"
        items.append((title, "Pending UT review"))

    for row in active_rounds[:2]:
        title = row.get("ProjectName") or row.get("RoundName") or "Untitled current trial"
        status_label = _product_team_status_label(row.get("Status"))
        start_date = _format_date(row.get("StartDate"))
        items.append((title, f"{status_label} · Starts {start_date}"))

    body_html = _render_mini_list(
        items[:4],
        "No Product Team trial work is waiting right now.",
    )

    body_html += f"""
        <p class="dashboard-card-note">
            {e(str(draft_count))} drafts ·
            {e(str(action_count))} actions ·
            {e(str(pending_count))} pending ·
            {e(str(active_count))} current
        </p>
    """

    if action_count:
        action_href = "/product/request-trial"
        action_label = "Review trial requests"
    elif draft_count or pending_count:
        action_href = "/product/request-trial"
        action_label = "Open trial requests"
    elif active_count:
        action_href = "/product/current-trials"
        action_label = "View current trials"
    else:
        action_href = "/product/request-trial"
        action_label = "Request a trial"

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Product Team",
        status=status,
        body_html=body_html,
        csrf_token=csrf_token,
        action_href=action_href,
        action_label=action_label,
        dismissible=definition["dismissible"],
    )


def _build_management_reporting_insights_card(user_id: str, csrf_token: str, definition: dict) -> str:
    from app.db.historical_aggregate_reports import list_published_historical_aggregate_reports_for_reporting_insights

    reports = list_published_historical_aggregate_reports_for_reporting_insights()

    total_reports = len(reports)
    product_types = sorted({
        str(report.get("product_type_display") or "-")
        for report in reports
    })
    business_groups = sorted({
        str(report.get("business_group") or "-")
        for report in reports
    })

    if total_reports:
        status = _count_label(total_reports, "published report")
    else:
        status = "No reports yet"

    def _reporting_kpi_value(value: object) -> float | None:
        if value in (None, "", "null"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _reporting_metric_display(value: object, *, decimals: int = 1, suffix: str = "") -> str:
        numeric_value = _reporting_kpi_value(value)
        if numeric_value is None:
            return "—"

        text = f"{numeric_value:.{decimals}f}"
        if text.endswith(".0"):
            text = text[:-2]
        return f"{text}{suffix}"

    def _reporting_is_tier_one(report: dict) -> bool:
        product_type = str(report.get("product_type_display") or "").strip().lower()
        return any(token in product_type for token in ("combo", "keyboard", "mouse"))

    def _reporting_target(report: dict, key: str) -> float:
        if key == "ready_for_sales":
            return 95.0
        if key == "software_rating":
            return 4.2
        if key == "nps":
            return 50.0 if _reporting_is_tier_one(report) else 45.0
        if key == "star_rating":
            return 4.4 if _reporting_is_tier_one(report) else 4.2
        return 0.0

    def _reporting_kpi_class(report: dict, key: str, value: object) -> str:
        numeric_value = _reporting_kpi_value(value)
        if numeric_value is None:
            return "is-muted"

        if key == "ready_for_sales":
            if numeric_value >= 95.0:
                return "is-positive"
            if numeric_value >= 80.0:
                return "is-warning"
            return "is-negative"

        target = _reporting_target(report, key)
        if numeric_value >= target:
            return "is-positive"

        near_target = target * 0.9 if target else target
        if numeric_value >= near_target:
            return "is-warning"

        return "is-negative"

    def _reporting_report_status(report: dict) -> tuple[str, str]:
        classes = []
        for key in ("star_rating", "nps", "ready_for_sales", "software_rating"):
            if _reporting_kpi_value(report.get(key)) is not None:
                classes.append(_reporting_kpi_class(report, key, report.get(key)))

        if not classes:
            return "KPI pending", "is-muted"
        if "is-negative" in classes:
            return "Watch", "is-negative"
        if "is-warning" in classes:
            return "Review", "is-warning"
        return "On target", "is-positive"

    def _reporting_kpi_chip(report: dict, key: str, label: str, *, decimals: int = 1, suffix: str = "") -> str:
        value = report.get(key)
        if _reporting_kpi_value(value) is None:
            return ""

        status_class = _reporting_kpi_class(report, key, value)
        return f"""
            <span class="dashboard-reporting-kpi-chip {e(status_class)}">
                <span class="dashboard-reporting-kpi-dot"></span>
                <span class="dashboard-reporting-kpi-label">{e(label)}</span>
                <strong>{e(_reporting_metric_display(value, decimals=decimals, suffix=suffix))}</strong>
            </span>
        """

    latest_reports_html = ""
    for report in reports[:4]:
        title = (
            report.get("internal_name")
            or report.get("market_name")
            or "Untitled report"
        )
        round_number = report.get("round_number")
        product_type = report.get("product_type_display") or "Product type —"
        published_at = _format_date(report.get("published_at") or report.get("updated_at"))
        status_label, status_class = _reporting_report_status(report)

        kpi_chips = "".join([
            _reporting_kpi_chip(report, "star_rating", "★", decimals=2),
            _reporting_kpi_chip(report, "nps", "NPS", decimals=0),
            _reporting_kpi_chip(report, "ready_for_sales", "RFS", decimals=1, suffix="%"),
            _reporting_kpi_chip(report, "software_rating", "SW", decimals=2),
        ])
        if not kpi_chips:
            kpi_chips = """
                <span class="dashboard-reporting-kpi-chip is-muted">
                    <span class="dashboard-reporting-kpi-dot"></span>
                    <span class="dashboard-reporting-kpi-label">KPI</span>
                    <strong>Pending</strong>
                </span>
            """

        latest_reports_html += f"""
            <div class="dashboard-reporting-row">
                <div class="dashboard-reporting-row-top">
                    <div class="dashboard-reporting-row-main">
                        <span class="dashboard-reporting-title">{e(title)}</span>
                        <span class="dashboard-reporting-meta">
                            {e(product_type)} · Round {e(str(round_number or '—'))} · Published {e(published_at)}
                        </span>
                    </div>
                    <span class="dashboard-reporting-status {e(status_class)}">{e(status_label)}</span>
                </div>
                <div class="dashboard-reporting-kpis">
                    {kpi_chips}
                </div>
            </div>
        """

    if latest_reports_html:
        body_html = f"""
            <div class="dashboard-reporting-insights">
                <div class="dashboard-reporting-hero">
                    <span class="dashboard-reporting-hero-number">{e(str(total_reports))}</span>
                    <span class="dashboard-reporting-hero-label">Published reports</span>
                    <span class="dashboard-reporting-hero-meta">
                        {e(str(len(product_types)))} product types · {e(str(len(business_groups)))} business groups
                    </span>
                </div>

                <div class="dashboard-reporting-section-label">Latest published</div>
                <div class="dashboard-reporting-list">
                    {latest_reports_html}
                </div>
            </div>
        """
    else:
        body_html = """
            <div class="dashboard-reporting-empty">
                <span class="dashboard-reporting-hero-number">0</span>
                <span class="dashboard-reporting-hero-label">No published reports yet</span>
                <p class="dashboard-card-note">Reports published to Reporting & Insights will appear here.</p>
            </div>
        """

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Management",
        status=status,
        body_html=body_html,
        csrf_token=csrf_token,
        action_href="/reporting/insights",
        action_label="Open Reporting & Insights",
        dismissible=definition["dismissible"],
    )

def _get_ut_lead_dashboard_summary(user_id: str) -> dict:
    from app.db.user_trial_lead import get_ut_lead_dashboard_summary

    return get_ut_lead_dashboard_summary(user_id)


def _ut_lead_round_title(row: dict) -> str:
    return (
        row.get("ProjectName")
        or row.get("MarketName")
        or row.get("RoundName")
        or "Untitled trial"
    )


def _ut_lead_round_meta(row: dict, *, include_owner: bool = False) -> str:
    meta_parts = [
        row.get("dashboard_status_label") or "Current",
        row.get("dashboard_progress") or "Progress not available",
        f"Action: {row.get('dashboard_current_action') or 'No immediate action.'}",
    ]

    if include_owner:
        meta_parts.append(f"Lead: {row.get('UTLeadName') or 'Unassigned'}")

    return " · ".join(str(part) for part in meta_parts if part)


def _build_ut_lead_trial_list_card(
    *,
    user_id: str,
    csrf_token: str,
    definition: dict,
    summary_key: str,
    empty_text: str,
    action_href: str,
    action_label: str,
    include_owner: bool = False,
) -> str:
    summary = _get_ut_lead_dashboard_summary(user_id)
    rows = summary.get(summary_key) or []
    counts = summary.get("counts", {})

    count = int(counts.get(summary_key) or len(rows))
    status = _count_label(count, "trial") if count else "None"

    items = [
        (
            _ut_lead_round_title(row),
            _ut_lead_round_meta(row, include_owner=include_owner),
        )
        for row in rows[:4]
    ]

    body_html = _render_mini_list(items, empty_text)

    if count > len(items):
        remaining_count = count - len(items)
        body_html += f"""
            <p class="dashboard-card-note">
                + {e(str(remaining_count))} more trial{'' if remaining_count == 1 else 's'}.
            </p>
        """

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="UT Lead",
        status=status,
        body_html=body_html,
        csrf_token=csrf_token,
        action_href=action_href,
        action_label=action_label,
        dismissible=definition["dismissible"],
    )


def _build_ut_lead_my_current_trials_card(user_id: str, csrf_token: str, definition: dict) -> str:
    summary = _get_ut_lead_dashboard_summary(user_id)
    rows = summary.get("my_current") or []
    counts = summary.get("counts", {})

    count = int(counts.get("my_current") or len(rows))
    status = _count_label(count, "trial") if count else "None"

    def _sum_dashboard_int(field_name: str) -> int:
        total = 0
        for row in rows:
            try:
                total += int(row.get(field_name) or 0)
            except (TypeError, ValueError):
                continue
        return total

    participant_count = _sum_dashboard_int("ParticipantCount")
    shipped_count = _sum_dashboard_int("ShippedCount")
    active_survey_count = _sum_dashboard_int("ActiveSurveyCount")
    activated_survey_count = _sum_dashboard_int("ActivatedSurveyCount")

    shipped_percent = 0
    if participant_count:
        shipped_percent = int(round((shipped_count / participant_count) * 100))

    survey_percent = 0
    if active_survey_count:
        survey_percent = int(round((activated_survey_count / active_survey_count) * 100))

    shipped_percent = max(0, min(100, shipped_percent))
    survey_percent = max(0, min(100, survey_percent))

    if not rows:
        body_html = '''
            <div class="dashboard-ut-current-empty">
                <span class="dashboard-ut-current-empty-number">0</span>
                <span class="dashboard-ut-current-empty-label">No current assigned trials</span>
                <p class="dashboard-card-note">Planning and upcoming work will still appear in their own cards.</p>
            </div>
        '''
    else:
        focus_row = rows[0]
        focus_title = _ut_lead_round_title(focus_row)
        focus_action = focus_row.get("dashboard_current_action") or "No immediate action."

        trial_rows_html = ""
        for row in rows[:3]:
            trial_rows_html += f'''
                <div class="dashboard-ut-current-row">
                    <div class="dashboard-ut-current-row-main">
                        <span class="dashboard-ut-current-row-title">{e(_ut_lead_round_title(row))}</span>
                        <span class="dashboard-ut-current-row-meta">{e(row.get("dashboard_progress") or "Progress not available")}</span>
                    </div>
                    <span class="dashboard-ut-current-row-status">{e(row.get("dashboard_status_label") or "Current")}</span>
                </div>
            '''

        remaining_html = ""
        if count > 3:
            remaining_count = count - 3
            remaining_html = f'''
                <p class="dashboard-card-note dashboard-ut-current-more">
                    + {e(str(remaining_count))} more current trial{'' if remaining_count == 1 else 's'}.
                </p>
            '''

        body_html = f'''
            <div class="dashboard-ut-current">
                <div class="dashboard-ut-current-hero">
                    <span class="dashboard-ut-current-hero-number">{e(str(count))}</span>
                    <span class="dashboard-ut-current-hero-label">Current assigned trial{'' if count == 1 else 's'}</span>
                </div>

                <div class="dashboard-ut-current-metrics">
                    <div class="dashboard-ut-current-metric">
                        <span class="dashboard-ut-current-metric-number">{e(str(participant_count))}</span>
                        <span class="dashboard-ut-current-metric-label">Selected users</span>
                    </div>
                    <div class="dashboard-ut-current-metric">
                        <span class="dashboard-ut-current-metric-number">{e(str(shipped_count))}</span>
                        <span class="dashboard-ut-current-metric-label">Shipped</span>
                    </div>
                    <div class="dashboard-ut-current-metric">
                        <span class="dashboard-ut-current-metric-number">{e(str(activated_survey_count))}</span>
                        <span class="dashboard-ut-current-metric-label">Surveys active</span>
                    </div>
                </div>

                <div class="dashboard-ut-current-progress-group">
                    <div class="dashboard-ut-current-progress-header">
                        <span>Shipping coverage</span>
                        <strong>{e(str(shipped_percent))}%</strong>
                    </div>
                    <div class="dashboard-progress-row dashboard-ut-current-progress-row">
                        <div class="dashboard-progress-track">
                            <div class="dashboard-progress-fill" style="width: {shipped_percent}%;"></div>
                        </div>
                    </div>

                    <div class="dashboard-ut-current-progress-header">
                        <span>Survey activation</span>
                        <strong>{e(str(survey_percent))}%</strong>
                    </div>
                    <div class="dashboard-progress-row dashboard-ut-current-progress-row dashboard-ut-current-progress-row-purple">
                        <div class="dashboard-progress-track">
                            <div class="dashboard-progress-fill" style="width: {survey_percent}%;"></div>
                        </div>
                    </div>
                </div>

                <div class="dashboard-ut-current-action">
                    <span class="dashboard-ut-current-action-label">Next action</span>
                    <strong>{e(focus_title)}</strong>
                    <p>{e(focus_action)}</p>
                </div>

                <div class="dashboard-ut-current-list">
                    {trial_rows_html}
                </div>
                {remaining_html}
            </div>
        '''

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="UT Lead",
        status=status,
        body_html=body_html,
        csrf_token=csrf_token,
        action_href="/ut-lead/trials?ut_lead=me",
        action_label="Open my trials",
        dismissible=definition["dismissible"],
    )


def _build_ut_lead_my_planning_queue_card(user_id: str, csrf_token: str, definition: dict) -> str:
    return _build_ut_lead_trial_list_card(
        user_id=user_id,
        csrf_token=csrf_token,
        definition=definition,
        summary_key="my_planning",
        empty_text="You have no assigned trials under planning.",
        action_href="/ut-lead/trials?ut_lead=me",
        action_label="Open my trials",
    )


def _build_ut_lead_my_upcoming_trials_card(user_id: str, csrf_token: str, definition: dict) -> str:
    return _build_ut_lead_trial_list_card(
        user_id=user_id,
        csrf_token=csrf_token,
        definition=definition,
        summary_key="my_upcoming",
        empty_text="You have no assigned upcoming trials outside the planning window.",
        action_href="/ut-lead/trials?ut_lead=me",
        action_label="Open my trials",
    )


def _build_ut_lead_team_current_trials_card(user_id: str, csrf_token: str, definition: dict) -> str:
    return _build_ut_lead_trial_list_card(
        user_id=user_id,
        csrf_token=csrf_token,
        definition=definition,
        summary_key="team_current",
        empty_text="The UT team has no current trials.",
        action_href="/ut-lead/trials?ut_lead=all",
        action_label="Open team trials",
        include_owner=True,
    )


def _build_ut_lead_team_planning_queue_card(user_id: str, csrf_token: str, definition: dict) -> str:
    return _build_ut_lead_trial_list_card(
        user_id=user_id,
        csrf_token=csrf_token,
        definition=definition,
        summary_key="team_planning",
        empty_text="The UT team has no trials under planning.",
        action_href="/ut-lead/trials?ut_lead=all",
        action_label="Open team trials",
        include_owner=True,
    )


def _build_ut_lead_assigned_bsc_surveys_card(user_id: str, csrf_token: str, definition: dict) -> str:
    summary = _get_ut_lead_dashboard_summary(user_id)
    rows = summary.get("assigned_bsc_surveys") or []
    counts = summary.get("counts", {})

    count = int(counts.get("assigned_bsc_surveys") or len(rows))
    status = _count_label(count, "survey") if count else "None"

    items = []
    for row in rows[:4]:
        title = row.get("survey_title") or "Untitled Bonus Survey"
        meta = " · ".join([
            row.get("dashboard_status_label") or "Assigned",
            row.get("dashboard_progress") or "Progress not available",
            f"Action: {row.get('dashboard_current_action') or 'No immediate action.'}",
        ])
        items.append((title, meta))

    body_html = _render_mini_list(
        items,
        "You have no assigned BSC surveys.",
    )

    if count > len(items):
        remaining_count = count - len(items)
        body_html += f"""
            <p class="dashboard-card-note">
                + {e(str(remaining_count))} more assigned survey{'' if remaining_count == 1 else 's'}.
            </p>
        """

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="UT Lead",
        status=status,
        body_html=body_html,
        csrf_token=csrf_token,
        action_href="/surveys/bonus",
        action_label="Open Bonus Surveys",
        dismissible=definition["dismissible"],
    )


def _get_admin_dashboard_stats() -> dict:
    from app.db.dashboard_admin_stats import get_admin_dashboard_stats

    return get_admin_dashboard_stats()


def _format_admin_percent(value: int | float | None) -> str:
    try:
        return f"{int(round(float(value or 0)))}%"
    except (TypeError, ValueError):
        return "0%"


def _admin_window_label(summary: dict) -> str:
    return f"last {int(summary.get('window_days') or 30)} days"


def _build_admin_site_overview_card(user_id: str, csrf_token: str, definition: dict) -> str:
    summary = _get_admin_dashboard_stats()
    data = summary.get("site_overview", {})
    window_label = _admin_window_label(summary)

    registered_count = int(data.get("registered_users") or 0)
    logged_in_count = int(data.get("logged_in_window") or 0)
    trials_started_count = int(data.get("trials_started_window") or 0)
    reports_count = int(data.get("reports_window") or 0)

    try:
        logged_in_percent = int(round(float(data.get("logged_in_window_percent") or 0)))
    except (TypeError, ValueError):
        logged_in_percent = 0

    logged_in_percent = max(0, min(100, logged_in_percent))

    if registered_count:
        engagement_note = f"{logged_in_count} of {registered_count} users logged in."
    else:
        engagement_note = "No real users are registered yet."

    body_html = f"""
        <div class="dashboard-site-overview">
            <div class="dashboard-site-hero">
                <span class="dashboard-site-hero-number">{e(str(registered_count))}</span>
                <span class="dashboard-site-hero-label">Real registered users</span>
            </div>

            <div class="dashboard-site-engagement">
                <div class="dashboard-site-section-header">
                    <span>30-day activity</span>
                    <strong>{e(str(logged_in_percent))}% logged in</strong>
                </div>
                <div class="dashboard-progress-row dashboard-site-progress-row">
                    <div class="dashboard-progress-track">
                        <div class="dashboard-progress-fill" style="width: {logged_in_percent}%;"></div>
                    </div>
                </div>
                <p class="dashboard-card-note dashboard-site-engagement-note">{e(engagement_note)}</p>
            </div>

            <div class="dashboard-site-activity-tiles">
                <div class="dashboard-site-activity-tile">
                    <span class="dashboard-site-tile-number">{e(str(trials_started_count))}</span>
                    <span class="dashboard-site-tile-label">Trials started</span>
                    <span class="dashboard-site-tile-meta">{e(window_label)}</span>
                </div>
                <div class="dashboard-site-activity-tile">
                    <span class="dashboard-site-tile-number">{e(str(reports_count))}</span>
                    <span class="dashboard-site-tile-label">Reports generated</span>
                    <span class="dashboard-site-tile-meta">{e(window_label)}</span>
                </div>
            </div>
        </div>
    """

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Admin",
        status=_count_label(registered_count, "user"),
        body_html=body_html,
        csrf_token=csrf_token,
        action_href="/admin/users",
        action_label="Open users",
        dismissible=definition["dismissible"],
    )


def _build_admin_user_pool_stats_card(user_id: str, csrf_token: str, definition: dict) -> str:
    summary = _get_admin_dashboard_stats()
    data = summary.get("user_pool", {})
    window_label = _admin_window_label(summary)

    registered_count = int(data.get("registered_users") or 0)
    profile_complete_count = int(data.get("profile_complete_users") or 0)
    elevated_count = int(data.get("elevated_users") or 0)

    items = [
        ("Profile complete", f"{profile_complete_count} users · {_format_admin_percent(data.get('profile_complete_percent'))}"),
        (f"New users, {window_label}", f"{int(data.get('new_users_window') or 0)} users"),
        (f"Logged in, {window_label}", f"{int(data.get('logged_in_window') or 0)} users · {_format_admin_percent(data.get('logged_in_window_percent'))}"),
        ("Countries represented", f"{int(data.get('countries_represented') or 0)} countries"),
        ("Elevated access", f"{elevated_count} users at level 30+"),
    ]

    if registered_count and profile_complete_count < registered_count:
        status = f"{_format_admin_percent(data.get('profile_complete_percent'))} complete"
    else:
        status = "Complete"

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Admin",
        status=status,
        body_html=_render_mini_list(items, "No user pool stats are available yet."),
        csrf_token=csrf_token,
        action_href="/admin/users",
        action_label="Review users",
        dismissible=definition["dismissible"],
    )


def _build_admin_trial_stats_card(user_id: str, csrf_token: str, definition: dict) -> str:
    summary = _get_admin_dashboard_stats()
    data = summary.get("trial_stats", {})
    window_label = _admin_window_label(summary)

    current_count = int(data.get("current_trials") or 0)
    planning_count = int(data.get("planning_trials") or 0)

    items = [
        ("Current trials", f"{current_count} active/recruiting/screening/running rounds"),
        ("Planning queue", f"{planning_count} pending/info/changes rounds"),
        ("Upcoming trials", f"{int(data.get('upcoming_trials') or 0)} future-start rounds"),
        (f"Completed, {window_label}", f"{int(data.get('completed_trials_window') or 0)} rounds"),
        ("Selected participants", f"{int(data.get('selected_participants') or 0)} participant assignments"),
    ]

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Admin",
        status=_count_label(current_count, "current trial"),
        body_html=_render_mini_list(items, "No trial stats are available yet."),
        csrf_token=csrf_token,
        action_href="/ut-lead/trials?ut_lead=all",
        action_label="Open all trials",
        dismissible=definition["dismissible"],
    )


def _build_admin_ut_lead_stats_card(user_id: str, csrf_token: str, definition: dict) -> str:
    summary = _get_admin_dashboard_stats()
    data = summary.get("ut_lead_stats", {})

    assigned_count = int(data.get("assigned_trials") or 0)
    unassigned_count = int(data.get("unassigned_planning_trials") or 0)
    active_lead_count = int(data.get("active_ut_leads") or 0)

    items = [
        ("Assigned non-terminal trials", f"{assigned_count} rounds"),
        ("Unassigned planning work", f"{unassigned_count} rounds"),
        ("Active UT Leads", f"{active_lead_count} leads with assigned work"),
    ]

    for row in (data.get("top_ut_leads") or [])[:3]:
        lead_name = row.get("UTLeadName") or row.get("UTLead_UserID") or "Unknown lead"
        items.append((lead_name, f"{int(row.get('active_trials') or 0)} assigned active/planning rounds"))

    status = _count_label(unassigned_count, "unassigned") if unassigned_count else "Assigned"

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Admin",
        status=status,
        body_html=_render_mini_list(items, "No UT Lead stats are available yet."),
        csrf_token=csrf_token,
        action_href="/ut-lead/trials?ut_lead=all",
        action_label="Review UT workload",
        dismissible=definition["dismissible"],
    )


def _build_admin_bg_product_stats_card(user_id: str, csrf_token: str, definition: dict) -> str:
    summary = _get_admin_dashboard_stats()
    data = summary.get("bg_product_stats", {})

    bg_count = int(data.get("active_business_groups") or 0)
    product_type_count = int(data.get("active_product_types") or 0)

    items = [
        ("Business Groups represented", f"{bg_count} groups"),
        ("Product types represented", f"{product_type_count} product types"),
    ]

    for row in (data.get("top_business_groups") or [])[:3]:
        label = row.get("label") or "Unknown BG"
        items.append((f"BG: {label}", f"{int(row.get('total') or 0)} trial rounds"))

    for row in (data.get("top_product_types") or [])[:2]:
        label = row.get("label") or "Unknown product type"
        items.append((f"Product: {label}", f"{int(row.get('total') or 0)} trial rounds"))

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Admin",
        status=_count_label(bg_count, "BG"),
        body_html=_render_mini_list(items[:5], "No BG/product stats are available yet."),
        csrf_token=csrf_token,
        action_href="/reporting/insights",
        action_label="Open Reporting & Insights",
        dismissible=definition["dismissible"],
    )


def _build_admin_reporting_stats_card(user_id: str, csrf_token: str, definition: dict) -> str:
    summary = _get_admin_dashboard_stats()
    data = summary.get("reporting_stats", {})
    window_label = _admin_window_label(summary)

    reports_window = int(data.get("reports_window") or 0)
    missing_count = int(data.get("completed_rounds_without_report") or 0)

    items = [
        (f"Generated/published, {window_label}", f"{reports_window} reports"),
        ("Published historical reports", f"{int(data.get('historical_published_total') or 0)} total · {int(data.get('historical_published_window') or 0)} in {window_label}"),
        ("Product Trial reports", f"{int(data.get('product_trial_reports_total') or 0)} total · {int(data.get('product_trial_reports_window') or 0)} in {window_label}"),
        ("BSC reports", f"{int(data.get('bonus_survey_reports_total') or 0)} total · {int(data.get('bonus_survey_reports_window') or 0)} in {window_label}"),
        ("Completed trials missing report", f"{missing_count} rounds"),
    ]

    status = _count_label(missing_count, "missing") if missing_count else _count_label(reports_window, "recent report")

    return _render_dashboard_card(
        key=definition["key"],
        title=definition["title"],
        eyebrow="Admin",
        status=status,
        body_html=_render_mini_list(items, "No reporting stats are available yet."),
        csrf_token=csrf_token,
        action_href="/reporting/insights",
        action_label="Open reports",
        dismissible=definition["dismissible"],
    )


def _build_legal_document_review_card(user_id: str, csrf_token: str, definition: dict) -> str:
    from app.db.legal_documents import get_legal_review_dashboard_summary

    summary = get_legal_review_dashboard_summary()
    counts = summary.get("counts", {})
    attention_rows = summary.get("attention_rows", [])

    overdue_count = int(counts.get("overdue") or 0)
    due_soon_count = int(counts.get("due_soon") or 0)
    never_reviewed_count = int(counts.get("never_reviewed") or 0)
    active_count = int(counts.get("active") or 0)

    if overdue_count:
        status = _count_label(overdue_count, "overdue")
        callout_label = "Needs action"
        callout_text = f"{_count_label(overdue_count, 'legal document')} overdue for annual review."
        callout_class = "is-overdue"
    elif due_soon_count:
        status = _count_label(due_soon_count, "due soon")
        callout_label = "Due soon"
        callout_text = f"{_count_label(due_soon_count, 'legal document')} coming due for review."
        callout_class = "is-due-soon"
    elif never_reviewed_count:
        status = _count_label(never_reviewed_count, "never reviewed")
        callout_label = "Needs first review"
        callout_text = f"{_count_label(never_reviewed_count, 'legal document')} never reviewed."
        callout_class = "is-never-reviewed"
    else:
        status = "Current"
        callout_label = "Current"
        callout_text = "All active legal documents are current for annual review."
        callout_class = "is-current"

    def _legal_review_row(row: dict) -> str:
        label = row.get("title") or "Untitled legal document"
        due_at = _format_date(row.get("review_due_at"))

        if row.get("is_overdue"):
            row_label = "Overdue"
            row_meta = f"Annual review due {due_at}"
            row_class = "is-overdue"
        elif row.get("is_never_reviewed"):
            row_label = "Never reviewed"
            row_meta = f"First annual review due {due_at}"
            row_class = "is-never-reviewed"
        else:
            row_label = "Due soon"
            row_meta = f"Annual review due {due_at}"
            row_class = "is-due-soon"

        return f"""
            <div class="dashboard-legal-review-row {e(row_class)}">
                <div class="dashboard-legal-review-row-main">
                    <span class="dashboard-legal-review-title">{e(label)}</span>
                    <span class="dashboard-legal-review-meta">{e(row_meta)}</span>
                </div>
                <span class="dashboard-legal-review-status">{e(row_label)}</span>
            </div>
        """

    attention_html = "".join(_legal_review_row(row) for row in attention_rows[:4])
    if not attention_html:
        attention_html = """
            <p class="dashboard-card-empty dashboard-legal-review-empty">
                No overdue, due-soon, or never-reviewed documents.
            </p>
        """

    remaining_count = max(0, len(attention_rows) - 4)
    remaining_html = ""
    if remaining_count:
        remaining_html = f"""
            <p class="dashboard-card-note dashboard-legal-review-more">
                + {e(str(remaining_count))} more document{'' if remaining_count == 1 else 's'} needing review.
            </p>
        """

    body_html = f"""
        <div class="dashboard-legal-review">
            <div class="dashboard-legal-review-callout {e(callout_class)}">
                <span class="dashboard-legal-review-callout-label">{e(callout_label)}</span>
                <strong>{e(callout_text)}</strong>
            </div>

            <div class="dashboard-legal-review-list">
                {attention_html}
            </div>
            {remaining_html}

            <p class="dashboard-card-note dashboard-legal-review-summary">
                {e(str(active_count))} active documents ·
                {e(str(overdue_count))} overdue ·
                {e(str(due_soon_count))} due soon ·
                {e(str(never_reviewed_count))} never reviewed
            </p>
        </div>
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

    if builder == "bsc_bonus_survey_workflow":
        return _build_bsc_bonus_survey_workflow_card(user_id, csrf_token, definition)

    if builder == "product_team_trial_requests":
        return _build_product_team_trial_requests_card(user_id, csrf_token, definition)

    if builder == "management_reporting_insights":
        return _build_management_reporting_insights_card(user_id, csrf_token, definition)

    if builder == "ut_lead_my_current_trials":
        return _build_ut_lead_my_current_trials_card(user_id, csrf_token, definition)

    if builder == "ut_lead_my_planning_queue":
        return _build_ut_lead_my_planning_queue_card(user_id, csrf_token, definition)

    if builder == "ut_lead_my_upcoming_trials":
        return _build_ut_lead_my_upcoming_trials_card(user_id, csrf_token, definition)

    if builder == "ut_lead_team_current_trials":
        return _build_ut_lead_team_current_trials_card(user_id, csrf_token, definition)

    if builder == "ut_lead_team_planning_queue":
        return _build_ut_lead_team_planning_queue_card(user_id, csrf_token, definition)

    if builder == "ut_lead_assigned_bsc_surveys":
        return _build_ut_lead_assigned_bsc_surveys_card(user_id, csrf_token, definition)

    if builder == "admin_site_overview":
        return _build_admin_site_overview_card(user_id, csrf_token, definition)

    if builder == "admin_user_pool_stats":
        return _build_admin_user_pool_stats_card(user_id, csrf_token, definition)

    if builder == "admin_trial_stats":
        return _build_admin_trial_stats_card(user_id, csrf_token, definition)

    if builder == "admin_ut_lead_stats":
        return _build_admin_ut_lead_stats_card(user_id, csrf_token, definition)

    if builder == "admin_bg_product_stats":
        return _build_admin_bg_product_stats_card(user_id, csrf_token, definition)

    if builder == "admin_reporting_stats":
        return _build_admin_reporting_stats_card(user_id, csrf_token, definition)

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


def _dashboard_card_policy_label(*, definition: dict, user_id: str) -> str:
    if _is_card_force_visible(definition=definition, user_id=user_id):
        return "Action needed"

    if definition.get("dismissible"):
        return "Optional"

    return "Required"


def _render_visible_dashboard_card_row(
    *,
    definition: dict,
    csrf_token: str,
    user_id: str,
    can_move_up: bool,
    can_move_down: bool,
) -> str:
    safe_key = e(definition["key"])
    safe_csrf_token = e(csrf_token)
    safe_policy_label = e(_dashboard_card_policy_label(definition=definition, user_id=user_id))

    up_disabled = "" if can_move_up else " disabled"
    down_disabled = "" if can_move_down else " disabled"

    return f"""
    <article class="dashboard-picker-card dashboard-picker-card-visible">
        <div class="dashboard-picker-card-copy">
            <div class="dashboard-picker-card-title-row">
                <h2>{e(definition["title"])}</h2>
                <span class="dashboard-picker-badge">{safe_policy_label}</span>
            </div>
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


def _render_visible_dashboard_card_rows(
    *,
    visible_definitions: list[dict],
    csrf_token: str,
    user_id: str,
) -> str:
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
                user_id=user_id,
                can_move_up=index > 0,
                can_move_down=index < last_index,
            )
        )

    return "".join(rows)


def _render_hidden_dashboard_card(*, definition: dict, csrf_token: str) -> str:
    return f"""
    <article class="dashboard-picker-card dashboard-picker-card-hidden">
        <div class="dashboard-picker-card-copy">
            <div class="dashboard-picker-card-title-row">
                <h2>{e(definition["title"])}</h2>
                <span class="dashboard-picker-badge muted">Hidden</span>
            </div>
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
        user_id=user_id,
    )
    hidden_definitions = _get_hidden_card_definitions(
        available_definitions=available_definitions,
        preferences=preferences,
        user_id=user_id,
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
        user_id=user_id,
    )
    hidden_definitions = _get_hidden_card_definitions(
        available_definitions=available_definitions,
        preferences=preferences,
        user_id=user_id,
    )

    visible_rows = _render_visible_dashboard_card_rows(
        visible_definitions=visible_definitions,
        csrf_token=csrf_token,
        user_id=user_id,
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
        user_id=user_id,
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