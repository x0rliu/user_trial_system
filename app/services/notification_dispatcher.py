import json
import mysql.connector
from app.config.config import DB_CONFIG
from app.services.email_smtp import send_email


SITE_BASE_URL = "http://localhost:8000"


def dispatch_notifications(notification_id: str):

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # --------------------------------------------------
        # Fetch notification event
        # --------------------------------------------------

        cur.execute("""
            SELECT
                nn.notification_id,
                nt.type_key,
                nt.title,
                nn.payload
            FROM notification_notifications nn
            JOIN notification_types nt
                ON nt.notification_type_id = nn.notification_type_id
            WHERE nn.notification_id = %s
        """, (notification_id,))

        event = cur.fetchone()
        if not event:
            return

        payload = event["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)

        # --------------------------------------------------
        # Fetch recipients
        # --------------------------------------------------

        cur.execute("""
            SELECT
                nr.user_id,
                up.Email
            FROM notification_recipients nr
            JOIN user_pool up
                ON up.user_id = nr.user_id
            WHERE nr.notification_id = %s
        """, (notification_id,))

        recipients = cur.fetchall()

        # --------------------------------------------------
        # Send notifications
        # --------------------------------------------------

        for r in recipients:

            if event["type_key"] == "trial_recruiting_started":

                subject = "Trial Recruiting Started"

                body = f"""
{payload["round_name"]} is now recruiting.

You asked to be notified when this trial opened.

View trial:
{SITE_BASE_URL}/trials/recruiting?round_id={payload["round_id"]}

You can also browse all recruiting trials:
{SITE_BASE_URL}/trials/recruiting
"""

                send_email(
                    to_email=r["Email"],
                    subject=subject,
                    text_body=body
                )

            elif event["type_key"] == "product_trial_device_delivered":

                project_name = payload.get("project_name") or "Product Trial"
                round_name = payload.get("round_name") or "round"
                delivery_type = payload.get("delivery_type") or "Home"
                courier = payload.get("courier") or "Unknown courier"
                tracking_number = payload.get("tracking_number") or "no tracking number"
                status_label = payload.get("carrier_status_label") or "Delivered"
                round_id = payload.get("round_id") or ""

                subject = "Please confirm device receipt"

                body = f"""
Carrier status for {project_name} / {round_name} is now: {status_label}.

Tracking: {courier} {tracking_number}
Delivery type: {delivery_type}

Please confirm from your Active Trials page.

I have received / picked up the device:
{SITE_BASE_URL}/trials/active?round_id={round_id}&device_action=received

I have not received / could not pick up the device:
{SITE_BASE_URL}/trials/active?round_id={round_id}&device_action=not_received

Take me to my active trials:
{SITE_BASE_URL}/trials/active
"""

                send_email(
                    to_email=r["Email"],
                    subject=subject,
                    text_body=body
                )

            elif event["type_key"] == "product_trial_device_receipt_problem":

                project_name = payload.get("project_name") or "Product Trial"
                round_name = payload.get("round_name") or "round"
                participant_name = payload.get("participant_name") or payload.get("participant_email") or "A participant"
                delivery_type = payload.get("delivery_type") or "delivery"
                courier = payload.get("courier") or "Unknown courier"
                tracking_number = payload.get("tracking_number") or "no tracking number"
                status_label = payload.get("carrier_status_label") or "carrier marked delivered"
                round_id = payload.get("round_id") or ""

                subject = "Device receipt problem reported"

                body = f"""
{participant_name} reported that carrier delivery and device receipt do not match.

Project: {project_name}
Round: {round_name}
Delivery type: {delivery_type}
Carrier status: {status_label}
Tracking: {courier} {tracking_number}

Open the trial:
{SITE_BASE_URL}/ut-lead/project?round_id={round_id}
"""

                send_email(
                    to_email=r["Email"],
                    subject=subject,
                    text_body=body
                )

    finally:
        conn.close()