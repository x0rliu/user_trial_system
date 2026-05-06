# app/services/active_trial.py

def build_active_trial_context(row: dict) -> dict:
    """
    Normalize DB row into deterministic UI state.
    No UI logic. No HTML. Pure state derivation.

    Phone ownership:
    - ShippingPhoneNumber is trial-specific and wins if present.
    - AccountMobileE164 is only a prefill fallback.
    - This function does not persist account mobile into shipping.
    """

    from datetime import datetime, timedelta

    # -------------------------
    # NDA
    # -------------------------
    nda = {
        "required": True,
        "signed": row.get("NDAStatus") == "Signed",
    }

    # -------------------------
    # SHIPPING ADDRESS DISPLAY
    # -------------------------
    address_display = "No address on file"

    delivery_type = row.get("DeliveryType")

    if delivery_type == "Home":
        if row.get("ShippingAddressLine1"):
            parts = [
                row.get("ShippingAddressLine1"),
                row.get("ShippingCity"),
                row.get("ShippingStateRegion"),
                row.get("ShippingPostalCode"),
                row.get("ShippingCountry"),
            ]
            address_display = ", ".join([p for p in parts if p])

        elif row.get("AddressLine1"):
            parts = [
                row.get("AddressLine1"),
                row.get("City"),
                row.get("StateRegion"),
                row.get("PostalCode"),
                row.get("Country"),
            ]
            address_display = ", ".join([p for p in parts if p])

        else:
            address_display = "No home address on file"

    elif delivery_type == "Office":
        if row.get("ShippingOfficeID"):
            address_display = row.get("OfficeName") or "Office selected"
        elif row.get("OfficeName"):
            address_display = row.get("OfficeName")
        else:
            address_display = "No office assigned"

    # -------------------------
    # SHIPPING ADDRESS
    # -------------------------
    shipping = {
        "required": True,
        "confirmed": bool(row.get("ShippingAddressConfirmedAt", False)),
    }

    # -------------------------
    # RESPONSIBILITIES
    # -------------------------
    responsibilities = {
        "accepted": bool(row.get("ResponsibilitiesAcceptedAt", False)),
    }

    # -------------------------
    # SHIPPING GATING
    # -------------------------
    shipping_ready = (
        nda["signed"]
        and shipping["confirmed"]
        and responsibilities["accepted"]
    )

    # -------------------------
    # DEVICE / LOGISTICS
    # -------------------------
    tracking_number = row.get("TrackingNumber")
    tracking_url = row.get("TrackingURL")
    shipped_at = row.get("ShippedAt")
    delivered_at = row.get("DeliveredAt")
    confirmed_at = row.get("DeviceReceivedConfirmedAt")

    device = {
        "tracking_number": tracking_number,
        "tracking_url": tracking_url,
        "shipped": bool(shipped_at),
        "delivered": bool(delivered_at),
        "confirmed": bool(confirmed_at),
    }

    if not tracking_number:
        device["state"] = "pending"
    elif tracking_number and not delivered_at:
        device["state"] = "in_transit"
    elif delivered_at and not confirmed_at:
        device["state"] = "awaiting_confirmation"
    else:
        device["state"] = "completed"

    # -------------------------
    # SURVEY 1
    # -------------------------
    survey1 = {
        "required": True,
        "completed": bool(row.get("Survey1CompletedAt", False)),
        "available": bool(row.get("Survey1URL")),
        "url": row.get("Survey1URL") or "#",
        "deadline": row.get("Survey1Deadline"),
    }

    # -------------------------
    # SURVEY 2
    # -------------------------
    survey2 = {
        "required": True,
        "completed": bool(row.get("Survey2CompletedAt", False)),
        "available": bool(row.get("Survey2URL")),
        "url": row.get("Survey2URL") or "#",
        "deadline": row.get("Survey2Deadline"),
    }

    # -------------------------
    # DEADLINES / REPLACEMENT LOGIC
    # -------------------------
    start_date = row.get("StartDate")
    selected_at = row.get("SelectedAt")
    attempt = row.get("ReplacementAttempt", 0)

    factory_cutoff = None
    effective_deadline = None
    needs_replacement = False

    if start_date and selected_at:
        factory_cutoff = start_date - timedelta(days=7)

        if isinstance(selected_at, datetime):
            selected_at = selected_at.date()

        if isinstance(factory_cutoff, datetime):
            factory_cutoff = factory_cutoff.date()

        total_window = factory_cutoff - selected_at
        max_attempts = 3

        if total_window.total_seconds() > 0:
            slot_duration = total_window / max_attempts
            effective_deadline = selected_at + (slot_duration * (attempt + 1))

            now = datetime.now()

            needs_replacement = (
                not shipping_ready
                and now > effective_deadline
                and now < factory_cutoff
            )

    # -------------------------
    # SHIPPING PHONE PREFILL
    # -------------------------
    shipping_phone = (row.get("ShippingPhoneNumber") or "").strip()

    account_mobile_country_code = (
        row.get("AccountMobileCountryCode") or ""
    ).strip()

    account_mobile_national = (
        row.get("AccountMobileNational") or ""
    ).strip()

    account_mobile_e164 = (
        row.get("AccountMobileE164") or ""
    ).strip()

    address_dial_code = (row.get("IntlDialCode") or "").strip()

    effective_phone = shipping_phone or account_mobile_e164

    if shipping_phone:
        effective_country_code = address_dial_code or account_mobile_country_code
        effective_national = ""
    else:
        effective_country_code = account_mobile_country_code
        effective_national = account_mobile_national

    if effective_phone and not effective_national:
        full_phone_clean = effective_phone.strip()
        country_code_clean = (effective_country_code or "").strip()

        if full_phone_clean and country_code_clean:
            if full_phone_clean.startswith(country_code_clean):
                effective_national = full_phone_clean[len(country_code_clean):]
            else:
                phone_without_plus = full_phone_clean.replace("+", "")
                code_without_plus = country_code_clean.replace("+", "")

                if phone_without_plus.startswith(code_without_plus):
                    effective_national = phone_without_plus[len(code_without_plus):]
                else:
                    effective_national = full_phone_clean
        else:
            effective_national = full_phone_clean

    if effective_national.startswith("0"):
        effective_national = effective_national[1:]

    # -------------------------
    # SHIPPING RECIPIENT PREFILL
    # -------------------------
    recipient_first_name = (
        row.get("ShippingRecipientFirstName")
        or row.get("AccountFirstName")
        or ""
    )

    recipient_last_name = (
        row.get("ShippingRecipientLastName")
        or row.get("AccountLastName")
        or ""
    )

    # -------------------------
    # FINAL STRUCTURE
    # -------------------------
    return {
        "ProjectName": row.get("ProjectName"),
        "RoundName": row.get("RoundName"),
        "RoundID": row.get("RoundID"),

        "delivery_type": row.get("DeliveryType"),

        "nda": nda,
        "shipping_address_display": address_display,
        "shipping": shipping,
        "responsibilities": responsibilities,

        "shipping_ready": shipping_ready,

        "device": device,

        "survey1": survey1,
        "survey2": survey2,

        # Form phone fields.
        # Shipping-specific phone wins.
        # Account mobile is fallback prefill only.
        "phone_country_code": effective_country_code,
        "phone_national": effective_national,

        # Used by current delivery completeness check.
        "phone_number": effective_phone,

        # Recipient fields.
        # Shipping-specific recipient wins.
        # Account name is fallback prefill only.
        "first_name": recipient_first_name,
        "last_name": recipient_last_name,

        "deadlines": {
            "factory_cutoff": factory_cutoff,
            "effective_deadline": effective_deadline,
        },
        "attempt": attempt,
        "needs_replacement": needs_replacement,

        "prefill": {
            "line1": row.get("ShippingAddressLine1") or row.get("AddressLine1") or "",
            "line2": row.get("ShippingAddressLine2") or "",
            "city": row.get("ShippingCity") or row.get("City") or "",
            "state": row.get("ShippingStateRegion") or row.get("StateRegion") or "",
            "postal": row.get("ShippingPostalCode") or row.get("PostalCode") or "",
            "country": row.get("ShippingCountry") or row.get("Country") or "",
        },
    }