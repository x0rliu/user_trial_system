# app/services/shipping_service.py

import mysql.connector
from app.config.config import DB_CONFIG


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