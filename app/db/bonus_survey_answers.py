# app/db/bonus_survey_answers.py

import mysql.connector
from app.config.config import DB_CONFIG


def delete_answers_for_bonus_survey(*, bonus_survey_id: int) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            DELETE a
            FROM bonus_survey_answers a
            JOIN bonus_survey_participation p
              ON p.bonus_survey_participation_id = a.bonus_survey_participation_id
            WHERE p.bonus_survey_id = %s
            """,
            (bonus_survey_id,),
        )

        conn.commit()
    finally:
        conn.close()


def insert_bonus_survey_answer(
    *,
    bonus_survey_participation_id: int,
    question_text: str,
    question_hash: str,
    answer_text: str | None,
) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bonus_survey_answers (
                bonus_survey_participation_id,
                QuestionText,
                QuestionHash,
                AnswerText
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                bonus_survey_participation_id,
                question_text,
                question_hash,
                answer_text,
            ),
        )

        conn.commit()
    finally:
        conn.close()

def get_bonus_survey_answer_rows(bonus_survey_id: int):
    """
    Fetch all completed answer rows for a given bonus survey.

    Returns flat rows. No formatting, no grouping.
    Includes:
    - demographics (from user_pool)
    - profile rows (CategoryName + LevelDescription)
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                bs.bonus_survey_id,
                bs.survey_title,

                p.bonus_survey_participation_id,
                p.user_id,
                p.completed_at,

                -- 🔥 DEMOGRAPHICS (user_pool)
                u.Gender,
                u.BirthYear,
                u.CountryCode,
                u.City,

                -- 🔥 PROFILE SYSTEM (multi-row, no aggregation)
                up.CategoryName,
                up.LevelDescription,

                -- 🔥 ANSWERS
                a.QuestionText,
                a.QuestionHash,
                a.AnswerText,
                a.CreatedAt AS answer_created_at

            FROM bonus_survey_answers a
            JOIN bonus_survey_participation p
                ON a.bonus_survey_participation_id = p.bonus_survey_participation_id
            JOIN bonus_surveys bs
                ON p.bonus_survey_id = bs.bonus_survey_id

            -- 🔥 DEMOGRAPHICS JOIN
            LEFT JOIN user_pool u
                ON u.user_id = p.user_id

            -- 🔥 PROFILE JOIN
            LEFT JOIN user_profile_map upm
                ON upm.user_id = p.user_id
            LEFT JOIN user_profiles up
                ON up.ProfileUID = upm.ProfileUID

            WHERE
                p.bonus_survey_id = %s
                AND p.completed_at IS NOT NULL

            ORDER BY
                p.bonus_survey_participation_id ASC,
                a.AnswerID ASC
            """,
            (bonus_survey_id,)
        )

        rows = cursor.fetchall()
        return rows

    finally:
        cursor.close()
        conn.close()