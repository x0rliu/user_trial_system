# app/handlers/notifications.py

from app.services.notifications import get_notification_by_id
from pathlib import Path
from app.services.notifications import (
    get_all_notifications,
    get_unread_count,
)
from app.handlers.surveys_notifications import render_approve_bonus_survey
from app.handlers.product_request_notifications import (
    render_product_trial_pending_approval,
    render_product_trial_declined,
    render_product_trial_info_requested,
    render_product_trial_change_requested,
)
RENDERERS = {
    "bonus_survey_pending_approval": render_approve_bonus_survey,
    "product_trial_pending_approval": render_product_trial_pending_approval,
    "product_trial_declined": render_product_trial_declined,
    "product_trial_info_requested": render_product_trial_info_requested,
    "product_trial_change_requested": render_product_trial_change_requested,
}



# --------------------------------------------------
# NOTIFICATIONS PAGE RENDERER
# --------------------------------------------------
# This file only defines renderers.
# main.py is responsible for routing.
# --------------------------------------------------


NOTIFICATIONS_TEMPLATE = Path("app/templates/notifications.html")

# Notification types that require an explicit approve/decline decision
# and must NOT be dismissible.
NON_DISMISSIBLE_TYPES = {
    "bonus_survey_pending_approval",
    "product_trial_pending_approval",
}


def render_notifications_page(user_id: str) -> str:
    """
    Returns the full notifications page HTML.
    Read-only. No state mutation.
    """

    notifications = get_all_notifications(user_id, limit=50)
    unread_count = get_unread_count(user_id)

    # --- load base template
    html = NOTIFICATIONS_TEMPLATE.read_text(encoding="utf-8")

    # --- build notification list HTML
    if notifications:
        items = []
        for n in notifications:
            items.append(f"""
            <li class="notification-item unread">
                <a href="/notifications/view?notification_id={n['notification_id']}">
                    {n['title']}
                </a>
            </li>
            """)
        notification_block = "\n".join(items)
    else:
        notification_block = (
            "<p class='notification-empty'>You have no notifications.</p>"
        )

    # --- inject content
    html = html.replace("__NOTIFICATION_ITEMS__", notification_block)
    html = html.replace("__UNREAD_COUNT__", str(unread_count))

    return html

def render_notification_detail_page(user_id: str, notification_id: str) -> str:
    """
    Detail view for a single notification.
    Read-only renderer (main.py handles mark_read / dismiss actions).
    """
    from app.services.notifications import get_notification_detail

    n = get_notification_detail(user_id, notification_id)
    if not n:
        return """
        <div class="page-container">
            <h1>Notification</h1>
            <p class="muted">Not found (or not addressed to you).</p>
            <p><a href="/notifications">Back to notifications</a></p>
        </div>
        """

    # Use your renderer mapping if present; otherwise show a safe fallback.
    rendered = render_notification({
        "title": n.get("title"),
        "payload": n.get("payload", {}),
        # We key off type_key (not "approval_intent") to avoid extra columns.
        "type_key": n.get("type_key"),
    })

    actions_html = ""
    actions = rendered.get("actions") or []
    if actions:
        buttons = []
        for a in actions:
            label = a.get("label", "Open")
            href = a.get("href", "#")
            style = a.get("style", "secondary")
            buttons.append(f'<a class="btn {style}" href="{href}">{label}</a>')
        actions_html = "<div class='notification-actions'>" + " ".join(buttons) + "</div>"

    message_html = rendered.get("message") or ""
    title = rendered.get("title") or (n.get("title") or "Notification")

    # Provide explicit dismiss
    # Dismiss is only allowed for non-approval notifications
    dismiss_html = ""

    if n.get("type_key") not in NON_DISMISSIBLE_TYPES:
        dismiss_link = f"/notifications/dismiss?notification_id={n['notification_id']}"
        dismiss_html = f'<a class="btn secondary" href="{dismiss_link}">Dismiss</a>'

    return f"""
    <div class="page-container notifications-page">
        <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
            <h1 style="margin:0;">{title}</h1>
            <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
                <h1 style="margin:0;">{title}</h1>
                {dismiss_html}
            </div>

        </div>

        <div class="notification-detail-meta muted" style="margin-top:8px;">
            <span>Type: {n.get("type_key") or "—"}</span>
            <span style="margin-left:12px;">Severity: {n.get("severity") or "—"}</span>
        </div>

        <div class="notification-detail-body" style="margin-top:16px;">
            {message_html}
        </div>

        {actions_html}

        <div style="margin-top:20px;">
            <a href="/notifications">← Back to notifications</a>
        </div>
    </div>
    """


def render_notification(notification: dict) -> dict:
    type_key = notification.get("type_key")

    if not type_key:
        return {
            "title": notification.get("title"),
            "message": "",
            "actions": [],
        }

    renderer = RENDERERS.get(type_key)
    if not renderer:
        return {
            "title": notification.get("title"),
            "message": notification.get("description") or "",
            "actions": [],
        }

    return renderer(notification.get("payload", {}))


def render_notification_view(user_id: str, notification_id: str) -> str:
    notification = get_notification_by_id(user_id, notification_id)

    if not notification:
        return "<p class='muted'>Notification not found.</p>"

    rendered = render_notification(notification)
    
    dismiss_html = ""
    if notification.get("type_key") not in NON_DISMISSIBLE_TYPES:
        dismiss_html = (
            f"<a href='/notifications/dismiss?notification_id={notification_id}'>"
            "Dismiss</a>"
        )

    actions_html = ""
    for action in rendered["actions"]:
        actions_html += (
            f"<a class='btn {action['style']}' "
            f"href='{action['href']}'>{action['label']}</a> "
        )

    return f"""
    <div class="notification-detail">
        <h1>{rendered['title']}</h1>

        <div class="notification-message">
            {rendered['message']}
        </div>

        <div class="notification-actions">
            {actions_html}
        </div>

        <div class="notification-footer">
            {dismiss_html}
        </div>
    </div>
    """
