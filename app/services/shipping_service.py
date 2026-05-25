# app/services/shipping_service.py

import csv
import time
import re
from datetime import datetime
from io import StringIO
from urllib.parse import quote_plus
from uuid import uuid4

import mysql.connector
import requests
from app.config.config import DB_CONFIG, UPS_TRACKING_CONFIG


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


_UPS_TOKEN_CACHE = {
    "access_token": "",
    "expires_at": 0,
}


def _parse_ups_datetime(date_value, time_value=None):
    date_text = str(date_value or "").strip()
    time_text = str(time_value or "").strip()

    if not date_text:
        return None

    candidates = []
    if time_text:
        candidates.extend([
            (f"{date_text}{time_text.zfill(6)}", "%Y%m%d%H%M%S"),
            (f"{date_text} {time_text}", "%Y-%m-%d %H:%M:%S"),
            (f"{date_text} {time_text}", "%Y-%m-%d %H:%M"),
        ])

    candidates.extend([
        (date_text, "%Y%m%d"),
        (date_text, "%Y-%m-%d"),
    ])

    for raw_value, fmt in candidates:
        try:
            return datetime.strptime(raw_value, fmt)
        except ValueError:
            continue

    return None


def _ups_package_list(payload: dict) -> list[dict]:
    track_response = payload.get("trackResponse") or payload.get("TrackResponse") or {}
    shipments = track_response.get("shipment") or track_response.get("Shipment") or []

    if isinstance(shipments, dict):
        shipments = [shipments]

    packages = []
    for shipment in shipments:
        package_rows = shipment.get("package") or shipment.get("Package") or []
        if isinstance(package_rows, dict):
            package_rows = [package_rows]
        packages.extend(package_rows)

    return packages


def _pick_ups_date(package: dict, date_type: str):
    target_type = str(date_type or "").strip().upper()
    rows = package.get("deliveryDate") or package.get("DeliveryDate") or []
    if isinstance(rows, dict):
        rows = [rows]

    for row in rows:
        row_type = str(row.get("type") or row.get("Type") or "").strip().upper()
        if row_type == target_type:
            return row.get("date") or row.get("Date")

    return None


def _pick_ups_time(package: dict, time_type: str):
    target_type = str(time_type or "").strip().upper()
    rows = package.get("deliveryTime") or package.get("DeliveryTime") or []
    if isinstance(rows, dict):
        rows = [rows]

    for row in rows:
        row_type = str(row.get("type") or row.get("Type") or "").strip().upper()
        if row_type == target_type:
            return row.get("endTime") or row.get("EndTime") or row.get("time") or row.get("Time")

    return None


def _ups_delivery_information(package: dict) -> dict:
    return (
        package.get("deliveryInformation")
        or package.get("DeliveryInformation")
        or {}
    )


def _ups_current_status(package: dict) -> dict:
    return (
        package.get("currentStatus")
        or package.get("CurrentStatus")
        or {}
    )


def _normalize_ups_status(package: dict) -> dict:
    current_status = _ups_current_status(package)
    status_description = str(
        current_status.get("description")
        or current_status.get("Description")
        or ""
    ).strip()
    status_code = str(
        current_status.get("code")
        or current_status.get("Code")
        or ""
    ).strip().upper()

    status_text = f"{status_code} {status_description}".strip().lower()

    normalized = "in_transit"
    if "delivered" in status_text or status_code == "D":
        normalized = "delivered"
    elif "out for delivery" in status_text:
        normalized = "out_for_delivery"
    elif "exception" in status_text or "failed" in status_text or "attempt" in status_text:
        normalized = "exception"
    elif "label" in status_text or "shipper created" in status_text:
        normalized = "shipping"

    delivered_date = _pick_ups_date(package, "DEL")
    delivered_time = _pick_ups_time(package, "DEL")
    delivered_at = _parse_ups_datetime(delivered_date, delivered_time)

    eta_date = (
        _pick_ups_date(package, "SDD")
        or _pick_ups_date(package, "RDD")
        or _pick_ups_date(package, "DEL")
    )
    eta_time = (
        _pick_ups_time(package, "SDD")
        or _pick_ups_time(package, "RDD")
        or _pick_ups_time(package, "DEL")
    )
    estimated_delivery_at = _parse_ups_datetime(eta_date, eta_time)

    delivery_info = _ups_delivery_information(package)
    signed_by = (
        delivery_info.get("receivedBy")
        or delivery_info.get("ReceivedBy")
        or delivery_info.get("signedForByName")
        or delivery_info.get("SignedForByName")
    )

    return normalize_carrier_status_update(
        status=normalized,
        label=status_description or TRACKING_STATUS_LABELS.get(normalized, "UPS status"),
        estimated_delivery_at=estimated_delivery_at,
        delivered_at=delivered_at,
        signed_by=signed_by,
        raw={
            "provider": "UPS",
            "current_status": current_status,
            "delivery_information": delivery_info,
            "package": package,
        },
    )


def _ups_tracking_is_configured() -> bool:
    return bool(
        UPS_TRACKING_CONFIG.get("enabled")
        and UPS_TRACKING_CONFIG.get("client_id")
        and UPS_TRACKING_CONFIG.get("client_secret")
        and UPS_TRACKING_CONFIG.get("token_url")
        and UPS_TRACKING_CONFIG.get("base_url")
    )


def _get_ups_access_token() -> str | None:
    if not _ups_tracking_is_configured():
        return None

    now = time.time()
    if _UPS_TOKEN_CACHE.get("access_token") and now < float(_UPS_TOKEN_CACHE.get("expires_at") or 0):
        return _UPS_TOKEN_CACHE["access_token"]

    client_id = UPS_TRACKING_CONFIG["client_id"]
    client_secret = UPS_TRACKING_CONFIG["client_secret"]
    merchant_id = UPS_TRACKING_CONFIG.get("merchant_id") or client_id

    response = requests.post(
        UPS_TRACKING_CONFIG["token_url"],
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "x-merchant-id": merchant_id,
        },
        timeout=15,
    )
    response.raise_for_status()

    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError("UPS token response did not include access_token")

    expires_in = int(payload.get("expires_in") or 3600)
    _UPS_TOKEN_CACHE["access_token"] = access_token
    _UPS_TOKEN_CACHE["expires_at"] = now + max(60, expires_in - 120)

    return access_token


def fetch_ups_tracking_status(shipment: dict) -> dict | None:
    tracking_number = canonical_tracking_number(shipment.get("TrackingNumber"))
    if not tracking_number:
        return None

    access_token = _get_ups_access_token()
    if not access_token:
        return None

    url = f"{UPS_TRACKING_CONFIG['base_url']}/api/track/v1/details/{quote_plus(tracking_number)}"
    response = requests.get(
        url,
        params={
            "locale": "en_US",
            "returnSignature": "false",
        },
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
            "transId": str(uuid4()),
            "transactionSrc": "UTS",
        },
        timeout=20,
    )
    response.raise_for_status()

    payload = response.json()
    packages = _ups_package_list(payload)
    if not packages:
        return normalize_carrier_status_update(
            status="unknown",
            label="UPS returned no package status",
            raw={"provider": "UPS", "response": payload},
        )

    return _normalize_ups_status(packages[0])


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


def sync_shipping_statuses(
    *,
    limit: int = 100,
    stale_minutes: int = 120,
    round_id: int | None = None,
    force: bool = False,
) -> dict:
    from app.db.project_participants import (
        get_shipments_pending_carrier_status_sync,
        update_participant_carrier_status_from_sync,
    )

    shipments = get_shipments_pending_carrier_status_sync(
        limit=limit,
        stale_minutes=stale_minutes,
        round_id=round_id,
        force=force,
    )

    summary = {
        "scope_round_id": round_id,
        "force": bool(force),
        "eligible": len(shipments),
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