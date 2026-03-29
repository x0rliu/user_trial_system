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

    sort_column = ALLOWED_SORT_COLUMNS.get(sort, "pr.CreatedAt")

    direction = "ASC" if str(direction).lower() == "asc" else "DESC"

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

        if status and status != "all":
            conditions.append("pr.Status = %s")
            params.append(status)

        else:
            conditions.append(
                "pr.Status NOT IN ('completed','withdrawn','declined','cancelled')"
            )

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        # --------------------------------------------------
        # Sorting
        # --------------------------------------------------

        sql += f" ORDER BY {sort_column} {direction}"

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
    Unlock overview for a project round.
    Returns True if unlocked, False otherwise.
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

def get_round_surveys(round_id: int):

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT
                prs.RoundSurveyID AS SurveyID,
                prs.SurveyLink,
                prs.SurveyDistributionLink AS DistributionLink,
                prs.CreatedAt,
                prs.CreatedByUserID,
                st.SurveyTypeName,
                CONCAT(up.FirstName, ' ', up.LastName) AS CreatedBy
            FROM project_round_surveys prs
            JOIN survey_types st
                ON prs.SurveyTypeID = st.SurveyTypeID
            LEFT JOIN user_pool up
                ON prs.CreatedByUserID = up.user_id
            WHERE prs.RoundID = %s
              AND prs.IsActive = 1
            ORDER BY prs.CreatedAt DESC
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

        print("Rows affected:", cur.rowcount)

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
    - First two configured surveys mapped to Survey 1 / Survey 2
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # --------------------------------------------------
        # 1. Get first two surveys configured for this round
        # --------------------------------------------------
        cur.execute(
            """
            SELECT SurveyID, SurveyTypeID
            FROM survey_tracker
            WHERE RoundID = %s
            ORDER BY CreatedAt ASC
            LIMIT 2
            """,
            (round_id,),
        )

        configured_surveys = cur.fetchall()

        survey1_id = configured_surveys[0]["SurveyID"] if len(configured_surveys) > 0 else None
        survey2_id = configured_surveys[1]["SurveyID"] if len(configured_surveys) > 1 else None

        # --------------------------------------------------
        # 2. Pull participants
        # --------------------------------------------------
        cur.execute(
            """
            SELECT
                pp.ParticipantID,
                pp.user_id,
                pp.Notes,
                up.FirstName,
                up.LastName,
                nda.NDAStatus
            FROM project_participants pp
            JOIN user_pool up
                ON pp.user_id = up.user_id
            LEFT JOIN project_ndas nda
                ON nda.ParticipantID = pp.ParticipantID
            WHERE pp.RoundID = %s
            """,
            (round_id,),
        )

        participants_raw = cur.fetchall()

        participants = {}

        for r in participants_raw:
            pid = r["ParticipantID"]

            participants[pid] = {
                "ParticipantID": pid,
                "user_id": r["user_id"],
                "FirstName": r["FirstName"],
                "LastName": r["LastName"],
                "NDAComplete": r.get("NDAStatus") == "signed",
                "Survey1Complete": False,
                "Survey1Reminders": 0,
                "Survey2Complete": False,
                "Survey2Reminders": 0,
                "Notes": r.get("Notes"),
            }

        # --------------------------------------------------
        # 3. Pull survey distribution for those surveys
        # --------------------------------------------------
        if survey1_id or survey2_id:

            cur.execute(
                """
                SELECT
                    user_id,
                    SurveyID,
                    CompletedAt,
                    ReminderCount
                FROM survey_distribution
                WHERE RoundID = %s
                """,
                (round_id,),
            )

            dist_rows = cur.fetchall()

            # --------------------------------------------------
            # Build lookup by user_id (survey layer identity)
            # --------------------------------------------------
            participants_by_userid = {
                p["user_id"]: p
                for p in participants.values()
            }

            for d in dist_rows:

                uid = d.get("user_id")
                if not uid:
                    continue

                participant = participants_by_userid.get(uid)
                if not participant:
                    continue

                completed = bool(d.get("CompletedAt"))
                reminders = d.get("ReminderCount") or 0

                if survey1_id and d["SurveyID"] == survey1_id:
                    participant["Survey1Complete"] = completed
                    participant["Survey1Reminders"] = reminders

                if survey2_id and d["SurveyID"] == survey2_id:
                    participant["Survey2Complete"] = completed
                    participant["Survey2Reminders"] = reminders

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
    Lock the Wanted User Profile section.
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
                ProfileLockedBy = %s
            WHERE RoundID = %s
            """,
            (locked_by, round_id),
        )

        conn.commit()

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