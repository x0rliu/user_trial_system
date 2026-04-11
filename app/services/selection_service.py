# services/selection_service.py

import mysql.connector
from app.config.config import DB_CONFIG
from app.services.user_score_service import calculate_user_score
from app.db.my_trials_db import get_connection


def create_or_get_selection_session(*, validated_round: dict, user_id: str):
    """
    Create or fetch a selection session for a given round.

    SECURITY:
    - Requires validated_round (no raw round_id allowed)
    - Ensures UT Lead ownership via validated context
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    if not validated_round or "RoundID" not in validated_round:
        raise ValueError("Invalid validated_round context")

    round_id = int(validated_round["RoundID"])
    ut_lead_user_id = validated_round.get("UTLead_UserID")

    # 🔒 Enforce ownership at service layer (defense-in-depth)
    if ut_lead_user_id != user_id:
        raise ValueError("Unauthorized: user does not own this round")

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # -------------------------
        # Try to get existing session
        # -------------------------
        cur.execute(
            """
            SELECT *
            FROM selection_sessions
            WHERE RoundID = %s
              AND UTLead_UserID = %s
            LIMIT 1
            """,
            (round_id, user_id),
        )
        session = cur.fetchone()

        if session:
            return session

        # -------------------------
        # Create new session
        # -------------------------
        cur.execute(
            """
            INSERT INTO selection_sessions (RoundID, UTLead_UserID, Status)
            VALUES (%s, %s, 'selection')
            """,
            (round_id, user_id),
        )

        conn.commit()

        session_id = cur.lastrowid

        # -------------------------
        # Return created session
        # -------------------------
        cur.execute(
            """
            SELECT *
            FROM selection_sessions
            WHERE SessionID = %s
            LIMIT 1
            """,
            (session_id,),
        )

        return cur.fetchone()

    finally:
        conn.close()

def get_selection_steps(*, session_id: int):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT *
            FROM selection_criteria_steps
            WHERE SessionID = %s
            ORDER BY StepOrder ASC
        """, (session_id,))

        return cur.fetchall()

    finally:
        conn.close()

def apply_selection_step(*, session_id: int, criteria_type: str, criteria_value: str):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # Get current steps
        cur.execute("""
            SELECT *
            FROM selection_criteria_steps
            WHERE SessionID = %s
            ORDER BY StepOrder ASC
        """, (session_id,))
        steps = cur.fetchall()

        step_order = len(steps) + 1

        # Get current pool BEFORE
        users_before_list = _compute_pool_from_steps(steps)
        users_before = len(users_before_list)

        # Apply new filter
        users_after_list = _apply_filter(users_before_list, criteria_type, criteria_value)
        users_after = len(users_after_list)

        # Insert step
        cur.execute("""
            INSERT INTO selection_criteria_steps (
                SessionID,
                StepOrder,
                CriteriaType,
                CriteriaValue,
                UsersBefore,
                UsersAfter
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            session_id,
            step_order,
            criteria_type,
            criteria_value,
            users_before,
            users_after
        ))

        conn.commit()

        return {
            "users_before": users_before,
            "users_after": users_after
        }

    finally:
        conn.close()

def get_current_pool(*, session_id: int):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT RoundID
            FROM selection_sessions
            WHERE SessionID = %s
        """, (session_id,))

        session = cur.fetchone()
        round_id = session["RoundID"]

    finally:
        conn.close()

    steps = get_selection_steps(session_id=session_id)

    return _compute_pool_from_steps(steps, round_id=round_id)

def get_current_participant_user_ids(*, round_id: int) -> set[str]:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT user_id
            FROM project_participants
            WHERE RoundID = %s
              AND CompletedAt IS NULL
              AND ParticipantStatus IN ('Selected', 'Active')
        """, (round_id,))

        rows = cur.fetchall()
        return {row[0] for row in rows if row and row[0]}

    finally:
        conn.close()

def simulate_filter(*, session_id: int, criteria_type: str, criteria_value: str):

    # 1. Get existing steps
    steps = get_selection_steps(session_id=session_id)

    # 2. Compute current pool
    current_pool = _compute_pool_from_steps(steps)
    users_before = len(current_pool)

    # 3. Apply simulated filter (no DB write)
    simulated_pool = _apply_filter(
        current_pool,
        criteria_type,
        criteria_value
    )

    users_after = len(simulated_pool)

    return {
        "users_before": users_before,
        "users_after": users_after
    }

def _compute_pool_from_steps(steps, round_id=None):
    users = _get_all_eligible_users(round_id=round_id)

    # -------------------------
    # LOAD ROUND CONFIG (REGION)
    # -------------------------
    region_value = None

    if round_id:
        import mysql.connector
        from app.config.config import DB_CONFIG

        conn = mysql.connector.connect(**DB_CONFIG)
        try:
            cur = conn.cursor(dictionary=True)

            cur.execute("""
                SELECT Region
                FROM project_rounds
                WHERE RoundID = %s
            """, (round_id,))

            row = cur.fetchone()
            if row:
                region_value = row.get("Region")

        finally:
            conn.close()

    # -------------------------
    # APPLY REGION HARD GATE (IF DEFINED)
    # -------------------------
    if region_value:
        users = _apply_filter(users, "region", region_value)

    # -------------------------
    # APPLY USER-DEFINED STEPS
    # -------------------------
    for step in steps:
        users = _apply_filter(users, step["CriteriaType"], step["CriteriaValue"])

    return users


def _get_all_eligible_users(*, round_id: int = None):
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # -------------------------
        # IF ROUND PROVIDED → USE APPLICANTS
        # -------------------------
        if round_id:
            cur.execute("""
                SELECT 
                    up.user_id,
                    up.FirstName,
                    up.LastName,
                    up.CountryCode,
                    up.BirthYear,
                    up.Email,
                    up.ParticipantStatus,
                    up.EmailVerified,
                    up.GlobalNDA_Status,
                    up.GuidelinesCompletedAt,
                    up.WelcomeSeenAt,
                    up.Status,
                    pa.MotivationText   -- 🔥 ADD THIS
                FROM user_pool up
                JOIN project_applicants pa
                  ON up.user_id = pa.user_id
                WHERE pa.RoundID = %s
                  AND pa.ApplicationStatus = 'Confirmed'
            """, (round_id,))

        # -------------------------
        # FALLBACK (DEV / TEST MODE)
        # -------------------------
        else:
            cur.execute("""
                SELECT 
                    user_id,
                    CountryCode,
                    BirthYear,
                    Email,
                    ParticipantStatus,
                    EmailVerified,
                    GlobalNDA_Status,
                    GuidelinesCompletedAt,
                    WelcomeSeenAt,
                    Status
                FROM user_pool
            """)

        rows = cur.fetchall()

        results = []

        for user in rows:

            eligible = True
            reasons = []

            # -------------------------
            # HARD GATES (LABEL ONLY)
            # -------------------------

            if user.get("ParticipantStatus") != "active":
                eligible = False
                reasons.append("inactive")

            if user.get("EmailVerified") != 1:
                eligible = False
                reasons.append("email_not_verified")

            if user.get("GlobalNDA_Status") != "Signed":
                eligible = False
                reasons.append("nda_not_signed")

            if not user.get("GuidelinesCompletedAt"):
                eligible = False
                reasons.append("guidelines_not_completed")

            if not user.get("WelcomeSeenAt"):
                eligible = False
                reasons.append("welcome_not_seen")

            if user.get("Status") != 0:
                eligible = False
                reasons.append("user_disabled")

            display_name = None

            if user.get("FirstName") or user.get("LastName"):
                display_name = f"{user.get('FirstName','')} {user.get('LastName','')}".strip()

            results.append({
                "user_id": user.get("user_id"),
                "FirstName": user.get("FirstName"),
                "LastName": user.get("LastName"),
                "CountryCode": user.get("CountryCode"),
                "BirthYear": user.get("BirthYear"),
                "Email": user.get("Email"),
                "ParticipantStatus": user.get("ParticipantStatus"),
                "EmailVerified": user.get("EmailVerified"),
                "GlobalNDA_Status": user.get("GlobalNDA_Status"),
                "GuidelinesCompletedAt": user.get("GuidelinesCompletedAt"),
                "WelcomeSeenAt": user.get("WelcomeSeenAt"),
                "Status": user.get("Status"),

                # 🔥 EXPLICIT — NOT implicit via **user
                "motivation": user.get("MotivationText") or "",

                "display_name": display_name,
                "eligible": eligible,
                "exclusion_reason": ", ".join(reasons) if reasons else None,

                "hard_gate_results": {
                    "region": {"passed": True, "value": None},
                    "concurrent": {"passed": True},
                    "blacklist": {"passed": True}
                }
            })
            
        return results

    finally:
        conn.close()


def _apply_filter(users, criteria_type, criteria_value):

    # -------------------------
    # REGION FILTER (HARD GATE → ANNOTATE)
    # -------------------------
    if criteria_type == "region":

        allowed_regions = [r.strip() for r in criteria_value.split(",") if r.strip()]

        for user in users:
            if user.get("CountryCode") not in allowed_regions:
                user["eligible"] = False

                # 🔥 STRUCTURED UPDATE
                user["hard_gate_results"]["region"]["passed"] = False
                user["hard_gate_results"]["region"]["value"] = user.get("CountryCode")

                reason = f"country_not_allowed ({user.get('CountryCode')})"

                existing = user.get("exclusion_reason")
                if existing:
                    user["exclusion_reason"] = f"{existing}, {reason}"
                else:
                    user["exclusion_reason"] = reason

        return users

    # -------------------------
    # CONCURRENT FILTER (HARD GATE → ANNOTATE)
    # -------------------------
    if criteria_type == "concurrent":

        active_user_ids = _get_users_in_active_trials()

        for user in users:
            if user["user_id"] in active_user_ids:
                user["eligible"] = False

                # 🔥 STRUCTURED UPDATE
                user["hard_gate_results"]["concurrent"]["passed"] = False

                reason = "in_active_trial"

                existing = user.get("exclusion_reason")
                if existing:
                    user["exclusion_reason"] = f"{existing}, {reason}"
                else:
                    user["exclusion_reason"] = reason

        return users

    # -------------------------
    # BLACKLIST FILTER (HARD GATE → ANNOTATE)
    # -------------------------
    if criteria_type == "blacklist":

        blacklisted_emails = _get_blacklisted_emails()

        for user in users:
            email = (
                user.get("Email")
                or user.get("email")
                or ""
            ).lower().strip()

            if email in blacklisted_emails:
                user["eligible"] = False

                # 🔥 STRUCTURED UPDATE
                user["hard_gate_results"]["blacklist"]["passed"] = False

                reason = "blacklisted"

                existing = user.get("exclusion_reason")
                if existing:
                    user["exclusion_reason"] = f"{existing}, {reason}"
                else:
                    user["exclusion_reason"] = reason

        return users

    # -------------------------
    # DEFAULT (no-op)
    # -------------------------
    return users

def select_top_users(*, validated_session: dict):
    """
    Generate a provisional top-user selection.

    IMPORTANT:
    - Writes provisional selected / alternate rows to selection_results
    - Does NOT finalize the session
    - Leaves final confirmation to the UT Lead
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # -------------------------
        # Get session
        # -------------------------
        session_id = int(validated_session["SessionID"])

        cur.execute("""
            SELECT *
            FROM selection_sessions
            WHERE SessionID = %s
        """, (session_id,))
        session = cur.fetchone()

        if not session:
            raise ValueError("Session not found")

        round_id = session["RoundID"]
        target = int(session.get("TargetUsers") or 0)

        # -------------------------
        # Get pool + profile
        # -------------------------
        final_pool = get_current_pool(session_id=session_id)

        from app.services.selection_profile_service import get_effective_profile_criteria
        from app.services.selection_scoring_service import score_users

        trial_profile = get_effective_profile_criteria(
            session_id=session_id,
            round_id=round_id,
        )

        # -------------------------
        # Context for scoring
        # -------------------------
        first_pass_context = {
            "eligible_pool_size": len(final_pool),
            "target_users": target
        }

        first_pass = score_users(final_pool, first_pass_context, trial_profile)

        eligible_pool = [
            u for u in first_pass
            if u.get("eligible", True)
        ]

        final_context = {
            "eligible_pool_size": len(eligible_pool),
            "target_users": target
        }

        scored_pool = score_users(final_pool, final_context, trial_profile)

        eligible_scored_pool = [
            u for u in scored_pool
            if u.get("eligible", True)
        ]

        # -------------------------
        # Select top N, or whole pool if pool < N
        # -------------------------
        select_count = min(target, len(eligible_scored_pool)) if target > 0 else 0

        selected = eligible_scored_pool[:select_count]
        alternates = eligible_scored_pool[select_count:select_count + 3]

        # -------------------------
        # DEBUG OUTPUT
        # -------------------------
        print("\n=== SELECT TOP USERS DEBUG ===")
        print({
            "session_id": session_id,
            "target": target,
            "eligible_pool": len(eligible_scored_pool),
            "selected_count": len(selected),
            "alternate_count": len(alternates),
        })

        for user in eligible_scored_pool:
            print({
                "user_id": user["user_id"],
                "final_score": user.get("final_score"),
                "quality_score": user.get("quality_score"),
                "profile_score_scaled": user.get("profile_score_scaled"),
            })

        # -------------------------
        # Clear previous provisional results
        # -------------------------
        cur.execute("""
            DELETE FROM selection_results
            WHERE SessionID = %s
        """, (session_id,))

        # -------------------------
        # Insert provisional selected
        # -------------------------
        for user in selected:
            cur.execute("""
                INSERT INTO selection_results (SessionID, UserID, ResultType, Score)
                VALUES (%s, %s, 'selected', %s)
            """, (
                session_id,
                user["user_id"],
                user.get("final_score"),
            ))

        # -------------------------
        # Insert provisional alternates
        # -------------------------
        for user in alternates:
            cur.execute("""
                INSERT INTO selection_results (SessionID, UserID, ResultType, Score)
                VALUES (%s, %s, 'alternate', %s)
            """, (
                session_id,
                user["user_id"],
                user.get("final_score"),
            ))

        # -------------------------
        # Keep session in selection mode
        # Do NOT finalize here
        # -------------------------
        cur.execute("""
            UPDATE selection_sessions
            SET Status = 'selection'
            WHERE SessionID = %s
        """, (session_id,))

        conn.commit()

    finally:
        conn.close()


def finalize_selection(*, validated_session: dict):
    """
    Final confirmation step.

    IMPORTANT:
    - Does NOT re-pick users
    - Assumes selection_results already contains the UT Lead-reviewed set
    - Writes finalized selected users into project_participants
    - Then marks the session finalized
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # --------------------------------------------------
        # Load session
        # --------------------------------------------------
        session_id = int(validated_session["SessionID"])

        cur.execute("""
            SELECT *
            FROM selection_sessions
            WHERE SessionID = %s
        """, (session_id,))
        session = cur.fetchone()

        if not session:
            raise ValueError("Session not found")

        round_id = session["RoundID"]

        # --------------------------------------------------
        # Pull finalized selected users
        # --------------------------------------------------
        cur.execute("""
            SELECT UserID
            FROM selection_results
            WHERE SessionID = %s
              AND ResultType = 'selected'
            ORDER BY AssignedAt ASC, ResultID ASC
        """, (session_id,))

        selected_rows = cur.fetchall()
        selected_user_ids = [row["UserID"] for row in selected_rows]

        # --------------------------------------------------
        # Replace current pre-execution participant rows
        # --------------------------------------------------
        cur.execute("""
            DELETE FROM project_participants
            WHERE RoundID = %s
              AND CompletedAt IS NULL
              AND ParticipantStatus IN ('Selected', 'Active')
        """, (round_id,))

        # --------------------------------------------------
        # Insert finalized participants
        # MVP defaults:
        # - DeliveryType: Home
        # - TrialNickname: user_id
        # - ProfileSnapshotCode: empty string
        # --------------------------------------------------
        for user_id in selected_user_ids:
            cur.execute("""
                INSERT INTO project_participants (
                    RoundID,
                    user_id,
                    DeliveryType,
                    ParticipantStatus,
                    Notes,
                    TrialNickname,
                    ProfileSnapshotCode
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                round_id,
                user_id,
                "Home",
                "Selected",
                None,
                user_id,
                "",
            ))

        # --------------------------------------------------
        # Mark session finalized
        # --------------------------------------------------
        cur.execute("""
            UPDATE selection_sessions
            SET Status = 'finalized',
                FinalizedAt = NOW()
            WHERE SessionID = %s
        """, (session_id,))

        conn.commit()

    finally:
        conn.close()


def _get_users_in_active_trials():
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT DISTINCT pp.user_id
            FROM project_participants pp
            JOIN project_rounds pr
              ON pp.RoundID = pr.RoundID
            WHERE pr.EndDate IS NOT NULL
              AND CURDATE() <= pr.EndDate
        """)

        rows = cur.fetchall()

        return {r[0] for r in rows}  # set for fast lookup

    finally:
        conn.close()

def get_selection_results(*, session_id: int):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT ResultID, SessionID, UserID, ResultType, Score, AssignedAt
            FROM selection_results
            WHERE SessionID = %s
            ORDER BY
                CASE
                    WHEN ResultType = 'selected' THEN 1
                    WHEN ResultType = 'alternate' THEN 2
                    ELSE 3
                END,
                AssignedAt ASC,
                ResultID ASC
        """, (session_id,))

        return cur.fetchall()

    finally:
        conn.close()


def clear_selection_results(*, validated_session: dict):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        session_id = int(validated_session["SessionID"])

        cur.execute("""
            DELETE FROM selection_results
            WHERE SessionID = %s
        """, (session_id,))
        conn.commit()
    finally:
        conn.close()


def replace_selected_users(*, validated_session: dict, user_ids: list[str]):
    """
    Replace the provisional selected set.

    MVP behavior:
    - overwrite current selection_results for this session
    - write checked users as ResultType='selected'
    - do not auto-generate alternates here
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    
    session_id = int(validated_session["SessionID"])

    try:
        cur = conn.cursor()

        cur.execute("""
            DELETE FROM selection_results
            WHERE SessionID = %s
        """, (session_id,))

        for user_id in user_ids:
            cur.execute("""
                INSERT INTO selection_results (SessionID, UserID, ResultType, AssignedAt)
                VALUES (%s, %s, 'selected', NOW())
            """, (session_id, user_id))

        conn.commit()

    finally:
        conn.close()


def _get_blacklisted_emails():
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT Email
            FROM user_blacklist
            WHERE BlacklistType = 'email'
              AND IsActive = 1
              AND (ExpiresAt IS NULL OR ExpiresAt >= NOW())
        """)

        rows = cur.fetchall()

        return {
            (r.get("Email") or r.get("email") or "").lower().strip()
            for r in rows
        }

    finally:
        conn.close()


def update_selection_session(validated_session: dict, updates: dict):
    """
    Update selection session fields.

    Minimal implementation:
    Assumes session is stored in DB.
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    set_clauses = []
    values = []

    for key, val in updates.items():
        set_clauses.append(f"{key} = %s")
        values.append(val)

    values.append(int(validated_session["SessionID"]))

    query = f"""
        UPDATE selection_sessions
        SET {', '.join(set_clauses)}
        WHERE SessionID = %s
    """

    cursor.execute(query, values)
    conn.commit()

    cursor.close()
    conn.close()