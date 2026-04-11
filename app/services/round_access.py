import mysql.connector
from app.config.config import DB_CONFIG
from app.db.user_roles import get_effective_permission_level


def validate_round_access(
    *,
    actor_user_id: str,
    round_id: int,
    required_role: str,
    allow_admin: bool = True,
) -> dict | None:
    if not actor_user_id or not round_id:
        return None

    try:
        round_id = int(round_id)
    except (TypeError, ValueError):
        return None

    permission_level = get_effective_permission_level(actor_user_id)
    is_admin = permission_level == 100

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                pr.*,
                pp.CreatedBy AS requested_by_user_id
            FROM project_rounds pr
            JOIN project_projects pp
              ON pp.ProjectID = pr.ProjectID
            WHERE pr.RoundID = %s
            LIMIT 1
            """,
            (round_id,),
        )
        round_row = cur.fetchone()

        from app.services.security_log import log_security_event

        if not round_row:
            log_security_event(
                user_id=actor_user_id,
                action="round_access",
                reason="round_not_found",
                metadata={"round_id": round_id},
            )
            return None

        if allow_admin and is_admin:
            return round_row

        if required_role == "ut_lead":
            if permission_level < 70:
                log_security_event(
                    user_id=actor_user_id,
                    action="round_access",
                    reason="insufficient_permission",
                    metadata={"round_id": round_id},
                )
                return None
            if round_row.get("UTLead_UserID") != actor_user_id:
                log_security_event(
                    user_id=actor_user_id,
                    action="round_access",
                    reason="ownership_mismatch",
                    metadata={"round_id": round_id},
                )
                return None
            return round_row

        if required_role == "product":
            if permission_level < 50:
                return None
            if round_row.get("requested_by_user_id") != actor_user_id:
                return None
            return round_row

        if required_role == "participant":
            if permission_level < 20:
                return None

            cur.execute(
                """
                SELECT 1
                FROM project_participants
                WHERE RoundID = %s
                  AND user_id = %s
                LIMIT 1
                """,
                (round_id, actor_user_id),
            )
            participant = cur.fetchone()

            if participant:
                return round_row

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
                LIMIT 1
                """,
                (actor_user_id,),
            )
            user_row = cur.fetchone()
            if not user_row:
                return None

            is_eligible = (
                user_row.get("ParticipantStatus") == "active"
                and bool(user_row.get("EmailVerified"))
                and user_row.get("GlobalNDA_Status") == "Signed"
                and bool(user_row.get("GuidelinesCompletedAt"))
                and bool(user_row.get("WelcomeSeenAt"))
                and int(user_row.get("Status") or 0) == 0
            )

            if not is_eligible:
                return None

            return round_row

        return None

    finally:
        conn.close()
