import mysql.connector
from app.config.config import DB_CONFIG
from app.db.user_roles import get_effective_permission_level
from app.services.round_access import validate_round_access


def validate_selection_session_access(
    *,
    actor_user_id: str,
    session_id: int,
    round_id: int,
) -> dict | None:
    if not actor_user_id or not session_id or not round_id:
        return None

    try:
        session_id = int(session_id)
        round_id = int(round_id)
    except (TypeError, ValueError):
        return None

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT SessionID, RoundID, UTLead_UserID, TargetUsers, Status
            FROM selection_sessions
            WHERE SessionID = %s
            LIMIT 1
            """,
            (session_id,),
        )
        selection_session = cur.fetchone()
    finally:
        conn.close()

    if not selection_session:
        return None

    if int(selection_session.get("RoundID") or 0) != round_id:
        return None

    round_row = validate_round_access(
        actor_user_id=actor_user_id,
        round_id=round_id,
        required_role="ut_lead",
        allow_admin=True,
    )
    if not round_row:
        return None

    permission_level = get_effective_permission_level(actor_user_id)
    is_admin = permission_level == 100

    if not is_admin and selection_session.get("UTLead_UserID") != actor_user_id:
        return None

    return selection_session
