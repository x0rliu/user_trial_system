# app/handlers/product_request_notifications.py


def render_product_trial_pending_approval(payload: dict) -> dict:
    project_name = payload.get("project_name") or "Unnamed Project"
    product_category = payload.get("product_category") or "unspecified product category"
    start_date = payload.get("estimated_start_date") or "unspecified start date"

    return {
        "title": "Product Trial Approval Required",
        "message": (
            f'The product trial "{project_name}" for {product_category} '
            f"has been submitted and is awaiting User Trials approval. "
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


def render_product_trial_approved(payload: dict) -> dict:
    round_id = payload.get("round_id")

    return {
        "title": "Product Trial Approved",
        "message": (
            "Your product trial request has been approved and will proceed "
            "with User Trials setup."
        ),
        "actions": [
            {
                "label": "View Current Trials",
                "href": "/product/current-trials",
                "style": "primary",
            }
        ],
    }


def render_product_trial_assigned(payload: dict) -> dict:
    round_id = payload.get("round_id")

    href = "/ut-lead/trials"
    if round_id:
        href = f"/ut-lead/project?round_id={round_id}"

    return {
        "title": "Product Trial Assigned",
        "message": (
            "You have been assigned as the User Trials Lead for a product trial."
        ),
        "actions": [
            {
                "label": "Open Trial Setup",
                "href": href,
                "style": "primary",
            }
        ],
    }


def render_product_trial_declined(payload: dict) -> dict:
    reason = payload.get("reason")

    message = "Your product trial request was declined."
    if reason:
        message += f" Reason: {reason}"

    return {
        "title": "Product Trial Declined",
        "message": message,
        "actions": [
            {
                "label": "View Requests",
                "href": "/product/request-trial",
                "style": "secondary",
            }
        ],
    }


def render_product_trial_info_requested(payload: dict) -> dict:
    reason = payload.get("reason")

    message = (
        "User Trials reviewed your product trial request and needs more "
        "information before it can proceed."
    )
    if reason:
        message += f" Details: {reason}"

    return {
        "title": "More Information Requested",
        "message": message,
        "actions": [
            {
                "label": "View Request",
                "href": "/product/request-trial",
                "style": "primary",
            }
        ],
    }


def render_product_trial_info_provided(payload: dict) -> dict:
    project_id = payload.get("project_id")
    round_name = payload.get("round_name") or "a product trial request"

    return {
        "title": "Product Trial Information Provided",
        "message": (
            f"The Product Team has provided additional information for {round_name}. "
            "The request is ready for User Trials review."
        ),
        "actions": [
            {
                "label": "View Approvals",
                "href": "/admin/approvals",
                "style": "primary",
            }
        ],
    }


def render_product_trial_change_requested(payload: dict) -> dict:
    reason = payload.get("reason")

    message = (
        "User Trials reviewed your product trial request and requires changes "
        "before it can proceed."
    )
    if reason:
        message += f" Requested changes: {reason}"

    return {
        "title": "Changes Requested",
        "message": message,
        "actions": [
            {
                "label": "View Request",
                "href": "/product/request-trial",
                "style": "primary",
            }
        ],
    }


def render_product_trial_change_accepted(payload: dict) -> dict:
    return {
        "title": "Changes Accepted",
        "message": (
            "The Product Team accepted the requested changes. "
            "The request is ready for User Trials review."
        ),
        "actions": [
            {
                "label": "View Approvals",
                "href": "/admin/approvals",
                "style": "primary",
            }
        ],
    }


def render_product_trial_change_countered(payload: dict) -> dict:
    reason = payload.get("reason")

    message = (
        "The Product Team proposed an alternative to the requested changes."
    )
    if reason:
        message += f" Counter proposal: {reason}"

    return {
        "title": "Changes Countered",
        "message": message,
        "actions": [
            {
                "label": "View Approvals",
                "href": "/admin/approvals",
                "style": "primary",
            }
        ],
    }


def render_product_trial_withdrawn_by_requestor(payload: dict) -> dict:
    return {
        "title": "Product Trial Withdrawn",
        "message": (
            "The Product Team has withdrawn their product trial request."
        ),
        "actions": [
            {
                "label": "View Approvals",
                "href": "/admin/approvals",
                "style": "secondary",
            }
        ],
    }


def render_trial_recruiting_started(payload: dict) -> dict:
    round_name = payload.get("round_name") or "a trial"

    return {
        "title": "Trial Recruiting Started",
        "message": (
            f"Recruiting has started for {round_name}."
        ),
        "actions": [
            {
                "label": "View Recruiting Trials",
                "href": "/trials/recruiting",
                "style": "primary",
            }
        ],
    }