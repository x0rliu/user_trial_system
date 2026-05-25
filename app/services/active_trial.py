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
    carrier_status = row.get("CarrierStatus")
    carrier_status_label = row.get("CarrierStatusLabel")
    carrier_estimated_delivery_at = row.get("CarrierEstimatedDeliveryAt")
    carrier_delivered_at = row.get("CarrierDeliveredAt")
    carrier_signed_by = row.get("CarrierSignedBy")
    carrier_last_checked_at = row.get("CarrierLastCheckedAt")
    confirmed_at = row.get("DeviceReceivedConfirmedAt")
    receipt_problem_reported_at = row.get("DeviceReceiptProblemReportedAt")
    receipt_problem_resolved_at = row.get("DeviceReceiptProblemResolvedAt")

    receipt_problem_open = (
        bool(receipt_problem_reported_at)
        and not receipt_problem_resolved_at
    )

    device = {
        "courier": row.get("Courier"),
        "tracking_number": tracking_number,
        "tracking_url": tracking_url,
        "carrier_status": carrier_status,
        "carrier_status_label": carrier_status_label,
        "carrier_estimated_delivery_at": carrier_estimated_delivery_at,
        "carrier_delivered_at": carrier_delivered_at,
        "carrier_signed_by": carrier_signed_by,
        "carrier_last_checked_at": carrier_last_checked_at,
        "receipt_problem_reported_at": receipt_problem_reported_at,
        "receipt_problem_resolved_at": receipt_problem_resolved_at,
        "receipt_problem_open": receipt_problem_open,
        "shipped": bool(shipped_at),
        "carrier_delivered": bool(carrier_delivered_at),
        "confirmed": bool(confirmed_at),
        "shipped_at": shipped_at,
        "confirmed_at": confirmed_at,
    }

    if confirmed_at:
        device["state"] = "completed"
    elif carrier_delivered_at:
        device["state"] = "awaiting_confirmation"
    elif tracking_number or shipped_at:
        device["state"] = "in_transit"
    else:
        device["state"] = "pending"

    # -------------------------
    # ROUND SURVEYS
    # -------------------------
    def clean_survey_label(value):
        label = str(value or "").replace("_", " ").strip()
        return label or "Survey"

    def normalize_round_survey(survey_row, survey_number: int):
        raw_link = (survey_row.get("SurveyDistributionLink") or "").strip()
        participant_activated_at = survey_row.get("ParticipantActivatedAt")
        device_confirmed = bool(confirmed_at)
        completed = bool(survey_row.get("Completed"))

        if completed:
            available = False
            activation_state = "completed"
            blocked_label = "Completed"
        elif not raw_link:
            available = False
            activation_state = "not_configured"
            blocked_label = "Not Available"
        elif not device_confirmed:
            available = False
            activation_state = "waiting_for_device_receipt"
            blocked_label = "Waiting for Device Receipt"
        elif survey_number == 1:
            available = True
            activation_state = "available"
            blocked_label = ""
        elif participant_activated_at:
            available = True
            activation_state = "available"
            blocked_label = ""
        else:
            available = False
            activation_state = "pending_ut_lead_activation"
            blocked_label = "Pending UT Lead Activation"

        return {
            "round_survey_id": survey_row.get("RoundSurveyID"),
            "survey_type_id": survey_row.get("SurveyTypeID"),
            "survey_number": survey_number,
            "label": clean_survey_label(
                survey_row.get("SurveyTypeName")
                or survey_row.get("SurveyTypeID")
            ),
            "description": survey_row.get("SurveyDescription") or "Open survey",
            "available": available,
            "activation_state": activation_state,
            "blocked_label": blocked_label,
            "participant_activated_at": participant_activated_at,
            "url": raw_link or "#",
            "completed": completed,
            "deadline": None,
        }

    report_issue = None
    surveys = []

    excluded_dynamic_survey_types = {
        "UTSurveyType0001",  # Recruiting
        "UTSurveyType0027",  # Consolidated/internal results
        "UTSurveyType0028",  # Report issue; rendered separately
    }

    participant_survey_number = 0

    for survey_row in row.get("RoundSurveys") or []:
        survey_type_id = survey_row.get("SurveyTypeID")
        survey_type_name = survey_row.get("SurveyTypeName")

        if survey_type_id == "UTSurveyType0028" or survey_type_name == "Report_Issue":
            raw_link = (survey_row.get("SurveyDistributionLink") or "").strip()
            report_issue = {
                "round_survey_id": survey_row.get("RoundSurveyID"),
                "survey_type_id": survey_type_id,
                "label": clean_survey_label(survey_type_name or survey_type_id),
                "description": survey_row.get("SurveyDescription") or "Report bugs, defects, or unexpected issues",
                "available": bool(raw_link),
                "activation_state": "available" if raw_link else "not_configured",
                "blocked_label": "" if raw_link else "Not Available",
                "url": raw_link or "#",
                "completed": False,
                "deadline": None,
            }
            continue

        if survey_type_id in excluded_dynamic_survey_types:
            continue

        participant_survey_number += 1
        surveys.append(normalize_round_survey(survey_row, participant_survey_number))

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
        "RoundNumber": row.get("RoundNumber"),
        "RoundID": row.get("RoundID"),

        "delivery_type": row.get("DeliveryType"),

        "nda": nda,
        "shipping_address_display": address_display,
        "shipping": shipping,
        "responsibilities": responsibilities,

        "shipping_ready": shipping_ready,

        "device": device,

        "report_issue": report_issue,
        "surveys": surveys,

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