# app/db/user_trial_lead.py

import mysql.connector
from app.config.config import DB_CONFIG
from app.db.round_stakeholders import get_round_stakeholders


def get_all_project_rounds_for_ut_lead(
    *,
    status: str | None = None,
    sort: str = "created",
    direction: str = "desc"
):
    """
    Returns project rounds for UT Lead visibility.

    Supports:
    - status filtering
    - column sorting
    - direction control

    Terminal rounds are hidden by default.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    # --------------------------------------------------
    # Allowed sorting columns (prevents SQL injection)
    # --------------------------------------------------

    ALLOWED_SORT_COLUMNS = {
        "created": "pr.CreatedAt",
        "start": "pr.StartDate",
        "ship": "pr.ShipDate",
        "round": "pr.RoundName",
        "users": "pr.TargetUsers",
        "region": "pr.Region",
    }

    safe_sort_key = str(sort or "created").strip().lower()
    sort_column = ALLOWED_SORT_COLUMNS.get(safe_sort_key, "pr.CreatedAt")

    safe_direction_key = str(direction or "desc").strip().lower()
    direction_sql = "ASC" if safe_direction_key == "asc" else "DESC"

    ALLOWED_STATUS_FILTERS = {
        "draft",
        "pending_review",
        "info_requested",
        "change_requested",
        "approved",
        "recruiting",
        "active",
        "completed",
        "withdrawn",
        "declined",
        "cancelled",
    }

    safe_status = str(status or "").strip().lower()
    if safe_status == "all":
        safe_status = "all"
    elif safe_status and safe_status not in ALLOWED_STATUS_FILTERS:
        raise ValueError("Invalid project round status filter")

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor(dictionary=True)

        # --------------------------------------------------
        # Base query
        # --------------------------------------------------

        sql = """
            SELECT
                pr.RoundID,
                pr.ProjectID,
                pr.RoundNumber,
                pr.RoundName,
                pr.Description,

                pr.StartDate,
                pr.EndDate,
                pr.ShipDate,
                pr.GateX_Date,

                pr.Region,
                pr.UserScope,
                pr.TargetUsers,

                pr.MinAge,
                pr.MaxAge,

                pr.PrototypeVersion,
                pr.ProductSKU,

                pr.UTLead_UserID,
                up.FirstName AS UTLead_FirstName,
                up.LastName  AS UTLead_LastName,

                pr.Status,

                pr.CreatedAt,
                pr.UpdatedAt

            FROM project_rounds pr

            LEFT JOIN user_pool up
                ON pr.UTLead_UserID = up.user_id
        """

        conditions = []
        params = []

        # --------------------------------------------------
        # Status filtering
        # --------------------------------------------------

        if safe_status and safe_status != "all":
            conditions.append("pr.Status = %s")
            params.append(safe_status)

        else:
            conditions.append(
                "pr.Status NOT IN ('completed','withdrawn','declined','cancelled')"
            )

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        # --------------------------------------------------
        # Sorting
        # --------------------------------------------------

        sql += f" ORDER BY {sort_column} {direction_sql}"

        # --------------------------------------------------
        # Execute
        # --------------------------------------------------

        cur.execute(sql, params)

        return cur.fetchall()

    finally:
        conn.close()

def get_project_round_by_id(round_id: str) -> dict | None:
    """
    Fetch a single project round by RoundID.
    Authoritative read-only source for UT Lead project details.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                -- Round Fields
                pr.RoundID,
                pr.ProjectID,
                pr.RoundNumber,
                pr.RoundName,
                pr.Description,

                pr.StartDate,
                pr.EndDate,
                pr.ShipDate,
                pr.GateX_Date,

                pr.Region,
                pr.UserScope,
                pr.TargetUsers,

                pr.MinAge,
                pr.MaxAge,

                pr.PrototypeVersion,
                pr.ProductSKU,

                pr.Status,
                pr.RecruitingStartDate,
                pr.RecruitingEndDate,
                pr.OverviewLocked,
                pr.OverviewLockedAt,
                pr.OverviewLockedBy,

                pr.ProfileLocked,
                pr.ProfileLockedAt,
                pr.ProfileLockedBy,

                pr.PlanningLocked,
                pr.PlanningLockedAt,
                pr.PlanningLockedBy,

                pr.UseExternalRecruitingSurvey,   -- 👈 ADD THIS LINE
                
                pr.CreatedAt,
                pr.UpdatedAt,

                -- UT Lead
                pr.UTLead_UserID,
                up.FirstName AS UTLead_FirstName,
                up.LastName  AS UTLead_LastName,

                -- Product Identity (Project-Level)
                pp.ProjectName,
                pp.MarketName,
                pp.BusinessGroup,
                pp.BusinessSubGroup,
                pp.ProductType,
                pp.Description AS ProjectDescription,
                pp.PRD_Document,
                pp.G1_Document,
                pp.G0_Document,
                pp.AdditionalDocs

            FROM project_rounds pr

            LEFT JOIN user_pool up
                ON pr.UTLead_UserID = up.user_id

            INNER JOIN project_projects pp
                ON pr.ProjectID = pp.ProjectID

            WHERE pr.RoundID = %s
            LIMIT 1
            """,
            (round_id,)
        )


        row = cur.fetchone()

        if row:
            # Attach round stakeholders
            row["Stakeholders"] = get_round_stakeholders(int(row["RoundID"]))

        return row

    finally:
        conn.close()

def update_project_round_overview(
    *,
    round_id: int,
    description: str | None,
    start_date: str | None,
    end_date: str | None,
    ship_date: str | None,
    region: str | None,
    user_scope: str | None,
    target_users: int | None,
    min_age: int | None,
    max_age: int | None,
    prototype_version: str | None,
    product_sku: str | None,
) -> bool:
    """
    Update editable overview fields for a project round.
    Enforced at DB layer: will NOT update if OverviewLocked = 1.
    Returns True if updated, False if blocked (locked or missing round).
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE project_rounds
            SET
                Description = %s,
                StartDate = %s,
                EndDate = %s,
                ShipDate = %s,
                Region = %s,
                UserScope = %s,
                TargetUsers = %s,
                MinAge = %s,
                MaxAge = %s,
                PrototypeVersion = %s,
                ProductSKU = %s,
                UpdatedAt = NOW()
            WHERE RoundID = %s
              AND OverviewLocked = 0
            """,
            (
                description,
                start_date,
                end_date,
                ship_date,
                region,
                user_scope,
                target_users,
                min_age,
                max_age,
                prototype_version,
                product_sku,
                round_id,
            ),
        )

        updated = cur.rowcount > 0
        if updated:
            conn.commit()
        else:
            conn.rollback()

        return updated

    finally:
        conn.close()


def lock_project_round_overview(
    *,
    round_id: int,
    locked_by_user_id: str,
) -> bool:
    """
    Lock overview section.
    DB-enforced: will only lock if not already locked.
    Returns True if lock applied, False if already locked or missing round.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE project_rounds
            SET
                OverviewLocked = 1,
                OverviewLockedAt = NOW(),
                OverviewLockedBy = %s,
                UpdatedAt = NOW()
            WHERE RoundID = %s
              AND OverviewLocked = 0
            """,
            (
                locked_by_user_id,
                round_id,
            ),
        )

        locked = cur.rowcount > 0
        if locked:
            conn.commit()
        else:
            conn.rollback()

        return locked

    finally:
        conn.close()

def unlock_project_round_overview(
    *,
    round_id: int,
) -> bool:
    """
    Reopen overview/details for a project round.
    Returns True if reopened, False otherwise.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE project_rounds
            SET
                OverviewLocked = 0,
                UpdatedAt = NOW()
            WHERE RoundID = %s
            """,
            (round_id,),
        )

        updated = cur.rowcount > 0
        if updated:
            conn.commit()
        else:
            conn.rollback()

        return updated

    finally:
        conn.close()


def unlock_project_round_planning(
    *,
    round_id: int,
) -> bool:
    """
    Reopen survey setup/planning for a project round.
    Returns True if reopened, False otherwise.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE project_rounds
            SET
                PlanningLocked = 0,
                UpdatedAt = NOW()
            WHERE RoundID = %s
            """,
            (round_id,),
        )

        updated = cur.rowcount > 0
        if updated:
            conn.commit()
        else:
            conn.rollback()

        return updated

    finally:
        conn.close()

def get_round_surveys(round_id: int):

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT
                prs.RoundSurveyID AS SurveyID,
                prs.RoundSurveyID AS RoundSurveyID,
                prs.RoundID,
                prs.SurveyTypeID,
                prs.SurveyLink,
                prs.SurveyDistributionLink AS DistributionLink,
                prs.CreatedAt,
                prs.CreatedByUserID,
                st.SurveyTypeName,
                st.SurveyDescription,
                CONCAT(up.FirstName, ' ', up.LastName) AS CreatedBy
            FROM project_round_surveys prs
            JOIN survey_types st
                ON prs.SurveyTypeID = st.SurveyTypeID
            LEFT JOIN user_pool up
                ON prs.CreatedByUserID = up.user_id
            WHERE prs.RoundID = %s
              AND prs.IsActive = 1
            ORDER BY prs.CreatedAt ASC, prs.RoundSurveyID ASC
        """, (round_id,))

        return cur.fetchall()

    finally:
        conn.close()

def add_round_survey(
    *,
    round_id: int,
    survey_type_id: str,
    survey_link: str,
    distribution_link: str | None,
    created_by_user_id: str,
) -> bool:
    """
    Insert survey link only if PlanningLocked = 0.
    Returns True if inserted, False if blocked.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO project_round_surveys
                (RoundID, SurveyTypeID, SurveyLink, SurveyDistributionLink, CreatedByUserID)
            SELECT %s, %s, %s, %s, %s
            FROM project_rounds
            WHERE RoundID = %s
            AND PlanningLocked = 0
            """,
            (
                round_id,
                survey_type_id,
                survey_link,
                distribution_link,      # ✅ this was missing
                created_by_user_id,
                round_id,
            ),
        )

        inserted = cur.rowcount > 0

        if inserted:
            conn.commit()
        else:
            conn.rollback()

        return inserted

    finally:
        conn.close()


def lock_project_round_planning(
    *,
    round_id: int,
    locked_by_user_id: str,
):
    """
    Lock planning section.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE project_rounds
            SET
                PlanningLocked = 1,
                PlanningLockedAt = NOW(),
                PlanningLockedBy = %s,
                UpdatedAt = NOW()
            WHERE RoundID = %s
              AND PlanningLocked = 0
            """,
            (
                locked_by_user_id,
                round_id,
            ),
        )

        conn.commit()

    finally:
        conn.close()

# --------------------------------------------------
# Survey Types (Static Lookup)
# --------------------------------------------------

def get_survey_types() -> list[dict]:
    """
    Return all available survey types.
    Used to populate planning dropdown.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                SurveyTypeID,
                SurveyTypeName,
                SurveyDescription
            FROM survey_types
            ORDER BY SurveyTypeName ASC
            """
        )

        return cur.fetchall()

    finally:
        conn.close()


def get_round_participants(round_id: int) -> list[dict]:
    """
    Return participants assigned to a round with:
    - NDA status
    - dynamic configured result-survey completion/reminder state

    DB source of truth:
    - project_participants owns membership
    - project_ndas owns NDA status
    - project_round_surveys owns configured round surveys
    - survey_distribution owns per-user survey completion/reminder rows
    """

    excluded_survey_type_ids = {
        "UTSurveyType0001",  # Recruiting
        "UTSurveyType0027",  # Consolidated/internal results
        "UTSurveyType0028",  # Report issue; not completion-gated
    }

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # --------------------------------------------------
        # 1. Get configured participant result surveys
        # --------------------------------------------------
        cur.execute(
            """
            SELECT
                prs.RoundSurveyID,
                prs.SurveyTypeID,
                prs.CreatedAt,
                st.SurveyTypeName,
                st.SurveyDescription
            FROM project_round_surveys prs
            JOIN survey_types st
                ON prs.SurveyTypeID = st.SurveyTypeID
            WHERE prs.RoundID = %s
              AND prs.IsActive = 1
            ORDER BY prs.CreatedAt ASC, prs.RoundSurveyID ASC
            """,
            (round_id,),
        )

        configured_surveys = []
        for survey in cur.fetchall():
            survey_type_id = survey.get("SurveyTypeID")
            survey_type_name = (survey.get("SurveyTypeName") or "").strip()
            normalized_name = survey_type_name.lower()

            if survey_type_id in excluded_survey_type_ids:
                continue
            if normalized_name in ("recruiting", "consolidated", "report_issue"):
                continue

            configured_surveys.append({
                "RoundSurveyID": survey.get("RoundSurveyID"),
                "SurveyTypeID": survey_type_id,
                "SurveyTypeName": survey_type_name or "Survey",
                "SurveyDescription": survey.get("SurveyDescription") or "",
            })

        # --------------------------------------------------
        # 2. Pull participants
        # --------------------------------------------------
        cur.execute(
            """
            SELECT
                pp.ParticipantID,
                pp.user_id,
                pp.Notes,
                pp.DeliveryType,
                pp.ShippingAddressConfirmedAt,
                pp.ResponsibilitiesAcceptedAt,
                pp.Courier,
                pp.TrackingNumber,
                pp.TrackingURL,
                pp.ShippedAt,
                pp.DeliveredAt,
                pp.DeviceReceivedConfirmedAt,
                pp.ParticipantStatus,
                pp.CompletedAt,
                pp.ShippingAddressLine1,
                pp.ShippingAddressLine2,
                pp.ShippingCity,
                pp.ShippingStateRegion,
                pp.ShippingPostalCode,
                pp.ShippingCountry,
                pp.ShippingOfficeID,
                pp.ShippingRecipientFirstName,
                pp.ShippingRecipientLastName,
                pp.ShippingPhoneNumber,
                up.Email,
                up.FirstName,
                up.LastName,
                nda.NDAStatus
            FROM project_participants pp
            JOIN user_pool up
                ON pp.user_id = up.user_id
            LEFT JOIN project_ndas nda
                ON nda.user_id = pp.user_id
                AND nda.RoundID = pp.RoundID
            WHERE pp.RoundID = %s
            ORDER BY up.FirstName ASC, up.LastName ASC, pp.ParticipantID ASC
            """,
            (round_id,),
        )

        participants_raw = cur.fetchall()

        participants = {}

        for r in participants_raw:
            pid = r["ParticipantID"]

            survey_states = []
            for survey in configured_surveys:
                survey_states.append({
                    "RoundSurveyID": survey.get("RoundSurveyID"),
                    "SurveyTypeID": survey.get("SurveyTypeID"),
                    "SurveyTypeName": survey.get("SurveyTypeName") or "Survey",
                    "SurveyDescription": survey.get("SurveyDescription") or "",
                    "Complete": False,
                    "ReminderCount": 0,
                })

            participants[pid] = {
                "ParticipantID": pid,
                "user_id": r["user_id"],
                "FirstName": r["FirstName"],
                "LastName": r["LastName"],
                "Email": r.get("Email"),
                "NDAComplete": (r.get("NDAStatus") or "").strip().lower() == "signed",
                "Surveys": survey_states,
                "Survey1Complete": False,
                "Survey1Reminders": 0,
                "Survey2Complete": False,
                "Survey2Reminders": 0,
                "DeliveryType": r.get("DeliveryType"),
                "ShippingAddressConfirmedAt": r.get("ShippingAddressConfirmedAt"),
                "ResponsibilitiesAcceptedAt": r.get("ResponsibilitiesAcceptedAt"),
                "Courier": r.get("Courier"),
                "TrackingNumber": r.get("TrackingNumber"),
                "TrackingURL": r.get("TrackingURL"),
                "ShippedAt": r.get("ShippedAt"),
                "DeliveredAt": r.get("DeliveredAt"),
                "DeviceReceivedConfirmedAt": r.get("DeviceReceivedConfirmedAt"),
                "ParticipantStatus": r.get("ParticipantStatus"),
                "CompletedAt": r.get("CompletedAt"),
                "ShippingAddressLine1": r.get("ShippingAddressLine1"),
                "ShippingAddressLine2": r.get("ShippingAddressLine2"),
                "ShippingCity": r.get("ShippingCity"),
                "ShippingStateRegion": r.get("ShippingStateRegion"),
                "ShippingPostalCode": r.get("ShippingPostalCode"),
                "ShippingCountry": r.get("ShippingCountry"),
                "ShippingOfficeID": r.get("ShippingOfficeID"),
                "ShippingRecipientFirstName": r.get("ShippingRecipientFirstName"),
                "ShippingRecipientLastName": r.get("ShippingRecipientLastName"),
                "ShippingPhoneNumber": r.get("ShippingPhoneNumber"),
                "Notes": r.get("Notes"),
            }

        # --------------------------------------------------
        # 3. Pull survey distribution for the configured survey types
        # --------------------------------------------------
        if configured_surveys and participants:

            cur.execute(
                """
                SELECT
                    user_id,
                    SurveyID,
                    SurveyTypeID,
                    CompletedAt,
                    ReminderCount
                FROM survey_distribution
                WHERE RoundID = %s
                """,
                (round_id,),
            )

            dist_rows = cur.fetchall()

            dist_by_user_and_type = {}
            for d in dist_rows:
                uid = d.get("user_id")
                survey_type_id = d.get("SurveyTypeID")
                if not uid or not survey_type_id:
                    continue

                key = (uid, survey_type_id)
                existing = dist_by_user_and_type.get(key)

                completed = bool(d.get("CompletedAt"))
                reminders = int(d.get("ReminderCount") or 0)

                if not existing:
                    dist_by_user_and_type[key] = {
                        "Complete": completed,
                        "ReminderCount": reminders,
                    }
                    continue

                existing["Complete"] = bool(existing.get("Complete")) or completed
                existing["ReminderCount"] = max(
                    int(existing.get("ReminderCount") or 0),
                    reminders,
                )

            participants_by_userid = {
                p["user_id"]: p
                for p in participants.values()
            }

            for uid, participant in participants_by_userid.items():
                for idx, survey in enumerate(participant.get("Surveys") or []):
                    dist_state = dist_by_user_and_type.get((uid, survey.get("SurveyTypeID")))
                    if not dist_state:
                        continue

                    survey["Complete"] = bool(dist_state.get("Complete"))
                    survey["ReminderCount"] = int(dist_state.get("ReminderCount") or 0)

                # Preserve legacy first/second keys for older call sites while
                # the UT Lead project renderer uses Surveys[].
                if len(participant.get("Surveys") or []) > 0:
                    participant["Survey1Complete"] = bool(participant["Surveys"][0].get("Complete"))
                    participant["Survey1Reminders"] = int(participant["Surveys"][0].get("ReminderCount") or 0)

                if len(participant.get("Surveys") or []) > 1:
                    participant["Survey2Complete"] = bool(participant["Surveys"][1].get("Complete"))
                    participant["Survey2Reminders"] = int(participant["Surveys"][1].get("ReminderCount") or 0)

        return list(participants.values())

    finally:
        conn.close()

# --------------------------------------------------
# Round Profile Criteria
# --------------------------------------------------

def get_round_profile_criteria(round_id: int):
    from app.db.connection import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT rpc.RoundCriteriaID,
               rpc.ProfileUID,
               rpc.Operator,
               up.CategoryName,
               up.LevelDescription,
               up.ProfileCode
        FROM round_profile_criteria rpc
        JOIN user_profiles up
            ON rpc.ProfileUID = up.ProfileUID
        WHERE rpc.RoundID = %s
        ORDER BY up.CategoryName ASC
    """, (round_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def update_round_participant_tracking_from_rows(*, round_id: int, tracking_rows: list[dict]) -> dict:
    """
    Update participant shipping tracking for one round from normalized CSV rows.

    Matching is by user_pool.Email. Existing non-empty DB values are preserved
    when a CSV cell is blank. UT Lead uploads write to the canonical participant
    logistics fields; future Product Team imports should not overwrite non-empty
    canonical values unless explicitly designed to do so.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    summary = {
        "total_rows": 0,
        "updated_rows": 0,
        "unmatched_rows": 0,
        "missing_email_rows": 0,
        "ignored_rows": 0,
    }

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                pp.ParticipantID,
                pp.Courier,
                pp.TrackingNumber,
                pp.TrackingURL,
                pp.ShippedAt,
                pp.DeliveredAt,
                up.Email
            FROM project_participants pp
            JOIN user_pool up
                ON up.user_id = pp.user_id
            WHERE pp.RoundID = %s
            """,
            (round_id,),
        )

        participants_by_email = {
            str(row.get("Email") or "").strip().lower(): row
            for row in cur.fetchall()
            if str(row.get("Email") or "").strip()
        }

        for row in tracking_rows or []:
            summary["total_rows"] += 1

            email = str(row.get("email") or "").strip().lower()
            if not email:
                summary["missing_email_rows"] += 1
                continue

            participant = participants_by_email.get(email)
            if not participant:
                summary["unmatched_rows"] += 1
                continue

            csv_tracking_number = str(row.get("tracking_number") or "").strip()
            if not csv_tracking_number:
                summary["ignored_rows"] += 1
                continue

            courier = str(row.get("courier") or "Unknown").strip() or "Unknown"
            tracking_number = csv_tracking_number
            tracking_url = str(row.get("tracking_url") or "").strip()

            cur.execute(
                """
                UPDATE project_participants
                SET
                    Courier = %s,
                    TrackingNumber = %s,
                    TrackingURL = %s,
                    CarrierStatus = CASE
                        WHEN %s IS NOT NULL AND %s <> '' THEN 'shipping'
                        ELSE CarrierStatus
                    END,
                    CarrierStatusLabel = CASE
                        WHEN %s IS NOT NULL AND %s <> '' THEN 'Tracking uploaded'
                        ELSE CarrierStatusLabel
                    END,
                    CarrierEstimatedDeliveryAt = NULL,
                    CarrierDeliveredAt = NULL,
                    CarrierSignedBy = NULL,
                    CarrierLastCheckedAt = NULL,
                    CarrierStatusRawJSON = NULL,
                    DeviceReceiptProblemReportedAt = NULL,
                    DeviceReceiptProblemResolvedAt = NULL,
                    DeviceReceiptProblemNote = NULL,
                    ShippedAt = COALESCE(
                        ShippedAt,
                        CASE
                            WHEN %s IS NOT NULL AND %s <> '' THEN NOW()
                            ELSE ShippedAt
                        END
                    ),
                    UpdatedAt = NOW()
                WHERE ParticipantID = %s
                  AND RoundID = %s
                """,
                (
                    courier,
                    tracking_number,
                    tracking_url,
                    tracking_number,
                    tracking_number,
                    tracking_number,
                    tracking_number,
                    tracking_number,
                    tracking_number,
                    participant["ParticipantID"],
                    round_id,
                ),
            )

            if cur.rowcount > 0:
                summary["updated_rows"] += 1

        conn.commit()
        return summary

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def add_round_profile_criteria(round_id: int, profile_uid: str, operator: str):
    from app.db.connection import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO round_profile_criteria
            (RoundID, ProfileUID, Operator)
        VALUES (%s, %s, %s)
    """, (round_id, profile_uid, operator))

    conn.commit()
    cursor.close()
    conn.close()


def delete_round_profile_criteria(round_id: int, criteria_id: int):
    from app.db.connection import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM round_profile_criteria
        WHERE RoundID = %s AND RoundCriteriaID = %s
    """, (round_id, criteria_id))

    conn.commit()
    cursor.close()
    conn.close()


def lock_project_round_profile(*, round_id: int, locked_by: str):
    """
    Confirm the Wanted User Profile section.
    """
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE project_rounds
            SET
                ProfileLocked = 1,
                ProfileLockedAt = NOW(),
                ProfileLockedBy = %s,
                UpdatedAt = NOW()
            WHERE RoundID = %s
            """,
            (locked_by, round_id),
        )

        conn.commit()

    finally:
        conn.close()


def unlock_project_round_profile(*, round_id: int) -> bool:
    """
    Reopen the Wanted User Profile section.
    Returns True if reopened, False otherwise.
    """
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE project_rounds
            SET
                ProfileLocked = 0,
                UpdatedAt = NOW()
            WHERE RoundID = %s
            """,
            (round_id,),
        )

        updated = cur.rowcount > 0
        if updated:
            conn.commit()
        else:
            conn.rollback()

        return updated

    finally:
        conn.close()


def update_recruiting_config(
    *,
    round_id: int,
    use_external: bool,
) -> None:

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE project_rounds
            SET UseExternalRecruitingSurvey = %s
            WHERE RoundID = %s
            """,
            (1 if use_external else 0, round_id),
        )

        conn.commit()

    finally:
        conn.close()


def delete_round_survey(
    *,
    round_id: int,
    survey_id: int,
) -> None:

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE project_round_surveys
            SET IsActive = 0
            WHERE RoundID = %s
              AND RoundSurveyID = %s
            """,
            (round_id, survey_id),
        )

        conn.commit()

    finally:
        conn.close()
    

def get_round_surveys_basic_stats(round_id: int) -> list[dict]:

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                st.SurveyID,
                COUNT(sa.AnswerID) AS total_answers,
                COUNT(DISTINCT sa.user_id) AS completed_count
            FROM survey_tracker st
            LEFT JOIN survey_answers sa
                ON st.SurveyID = sa.SurveyID
            WHERE st.RoundID = %s
            GROUP BY st.SurveyID
            """,
            (round_id,)
        )

        rows = cur.fetchall()

        # Attach total_participants from distribution
        for row in rows:

            cur.execute(
                """
                SELECT COUNT(*) AS total_participants
                FROM survey_distribution
                WHERE RoundID = %s
                AND SurveyID = %s
                """,
                (round_id, row["SurveyID"])
            )

            result = cur.fetchone()
            row["total_participants"] = result["total_participants"] if result else 0

        return rows

    finally:
        conn.close()

def add_round_profile_criteria(round_id: int, profile_uid: str, operator: str):
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO round_profile_criteria (RoundID, ProfileUID, Operator)
                SELECT %s, %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM round_profile_criteria
                    WHERE RoundID = %s AND ProfileUID = %s AND Operator = %s
                )
                """,
                (round_id, profile_uid, operator,
                round_id, profile_uid, operator),
            )
        conn.commit()
    finally:
        conn.close()


def remove_round_profile_criteria(round_id: int, profile_uid: str):
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM round_profile_criteria
                WHERE RoundID = %s AND ProfileUID = %s
                """,
                (round_id, profile_uid),
            )
        conn.commit()
    finally:
        conn.close()