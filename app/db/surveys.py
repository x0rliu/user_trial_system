# app/db/surveys.py

import mysql.connector
from typing import Iterable, Tuple
from app.config.config import DB_CONFIG
import json

def create_bonus_survey(
    *,
    created_by_user_id: str,
    survey_name: str,
    survey_link: str,
    purpose: str | None,
    start_date: str,
    end_date: str,
    status: str,
) -> int:
    """
    Insert a bonus survey record.
    Returns BonusSurveyID.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bonus_surveys (
                created_by_user_id,
                survey_title,
                survey_link,
                response_destination,
                open_at,
                close_at,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                created_by_user_id,
                survey_name,
                survey_link,
                purpose,
                start_date,
                end_date,
                status,
            ),
        )

        conn.commit()
        return cur.lastrowid

    finally:
        conn.close()


def insert_bonus_survey_targeting_rules(
    *,
    bonus_survey_id: int,
    created_by_user_id: str,
    rules: Iterable[dict],
) -> None:
    """
    Insert targeting rules for a bonus survey.

    Each rule dict must contain:
      - criterion
      - operator
      - value
      - value_type
      - description (optional)
    """

    if not rules:
        return

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.executemany(
            """
            INSERT INTO bonus_survey_targeting_rules (
                BonusSurveyID,
                Criterion,
                Operator,
                Value,
                ValueType,
                Description,
                CreatedByUserID
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    bonus_survey_id,
                    rule["criterion"],
                    rule["operator"],
                    rule["value"],
                    rule["value_type"],
                    rule.get("description"),
                    created_by_user_id,
                )
                for rule in rules
            ],
        )

        conn.commit()

    finally:
        conn.close()


def get_bonus_survey_by_id(bonus_survey_id: int) -> dict | None:
    """
    Fetch a bonus survey by ID.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                bonus_survey_id,
                created_by_user_id,
                survey_title,
                survey_link,
                response_destination,
                open_at,
                close_at,
                status,
                created_at,
                updated_at
            FROM bonus_surveys
            WHERE bonus_survey_id = %s
            """,
            (bonus_survey_id,),
        )

        return cur.fetchone()

    finally:
        conn.close()


def get_bonus_survey_targeting_rules(bonus_survey_id: int) -> list[dict]:
    """
    Fetch targeting rules for a bonus survey.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                RuleID,
                BonusSurveyID,
                Criterion,
                Operator,
                Value,
                ValueType,
                Description,
                CreatedAt,
                CreatedByUserID
            FROM bonus_survey_targeting_rules
            WHERE BonusSurveyID = %s
            ORDER BY RuleID
            """,
            (bonus_survey_id,),
        )

        return cur.fetchall()

    finally:
        conn.close()


def get_pending_bonus_surveys_for_user(
    created_by_user_id: str,
) -> list[dict]:
    """
    Fetch pending approval bonus surveys created by a user.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                bonus_survey_id,
                survey_title,
                status,
                created_at
            FROM bonus_surveys
            WHERE created_by_user_id = %s
                AND status IN (
                    'pending_approval',
                    'pending',
                    'submitted'
                )
            ORDER BY created_at DESC
            """,
            (created_by_user_id,),
        )

        return cur.fetchall()

    finally:
        conn.close()

def get_active_bonus_surveys_for_user(user_id: str) -> list[dict]:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                bonus_survey_id,
                survey_title
            FROM bonus_surveys
            WHERE created_by_user_id = %s
              AND status = 'active'
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        return cur.fetchall() or []
    finally:
        conn.close()


def update_bonus_survey_status(
    *,
    bonus_survey_id: int,
    status: str,
) -> None:
    """
    Directly update bonus survey status by survey ID.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_surveys
            SET status = %s,
                updated_at = NOW()
            WHERE bonus_survey_id = %s
            """,
            (status, bonus_survey_id),
        )

        conn.commit()

    finally:
        conn.close()


def set_bonus_survey_status_by_tracker(
    *,
    tracker_id: int,
    new_status: str,
) -> None:
    """
    Update bonus survey status using its tracker.
    """

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

        bonus_survey_id = row[0]

        cur.execute(
            """
            UPDATE bonus_surveys
            SET status = %s,
                updated_at = NOW()
            WHERE bonus_survey_id = %s
            """,
            (new_status, bonus_survey_id),
        )

        conn.commit()

    finally:
        conn.close()

def get_eligible_active_bonus_surveys_for_user(user_id: str) -> list[dict]:
    """
    Return active bonus surveys this user is eligible to take.
    Eligibility rules are currently minimal but expandable.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                bs.bonus_survey_id,
                bs.survey_title,
                bs.open_at,
                bs.close_at,
                bs.response_destination AS purpose,
                bs.created_by_user_id,

                CONCAT(up.FirstName, ' ', up.LastName) AS requestor_name
            FROM bonus_surveys bs
            JOIN user_pool up
            ON up.user_id = bs.created_by_user_id
            WHERE bs.status = 'active'
            AND bs.is_open = 1
            ORDER BY bs.open_at ASC
            """
        )


        return cur.fetchall() or []

    finally:
        conn.close()

# app/db/D.py


from app.config.config import DB_CONFIG
import mysql.connector


def get_bonus_survey_by_id(bonus_survey_id: int) -> dict | None:
    """
    Fetch a single bonus survey by ID.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT *
            FROM bonus_surveys
            WHERE bonus_survey_id = %s
            LIMIT 1
            """,
            (bonus_survey_id,),
        )

        return cur.fetchone()

    finally:
        conn.close()

def get_bonus_survey_engagement(*, survey_id: int):
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN seen_at IS NOT NULL THEN 1 ELSE 0 END) AS clicks,
                SUM(CASE WHEN started_at IS NOT NULL THEN 1 ELSE 0 END) AS opens,
                SUM(CASE WHEN completed_at IS NOT NULL THEN 1 ELSE 0 END) AS responses
            FROM bonus_survey_participation
            WHERE bonus_survey_id = %s
            """,
            (survey_id,),
        )

        row = cur.fetchone() or {}

        total = row.get("total") or 0
        responses = row.get("responses") or 0

        completion_rate = 0
        if total > 0:
            completion_rate = round((responses / total) * 100, 1)

        return {
            "clicks": row.get("clicks") or 0,
            "opens": row.get("opens") or 0,
            "responses": responses,
            "completion_rate": completion_rate,
        }

    finally:
        conn.close()

def update_bonus_survey_open_state(*, bonus_survey_id: int, is_open: int):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_surveys
            SET is_open = %s,
                updated_at = NOW()
            WHERE bonus_survey_id = %s
            """,
            (is_open, bonus_survey_id),
        )

        if cur.rowcount == 0:
            raise RuntimeError(
                f"update_bonus_survey_open_state failed: no survey found for id={bonus_survey_id}"
            )

        conn.commit()
    finally:
        conn.close()

def save_bonus_survey_sections(
    *,
    bonus_survey_id: int,
    section_payload: dict,
) -> None:
    """
    Persist AI-derived section structure.

    Expected format:
    {
        "sections": [
            {
                "section_key": "...",
                "questions": [...]
            }
        ]
    }
    """

    if not isinstance(section_payload, dict):
        raise ValueError("section_payload must be dict")

    if "sections" not in section_payload:
        raise ValueError("section_payload missing 'sections'")

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_surveys
            SET section_json = %s,
                updated_at = NOW()
            WHERE bonus_survey_id = %s
            """,
            (
                json.dumps(section_payload, ensure_ascii=False),
                bonus_survey_id,
            ),
        )

        if cur.rowcount == 0:
            raise RuntimeError(
                f"save_bonus_survey_sections failed: no survey found for id={bonus_survey_id}"
            )

        conn.commit()

    finally:
        conn.close()


def get_bonus_survey_sections(
    *,
    bonus_survey_id: int,
) -> dict | None:
    """
    Fetch stored section structure.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT section_json
            FROM bonus_surveys
            WHERE bonus_survey_id = %s
            LIMIT 1
            """,
            (bonus_survey_id,),
        )

        row = cur.fetchone()

    finally:
        conn.close()

    if not row:
        return None

    raw = row.get("section_json")

    if not raw:
        return None

    try:
        return json.loads(raw)
    except Exception:
        return None