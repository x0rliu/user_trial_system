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


def _ut_lead_dashboard_as_date(value):
    from datetime import datetime

    if value in (None, "", "0000-00-00"):
        return None

    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value.date() if hasattr(value, "hour") else value

    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except Exception:
        return None


def _derive_ut_lead_dashboard_lifecycle(row: dict) -> str:
    from datetime import date, timedelta

    today = date.today()
    planning_window_end = today + timedelta(days=42)

    raw_status = str(row.get("Status") or "").strip().lower()
    start_date = _ut_lead_dashboard_as_date(row.get("StartDate"))
    ship_date = _ut_lead_dashboard_as_date(row.get("ShipDate"))

    if raw_status in {"closed", "completed", "withdrawn", "declined", "cancelled"}:
        return "terminal"

    if raw_status in {"recruiting", "screening", "active", "running"}:
        return "current"

    if start_date and start_date <= today:
        return "current"

    if raw_status in {"pending_ut_review", "info_requested", "change_requested"}:
        return "planning"

    if ship_date and ship_date <= planning_window_end:
        return "planning"

    if start_date or ship_date:
        return "upcoming"

    return "planning"


def _ut_lead_dashboard_status_label(row: dict) -> str:
    status_map = {
        "pending_ut_review": "Pending UT review",
        "info_requested": "Info requested",
        "change_requested": "Changes requested",
        "approved": "Approved",
        "recruiting": "Recruiting",
        "screening": "Screening",
        "active": "Active",
        "running": "In progress",
        "completed": "Completed",
        "closed": "Closed",
    }

    raw_status = str(row.get("Status") or "").strip().lower()
    return status_map.get(raw_status, raw_status.replace("_", " ").title() or "Current")


def _derive_ut_lead_dashboard_action(row: dict) -> str:
    raw_status = str(row.get("Status") or "").strip().lower()
    lifecycle = row.get("dashboard_lifecycle") or _derive_ut_lead_dashboard_lifecycle(row)

    participant_count = int(row.get("ParticipantCount") or 0)
    shipped_count = int(row.get("ShippedCount") or 0)
    active_survey_count = int(row.get("ActiveSurveyCount") or 0)
    activated_survey_count = int(row.get("ActivatedSurveyCount") or 0)

    if raw_status == "pending_ut_review":
        return "Review request and approve or ask for changes."

    if raw_status in {"info_requested", "change_requested"}:
        return "Wait for Product Team updates."

    if not row.get("OverviewLocked"):
        return "Lock project details."

    if not row.get("ProfileLocked"):
        return "Lock wanted user profile."

    if not row.get("PlanningLocked"):
        return "Add and lock survey links."

    if raw_status == "approved":
        if lifecycle == "upcoming":
            return "Monitor launch timing."
        return "Open recruiting when ready."

    if raw_status == "recruiting":
        if row.get("RecruitingEndDate"):
            return "Finalize user selection."
        return "Monitor applicants and close recruiting when ready."

    if raw_status == "screening":
        return "Finalize selected participants."

    if raw_status in {"active", "running"}:
        if participant_count == 0:
            return "Select participants."
        if shipped_count < participant_count:
            return "Ship remaining devices."
        if active_survey_count == 0:
            return "Add active survey links."
        if activated_survey_count < active_survey_count:
            return "Activate the next participant survey."
        return "Monitor survey completion and participant support."

    if lifecycle == "planning":
        return "Complete planning checklist."

    if lifecycle == "upcoming":
        return "No immediate action; monitor timing."

    return "No immediate action."


def _format_ut_lead_dashboard_progress(row: dict) -> str:
    participant_count = int(row.get("ParticipantCount") or 0)
    shipped_count = int(row.get("ShippedCount") or 0)
    active_survey_count = int(row.get("ActiveSurveyCount") or 0)
    activated_survey_count = int(row.get("ActivatedSurveyCount") or 0)

    progress_parts = []

    if participant_count:
        progress_parts.append(f"{participant_count} selected")

    if shipped_count or participant_count:
        progress_parts.append(f"{shipped_count}/{participant_count} shipped")

    if active_survey_count:
        progress_parts.append(f"{activated_survey_count}/{active_survey_count} surveys active")

    if not progress_parts:
        if row.get("ShipDate"):
            progress_parts.append(f"Ships {row.get('ShipDate')}")
        elif row.get("StartDate"):
            progress_parts.append(f"Starts {row.get('StartDate')}")
        else:
            progress_parts.append("Setup not complete")

    return " · ".join(progress_parts)


def _normalize_ut_lead_dashboard_row(row: dict) -> dict:
    normalized = dict(row or {})
    lifecycle = _derive_ut_lead_dashboard_lifecycle(normalized)

    normalized["dashboard_lifecycle"] = lifecycle
    normalized["dashboard_status_label"] = _ut_lead_dashboard_status_label(normalized)
    normalized["dashboard_progress"] = _format_ut_lead_dashboard_progress(normalized)
    normalized["dashboard_current_action"] = _derive_ut_lead_dashboard_action(normalized)

    return normalized


def _sort_ut_lead_dashboard_rows(rows: list[dict]) -> list[dict]:
    def sort_key(row: dict):
        next_date = (
            _ut_lead_dashboard_as_date(row.get("StartDate"))
            or _ut_lead_dashboard_as_date(row.get("ShipDate"))
            or _ut_lead_dashboard_as_date(row.get("UpdatedAt"))
        )

        return (
            next_date is None,
            next_date,
            str(row.get("ProjectName") or row.get("RoundName") or ""),
        )

    return sorted(rows, key=sort_key)


def _bonus_survey_status_label(row: dict) -> str:
    tracker_state = str(row.get("current_state") or "").strip().lower()
    survey_status = str(row.get("status") or "").strip().lower()

    if tracker_state == "changes_requested":
        return "Changes requested"
    if tracker_state == "pending" or survey_status == "pending_approval":
        return "Pending approval"
    if survey_status == "active" and int(row.get("is_open") or 0) == 1:
        return "Active"
    if survey_status == "active" and int(row.get("is_open") or 0) == 0:
        return "Closed"
    if survey_status == "archived":
        return "Archived"

    return survey_status.replace("_", " ").title() or "Assigned"


def _bonus_survey_progress_label(row: dict) -> str:
    total_count = int(row.get("ParticipantCount") or 0)
    completed_count = int(row.get("CompletedCount") or 0)

    if total_count:
        return f"{completed_count}/{total_count} responses"

    if row.get("close_at"):
        return f"Closes {row.get('close_at')}"

    if row.get("open_at"):
        return f"Opens {row.get('open_at')}"

    return "No responses tracked"


def _bonus_survey_action_label(row: dict) -> str:
    tracker_state = str(row.get("current_state") or "").strip().lower()
    survey_status = str(row.get("status") or "").strip().lower()
    is_open = int(row.get("is_open") or 0) == 1

    if tracker_state == "pending" or survey_status == "pending_approval":
        return "Review survey setup."

    if tracker_state == "changes_requested":
        return "Review requested changes."

    if survey_status == "active" and is_open:
        return "Monitor responses."

    if survey_status == "active" and not is_open:
        return "Prepare or review readout."

    if survey_status == "archived":
        return "No immediate action."

    return "Check survey status."


def _normalize_assigned_bonus_survey_row(row: dict) -> dict:
    normalized = dict(row or {})
    normalized["dashboard_status_label"] = _bonus_survey_status_label(normalized)
    normalized["dashboard_progress"] = _bonus_survey_progress_label(normalized)
    normalized["dashboard_current_action"] = _bonus_survey_action_label(normalized)
    return normalized


def get_ut_lead_dashboard_summary(user_id: str) -> dict:
    """
    Return dashboard-ready UT Lead trial and assigned Bonus Survey summary.

    UT Lead assignment is DB-scoped here so the dashboard handler does not
    invent visibility rules while rendering cards.
    """

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                pr.RoundID,
                pr.ProjectID,
                pr.RoundNumber,
                pr.RoundName,
                pr.StartDate,
                pr.EndDate,
                pr.ShipDate,
                pr.GateX_Date,
                pr.Region,
                pr.TargetUsers,
                pr.UTLead_UserID,
                pr.Status,
                pr.RecruitingStartDate,
                pr.RecruitingEndDate,
                pr.OverviewLocked,
                pr.ProfileLocked,
                pr.PlanningLocked,
                pr.CreatedAt,
                pr.UpdatedAt,

                pp.ProjectName,
                pp.MarketName,
                pp.ProductType,
                pp.BusinessGroup,

                NULLIF(
                    TRIM(CONCAT(
                        COALESCE(up.FirstName, ''),
                        ' ',
                        COALESCE(up.LastName, '')
                    )),
                    ''
                ) AS UTLeadName,

                COALESCE(participant_stats.ParticipantCount, 0) AS ParticipantCount,
                COALESCE(participant_stats.ShippingConfirmedCount, 0) AS ShippingConfirmedCount,
                COALESCE(participant_stats.ShippedCount, 0) AS ShippedCount,
                COALESCE(participant_stats.DeviceReceivedCount, 0) AS DeviceReceivedCount,
                COALESCE(survey_stats.ActiveSurveyCount, 0) AS ActiveSurveyCount,
                COALESCE(survey_stats.ActivatedSurveyCount, 0) AS ActivatedSurveyCount

            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            LEFT JOIN user_pool up
                ON up.user_id = pr.UTLead_UserID
            LEFT JOIN (
                SELECT
                    RoundID,
                    COUNT(*) AS ParticipantCount,
                    SUM(CASE WHEN ShippingAddressConfirmedAt IS NOT NULL THEN 1 ELSE 0 END) AS ShippingConfirmedCount,
                    SUM(CASE WHEN ShippedAt IS NOT NULL OR DeliveredAt IS NOT NULL THEN 1 ELSE 0 END) AS ShippedCount,
                    SUM(CASE WHEN DeviceReceivedConfirmedAt IS NOT NULL THEN 1 ELSE 0 END) AS DeviceReceivedCount
                FROM project_participants
                GROUP BY RoundID
            ) participant_stats
                ON participant_stats.RoundID = pr.RoundID
            LEFT JOIN (
                SELECT
                    RoundID,
                    COUNT(*) AS ActiveSurveyCount,
                    SUM(CASE WHEN ParticipantActivatedAt IS NOT NULL THEN 1 ELSE 0 END) AS ActivatedSurveyCount
                FROM project_round_surveys
                WHERE IsActive = 1
                GROUP BY RoundID
            ) survey_stats
                ON survey_stats.RoundID = pr.RoundID

            WHERE pr.Status NOT IN ('closed', 'completed', 'withdrawn', 'declined', 'cancelled')

            ORDER BY
                CASE
                    WHEN pr.Status IN ('active', 'running') THEN 1
                    WHEN pr.Status = 'screening' THEN 2
                    WHEN pr.Status = 'recruiting' THEN 3
                    WHEN pr.Status IN ('pending_ut_review', 'info_requested', 'change_requested') THEN 4
                    WHEN pr.Status = 'approved' THEN 5
                    ELSE 6
                END,
                COALESCE(pr.StartDate, pr.ShipDate, DATE(pr.UpdatedAt), DATE(pr.CreatedAt)) ASC,
                pp.ProjectName ASC
            """
        )

        trial_rows = [
            _normalize_ut_lead_dashboard_row(row)
            for row in (cur.fetchall() or [])
        ]

        my_rows = [
            row
            for row in trial_rows
            if str(row.get("UTLead_UserID") or "") == str(user_id)
        ]

        my_current = _sort_ut_lead_dashboard_rows([
            row for row in my_rows
            if row.get("dashboard_lifecycle") == "current"
        ])
        my_planning = _sort_ut_lead_dashboard_rows([
            row for row in my_rows
            if row.get("dashboard_lifecycle") == "planning"
        ])
        my_upcoming = _sort_ut_lead_dashboard_rows([
            row for row in my_rows
            if row.get("dashboard_lifecycle") == "upcoming"
        ])
        team_current = _sort_ut_lead_dashboard_rows([
            row for row in trial_rows
            if row.get("dashboard_lifecycle") == "current"
        ])
        team_planning = _sort_ut_lead_dashboard_rows([
            row for row in trial_rows
            if row.get("dashboard_lifecycle") == "planning"
        ])

        cur.execute(
            """
            SELECT
                bs.bonus_survey_id,
                bs.survey_title,
                bs.open_at,
                bs.close_at,
                bs.status,
                bs.is_open,
                bs.created_at,
                bs.updated_at,
                bst.tracker_id,
                bst.current_state,
                assignment.AssignedUTLeadID,
                assignment.CreatedAt AS AssignedAt,

                NULLIF(
                    TRIM(CONCAT(
                        COALESCE(owner.FirstName, ''),
                        ' ',
                        COALESCE(owner.LastName, '')
                    )),
                    ''
                ) AS CreatedByName,

                COALESCE(participation_stats.ParticipantCount, 0) AS ParticipantCount,
                COALESCE(participation_stats.CompletedCount, 0) AS CompletedCount,
                COALESCE(participation_stats.NeedsReviewCount, 0) AS NeedsReviewCount

            FROM bonus_surveys bs
            JOIN bonus_survey_tracker bst
                ON bst.survey_id = bs.bonus_survey_id
            JOIN approval_actions assignment
                ON assignment.ApprovalType = 'bonus_survey'
               AND CAST(assignment.ApprovalID AS UNSIGNED) = bst.tracker_id
               AND assignment.AssignedUTLeadID = %s
               AND assignment.CreatedAt = (
                    SELECT MAX(a2.CreatedAt)
                    FROM approval_actions a2
                    WHERE a2.ApprovalType = 'bonus_survey'
                      AND a2.ApprovalID = assignment.ApprovalID
                      AND a2.AssignedUTLeadID IS NOT NULL
               )
            LEFT JOIN user_pool owner
                ON owner.user_id = bs.created_by_user_id
            LEFT JOIN (
                SELECT
                    bonus_survey_id,
                    COUNT(*) AS ParticipantCount,
                    SUM(CASE WHEN completed_at IS NOT NULL THEN 1 ELSE 0 END) AS CompletedCount,
                    SUM(CASE WHEN needs_review = 1 THEN 1 ELSE 0 END) AS NeedsReviewCount
                FROM bonus_survey_participation
                GROUP BY bonus_survey_id
            ) participation_stats
                ON participation_stats.bonus_survey_id = bs.bonus_survey_id
            WHERE bs.status IN ('pending_approval', 'approved', 'active', 'archived')
            ORDER BY
                CASE
                    WHEN bs.status = 'pending_approval' THEN 1
                    WHEN bs.status = 'approved' THEN 2
                    WHEN bs.status = 'active' AND bs.is_open = 1 THEN 3
                    WHEN bs.status = 'active' AND bs.is_open = 0 THEN 4
                    ELSE 5
                END,
                COALESCE(bs.close_at, bs.open_at, bs.updated_at, bs.created_at) ASC,
                bs.survey_title ASC
            """,
            (user_id,),
        )

        assigned_bsc_surveys = [
            _normalize_assigned_bonus_survey_row(row)
            for row in (cur.fetchall() or [])
        ]

        return {
            "my_current": my_current,
            "my_planning": my_planning,
            "my_upcoming": my_upcoming,
            "team_current": team_current,
            "team_planning": team_planning,
            "assigned_bsc_surveys": assigned_bsc_surveys,
            "counts": {
                "my_current": len(my_current),
                "my_planning": len(my_planning),
                "my_upcoming": len(my_upcoming),
                "team_current": len(team_current),
                "team_planning": len(team_planning),
                "assigned_bsc_surveys": len(assigned_bsc_surveys),
            },
        }

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
                prs.ParticipantActivatedAt,
                prs.ParticipantActivatedByUserID,
                prs.ParticipantActivationNotificationSentAt,
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
                prs.ParticipantActivatedAt,
                prs.ParticipantActivatedByUserID,
                prs.ParticipantActivationNotificationSentAt,
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
                "ParticipantActivatedAt": survey.get("ParticipantActivatedAt"),
                "ParticipantActivatedByUserID": survey.get("ParticipantActivatedByUserID"),
                "ParticipantActivationNotificationSentAt": survey.get("ParticipantActivationNotificationSentAt"),
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
                    "ParticipantActivatedAt": survey.get("ParticipantActivatedAt"),
                    "ParticipantActivatedByUserID": survey.get("ParticipantActivatedByUserID"),
                    "ParticipantActivationNotificationSentAt": survey.get("ParticipantActivationNotificationSentAt"),
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
               rpc.MatchMode,
               rpc.PriorityRank,
               rpc.WeightPercent,
               rpc.CriteriaLabel,
               rpc.IsActive,
               up.CategoryID,
               up.CategoryName,
               up.LevelDescription,
               up.ProfileCode
        FROM round_profile_criteria rpc
        JOIN user_profiles up
            ON rpc.ProfileUID = up.ProfileUID
        WHERE rpc.RoundID = %s
          AND rpc.IsActive = 1
        ORDER BY
            rpc.MatchMode ASC,
            rpc.PriorityRank ASC,
            up.CategoryName ASC,
            up.LevelDescription ASC
    """, (round_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def _refresh_round_profile_criteria_weights(round_id: int):
    """
    Recalculate and persist WeightPercent for active WEIGHTED criteria.

    This keeps the DB auditable while preserving PriorityRank as the
    user-editable source field.
    """

    from app.db.connection import get_db_connection
    from app.services.selection_weight_service import calculate_weighted_profile_percent

    criteria_rows = get_round_profile_criteria(round_id)
    weighted_rows = calculate_weighted_profile_percent(criteria_rows)

    weighted_ids = set()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        for row in weighted_rows:
            criteria_id = row.get("RoundCriteriaID")
            weight_percent = row.get("WeightPercent")

            if not criteria_id:
                continue

            weighted_ids.add(criteria_id)

            cursor.execute("""
                UPDATE round_profile_criteria
                SET WeightPercent = %s
                WHERE RoundID = %s
                  AND RoundCriteriaID = %s
                  AND MatchMode = 'WEIGHTED'
                  AND IsActive = 1
            """, (weight_percent, round_id, criteria_id))

        if weighted_ids:
            placeholders = ", ".join(["%s"] * len(weighted_ids))
            cursor.execute(f"""
                UPDATE round_profile_criteria
                SET WeightPercent = NULL
                WHERE RoundID = %s
                  AND (
                        MatchMode <> 'WEIGHTED'
                        OR IsActive <> 1
                        OR RoundCriteriaID NOT IN ({placeholders})
                  )
            """, tuple([round_id] + list(weighted_ids)))
        else:
            cursor.execute("""
                UPDATE round_profile_criteria
                SET WeightPercent = NULL
                WHERE RoundID = %s
            """, (round_id,))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


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


def resolve_device_receipt_problem(*, round_id: int, participant_id: int, resolved_by_user_id: str) -> bool:
    """
    Mark an open participant receipt-problem report as resolved.

    Scope is constrained by round_id + participant_id so UT Lead actions
    cannot resolve issues outside the current round context.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE project_participants
            SET
                DeviceReceiptProblemResolvedAt = NOW(),
                DeviceReceiptProblemNote = CASE
                    WHEN DeviceReceiptProblemNote IS NULL OR DeviceReceiptProblemNote = ''
                    THEN CONCAT('Resolved by UT Lead: ', %s)
                    ELSE CONCAT(DeviceReceiptProblemNote, '\nResolved by UT Lead: ', %s)
                END,
                UpdatedAt = NOW()
            WHERE ParticipantID = %s
              AND RoundID = %s
              AND DeviceReceiptProblemReportedAt IS NOT NULL
              AND DeviceReceiptProblemResolvedAt IS NULL
              AND DeviceReceivedConfirmedAt IS NULL
            """,
            (resolved_by_user_id, resolved_by_user_id, participant_id, round_id),
        )

        conn.commit()
        return cur.rowcount > 0

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


def _is_oobe_first_impression_survey_type(
    *,
    survey_type_id: str | None,
    survey_type_name: str | None,
) -> bool:
    survey_type_id = str(survey_type_id or "").strip()
    survey_type_name = str(survey_type_name or "").strip().lower()

    return (
        survey_type_id == "UTSurveyType1001"
        or "oobe" in survey_type_name
        or ("first" in survey_type_name and "impression" in survey_type_name)
    )


def _coerce_product_trial_deadline_date(value):
    from datetime import date, datetime

    if not value:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        clean_value = value.strip()
        if not clean_value:
            return None

        try:
            return datetime.fromisoformat(clean_value.replace("Z", "")).date()
        except ValueError:
            pass

        try:
            return date.fromisoformat(clean_value[:10])
        except ValueError:
            return None

    return None


def _add_business_days_for_product_trial_deadline(value, business_days: int = 2) -> str:
    from datetime import timedelta

    current = _coerce_product_trial_deadline_date(value)
    if current is None:
        return ""

    remaining = int(business_days or 0)
    while remaining > 0:
        current = current + timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1

    return current.isoformat()


def activate_round_survey_for_participants(
    *,
    round_id: int,
    round_survey_id: int,
    activated_by_user_id: str,
) -> dict:
    """
    Explicitly activate a configured participant survey for this round.

    OOBE / First Impression is unlocked by participant device receipt.
    All other participant result surveys are unlocked by explicit UT Lead activation.
    The DB layer validates that the survey belongs to the round and is an active
    configured survey before mutating state.
    """

    excluded_survey_type_ids = {
        "UTSurveyType0001",
        "UTSurveyType0027",
        "UTSurveyType0028",
    }

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                prs.RoundSurveyID,
                prs.RoundID,
                prs.SurveyTypeID,
                prs.ParticipantActivatedAt,
                prs.ParticipantActivationNotificationSentAt,
                st.SurveyTypeName,
                st.SurveyDescription,
                pr.RoundName,
                pr.RoundNumber,
                pj.ProjectID,
                pj.ProjectName
            FROM project_round_surveys prs
            JOIN survey_types st
                ON st.SurveyTypeID = prs.SurveyTypeID
            JOIN project_rounds pr
                ON pr.RoundID = prs.RoundID
            JOIN project_projects pj
                ON pj.ProjectID = pr.ProjectID
            WHERE prs.RoundID = %s
              AND prs.RoundSurveyID = %s
              AND prs.IsActive = 1
            LIMIT 1
            """,
            (round_id, round_survey_id),
        )
        survey = cur.fetchone()

        if not survey:
            conn.rollback()
            return {"activated": False, "reason": "not_found", "notified": 0}

        survey_type_id = survey.get("SurveyTypeID")
        survey_type_name = (survey.get("SurveyTypeName") or "").strip()

        if survey_type_id in excluded_survey_type_ids or survey_type_name.lower() in ("recruiting", "consolidated", "report_issue"):
            conn.rollback()
            return {"activated": False, "reason": "not_participant_result_survey", "notified": 0}

        if _is_oobe_first_impression_survey_type(
            survey_type_id=survey_type_id,
            survey_type_name=survey_type_name,
        ):
            conn.rollback()
            return {"activated": False, "reason": "auto_after_device_receipt", "notified": 0}

        already_activated = bool(survey.get("ParticipantActivatedAt"))

        if not already_activated:
            cur.execute(
                """
                UPDATE project_round_surveys
                SET
                    ParticipantActivatedAt = NOW(),
                    ParticipantActivatedByUserID = %s
                WHERE RoundID = %s
                  AND RoundSurveyID = %s
                  AND IsActive = 1
                  AND ParticipantActivatedAt IS NULL
                """,
                (activated_by_user_id, round_id, round_survey_id),
            )

        cur.execute(
            """
            SELECT ParticipantActivatedAt
            FROM project_round_surveys
            WHERE RoundID = %s
              AND RoundSurveyID = %s
              AND IsActive = 1
            LIMIT 1
            """,
            (round_id, round_survey_id),
        )
        activation_row = cur.fetchone() or {}
        if activation_row.get("ParticipantActivatedAt"):
            survey["ParticipantActivatedAt"] = activation_row.get("ParticipantActivatedAt")

        survey_deadline = _add_business_days_for_product_trial_deadline(
            survey.get("ParticipantActivatedAt"),
            2,
        )

        cur.execute(
            """
            SELECT
                pp.user_id,
                up.Email,
                up.FirstName,
                up.LastName
            FROM project_participants pp
            JOIN user_pool up
                ON up.user_id = pp.user_id
            WHERE pp.RoundID = %s
              AND pp.ParticipantStatus IN ('Selected', 'Active')
              AND pp.CompletedAt IS NULL
              AND pp.user_id IS NOT NULL
            ORDER BY up.FirstName ASC, up.LastName ASC, pp.ParticipantID ASC
            """,
            (round_id,),
        )
        recipients = cur.fetchall() or []

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    recipient_user_ids = [
        row.get("user_id")
        for row in recipients
        if row.get("user_id")
    ]

    notified_count = 0

    if recipient_user_ids and not survey.get("ParticipantActivationNotificationSentAt"):
        try:
            from app.db.notifications import create_notification_event
            from app.services.notification_dispatcher import dispatch_notifications

            notification_id = create_notification_event(
                type_key="product_trial_survey_activated",
                user_ids=recipient_user_ids,
                created_by=activated_by_user_id,
                payload={
                    "round_id": survey.get("RoundID"),
                    "round_name": survey.get("RoundName"),
                    "round_number": survey.get("RoundNumber"),
                    "project_id": survey.get("ProjectID"),
                    "project_name": survey.get("ProjectName"),
                    "round_survey_id": survey.get("RoundSurveyID"),
                    "survey_type_id": survey.get("SurveyTypeID"),
                    "survey_name": survey_type_name or "Survey",
                    "survey_description": survey.get("SurveyDescription") or "",
                    "participant_activated_at": str(survey.get("ParticipantActivatedAt") or ""),
                    "survey_deadline": survey_deadline,
                    "survey_deadline_rule": "2 business days after activation",
                },
            )

            if notification_id:
                dispatch_notifications(notification_id)
                notified_count = len(recipient_user_ids)

                conn = mysql.connector.connect(**DB_CONFIG)
                try:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        UPDATE project_round_surveys
                        SET ParticipantActivationNotificationSentAt = NOW()
                        WHERE RoundID = %s
                          AND RoundSurveyID = %s
                          AND ParticipantActivationNotificationSentAt IS NULL
                        """,
                        (round_id, round_survey_id),
                    )
                    conn.commit()
                finally:
                    conn.close()

        except Exception:
            notified_count = 0

    return {
        "activated": True,
        "already_activated": already_activated,
        "notified": notified_count,
    }


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

    _refresh_round_profile_criteria_weights(round_id)


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

    _refresh_round_profile_criteria_weights(round_id)


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

    _refresh_round_profile_criteria_weights(round_id)


def update_round_profile_criteria_selection_settings(
    *,
    round_id: int,
    criteria_id: int,
    match_mode: str,
    priority_rank: int,
) -> bool:
    """
    Update selection-model settings for one round profile criterion.

    Ownership is enforced by requiring both RoundID and RoundCriteriaID.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    safe_match_mode = str(match_mode or "").strip().upper()

    if safe_match_mode not in ("WEIGHTED", "HARD_GATE"):
        safe_match_mode = "WEIGHTED"

    try:
        safe_priority_rank = int(priority_rank)
    except (TypeError, ValueError):
        safe_priority_rank = 1

    if safe_priority_rank < 1:
        safe_priority_rank = 1

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE round_profile_criteria
                SET
                    MatchMode = %s,
                    PriorityRank = %s
                WHERE RoundID = %s
                  AND RoundCriteriaID = %s
                  AND IsActive = 1
                """,
                (
                    safe_match_mode,
                    safe_priority_rank,
                    round_id,
                    criteria_id,
                ),
            )

            updated = cursor.rowcount > 0

        if updated:
            conn.commit()
        else:
            conn.rollback()

    finally:
        conn.close()

    if updated:
        _refresh_round_profile_criteria_weights(round_id)

    return updated