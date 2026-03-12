import json
import mysql.connector
from app.config.config import DB_CONFIG
from app.services.email_smtp import send_email


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
http://localhost:8000/trials/recruiting?round_id={payload["round_id"]}

You can also browse all recruiting trials:
http://localhost:8000/trials/recruiting
"""

                send_email(
                    to_email=r["Email"],
                    subject=subject,
                    text_body=body
                )

    finally:
        conn.close()