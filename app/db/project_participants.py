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
        pr.RoundName,
        pr.StartDate,
        pr.EndDate,

        pj.ProjectName,
        pj.ProductType,

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
        pp.ShippedAt,
        pp.DeliveredAt,
        pp.DeviceReceivedConfirmedAt,

        -- NDA (SOURCE OF TRUTH)
        pn.NDAStatus,
        pn.DateSigned,

        -- Home address (default)
        ha.AddressLine1,
        ha.City,
        ha.StateRegion,
        ha.PostalCode,
        ha.Country,

        pp.ShippingAddressLine1,
        pp.ShippingAddressLine2,
        pp.ShippingCity,
        pp.ShippingStateRegion,
        pp.ShippingPostalCode,
        pp.ShippingCountry,
        pp.ShippingOfficeID,
        pp.ShippingSavedGlobally,

        -- 🔥 NEW (MISSING)
        pp.ShippingRecipientFirstName,
        pp.ShippingRecipientLastName,
        pp.ShippingPhoneNumber,

        -- Office
        oa.OfficeID,
        so.OfficeName,

        -- 🔥 NEW
        cc.IntlDialCode

    FROM project_participants pp

    JOIN project_rounds pr ON pp.RoundID = pr.RoundID
    JOIN project_projects pj ON pr.ProjectID = pj.ProjectID

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

    cursor.close()
    conn.close()

    results = []

    for r in rows:
        results.append({
            "RoundID": r["RoundID"],

            "ProjectName": r["ProjectName"],
            "RoundName": r["RoundName"],
            "ProductType": r["ProductType"],
            "StartDate": r["StartDate"],
            "EndDate": r["EndDate"],

            # -------------------------
            # CORE STATE (CRITICAL)
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
            "ShippedAt": r.get("ShippedAt"),
            "DeliveredAt": r.get("DeliveredAt"),
            "DeviceReceivedConfirmedAt": r.get("DeviceReceivedConfirmedAt"),

            # -------------------------
            # NDA
            # -------------------------
            "NDAStatus": r.get("NDAStatus"),
            "NDASignedAt": r.get("DateSigned"),

            # -------------------------
            # ADDRESS (USER DEFAULT)
            # -------------------------
            "AddressLine1": r.get("AddressLine1"),
            "City": r.get("City"),
            "StateRegion": r.get("StateRegion"),
            "PostalCode": r.get("PostalCode"),
            "Country": r.get("Country"),

            # -------------------------
            # ADDRESS (ROUND OVERRIDE)
            # -------------------------
            "ShippingAddressLine1": r.get("ShippingAddressLine1"),
            "ShippingAddressLine2": r.get("ShippingAddressLine2"),
            "ShippingCity": r.get("ShippingCity"),
            "ShippingStateRegion": r.get("ShippingStateRegion"),
            "ShippingPostalCode": r.get("ShippingPostalCode"),
            "ShippingCountry": r.get("ShippingCountry"),
            "ShippingOfficeID": r.get("ShippingOfficeID"),
            "ShippingSavedGlobally": bool(r.get("ShippingSavedGlobally")),

            # 🔥 NEW (THIS WAS MISSING)
            "ShippingRecipientFirstName": r.get("ShippingRecipientFirstName"),
            "ShippingRecipientLastName": r.get("ShippingRecipientLastName"),
            "ShippingPhoneNumber": r.get("ShippingPhoneNumber"),

            # -------------------------
            # ADDRESS (OFFICE)
            # -------------------------
            "OfficeID": r.get("OfficeID"),
            "OfficeName": r.get("OfficeName"),

            # 🔥 NEW
            "IntlDialCode": r.get("IntlDialCode"),
        })

    return results

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