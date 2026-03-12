# app/db/surveys.py

import mysql.connector
from typing import Iterable, Tuple
from app.config.config import DB_CONFIG


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

        # Resolve bonus_survey_id from tracker
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

        # Update survey status
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
            ORDER BY bs.open_at ASC
            """
        )


        return cur.fetchall() or []

    finally:
        conn.close()

