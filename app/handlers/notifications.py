# app/handlers/notifications.py

import re
from html import unescape
from pathlib import Path

from app.handlers.product_request_notifications import (
    render_product_trial_approved,
    render_product_trial_assigned,
    render_product_trial_change_accepted,
    render_product_trial_change_countered,
    render_product_trial_change_requested,
    render_product_trial_declined,
    render_product_trial_info_provided,
    render_product_trial_info_requested,
    render_product_trial_pending_approval,
    render_product_trial_withdrawn_by_requestor,
    render_trial_recruiting_started,
)
from app.handlers.surveys_notifications import (
    render_approve_bonus_survey,
    render_bonus_survey_approved,
)
from app.services.notifications import (
    get_all_notifications,
    get_notification_detail,
    get_unread_count,
)
from app.utils.html_escape import escape_html as e

RENDERERS = {
    "bonus_survey_pending_approval": render_approve_bonus_survey,
    "bonus_survey_approved": render_bonus_survey_approved,

    "product_trial_pending_approval": render_product_trial_pending_approval,
    "product_trial_approved": render_product_trial_approved,
    "product_trial_assigned": render_product_trial_assigned,
    "product_trial_declined": render_product_trial_declined,
    "product_trial_info_requested": render_product_trial_info_requested,
    "product_trial_info_provided": render_product_trial_info_provided,
    "product_trial_change_requested": render_product_trial_change_requested,
    "product_trial_change_accepted": render_product_trial_change_accepted,
    "product_trial_change_countered": render_product_trial_change_countered,
    "product_trial_withdrawn_by_requestor": render_product_trial_withdrawn_by_requestor,

    "trial_recruiting_started": render_trial_recruiting_started,
}


NOTIFICATIONS_TEMPLATE = Path("app/templates/notifications.html")


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def _plain_text_notification_value(raw_value) -> str:
    """
    Notification title/message/label copy must be plain text.

    This prevents accidental HTML such as <strong>...</strong> from rendering
    as raw visible tags in the notification UI.
    """
    if raw_value is None:
        return ""

    text = unescape(str(raw_value))
    text = re.sub(r"<[^>]*>", "", text)
    text = " ".join(text.split())

    return text


def _normalize_rendered_notification(
    rendered: dict | None,
    *,
    fallback_title: str | None = None,
) -> dict:
    """
    Normalizes renderer output before any notification UI uses it.

    This keeps notification copy presentation-safe in:
    - the bell dropdown
    - the notifications page
    - the notification detail page
    """
    if not isinstance(rendered, dict):
        rendered = {}

    title = _plain_text_notification_value(
        rendered.get("title") or fallback_title or "Notification"
    ) or "Notification"

    message = _plain_text_notification_value(
        rendered.get("message") or ""
    )

    raw_actions = rendered.get("actions") or []
    actions = []

    if isinstance(raw_actions, list):
        for action in raw_actions:
            if not isinstance(action, dict):
                continue

            clean_action = dict(action)
            clean_action["label"] = (
                _plain_text_notification_value(action.get("label")) or "Open"
            )
            actions.append(clean_action)

    return {
        "title": title,
        "message": message,
        "actions": actions,
    }


def _safe_internal_href(raw_href: str | None) -> str:
    """
    Allow only internal absolute paths as notification targets.
    Reject external URLs and protocol-relative URLs.
    """
    if not isinstance(raw_href, str):
        return "#"
    if not raw_href.startswith("/"):
        return "#"
    if raw_href.startswith("//"):
        return "#"
    return raw_href


def _notification_is_new(notification: dict) -> bool:
    """
    A notification is actionable in notification UI only while it is unread
    and not dismissed. The approval page remains the source of truth for
    actual approval work.
    """
    return (
        not bool(notification.get("is_read"))
        and not bool(notification.get("is_dismissed"))
    )


def _render_action_forms(
    *,
    notification_id: str,
    actions: list[dict],
    compact: bool = False,
) -> str:
    """
    Notification actions mutate recipient state first, then redirect.
    This keeps GET routes render-only and makes notification visibility DB-derived.
    """
    actions_html = ""
    button_class = "notification-action-button" if compact else "notification-page-action"

    for action in actions:
        label = e(action.get("label") or "Open")
        raw_href = action.get("href") or "#"
        safe_href = _safe_internal_href(raw_href)

        if safe_href == "#":
            continue

        if safe_href.startswith("/notifications/"):
            actions_html += f"""
            <form method="POST" action="{e(safe_href)}" style="display:inline;">
                <input type="hidden" name="notification_id" value="{e(notification_id)}">
                <button type="submit" class="{button_class}">{label}</button>
            </form>
            """
        else:
            actions_html += f"""
            <form method="POST" action="/notifications/open" style="display:inline;">
                <input type="hidden" name="notification_id" value="{e(notification_id)}">
                <input type="hidden" name="target_url" value="{e(safe_href)}">
                <button type="submit" class="{button_class}">{label}</button>
            </form>
            """

    return actions_html


def _render_status_label(notification: dict) -> str:
    if notification.get("is_dismissed"):
        return "Dismissed"
    if notification.get("is_read"):
        return "Read"
    return "New"


# --------------------------------------------------
# NOTIFICATIONS PAGE RENDERER
# --------------------------------------------------

def render_notifications_page(user_id: str) -> str:
    """
    Returns the full notifications page HTML.

    GET is render-only. Opening this page does not mark notifications read,
    dismissed, or otherwise mutate notification state.
    """

    try:
        notifications = get_all_notifications(user_id, limit=50)
    except Exception as err:
        print("ERROR loading notifications:", err)
        notifications = []

    try:
        unread_count = get_unread_count(user_id)
    except Exception as err:
        print("ERROR loading unread count:", err)
        unread_count = 0

    html = NOTIFICATIONS_TEMPLATE.read_text(encoding="utf-8")

    if notifications:
        items = []

        for notification in notifications:
            notification_id = notification.get("notification_id") or ""

            cls = "notification-item"
            if not notification.get("is_read"):
                cls += " unread"
            if notification.get("is_dismissed"):
                cls += " dismissed"

            rendered = render_notification(
                {
                    "title": notification.get("title"),
                    "payload": notification.get("payload", {}),
                    "type_key": notification.get("type_key"),
                }
            )

            title = e(rendered.get("title") or notification.get("title") or "Notification")
            message = e(rendered.get("message") or "")
            status_label = e(_render_status_label(notification))
            actions_html = ""

            if _notification_is_new(notification):
                actions_html = _render_action_forms(
                    notification_id=notification_id,
                    actions=rendered.get("actions", []),
                )

            items.append(f"""
            <li class="{cls}">
                <div class="notification-card-main">
                    <div class="notification-card-header">
                        <div class="notification-title">{title}</div>
                        <div class="notification-status">{status_label}</div>
                    </div>
                    <div class="notification-message">{message}</div>
                    <div class="notification-actions">
                        {actions_html}
                    </div>
                </div>
            </li>
            """)

        notification_block = "\n".join(items)
    else:
        notification_block = "<p class='notification-empty'>You have no notifications.</p>"

    html = html.replace("__NOTIFICATION_ITEMS__", notification_block)
    html = html.replace("__UNREAD_COUNT__", str(unread_count))

    return html


def render_notification_view(user_id: str, notification_id: str) -> str:
    """
    Render one notification detail page.

    GET is render-only. Use POST /notifications/open to mark a notification
    dismissed and redirect to its target action.
    """
    notification = get_notification_detail(user_id, notification_id)

    if not notification:
        return """
        <div class="page-container notifications-page">
            <h1>Notification</h1>
            <p class="notification-empty">Notification not found.</p>
            <p><a class="notification-secondary-link" href="/notifications">Back to notifications</a></p>
        </div>
        """

    rendered = render_notification(
        {
            "title": notification.get("title"),
            "payload": notification.get("payload", {}),
            "type_key": notification.get("type_key"),
        }
    )

    title = e(rendered.get("title") or notification.get("title") or "Notification")
    message = e(rendered.get("message") or "")
    actions_html = ""

    if _notification_is_new(notification):
        actions_html = _render_action_forms(
            notification_id=notification.get("notification_id") or "",
            actions=rendered.get("actions", []),
        )

    return f"""
    <div class="page-container notifications-page">
        <h1>{title}</h1>
        <div class="notification-detail-card">
            <div class="notification-message">{message}</div>
            <div class="notification-actions">
                {actions_html}
                <a class="notification-secondary-link" href="/notifications">Back to notifications</a>
            </div>
        </div>
    </div>
    """


def render_notification(notification: dict) -> dict:
    type_key = notification.get("type_key")
    fallback_title = notification.get("title") or "Notification"

    if not type_key:
        return _normalize_rendered_notification(
            {
                "title": fallback_title,
                "message": "",
                "actions": [],
            },
            fallback_title=fallback_title,
        )

    renderer = RENDERERS.get(type_key)
    if not renderer:
        return _normalize_rendered_notification(
            {
                "title": fallback_title,
                "message": notification.get("description") or "",
                "actions": [],
            },
            fallback_title=fallback_title,
        )

    rendered = renderer(notification.get("payload", {}))

    return _normalize_rendered_notification(
        rendered,
        fallback_title=fallback_title,
    )