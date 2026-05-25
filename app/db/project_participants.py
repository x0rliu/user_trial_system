# app/db/project_participants.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_active_trials_for_user(user_id: str) -> list[dict]:
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    sql = """
    SELECT
        pp.user_id,

        pr.RoundID,
        pr.RoundNumber,
        pr.RoundName,
        pr.StartDate,
        pr.EndDate,

        pj.ProjectName,
        pj.ProductType,

        -- Account identity / account mobile
        up.FirstName AS AccountFirstName,
        up.LastName AS AccountLastName,
        up.MobileCountryCode AS AccountMobileCountryCode,
        up.MobileNational AS AccountMobileNational,
        up.MobileE164 AS AccountMobileE164,

        -- Participant core state
        pp.DeliveryType,
        pp.ShippingAddressConfirmedAt,
        pp.ResponsibilitiesAcceptedAt,
        pp.SelectedAt,
        pp.ReplacementAttempt,

        -- Logistics
        pp.Courier,
        pp.TrackingNumber,
        pp.TrackingURL,
        pp.CarrierStatus,
        pp.CarrierStatusLabel,
        pp.CarrierEstimatedDeliveryAt,
        pp.CarrierDeliveredAt,
        pp.CarrierSignedBy,
        pp.CarrierLastCheckedAt,
        pp.ShippedAt,
        pp.DeliveredAt,
        pp.DeviceReceivedConfirmedAt,
        pp.DeviceReceiptProblemReportedAt,
        pp.DeviceReceiptProblemResolvedAt,
        pp.DeviceReceiptProblemNote,

        -- NDA source of truth
        pn.NDAStatus,
        pn.DateSigned,

        -- Home address default
        ha.AddressLine1,
        ha.City,
        ha.StateRegion,
        ha.PostalCode,
        ha.Country,

        -- Round shipping override
        pp.ShippingAddressLine1,
        pp.ShippingAddressLine2,
        pp.ShippingCity,
        pp.ShippingStateRegion,
        pp.ShippingPostalCode,
        pp.ShippingCountry,
        pp.ShippingOfficeID,
        pp.ShippingSavedGlobally,

        -- Trial-specific shipping contact
        pp.ShippingRecipientFirstName,
        pp.ShippingRecipientLastName,
        pp.ShippingPhoneNumber,

        -- Office
        oa.OfficeID,
        so.OfficeName,

        -- Dial code from saved address country
        cc.IntlDialCode

    FROM project_participants pp

    JOIN project_rounds pr
        ON pp.RoundID = pr.RoundID

    JOIN project_projects pj
        ON pr.ProjectID = pj.ProjectID

    LEFT JOIN user_pool up
        ON up.user_id = pp.user_id

    LEFT JOIN project_ndas pn
        ON pn.user_id = pp.user_id
        AND pn.RoundID = pp.RoundID

    LEFT JOIN user_home_address ha
        ON ha.user_id = pp.user_id
        AND ha.IsDefault = 1

    LEFT JOIN user_office_assignment oa
        ON oa.user_id = pp.user_id
        AND oa.IsPrimary = 1

    LEFT JOIN user_pool_country_codes cc
        ON TRIM(LOWER(ha.Country)) = TRIM(LOWER(cc.CountryName))

    LEFT JOIN system_office_locations so
        ON so.OfficeID = oa.OfficeID

    WHERE pp.user_id = %s
      AND pp.ParticipantStatus IN ('Selected', 'Active')
      AND pp.CompletedAt IS NULL
    """

    cursor.execute(sql, (user_id,))
    rows = cursor.fetchall()

    round_surveys_by_round = {}
    round_ids = sorted({int(r["RoundID"]) for r in rows if r.get("RoundID")})

    if round_ids:
        placeholders = ", ".join(["%s"] * len(round_ids))

        cursor.execute(f"""
            SELECT
                prs.RoundSurveyID,
                prs.RoundID,
                prs.SurveyTypeID,
                prs.SurveyDistributionLink,
                prs.CreatedAt,
                st.SurveyTypeName,
                st.SurveyDescription
            FROM project_round_surveys prs
            LEFT JOIN survey_types st
                ON st.SurveyTypeID = prs.SurveyTypeID
            WHERE prs.RoundID IN ({placeholders})
              AND prs.IsActive = 1
            ORDER BY prs.RoundID, prs.CreatedAt, prs.RoundSurveyID
        """, tuple(round_ids))

        for survey_row in cursor.fetchall():
            survey_round_id = int(survey_row.get("RoundID") or 0)
            round_surveys_by_round.setdefault(survey_round_id, []).append({
                "RoundSurveyID": survey_row.get("RoundSurveyID"),
                "RoundID": survey_row.get("RoundID"),
                "SurveyTypeID": survey_row.get("SurveyTypeID"),
                "SurveyTypeName": survey_row.get("SurveyTypeName"),
                "SurveyDescription": survey_row.get("SurveyDescription"),
                "SurveyDistributionLink": survey_row.get("SurveyDistributionLink"),
                "CreatedAt": survey_row.get("CreatedAt"),
            })

    cursor.close()
    conn.close()

    results = []

    for r in rows:
        results.append({
            "RoundID": r["RoundID"],
            "RoundNumber": r["RoundNumber"],

            "ProjectName": r["ProjectName"],
            "RoundName": r["RoundName"],
            "ProductType": r["ProductType"],
            "StartDate": r["StartDate"],
            "EndDate": r["EndDate"],

            # -------------------------
            # ACCOUNT PREFILL DATA
            # -------------------------
            "AccountFirstName": r.get("AccountFirstName"),
            "AccountLastName": r.get("AccountLastName"),
            "AccountMobileCountryCode": r.get("AccountMobileCountryCode"),
            "AccountMobileNational": r.get("AccountMobileNational"),
            "AccountMobileE164": r.get("AccountMobileE164"),

            # -------------------------
            # CORE STATE
            # -------------------------
            "DeliveryType": r.get("DeliveryType"),
            "ShippingAddressConfirmedAt": r.get("ShippingAddressConfirmedAt"),
            "ResponsibilitiesAcceptedAt": r.get("ResponsibilitiesAcceptedAt"),
            "SelectedAt": r.get("SelectedAt"),
            "ReplacementAttempt": r.get("ReplacementAttempt"),

            # -------------------------
            # LOGISTICS
            # -------------------------
            "Courier": r.get("Courier"),
            "TrackingNumber": r.get("TrackingNumber"),
            "TrackingURL": r.get("TrackingURL"),
            "CarrierStatus": r.get("CarrierStatus"),
            "CarrierStatusLabel": r.get("CarrierStatusLabel"),
            "CarrierEstimatedDeliveryAt": r.get("CarrierEstimatedDeliveryAt"),
            "CarrierDeliveredAt": r.get("CarrierDeliveredAt"),
            "CarrierSignedBy": r.get("CarrierSignedBy"),
            "CarrierLastCheckedAt": r.get("CarrierLastCheckedAt"),
            "ShippedAt": r.get("ShippedAt"),
            "DeliveredAt": r.get("DeliveredAt"),
            "DeviceReceivedConfirmedAt": r.get("DeviceReceivedConfirmedAt"),
            "DeviceReceiptProblemReportedAt": r.get("DeviceReceiptProblemReportedAt"),
            "DeviceReceiptProblemResolvedAt": r.get("DeviceReceiptProblemResolvedAt"),
            "DeviceReceiptProblemNote": r.get("DeviceReceiptProblemNote"),

            # -------------------------
            # NDA
            # -------------------------
            "NDAStatus": r.get("NDAStatus"),
            "NDASignedAt": r.get("DateSigned"),

            # -------------------------
            # ADDRESS DEFAULT
            # -------------------------
            "AddressLine1": r.get("AddressLine1"),
            "City": r.get("City"),
            "StateRegion": r.get("StateRegion"),
            "PostalCode": r.get("PostalCode"),
            "Country": r.get("Country"),

            # -------------------------
            # ADDRESS ROUND OVERRIDE
            # -------------------------
            "ShippingAddressLine1": r.get("ShippingAddressLine1"),
            "ShippingAddressLine2": r.get("ShippingAddressLine2"),
            "ShippingCity": r.get("ShippingCity"),
            "ShippingStateRegion": r.get("ShippingStateRegion"),
            "ShippingPostalCode": r.get("ShippingPostalCode"),
            "ShippingCountry": r.get("ShippingCountry"),
            "ShippingOfficeID": r.get("ShippingOfficeID"),
            "ShippingSavedGlobally": bool(r.get("ShippingSavedGlobally")),

            # -------------------------
            # TRIAL-SPECIFIC SHIPPING CONTACT
            # -------------------------
            "ShippingRecipientFirstName": r.get("ShippingRecipientFirstName"),
            "ShippingRecipientLastName": r.get("ShippingRecipientLastName"),
            "ShippingPhoneNumber": r.get("ShippingPhoneNumber"),

            # -------------------------
            # OFFICE
            # -------------------------
            "OfficeID": r.get("OfficeID"),
            "OfficeName": r.get("OfficeName"),

            # -------------------------
            # ADDRESS-BASED DIAL CODE
            # -------------------------
            "IntlDialCode": r.get("IntlDialCode"),

            # -------------------------
            # ROUND SURVEYS
            # -------------------------
            "RoundSurveys": round_surveys_by_round.get(int(r.get("RoundID") or 0), []),
        })

    return results


def get_accepted_project_responsibilities_for_user(*, user_id: str) -> list[dict]:
    """
    Return project responsibility acknowledgments for the Settings agreements table.

    DB source of truth:
    - project_participants.ResponsibilitiesAcceptedAt owns the acknowledgment.
    - project_projects/project_rounds only provide display labels.
    """

    if not user_id:
        return []

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                pp.ParticipantID,
                pp.RoundID,
                pp.ResponsibilitiesAcceptedAt,
                pj.ProjectName,
                pr.RoundName,
                pr.RoundNumber
            FROM project_participants pp
            JOIN project_rounds pr
              ON pr.RoundID = pp.RoundID
            JOIN project_projects pj
              ON pj.ProjectID = pr.ProjectID
            WHERE pp.user_id = %s
              AND pp.ResponsibilitiesAcceptedAt IS NOT NULL
            ORDER BY pp.ResponsibilitiesAcceptedAt DESC, pp.ParticipantID DESC
            """,
            (user_id,),
        )

        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()


def remove_project_participant(*, round_id: int, user_id: str) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    sql = """
    DELETE FROM project_participants
    WHERE RoundID = %s AND user_id = %s
    """

    cursor.execute(sql, (round_id, user_id))
    conn.commit()

    cursor.close()
    conn.close()

def get_past_trials_for_user(user_id: str) -> list[dict]:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    sql = """
    SELECT
        pp.ParticipantID,
        pp.RoundID,
        pj.ProjectName,
        pp.TrialNickname,
        pr.RoundName,
        pr.StartDate,
        pr.EndDate,

        COUNT(sd.DistributionID) AS surveys_issued,

        SUM(
            CASE
                WHEN sd.CompletedAt IS NOT NULL THEN 1
                ELSE 0
            END
        ) AS surveys_returned

    FROM project_participants pp

    JOIN project_rounds pr
        ON pp.RoundID = pr.RoundID

    JOIN project_projects pj
        ON pr.ProjectID = pj.ProjectID

    LEFT JOIN survey_distribution sd
        ON sd.RoundID = pp.RoundID
        AND sd.user_id = pp.user_id

    WHERE
        pp.user_id = %s
        AND pp.ParticipantStatus = 'Completed'

    GROUP BY
        pp.ParticipantID,
        pp.RoundID,
        pj.ProjectName,
        pp.TrialNickname,
        pr.RoundName,
        pr.StartDate,
        pr.EndDate

    ORDER BY
        pr.EndDate DESC
    """

    cursor.execute(sql, (user_id,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows

def user_is_currently_in_trial(*, user_id: str) -> bool:
    """
    Returns True if the user is currently participating in a trial.

    Definition:
        - ParticipantStatus = 'Selected' OR 'Active'
        - CompletedAt is NULL
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT 1
            FROM project_participants
            WHERE user_id = %s
              AND CompletedAt IS NULL
              AND ParticipantStatus IN ('Selected', 'Active')
            LIMIT 1
            """,
            (user_id,),
        )

        return cur.fetchone() is not None

    finally:
        conn.close()

def confirm_shipping_address(*, user_id: str, round_id: int) -> None:
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE project_participants
            SET ShippingAddressConfirmedAt = NOW()
            WHERE user_id = %s AND RoundID = %s
            """,
            (user_id, round_id),
        )

        conn.commit()
    finally:
        conn.close()

def confirm_responsibilities(*, user_id: str, round_id: int) -> None:
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE project_participants
            SET ResponsibilitiesAcceptedAt = NOW()
            WHERE user_id = %s AND RoundID = %s
            """,
            (user_id, round_id),
        )

        conn.commit()
    finally:
        conn.close()


def confirm_device_received(*, user_id: str, round_id: int) -> None:
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE project_participants
            SET
                DeviceReceivedConfirmedAt = COALESCE(DeviceReceivedConfirmedAt, NOW()),
                DeviceReceiptProblemResolvedAt = CASE
                    WHEN DeviceReceiptProblemReportedAt IS NOT NULL
                    THEN COALESCE(DeviceReceiptProblemResolvedAt, NOW())
                    ELSE DeviceReceiptProblemResolvedAt
                END,
                UpdatedAt = NOW()
            WHERE user_id = %s
              AND RoundID = %s
              AND ParticipantStatus IN ('Selected', 'Active')
              AND CompletedAt IS NULL
            """,
            (user_id, round_id),
        )

        conn.commit()
    finally:
        conn.close()


def report_device_receipt_problem(*, user_id: str, round_id: int, note: str | None = None) -> dict:
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                pp.ParticipantID,
                pp.RoundID,
                pp.user_id,
                pp.DeliveryType,
                pp.Courier,
                pp.TrackingNumber,
                pp.TrackingURL,
                pp.CarrierStatusLabel,
                pp.CarrierDeliveredAt,
                pp.DeviceReceivedConfirmedAt,
                pp.DeviceReceiptProblemReportedAt,
                pp.DeviceReceiptProblemResolvedAt,
                pr.UTLead_UserID,
                pr.RoundName,
                pr.RoundNumber,
                pj.ProjectName,
                up.FirstName,
                up.LastName,
                up.Email
            FROM project_participants pp
            JOIN project_rounds pr
                ON pr.RoundID = pp.RoundID
            JOIN project_projects pj
                ON pj.ProjectID = pr.ProjectID
            LEFT JOIN user_pool up
                ON up.user_id = pp.user_id
            WHERE pp.user_id = %s
              AND pp.RoundID = %s
              AND pp.ParticipantStatus IN ('Selected', 'Active')
              AND pp.CompletedAt IS NULL
            LIMIT 1
            """,
            (user_id, round_id),
        )
        row = cursor.fetchone()

        if not row:
            conn.rollback()
            return {"reported": False, "reason": "not_found"}

        if row.get("DeviceReceivedConfirmedAt"):
            conn.rollback()
            return {"reported": False, "reason": "already_confirmed"}

        already_open = (
            bool(row.get("DeviceReceiptProblemReportedAt"))
            and not row.get("DeviceReceiptProblemResolvedAt")
        )

        cursor.execute(
            """
            UPDATE project_participants
            SET
                DeviceReceiptProblemReportedAt = COALESCE(DeviceReceiptProblemReportedAt, NOW()),
                DeviceReceiptProblemResolvedAt = NULL,
                DeviceReceiptProblemNote = %s,
                UpdatedAt = NOW()
            WHERE user_id = %s
              AND RoundID = %s
              AND ParticipantStatus IN ('Selected', 'Active')
              AND CompletedAt IS NULL
              AND DeviceReceivedConfirmedAt IS NULL
            """,
            (note, user_id, round_id),
        )

        conn.commit()

    finally:
        conn.close()

    notified = False
    ut_lead_user_id = row.get("UTLead_UserID")

    if ut_lead_user_id and not already_open:
        try:
            from app.db.notifications import create_notification_event

            participant_name = " ".join([
                str(row.get("FirstName") or "").strip(),
                str(row.get("LastName") or "").strip(),
            ]).strip()

            notification_id = create_notification_event(
                type_key="product_trial_device_receipt_problem",
                user_ids=[ut_lead_user_id],
                created_by=user_id,
                payload={
                    "round_id": row.get("RoundID"),
                    "round_name": row.get("RoundName"),
                    "round_number": row.get("RoundNumber"),
                    "project_name": row.get("ProjectName"),
                    "participant_user_id": row.get("user_id"),
                    "participant_name": participant_name,
                    "participant_email": row.get("Email"),
                    "delivery_type": row.get("DeliveryType"),
                    "courier": row.get("Courier"),
                    "tracking_number": row.get("TrackingNumber"),
                    "tracking_url": row.get("TrackingURL"),
                    "carrier_status_label": row.get("CarrierStatusLabel"),
                    "carrier_delivered_at": str(row.get("CarrierDeliveredAt") or ""),
                    "note": note,
                },
            )

            if notification_id:
                from app.services.notification_dispatcher import dispatch_notifications
                dispatch_notifications(notification_id)

            notified = True
        except Exception:
            notified = False

    return {
        "reported": True,
        "already_open": already_open,
        "notified": notified,
        "ut_lead_user_id": ut_lead_user_id,
    }

def get_shipments_pending_carrier_status_sync(*, limit: int = 100, stale_minutes: int = 120) -> list[dict]:
    import mysql.connector
    from app.config.config import DB_CONFIG

    safe_limit = max(1, min(int(limit or 100), 500))
    safe_stale_minutes = max(5, int(stale_minutes or 120))

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                pp.ParticipantID,
                pp.RoundID,
                pp.user_id,
                pp.DeliveryType,
                pp.Courier,
                pp.TrackingNumber,
                pp.TrackingURL,
                pp.CarrierStatus,
                pp.CarrierStatusLabel,
                pp.CarrierEstimatedDeliveryAt,
                pp.CarrierDeliveredAt,
                pp.CarrierSignedBy,
                pp.CarrierLastCheckedAt,
                pp.DeviceReceivedConfirmedAt,
                pr.RoundName,
                pr.RoundNumber,
                pj.ProjectName,
                up.FirstName,
                up.LastName,
                up.Email
            FROM project_participants pp
            JOIN project_rounds pr
                ON pr.RoundID = pp.RoundID
            JOIN project_projects pj
                ON pj.ProjectID = pr.ProjectID
            LEFT JOIN user_pool up
                ON up.user_id = pp.user_id
            WHERE pp.TrackingNumber IS NOT NULL
              AND pp.TrackingNumber <> ''
              AND pp.Courier IN ('UPS', 'FedEx', 'DHL', 'SF Express')
              AND pp.ParticipantStatus IN ('Selected', 'Active')
              AND pp.CompletedAt IS NULL
              AND pp.DeviceReceivedConfirmedAt IS NULL
              AND (
                    pp.CarrierLastCheckedAt IS NULL
                    OR pp.CarrierLastCheckedAt < DATE_SUB(NOW(), INTERVAL %s MINUTE)
                  )
            ORDER BY
                pp.CarrierLastCheckedAt IS NULL DESC,
                pp.CarrierLastCheckedAt ASC,
                pp.ShippedAt ASC,
                pp.ParticipantID ASC
            LIMIT %s
            """,
            (safe_stale_minutes, safe_limit),
        )
        return cursor.fetchall() or []
    finally:
        conn.close()


def update_participant_carrier_status_from_sync(*, participant_id: int, status: dict) -> dict:
    import json
    import mysql.connector
    from app.config.config import DB_CONFIG

    carrier_status = str(status.get("status") or "shipping").strip().lower()[:50]
    carrier_status_label = str(status.get("label") or carrier_status or "Shipping").strip()[:150]
    estimated_delivery_at = status.get("estimated_delivery_at")
    delivered_at = status.get("delivered_at")
    signed_by = str(status.get("signed_by") or "").strip()[:150] or None
    raw_json = json.dumps(status.get("raw") or {}, default=str)

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                pp.ParticipantID,
                pp.RoundID,
                pp.user_id,
                pp.DeliveryType,
                pp.Courier,
                pp.TrackingNumber,
                pp.TrackingURL,
                pp.CarrierDeliveredAt,
                pp.DeviceReceivedConfirmedAt,
                pr.RoundName,
                pr.RoundNumber,
                pj.ProjectName,
                up.FirstName,
                up.LastName,
                up.Email
            FROM project_participants pp
            JOIN project_rounds pr
                ON pr.RoundID = pp.RoundID
            JOIN project_projects pj
                ON pj.ProjectID = pr.ProjectID
            LEFT JOIN user_pool up
                ON up.user_id = pp.user_id
            WHERE pp.ParticipantID = %s
              AND pp.ParticipantStatus IN ('Selected', 'Active')
              AND pp.CompletedAt IS NULL
            LIMIT 1
            """,
            (participant_id,),
        )
        row = cursor.fetchone()

        if not row:
            conn.rollback()
            return {"updated": False, "reason": "not_found", "delivered_transition": False}

        was_delivered = bool(row.get("CarrierDeliveredAt"))
        already_confirmed = bool(row.get("DeviceReceivedConfirmedAt"))

        cursor.execute(
            """
            UPDATE project_participants
            SET
                CarrierStatus = %s,
                CarrierStatusLabel = %s,
                CarrierEstimatedDeliveryAt = %s,
                CarrierDeliveredAt = CASE
                    WHEN %s IS NOT NULL THEN %s
                    ELSE CarrierDeliveredAt
                END,
                CarrierSignedBy = %s,
                CarrierLastCheckedAt = NOW(),
                CarrierStatusRawJSON = %s,
                UpdatedAt = NOW()
            WHERE ParticipantID = %s
              AND ParticipantStatus IN ('Selected', 'Active')
              AND CompletedAt IS NULL
            """,
            (
                carrier_status,
                carrier_status_label,
                estimated_delivery_at,
                delivered_at,
                delivered_at,
                signed_by,
                raw_json,
                participant_id,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    delivered_transition = bool(delivered_at) and not was_delivered and not already_confirmed
    notified = False

    if delivered_transition:
        try:
            from app.db.notifications import create_notification_event
            from app.services.notification_dispatcher import dispatch_notifications

            participant_name = " ".join([
                str(row.get("FirstName") or "").strip(),
                str(row.get("LastName") or "").strip(),
            ]).strip()

            notification_id = create_notification_event(
                type_key="product_trial_device_delivered",
                user_ids=[row.get("user_id")],
                created_by="system",
                payload={
                    "round_id": row.get("RoundID"),
                    "round_name": row.get("RoundName"),
                    "round_number": row.get("RoundNumber"),
                    "project_name": row.get("ProjectName"),
                    "participant_user_id": row.get("user_id"),
                    "participant_name": participant_name,
                    "participant_email": row.get("Email"),
                    "delivery_type": row.get("DeliveryType"),
                    "courier": row.get("Courier"),
                    "tracking_number": row.get("TrackingNumber"),
                    "tracking_url": row.get("TrackingURL"),
                    "carrier_status": carrier_status,
                    "carrier_status_label": carrier_status_label,
                    "carrier_estimated_delivery_at": str(estimated_delivery_at or ""),
                    "carrier_delivered_at": str(delivered_at or ""),
                    "carrier_signed_by": signed_by,
                },
            )

            if notification_id:
                dispatch_notifications(notification_id)

            notified = True
        except Exception:
            notified = False

    return {
        "updated": True,
        "participant_id": participant_id,
        "status": carrier_status,
        "delivered_transition": delivered_transition,
        "notified": notified,
    }