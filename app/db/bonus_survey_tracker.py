# app/db/bonus_survey_tracker.py

from app.config.config import DB_CONFIG
import mysql.connector


def create_tracker_for_bonus_survey(*, bonus_survey_id: int) -> int:
    """
    Create a tracker row for a bonus survey.
    Returns tracker_id.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bonus_survey_tracker (
                survey_id,
                current_state
            )
            VALUES (%s, %s)
            """,
            (bonus_survey_id, "pending"),
        )

        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def add_tracker_entry_submitted(
    *,
    tracker_id: int,
    actor_user_id: str,
):
    """
    Add initial 'submitted' entry to tracker.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bonus_survey_tracker_entries (
                tracker_id,
                entry_type,
                actor_user_id
            )
            VALUES (%s, %s, %s)
            """,
            (tracker_id, "submitted", actor_user_id),
        )

        conn.commit()
    finally:
        conn.close()

def add_tracker_entry_info_requested(
    *,
    tracker_id: int,
    actor_user_id: str,
    detail_text: str,
):
    """
    Approver asks for more information.
    Does NOT change tracker state.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bonus_survey_tracker_entries (
                tracker_id,
                entry_type,
                actor_user_id,
                reason_code,
                detail_text
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                tracker_id,
                "info_requested",
                actor_user_id,
                "more_information",
                detail_text,
            ),
        )

        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def add_tracker_entry_info_response(
    *,
    tracker_id: int,
    actor_user_id: str,
    resolves_entry_id: int,
    detail_text: str,
):
    """
    BSC responds to an info request.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bonus_survey_tracker_entries (
                tracker_id,
                entry_type,
                actor_user_id,
                resolves_entry_id,
                detail_text
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                tracker_id,
                "info_response",
                actor_user_id,
                resolves_entry_id,
                detail_text,
            ),
        )

        conn.commit()
    finally:
        conn.close()


def add_tracker_entry_changes_requested(
    *,
    tracker_id: int,
    actor_user_id: str,
    detail_text: str,
):
    """
    Approver requests changes.
    Moves tracker state to 'changes_requested'.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bonus_survey_tracker_entries (
                tracker_id,
                entry_type,
                actor_user_id,
                reason_code,
                detail_text
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                tracker_id,
                "changes_requested",
                actor_user_id,
                "request_change",
                detail_text,
            ),
        )

        cur.execute(
            """
            UPDATE bonus_survey_tracker
            SET current_state = %s
            WHERE tracker_id = %s
            """,
            ("changes_requested", tracker_id),
        )

        conn.commit()
    finally:
        conn.close()


def add_tracker_entry_resubmitted(
    *,
    tracker_id: int,
    actor_user_id: str,
):
    """
    BSC resubmits after changes.
    Moves tracker state back to 'pending'.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bonus_survey_tracker_entries (
                tracker_id,
                entry_type,
                actor_user_id
            )
            VALUES (%s, %s, %s)
            """,
            (tracker_id, "resubmitted", actor_user_id),
        )

        cur.execute(
            """
            UPDATE bonus_survey_tracker
            SET current_state = %s
            WHERE tracker_id = %s
            """,
            ("pending", tracker_id),
        )

        conn.commit()
    finally:
        conn.close()


def add_tracker_entry_approved(
    *,
    tracker_id: int,
    actor_user_id: str,
):
    """
    Approver approves survey.
    Locks tracker and moves to 'active'.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bonus_survey_tracker_entries (
                tracker_id,
                entry_type,
                actor_user_id
            )
            VALUES (%s, %s, %s)
            """,
            (tracker_id, "approved", actor_user_id),
        )

        cur.execute(
            """
            UPDATE bonus_survey_tracker
            SET current_state = %s,
                locked_at = NOW()
            WHERE tracker_id = %s
            """,
            ("active", tracker_id),
        )

        conn.commit()
    finally:
        conn.close()


def add_tracker_entry_rejected(
    *,
    tracker_id: int,
    actor_user_id: str,
    detail_text: str,
):
    """
    Approver rejects survey as unsuitable.
    Terminal state.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bonus_survey_tracker_entries (
                tracker_id,
                entry_type,
                actor_user_id,
                reason_code,
                detail_text
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                tracker_id,
                "rejected",
                actor_user_id,
                "unsuitable",
                detail_text,
            ),
        )

        cur.execute(
            """
            UPDATE bonus_survey_tracker
            SET current_state = %s,
                locked_at = NOW()
            WHERE tracker_id = %s
            """,
            ("rejected", tracker_id),
        )

        conn.commit()
    finally:
        conn.close()

def get_pending_bonus_survey_trackers() -> list[dict]:
    """
    Fetch all bonus survey trackers that are awaiting action.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                t.tracker_id,
                t.survey_id AS bonus_survey_id,
                t.current_state,
                s.survey_title,
                s.created_by_user_id,
                s.created_at
            FROM bonus_survey_tracker t
            JOIN bonus_surveys s
              ON s.bonus_survey_id = t.survey_id
            WHERE t.current_state IN (
                'pending',
                'changes_requested'
            )
            ORDER BY s.created_at ASC
            """
        )

        return cur.fetchall() or []

    finally:
        conn.close()


def get_pending_bonus_survey_approvals() -> list[dict]:
    """
    Return all bonus surveys awaiting approval.

    Inclusion rules:
    - bonus_surveys.status = 'pending_approval'
    - tracker.current_state = 'pending'
    - tracker.locked_at IS NULL

    Ordering:
    - Oldest activity first
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                bs.bonus_survey_id,
                bs.survey_title,

                bs.created_by_user_id AS requested_by_user_id,
                CONCAT(up.FirstName, ' ', up.LastName) AS requested_by_name,

                t.tracker_id,
                t.current_state,

                MIN(e.created_at) AS submitted_at,
                MAX(e.created_at) AS last_activity_at,
                MAX(e.entry_type) AS last_entry_type

            FROM bonus_surveys bs

            JOIN bonus_survey_tracker t
            ON t.survey_id = bs.bonus_survey_id

            LEFT JOIN bonus_survey_tracker_entries e
            ON e.tracker_id = t.tracker_id

            LEFT JOIN user_pool up
            ON up.user_id = bs.created_by_user_id

            WHERE bs.status = 'pending_approval'
            AND t.current_state = 'pending'
            AND t.locked_at IS NULL

            GROUP BY
                bs.bonus_survey_id,
                t.tracker_id,
                bs.created_by_user_id,
                up.FirstName,
                up.LastName

            ORDER BY last_activity_at ASC
            """
        )

        return cur.fetchall() or []

    finally:
        conn.close()


def get_tracker_by_id(tracker_id: int) -> dict | None:
    """
    Fetch a single bonus survey tracker by ID.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                tracker_id,
                survey_id AS bonus_survey_id,
                current_state,
                created_at,
                locked_at
            FROM bonus_survey_tracker
            WHERE tracker_id = %s
            LIMIT 1
            """,
            (tracker_id,),
        )

        return cur.fetchone()

    finally:
        conn.close()

def get_tracker_entries(tracker_id: int) -> list[dict]:
    """
    Fetch all timeline entries for a tracker, oldest first.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                entry_id,
                tracker_id,
                entry_type,
                actor_user_id,
                reason_code,
                detail_text,
                resolves_entry_id,
                created_at
            FROM bonus_survey_tracker_entries
            WHERE tracker_id = %s
            ORDER BY created_at ASC
            """,
            (tracker_id,),
        )

        return cur.fetchall() or []

    finally:
        conn.close()

def get_bonus_survey_id_by_tracker(tracker_id: int) -> int:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT survey_id
            FROM bonus_survey_tracker
            WHERE tracker_id = %s
            """,
            (tracker_id,),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                f"No bonus_survey_tracker found for tracker_id={tracker_id}"
            )
        return row[0]
    finally:
        conn.close()
