# app/services/shipping_service.py

import csv
import re
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