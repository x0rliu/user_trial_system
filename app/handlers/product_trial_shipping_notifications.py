# app/handlers/product_trial_shipping_notifications.py


def render_product_trial_device_receipt_problem(payload: dict) -> dict:
    project_name = payload.get("project_name") or "Product Trial"
    round_name = payload.get("round_name") or "round"
    participant_name = payload.get("participant_name") or payload.get("participant_email") or "A participant"
    delivery_type = payload.get("delivery_type") or "delivery"
    courier = payload.get("courier") or "Unknown courier"
    tracking_number = payload.get("tracking_number") or "no tracking number"
    carrier_status_label = payload.get("carrier_status_label") or "carrier marked delivered"
    round_id = payload.get("round_id")

    href = "/ut-lead/trials"
    if round_id:
        href = f"/ut-lead/project?round_id={round_id}"

    return {
        "title": "Device Receipt Problem Reported",
        "message": (
            f"{participant_name} reported that the device is not in hand for "
            f"{project_name} / {round_name}. Delivery type: {delivery_type}. "
            f"Carrier status: {carrier_status_label}. Tracking: {courier} {tracking_number}."
        ),
        "actions": [
            {
                "label": "Open Trial",
                "href": href,
                "style": "primary",
            }
        ],
    }


def render_product_trial_device_delivered(payload: dict) -> dict:
    project_name = payload.get("project_name") or "Product Trial"
    round_name = payload.get("round_name") or "round"
    delivery_type = payload.get("delivery_type") or "Home"
    courier = payload.get("courier") or "Unknown courier"
    tracking_number = payload.get("tracking_number") or "no tracking number"
    carrier_status_label = payload.get("carrier_status_label") or "Delivered"

    if delivery_type == "Office":
        message = (
            f"Carrier status for {project_name} / {round_name} is now {carrier_status_label}. "
            f"The device should be at the pickup office. Please confirm after you pick it up. "
            f"Tracking: {courier} {tracking_number}."
        )
    else:
        message = (
            f"Carrier status for {project_name} / {round_name} is now {carrier_status_label}. "
            f"Please confirm once the device is in hand. Tracking: {courier} {tracking_number}."
        )

    return {
        "title": "Please Confirm Device Receipt",
        "message": message,
        "actions": [
            {
                "label": "Open Active Trials",
                "href": "/trials/active",
                "style": "primary",
            }
        ],
    }