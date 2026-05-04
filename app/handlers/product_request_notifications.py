# app/handlers/product_request_notifications.py


def render_product_trial_pending_approval(payload: dict) -> dict:
    project_name = payload.get("project_name") or "Unnamed Project"
    product_category = payload.get("product_category") or "—"
    start_date = payload.get("estimated_start_date") or "—"

    return {
        "title": "Product Trial Approval Required",
        "message": (
            f'The product trial "{project_name}" ({product_category}) '
            f"was submitted for UT approval. "
            f"Estimated start: {start_date}."
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

    message = "Your product trial request was declined."
    if reason:
        message += f" Reason: {reason}"

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

    message = "UT has reviewed your product trial request and needs more information."
    if reason:
        message += f" Details: {reason}"
    message += " Please review your request and resubmit once clarified."

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

    message = "UT has reviewed your product trial request and requires changes before it can proceed."
    if reason:
        message += f" Requested changes: {reason}"
    message += " Please update your request and resubmit when ready."

    return {
        "title": "Changes required for product trial",
        "message": message,
        "actions": [],
    }