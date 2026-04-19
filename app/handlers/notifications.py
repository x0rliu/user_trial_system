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
from app.utils.html_escape import escape_html as e

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
    Opening this page marks notifications as read.
    """

    # --------------------------------------------------
    # Load notifications
    # --------------------------------------------------
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

    # --------------------------------------------------
    # Load template
    # --------------------------------------------------
    html = NOTIFICATIONS_TEMPLATE.read_text(encoding="utf-8")

    # --------------------------------------------------
    # Build notification list HTML
    # --------------------------------------------------
    if notifications:

        items = []

        for n in notifications:

            cls = "notification-item"
            if not n.get("is_read"):
                cls += " unread"

            title = e(n.get("title") or "Notification")

            rendered = render_notification({
                "title": n.get("title"),
                "payload": n.get("payload", {}),
                "type_key": n.get("type_key"),
            })

            # IMPORTANT: treat rendered output as untrusted
            message = e(rendered.get("message", ""))
            actions = rendered.get("actions", [])

            actions_html = ""

            for a in actions:
                label = e(a.get("label", "Open"))
                raw_href = a.get("href", "#")
                style = e(a.get("style", "secondary"))

                # Only allow internal links
                safe_href = raw_href if isinstance(raw_href, str) and raw_href.startswith("/") else "#"

                if safe_href.startswith("/notifications/"):
                    # POST action
                    actions_html += f"""
                    <form method="POST" action="{safe_href}" style="display:inline;">
                        <input type="hidden" name="notification_id" value="{n.get('notification_id')}">
                        <button type="submit" class="btn {style}">{label}</button>
                    </form>
                    """
                else:
                    # normal navigation
                    actions_html += (
                        f"<a class='btn {style}' href='{safe_href}'>{label}</a>"
                    )

            items.append(f"""
            <li class="{cls}">
                <div class="notification-title">{title}</div>
                <div class="notification-message">{message}</div>
                <div class="notification-actions">
                    {actions_html}
                </div>
            </li>
            """)

        notification_block = "\n".join(items)

    else:
        notification_block = (
            "<p class='notification-empty'>You have no notifications.</p>"
        )

    # --------------------------------------------------
    # Inject content
    # --------------------------------------------------
    html = html.replace("__NOTIFICATION_ITEMS__", notification_block)
    html = html.replace("__UNREAD_COUNT__", str(unread_count))

    return html

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