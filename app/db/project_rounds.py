def _insert_project(cur, project: dict):
    basics = project["basics"]
    timing = project.get("timing_scope", {})

    cur.execute(
        """
        INSERT INTO project_projects (
            ProjectID,
            ProjectName,
            MarketName,
            BusinessGroup,
            BusinessSubGroup,
            ProductType,
            Description,
            MinAge,
            MaxAge,
            GuardianRequired,
            ProjectStatus,
            GateX_Date,
            CreatedBy,
            CreatedAt,
            UpdatedAt
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """,
        (
            project["project_id"],
            basics["project_name"],
            basics["market_name"],                 # NEW
            basics["business_group"],
            basics.get("business_sub_group", "unspecified"),
            basics["product_category"],
            basics.get("purpose"),
            timing.get("min_age", 18),
            timing.get("max_age", 99),
            1 if timing.get("guardian_required") else 0,
            "draft",  # informational only
            basics.get("gate_x_date"),              # NEW (nullable)
            project["created_by"],
        )
    )
# ProjectStatus is informational only.
# Round status is authoritative for lifecycle.


def _insert_initial_round(cur, project: dict):
    basics = project["basics"]
    timing = project["timing_scope"]

    region = ",".join(timing.get("countries", [])) or "GLOBAL"

    cur.execute(
        """
        INSERT INTO project_rounds (
            ProjectID,
            RoundNumber,
            RoundName,
            Region,
            UserScope,
            TargetUsers,
            MinAge,
            MaxAge,
            Status,
            CreatedAt,
            UpdatedAt
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """,
        (
            project["project_id"],
            1,
            f'{basics["project_name"]} – Round 1',
            region,
            timing.get("user_scope", "Hybrid"),
            timing.get("target_users", 0),
            timing.get("min_age", 18),
            timing.get("max_age", 99),
            "pending_ut_review",
        )
    )

def _user_is_eligible_for_trials(cur, *, user_id: str) -> bool:
    """
    Determines whether a user can see/apply to trials.
    """

    cur.execute(
        """
        SELECT
            ParticipantStatus,
            EmailVerified,
            GlobalNDA_Status,
            GuidelinesCompletedAt,
            WelcomeSeenAt,
            Status
        FROM user_pool
        WHERE user_id = %s
        """,
        (user_id,),
    )

    row = cur.fetchone()

    if not row:
        return False

    # Must be active participant
    if row["ParticipantStatus"] != "active":
        return False

    # Email must be verified
    if not row["EmailVerified"]:
        return False

    # Must have signed global NDA
    if row["GlobalNDA_Status"] != "Signed":
        return False

    # Must complete onboarding
    if not row["GuidelinesCompletedAt"]:
        return False

    if not row["WelcomeSeenAt"]:
        return False

    # Status flag (future moderation / banning)
    if row["Status"] != 0:
        return False

    return True


def _insert_stakeholders(cur, snapshot, round_id):
    stakeholders = snapshot.get("stakeholders", {}).get("roles", [])

    for s in stakeholders:
        cur.execute(
            """
            INSERT INTO project_stakeholders
            (ProjectID, RoundID, DisplayName, StakeholderRole, IsPrimary, Active, AssignedAt)
            VALUES (%s, %s, %s, %s, %s, 1, NOW())
            """,
            (
                snapshot["project_id"],
                round_id,
                s.get("name"),
                s.get("role"),
                1 if s.get("role") == "Primary Contact" else 0,
            ),
        )


def create_project_from_request(
    *,
    project_id: str,
    created_by: str,
    project_snapshot: dict,
    submitted_at,
):
    """
    Authoritative DB write for Product Team trial submission.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        # --------------------------------------------------
        # Normalize snapshot + assert ProjectID
        # --------------------------------------------------
        snapshot = dict(project_snapshot)
        snapshot["project_id"] = project_id

        # --------------------------------------------------
        # 1️⃣ INSERT PROJECT (PARENT)
        # --------------------------------------------------
        _insert_project(cur, snapshot)

        # 🔒 HARD ASSERT: parent must exist
        cur.execute(
            "SELECT 1 FROM project_projects WHERE ProjectID = %s",
            (project_id,)
        )
        if cur.fetchone() is None:
            raise RuntimeError(
                f"project_projects insert failed for ProjectID={project_id}"
            )

        # --------------------------------------------------
        # 2️⃣ INSERT INITIAL ROUND (CHILD)
        # --------------------------------------------------
        _insert_initial_round(cur, snapshot)

        round_id = cur.lastrowid

        # --------------------------------------------------
        # 3️⃣ INSERT STAKEHOLDERS
        # --------------------------------------------------
        _insert_stakeholders(cur, snapshot, round_id)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_pending_project_rounds_for_user(*, user_id: str):
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                pr.ProjectID,
                pr.RoundID,
                pr.RoundName,
                pp.ProjectName
            FROM project_rounds pr
            JOIN project_projects pp ON pp.ProjectID = pr.ProjectID
            WHERE pr.Status = 'pending_ut_review'
                AND pp.CreatedBy = %s
            ORDER BY pr.CreatedAt DESC
            """,
            (user_id,)
        )

        return cur.fetchall()
    finally:
        conn.close()


def get_active_project_rounds_for_user(*, user_id: str):
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                pr.ProjectID,
                pr.RoundID,
                pr.RoundName,
                pp.ProjectName
            FROM project_rounds pr
            JOIN project_projects pp ON pp.ProjectID = pr.ProjectID
            WHERE pr.Status = 'active'
              AND pr.UTLead_UserID = %s
            ORDER BY pr.CreatedAt DESC
            """,
            (user_id,)
        )

        return cur.fetchall()
    finally:
        conn.close()

def get_project_with_latest_round(*, project_id: str):
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # 1. Project
        cur.execute(
            """
            SELECT *
            FROM project_projects
            WHERE ProjectID = %s
            """,
            (project_id,)
        )
        project = cur.fetchone()
        if not project:
            return None

        # 2. Latest round
        cur.execute(
            """
            SELECT *
            FROM project_rounds
            WHERE ProjectID = %s
            ORDER BY RoundNumber DESC
            LIMIT 1
            """,
            (project_id,)
        )
        round_ = cur.fetchone()
        if not round_:
            return None

        return project, round_

    finally:
        conn.close()

def get_pending_project_trial_approvals():
    """
    Returns all project rounds pending UT review.
    UT-lead facing.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                pr.RoundID,
                pr.ProjectID,
                pr.RoundName,
                pr.Region,
                pr.TargetUsers,
                pr.CreatedAt AS submitted_at,

                pp.ProjectName,
                pp.BusinessGroup,
                pp.ProductType,

                pp.CreatedBy AS requested_by_user_id,
                CONCAT(u.FirstName, ' ', u.LastName) AS requested_by_name

            FROM project_rounds pr
            JOIN project_projects pp
            ON pp.ProjectID = pr.ProjectID
            JOIN user_pool u
            ON u.user_id = pp.CreatedBy

            WHERE pr.Status = 'pending_ut_review'
            ORDER BY pr.CreatedAt DESC
            """
        )

        return cur.fetchall()

    finally:
        conn.close()


def get_info_requested_project_rounds_for_user(*, user_id: str):
    """
    Returns project rounds where UT has requested more information
    from the original requestor.
    Product Team facing.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                pr.ProjectID,
                pr.RoundID,
                pr.RoundName,
                pp.ProjectName,
                pr.UpdatedAt AS info_requested_at
            FROM project_rounds pr
            JOIN project_projects pp
              ON pp.ProjectID = pr.ProjectID
            WHERE pr.Status = 'info_requested'
              AND pp.CreatedBy = %s
            ORDER BY pr.UpdatedAt DESC
            """,
            (user_id,),
        )

        return cur.fetchall()

    finally:
        conn.close()



def close_project_round_as_declined(*, project_id: str):
    """
    Authoritatively mark the latest project round as declined.
    Round status is the lifecycle source of truth.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        # --------------------------------------------------
        # Close latest round
        # --------------------------------------------------
        cur.execute(
            """
            UPDATE project_rounds
            SET Status = 'declined',
                UpdatedAt = NOW()
            WHERE ProjectID = %s
            ORDER BY RoundNumber DESC
            LIMIT 1
            """,
            (project_id,)
        )

        if cur.rowcount == 0:
            raise RuntimeError(
                f"No project_rounds updated for ProjectID={project_id}"
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def mark_project_round_info_requested(
    *,
    project_id: str,
    acted_by: str,
) -> None:
    """
    Transition the latest project round into info_requested state.
    UT has reviewed and is awaiting clarification from requestor.
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
                Status = 'info_requested',
                UpdatedAt = NOW()
            WHERE ProjectID = %s
            ORDER BY RoundNumber DESC
            LIMIT 1
            """,
            (project_id,),
        )

        if cur.rowcount == 0:
            raise RuntimeError(
                f"No project_rounds updated for ProjectID={project_id}"
            )

        conn.commit()

    finally:
        conn.close()

def mark_project_round_change_requested(
    *,
    project_id: str,
    acted_by: str,
) -> None:
    """
    Transition the latest project round into change_requested state.
    UT has reviewed the request and requires specific changes.
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
                Status = 'change_requested',
                UpdatedAt = NOW()
            WHERE ProjectID = %s
            ORDER BY RoundNumber DESC
            LIMIT 1
            """,
            (project_id,),
        )

        if cur.rowcount == 0:
            raise RuntimeError(
                f"No project_rounds updated for ProjectID={project_id}"
            )

        conn.commit()

    finally:
        conn.close()

def get_action_required_project_rounds_for_user(*, user_id: str):
    """
    Product Team–owned User Trial requests that require action.
    Authoritative slice for:
      - info_requested
      - change_requested
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                pr.ProjectID,
                pr.RoundID,
                pr.RoundName,
                pp.ProjectName,
                pr.Status,
                pr.UpdatedAt
            FROM project_rounds pr
            JOIN project_projects pp
              ON pp.ProjectID = pr.ProjectID
            WHERE pr.Status IN ('info_requested', 'change_requested')
              AND pp.CreatedBy = %s
            ORDER BY pr.UpdatedAt DESC
            """,
            (user_id,),
        )

        return cur.fetchall()

    finally:
        conn.close()

ALLOWED_ROUND_TRANSITIONS = {
    "pending_ut_review": {"info_requested", "change_requested", "declined", "approved"},
    "info_requested": {"pending_ut_review"},
    "change_requested": {"pending_ut_review"},
    "approved": {"recruiting", "withdrawn"},
    "recruiting": {"screening", "cancelled"},
    "screening": {"active", "cancelled"},
    "active": {"completed", "cancelled"},
}

def set_project_round_status(
    *,
    round_id: int,
    status: str,
    ut_lead_id: str | None = None,
):
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # --------------------------------------------------
        # Fetch current status
        # --------------------------------------------------
        cur.execute(
            "SELECT Status FROM project_rounds WHERE RoundID = %s",
            (round_id,)
        )
        row = cur.fetchone()

        if not row:
            raise RuntimeError(f"Round {round_id} not found")

        current_status = row["Status"] or "pending_ut_review"

        # --------------------------------------------------
        # No-op if status already correct (idempotent)
        # --------------------------------------------------

        if current_status == status:
            return

        # --------------------------------------------------
        # Validate transition
        # --------------------------------------------------

        allowed = ALLOWED_ROUND_TRANSITIONS.get(current_status, set())

        if status not in allowed:
            raise RuntimeError(
                f"Invalid round transition {current_status} → {status}"
            )

        # --------------------------------------------------
        # Apply update
        # --------------------------------------------------

        if status == "recruiting":
            cur.execute(
                """
                UPDATE project_rounds
                SET
                    Status = %s,
                    RecruitingStartDate = CURDATE(),
                    UTLead_UserID = %s,
                    UpdatedAt = NOW()
                WHERE RoundID = %s
                """,
                (status, ut_lead_id, round_id),
            )

        elif ut_lead_id is not None:
            cur.execute(
                """
                UPDATE project_rounds
                SET
                    Status = %s,
                    UTLead_UserID = %s,
                    UpdatedAt = NOW()
                WHERE RoundID = %s
                """,
                (status, ut_lead_id, round_id),
            )

        else:
            cur.execute(
                """
                UPDATE project_rounds
                SET
                    Status = %s,
                    UpdatedAt = NOW()
                WHERE RoundID = %s
                """,
                (status, round_id),
            )

        conn.commit()

        # --------------------------------------------------
        # Notify watchers
        # --------------------------------------------------

        if status == "recruiting":

            from app.services.notifications import notify_many_users
            from app.services.notification_dispatcher import dispatch_notifications

            # Fetch round name
            cur.execute("""
                SELECT RoundName
                FROM project_rounds
                WHERE RoundID = %s
            """, (round_id,))

            row = cur.fetchone()
            round_name = row["RoundName"] if row else "Trial"

            # Fetch watchers
            cur.execute("""
                SELECT user_id
                FROM project_round_interest
                WHERE RoundID = %s
                AND NotifiedAt IS NULL
            """, (round_id,))

            watchers = [r["user_id"] for r in cur.fetchall()]

            if watchers:

                notification_id = notify_many_users(
                    user_ids=watchers,
                    type_key="trial_recruiting_started",
                    context={
                        "round_id": round_id,
                        "round_name": round_name
                    }
                )

                if notification_id:
                    dispatch_notifications(notification_id)

                # Mark watchers as notified
                cur.execute("""
                    UPDATE project_round_interest
                    SET NotifiedAt = NOW()
                    WHERE RoundID = %s
                    AND NotifiedAt IS NULL
                """, (round_id,))

                conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def mark_project_round_pending_ut_review(*, project_id: str) -> None:
    """
    Product Team responded to an info request.
    Round re-enters UT review.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE project_rounds
            SET Status = 'pending_ut_review',
                UpdatedAt = NOW()
            WHERE ProjectID = %s
            ORDER BY RoundNumber DESC
            LIMIT 1
            """,
            (project_id,),
        )

        if cur.rowcount == 0:
            raise RuntimeError(
                f"No project_rounds updated for ProjectID={project_id}"
            )

        conn.commit()

    finally:
        conn.close()

def get_current_project_rounds_for_user(*, user_id: str):
    """
    Product Team-facing.

    Returns ALL active trials (not closed).

    Definition:
      - Current = Status != 'closed'
      - Past = Status = 'closed' (handled separately)
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                pr.ProjectID,
                pr.RoundID,
                pr.RoundName,
                pr.StartDate,
                pr.EndDate,
                pr.Region,
                pr.MinAge,
                pr.MaxAge,
                pr.Status,
                pr.RecruitingStartDate,
                pr.RecruitingEndDate,
                pr.UTLead_UserID,
                
                pp.ProjectName,
                pp.ProductType

            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID

            WHERE pp.CreatedBy = %s
              AND pr.Status != 'closed'

            ORDER BY
                CASE
                    WHEN pr.Status = 'running' THEN 1
                    WHEN pr.Status = 'recruiting' THEN 2
                    WHEN pr.Status = 'approved' THEN 3
                    ELSE 4
                END,
                pr.StartDate ASC
            """,
            (user_id,),
        )

        return cur.fetchall()

    finally:
        conn.close()


def get_upcoming_project_rounds():
    """
    DB layer ONLY.

    Returns ALL upcoming rounds that:
      - are approved
      - have not started recruiting

    NO user-specific filtering here.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                pr.ProjectID,
                pr.RoundID,
                pr.RoundName,
                pr.StartDate,
                pr.EndDate,
                pr.ShipDate,
                pr.Region,
                pr.MinAge,
                pr.MaxAge,
                pr.RecruitingStartDate,
                pp.ProjectName,
                pp.ProductType
            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            WHERE pr.Status = 'approved'
              AND pr.RecruitingStartDate IS NULL
            ORDER BY pr.StartDate ASC
            """
        )

        return cur.fetchall()

    finally:
        conn.close()


def get_project_round_by_id(*, round_id: int):
    """
    Fetch a single project round by RoundID.
    Used by Product Team current trials detail view.
    """
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                pr.*,
                pp.ProjectName,
                pp.ProductType
            FROM project_rounds pr
            JOIN project_projects pp
              ON pp.ProjectID = pr.ProjectID
            WHERE pr.RoundID = %s
            LIMIT 1
            """,
            (round_id,),
        )

        return cur.fetchone()

    finally:
        conn.close()

def get_recruiting_project_rounds():
    """
    DB layer ONLY.

    Returns ALL recruiting rounds.
    No user filtering.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                pr.ProjectID,
                pr.RoundID,
                pr.RoundName,
                pr.StartDate,
                pr.EndDate,
                pr.ShipDate,
                pr.Region,
                pr.MinAge,
                pr.MaxAge,
                pr.RecruitingStartDate,
                pp.ProjectName,
                pp.ProductType
            FROM project_rounds pr
            JOIN project_projects pp
                ON pp.ProjectID = pr.ProjectID
            WHERE pr.Status = 'approved'
              AND pr.RecruitingStartDate IS NOT NULL
            ORDER BY pr.StartDate ASC
            """
        )

        return cur.fetchall()

    finally:
        conn.close()

def withdraw_project_round(*, round_id: int, by_user_id: str):
    """
    Pre-approval withdrawal by Product Team.
    Terminal state.
    """
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE project_rounds
            SET Status = 'withdrawn',
                UpdatedAt = NOW()
            WHERE RoundID = %s
            """,
            (round_id,),
        )

        conn.commit()
    finally:
        conn.close()

def get_round_stakeholders(*, round_id: int):
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                DisplayName,
                StakeholderRole
            FROM project_stakeholders
            WHERE RoundID = %s
            ORDER BY IsPrimary DESC, DisplayName
            """,
            (round_id,)
        )

        return cur.fetchall()

    finally:
        conn.close()


def get_rounds_for_project_review(*, project_id: str):
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT *
            FROM project_rounds
            WHERE ProjectID = %s
            ORDER BY RoundID ASC
            """,
            (project_id,),
        )

        return cur.fetchall()

    finally:
        conn.close()