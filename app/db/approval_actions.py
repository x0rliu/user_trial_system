# db/approval_actions.py

def insert_approval_action(
    *,
    approval_type: str,
    approval_id: int,
    action_type: str,
    reason_category: str | None,
    reason_text: str | None,
    assigned_ut_lead_id: str | None = None,
    action_by_user_id: str,
):

    if approval_type == "product_trial":
        if not isinstance(approval_id, int):
            raise ValueError(
                "approval_actions for product_trial must use RoundID (int), not ProjectID"
            )

    if not action_type:
        raise ValueError("approval_actions.ActionType must not be NULL")

    if approval_type == "product_trial" and not isinstance(approval_id, int):
        raise ValueError("product_trial ApprovalID must be RoundID (int)")

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO approval_actions (
                ApprovalType,
                ApprovalID,
                ActionType,
                ReasonText,
                AssignedUTLeadID,
                ActionByUserID,
                CreatedAt
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                approval_type,
                approval_id,
                action_type,
                reason_text,
                assigned_ut_lead_id,
                action_by_user_id,
            )
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def _get_action_required_project_rounds_for_user(
    *,
    user_id: str,
    status: str,
):
    """
    Internal helper.
    Returns project rounds where UT action is required from Product Team.
    Status must be 'info_requested' or 'change_requested'.
    """

    if status not in {"info_requested", "change_requested"}:
        raise ValueError(f"Invalid status: {status}")

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
                pr.Status AS round_status,
                pr.UpdatedAt AS status_updated_at,

                pp.ProjectName,

                aa.ActionID,
                aa.ActionType,
                aa.ReasonCategory,
                aa.ReasonText,
                aa.CreatedAt AS action_created_at

            FROM project_rounds pr
            JOIN project_projects pp
              ON pp.ProjectID = pr.ProjectID

            JOIN approval_actions aa
              ON aa.ApprovalID = pr.RoundID
             AND aa.ActionType IN ('request_info', 'request_changes')

            WHERE pr.Status = %s
              AND pp.CreatedBy = %s

            -- latest UT request only
            AND aa.CreatedAt = (
                SELECT MAX(a2.CreatedAt)
                FROM approval_actions a2
                WHERE a2.ApprovalID = pr.RoundID
                  AND a2.ActionType IN ('request_info', 'request_changes')
            )

            ORDER BY aa.CreatedAt DESC
            """,
            (status, user_id),
        )

        return cur.fetchall()

    finally:
        conn.close()

def get_info_requested_project_rounds_for_user(*, user_id: str):
    """
    Product Team facing.
    UT has requested additional information.
    """
    return _get_action_required_project_rounds_for_user(
        user_id=user_id,
        status="info_requested",
    )

def get_change_requested_project_rounds_for_user(*, user_id: str):
    """
    Product Team facing.
    UT has proposed a change requiring agreement.
    """
    return _get_action_required_project_rounds_for_user(
        user_id=user_id,
        status="change_requested",
    )

def get_latest_request_info_action(*, round_id: int):
    """
    Returns the latest UT 'request_info' action for a round.
    """
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                ActionID,
                ActionType,
                ReasonCategory,
                ReasonText,
                CreatedAt
            FROM approval_actions
            WHERE ApprovalType = 'product_trial'
              AND ApprovalID = %s
              AND ActionType = 'request_info'
            ORDER BY CreatedAt DESC
            LIMIT 1
            """,
            (round_id,),
        )

        return cur.fetchone()

    finally:
        conn.close()


def get_latest_change_request_action(*, round_id: int):
    """
    Returns the latest UT 'request_changes' action for a round.
    """
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                ActionID,
                ActionType,
                ReasonCategory,
                ReasonText,
                CreatedAt
            FROM approval_actions
            WHERE ApprovalType = 'product_trial'
              AND ApprovalID = %s
              AND ActionType = 'request_changes'
            ORDER BY CreatedAt DESC
            LIMIT 1
            """,
            (round_id,),
        )

        return cur.fetchone()

    finally:
        conn.close()

def get_latest_request_info_requester_user_id(*, round_id: int) -> str | None:
    """
    Returns the ActionByUserID of the most recent UT 'request_info' action for this round.
    Used to notify the original requester after Product Team responds.
    """
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT ActionByUserID
            FROM approval_actions
            WHERE ApprovalType = 'product_trial'
              AND ApprovalID = %s
              AND ActionType = 'request_info'
            ORDER BY CreatedAt DESC
            LIMIT 1
            """,
            (round_id,),
        )

        row = cur.fetchone()
        return row["ActionByUserID"] if row else None

    finally:
        conn.close()
