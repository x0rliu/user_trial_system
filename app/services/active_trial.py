# app/services/active_trial.py

def build_active_trial_context(row: dict) -> dict:
    """
    Normalize DB row into deterministic UI state.
    No UI logic. No HTML. Pure state derivation.
    """

    from datetime import datetime, timedelta

    # -------------------------
    # NDA
    # -------------------------
    nda = {
        "required": True,  # always show in UI
        "signed": row.get("NDAStatus") == "Signed"
    }

    # -------------------------
    # SHIPPING ADDRESS DISPLAY
    # -------------------------
    address_display = "No address on file"

    delivery_type = row.get("DeliveryType")

    # PRIORITY:
    # 1. Round override
    # 2. User default
    # 3. Fallback message

    if delivery_type == "Home":

        # Round-level override
        if row.get("ShippingAddressLine1"):
            parts = [
                row.get("ShippingAddressLine1"),
                row.get("ShippingCity"),
                row.get("ShippingStateRegion"),
                row.get("ShippingPostalCode"),
                row.get("ShippingCountry"),
            ]
            address_display = ", ".join([p for p in parts if p])

        # Fallback to user default
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

        # Round override (future-proof)
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
        "required": True,  # FORCE visible
        "confirmed": bool(row.get("ShippingAddressConfirmedAt", False))
    }

    # -------------------------
    # RESPONSIBILITIES
    # -------------------------
    responsibilities = {
        "accepted": bool(row.get("ResponsibilitiesAcceptedAt", False))
    }

    # -------------------------
    # SHIPPING GATING (CRITICAL)
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
        "confirmed": bool(confirmed_at)
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
        "required": True,  # FORCE visible
        "completed": bool(row.get("Survey1CompletedAt", False)),
        "available": bool(row.get("Survey1URL")),
        "url": row.get("Survey1URL") or "#",
        "deadline": row.get("Survey1Deadline")
    }

    # -------------------------
    # SURVEY 2
    # -------------------------
    survey2 = {
        "required": True,
        "completed": bool(row.get("Survey2CompletedAt", False)),
        "available": bool(row.get("Survey2URL")),
        "url": row.get("Survey2URL") or "#",
        "deadline": row.get("Survey2Deadline")
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

        from datetime import datetime, date

        # Normalize selected_at → date
        if isinstance(selected_at, datetime):
            selected_at = selected_at.date()

        # Normalize factory_cutoff → date (defensive)
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
    else:
        # disable deadline logic if missing data
        factory_cutoff = None
        effective_deadline = None
        needs_replacement = False

    # -------------------------
    # FINAL STRUCTURE
    # -------------------------
    return {
        # -------------------------
        # DISPLAY FIELDS (REQUIRED)
        # -------------------------
        "ProjectName": row.get("ProjectName"),
        "RoundName": row.get("RoundName"),
        "RoundID": row.get("RoundID"),

        # -------------------------
        # EXISTING
        # -------------------------
        "delivery_type": row.get("DeliveryType"),

        "nda": nda,
        "shipping_address_display": address_display,
        "shipping": shipping,
        "responsibilities": responsibilities,

        "shipping_ready": shipping_ready,

        "device": device,

        "survey1": survey1,
        "survey2": survey2,

        # NEW
        "deadlines": {
            "factory_cutoff": factory_cutoff,
            "effective_deadline": effective_deadline
        },
        "attempt": attempt,
        "needs_replacement": needs_replacement,
    
        # -------------------------
        # PREFILL (FORM STATE)
        # -------------------------
        "prefill": {
            "line1": row.get("ShippingAddressLine1") or row.get("AddressLine1") or "",
            "line2": row.get("ShippingAddressLine2") or "",
            "city": row.get("ShippingCity") or row.get("City") or "",
            "state": row.get("ShippingStateRegion") or row.get("StateRegion") or "",
            "postal": row.get("ShippingPostalCode") or row.get("PostalCode") or "",
            "country": row.get("ShippingCountry") or row.get("Country") or "",
        }
    }