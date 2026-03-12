# app/handlers/product_request_notifications.py

def render_product_trial_pending_approval(payload: dict) -> dict:
    project_name = payload.get("project_name", "Unnamed Project")
    product_category = payload.get("product_category", "—")
    start_date = payload.get("estimated_start_date", "—")

    return {
        "title": "Product Trial Approval Required",
        "message": (
            f"The product trial <strong>{project_name}</strong> "
            f"({product_category}) has been submitted and is awaiting UT approval."
            f"<br><span class='muted small'>Estimated start: {start_date}</span>"
        ),
        "actions": [
            {
                "label": "View Approvals",
                "href": "/admin/approvals",
                "style": "primary",
            }
        ],
    }

def render_product_trial_declined(payload: dict) -> dict:
    """
    Renderer for declined product trial notifications.
    """

    reason = payload.get("reason")

    message = (
        f"<p>Your product trial request was declined.</p>"
        + (f"<p><strong>Reason:</strong> {reason}</p>" if reason else "")
    )

    return {
        "title": "Product trial request declined",
        "message": message,
        "actions": [],
    }

def render_product_trial_info_requested(payload: dict) -> dict:
    """
    Renderer for product trial info requested notifications.
    UT has reviewed the request and requires clarification.
    """

    reason = payload.get("reason")

    message = (
        "<p>UT has reviewed your product trial request and needs more information.</p>"
        + (f"<p><strong>Details:</strong> {reason}</p>" if reason else "")
        + "<p>Please review your request and resubmit once clarified.</p>"
    )

    return {
        "title": "More information required for product trial",
        "message": message,
        "actions": [],
    }

def render_product_trial_change_requested(payload: dict) -> dict:
    """
    Renderer for product trial change requested notifications.
    UT has reviewed the request and requires changes before approval.
    """

    reason = payload.get("reason")

    message = (
        "<p>UT has reviewed your product trial request and requires changes before it can proceed.</p>"
        + (f"<p><strong>Requested changes:</strong> {reason}</p>" if reason else "")
        + "<p>Please update your request and resubmit when ready.</p>"
    )

    return {
        "title": "Changes required for product trial",
        "message": message,
        "actions": [],
    }
