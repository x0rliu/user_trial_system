# app/services/shipping_service.py

import csv
import re
from datetime import datetime
from io import StringIO
from urllib.parse import quote_plus

import mysql.connector
from app.config.config import DB_CONFIG


SUPPORTED_TRACKING_CARRIERS = {
    "UPS",
    "FedEx",
    "DHL",
    "SF Express",
}


TRACKING_CARRIER_ALIASES = {
    "ups": "UPS",
    "united parcel service": "UPS",
    "fedex": "FedEx",
    "federal express": "FedEx",
    "dhl": "DHL",
    "dhl express": "DHL",
    "sf": "SF Express",
    "sf express": "SF Express",
    "sf-express": "SF Express",
    "shunfeng": "SF Express",
    "shun feng": "SF Express",
}


def canonical_tracking_number(value: str | None) -> str:
    return "".join(str(value or "").strip().upper().split())


def normalize_tracking_carrier(value: str | None) -> str:
    carrier_key = str(value or "").strip().lower()
    return TRACKING_CARRIER_ALIASES.get(carrier_key, "")


def tracking_url_for_carrier(courier: str, tracking_number: str) -> str:
    encoded = quote_plus(tracking_number)
    carrier = normalize_tracking_carrier(courier)

    if carrier == "UPS":
        return f"https://www.ups.com/track?tracknum={encoded}"
    if carrier == "FedEx":
        return f"https://www.fedex.com/fedextrack/?trknbr={encoded}"
    if carrier == "DHL":
        return f"https://www.dhl.com/global-en/home/tracking/tracking-express.html?submit=1&tracking-id={encoded}"

    # SF Express and ambiguous/unknown carriers use an aggregator fallback for MVP.
    return f"https://www.17track.net/en/track-details?nums={encoded}"


def infer_tracking_carrier(tracking_number: str | None) -> dict:
    """
    Deterministically infer a carrier from common tracking-number patterns.

    MVP carrier scope:
    - UPS
    - DHL
    - FedEx
    - SF Express

    Ambiguous numbers remain Unknown unless the upload explicitly supplies Courier.
    """

    number = canonical_tracking_number(tracking_number)
    if not number:
        return {"courier": "Unknown", "tracking_url": ""}

    courier = "Unknown"

    if re.fullmatch(r"1Z[0-9A-Z]{16}", number):
        courier = "UPS"
    elif re.fullmatch(r"JD\d{18,}", number):
        courier = "DHL"
    elif re.fullmatch(r"\d{10}", number):
        courier = "DHL"
    elif re.fullmatch(r"\d{12}|\d{15}", number):
        courier = "FedEx"
    elif re.fullmatch(r"SF[0-9A-Z]{10,}", number):
        courier = "SF Express"

    return {
        "courier": courier,
        "tracking_url": tracking_url_for_carrier(courier, number),
    }


def build_tracking_row(*, email: str, tracking_number: str, courier: str | None = None) -> dict:
    number = canonical_tracking_number(tracking_number)
    explicit_carrier = normalize_tracking_carrier(courier)

    if explicit_carrier:
        carrier = explicit_carrier
        tracking_url = tracking_url_for_carrier(carrier, number) if number else ""
    else:
        carrier_info = infer_tracking_carrier(number)
        carrier = carrier_info["courier"]
        tracking_url = carrier_info["tracking_url"]

    return {
        "email": str(email or "").strip().lower(),
        "courier": carrier,
        "tracking_number": number,
        "tracking_url": tracking_url,
    }


def parse_tracking_csv_rows(csv_bytes: bytes) -> list[dict]:
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(StringIO(text))

    if not reader.fieldnames:
        raise ValueError("tracking CSV is missing headers")

    headers = [str(header or "").strip() for header in reader.fieldnames]
    required_headers = ["Email", "Tracking Number"]
    allowed_headers = [
        required_headers,
        ["Email", "Tracking Number", "Courier"],
    ]

    if headers not in allowed_headers:
        raise ValueError("tracking CSV must use the standard template headers")

    rows = []
    for raw_row in reader:
        raw_row = raw_row or {}
        rows.append(build_tracking_row(
            email=raw_row.get("Email"),
            tracking_number=raw_row.get("Tracking Number"),
            courier=raw_row.get("Courier"),
        ))

    return rows


TRACKING_STATUS_LABELS = {
    "shipping": "Shipping",
    "in_transit": "In transit",
    "out_for_delivery": "Out for delivery",
    "delivered": "Delivered",
    "exception": "Delivery exception",
    "unknown": "Unknown status",
}


TRACKING_STATUS_ALIASES = {
    "shipping": "shipping",
    "shipped": "shipping",
    "label_created": "shipping",
    "pre_transit": "shipping",
    "transit": "in_transit",
    "in_transit": "in_transit",
    "in transit": "in_transit",
    "on_the_way": "in_transit",
    "out_for_delivery": "out_for_delivery",
    "out for delivery": "out_for_delivery",
    "ofd": "out_for_delivery",
    "delivered": "delivered",
    "delivery": "delivered",
    "signed": "delivered",
    "exception": "exception",
    "failed_attempt": "exception",
    "failed attempt": "exception",
}


def normalize_carrier_status_update(
    *,
    status: str,
    label: str | None = None,
    estimated_delivery_at=None,
    delivered_at=None,
    signed_by: str | None = None,
    raw: dict | None = None,
) -> dict:
    status_key = str(status or "").strip().lower()
    normalized_status = TRACKING_STATUS_ALIASES.get(status_key, "unknown")

    if normalized_status == "delivered" and not delivered_at:
        delivered_at = datetime.now().replace(microsecond=0)

    return {
        "status": normalized_status,
        "label": str(label or TRACKING_STATUS_LABELS.get(normalized_status, "Unknown status")).strip(),
        "estimated_delivery_at": estimated_delivery_at,
        "delivered_at": delivered_at,
        "signed_by": signed_by,
        "raw": raw or {},
    }


def fetch_ups_tracking_status(shipment: dict) -> dict | None:
    # Placeholder for UPS direct Track API integration.
    # Return None so the sync job skips DB mutation until credentials/client code are configured.
    return None


def fetch_fedex_tracking_status(shipment: dict) -> dict | None:
    # Placeholder for FedEx Track API integration.
    return None


def fetch_dhl_tracking_status(shipment: dict) -> dict | None:
    # Placeholder for DHL shipment tracking integration.
    return None


def fetch_sf_express_tracking_status(shipment: dict) -> dict | None:
    # Placeholder for SF Express tracking integration.
    return None


def fetch_tracking_status_for_shipment(shipment: dict) -> dict | None:
    carrier = normalize_tracking_carrier(shipment.get("Courier"))

    if carrier == "UPS":
        return fetch_ups_tracking_status(shipment)
    if carrier == "FedEx":
        return fetch_fedex_tracking_status(shipment)
    if carrier == "DHL":
        return fetch_dhl_tracking_status(shipment)
    if carrier == "SF Express":
        return fetch_sf_express_tracking_status(shipment)

    return None


def sync_shipping_statuses(*, limit: int = 100, stale_minutes: int = 120) -> dict:
    from app.db.project_participants import (
        get_shipments_pending_carrier_status_sync,
        update_participant_carrier_status_from_sync,
    )

    shipments = get_shipments_pending_carrier_status_sync(
        limit=limit,
        stale_minutes=stale_minutes,
    )

    summary = {
        "checked": 0,
        "updated": 0,
        "delivered": 0,
        "notified": 0,
        "skipped": 0,
        "errors": 0,
    }

    for shipment in shipments:
        summary["checked"] += 1

        try:
            status_update = fetch_tracking_status_for_shipment(shipment)
            if not status_update:
                summary["skipped"] += 1
                continue

            result = update_participant_carrier_status_from_sync(
                participant_id=shipment["ParticipantID"],
                status=status_update,
            )

            if result.get("updated"):
                summary["updated"] += 1
            if result.get("delivered_transition"):
                summary["delivered"] += 1
            if result.get("notified"):
                summary["notified"] += 1

        except Exception:
            summary["errors"] += 1

    return summary


def save_shipping_address(
    *,
    user_id: str,
    round_id: int,
    delivery_type: str,
    address_data: dict,
    recipient_data: dict,   # 🔥 ADD THIS
    office_id: str | None,
    save_globally: bool
):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor()

        # -------------------------
        # Always write to ROUND
        # -------------------------
        cursor.execute(
        """
        UPDATE project_participants
        SET
            DeliveryType = %s,
            ShippingAddressLine1 = %s,
            ShippingAddressLine2 = %s,
            ShippingCity = %s,
            ShippingStateRegion = %s,
            ShippingPostalCode = %s,
            ShippingCountry = %s,
            ShippingOfficeID = %s,
            ShippingSavedGlobally = %s,

            -- 🔥 NEW: recipient + phone
            ShippingRecipientFirstName = %s,
            ShippingRecipientLastName = %s,
            ShippingPhoneNumber = %s,

            -- 🔥 CRITICAL: marks step complete
            ShippingAddressConfirmedAt = NOW()

        WHERE user_id = %s AND RoundID = %s
        """,
        (
            delivery_type,
            address_data.get("line1"),
            address_data.get("line2"),
            address_data.get("city"),
            address_data.get("state"),
            address_data.get("postal"),
            address_data.get("country"),
            office_id,
            1 if save_globally else 0,

            # 🔥 new fields
            recipient_data.get("first_name"),
            recipient_data.get("last_name"),
            recipient_data.get("phone") if recipient_data.get("phone") else None,

            user_id,
            round_id,
        )
    )

        # -------------------------
        # Optional: save to user
        # -------------------------
        if save_globally and delivery_type == "Home":

            # Check if user already has a default address
            cursor.execute(
                """
                SELECT HomeAddressID
                FROM user_home_address
                WHERE user_id = %s AND IsDefault = 1
                LIMIT 1
                """,
                (user_id,)
            )

            existing = cursor.fetchone()

            if existing:
                # -------------------------
                # UPDATE existing
                # -------------------------
                cursor.execute(
                    """
                    UPDATE user_home_address
                    SET
                        AddressLine1 = %s,
                        AddressLine2 = %s,
                        City = %s,
                        StateRegion = %s,
                        PostalCode = %s,
                        Country = %s,
                        UpdatedAt = NOW()
                    WHERE HomeAddressID = %s
                    """,
                    (
                        address_data.get("line1"),
                        address_data.get("line2"),
                        address_data.get("city"),
                        address_data.get("state"),
                        address_data.get("postal"),
                        address_data.get("country"),
                        existing[0],
                    ),
                )

            else:
                # -------------------------
                # INSERT new
                # -------------------------
                cursor.execute(
                    """
                    INSERT INTO user_home_address (
                        user_id,
                        AddressLine1,
                        AddressLine2,
                        City,
                        StateRegion,
                        PostalCode,
                        Country,
                        IsDefault
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
                    """,
                    (
                        user_id,
                        address_data.get("line1"),
                        address_data.get("line2"),
                        address_data.get("city"),
                        address_data.get("state"),
                        address_data.get("postal"),
                        address_data.get("country"),
                    ),
                )

        conn.commit()

    finally:
        conn.close()


def cleanup_round_shipping(*, user_id: str, round_id: int):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT ShippingSavedGlobally
            FROM project_participants
            WHERE user_id = %s AND RoundID = %s
            """,
            (user_id, round_id),
        )

        row = cursor.fetchone()

        if row and not row[0]:
            cursor.execute(
                """
                UPDATE project_participants
                SET
                    ShippingAddressLine1 = NULL,
                    ShippingAddressLine2 = NULL,
                    ShippingCity = NULL,
                    ShippingStateRegion = NULL,
                    ShippingPostalCode = NULL,
                    ShippingCountry = NULL,
                    ShippingOfficeID = NULL
                WHERE user_id = %s AND RoundID = %s
                """,
                (user_id, round_id),
            )

        conn.commit()

    finally:
        conn.close()