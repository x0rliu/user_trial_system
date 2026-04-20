# app/db/bonus_survey_sections.py

import mysql.connector
from app.config.config import DB_CONFIG


# -------------------------
# GET
# -------------------------
def get_bonus_survey_sections(*, bonus_survey_id: int) -> list[dict]:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                section_id,
                section_key,
                display_name,
                section_order
            FROM bonus_survey_sections
            WHERE bonus_survey_id = %s
            ORDER BY section_order ASC, section_id ASC
            """,
            (bonus_survey_id,)
        )

        return cur.fetchall()

    finally:
        conn.close()


# -------------------------
# CREATE
# -------------------------
def create_bonus_survey_section(
    *,
    bonus_survey_id: int,
    section_key: str,
    display_name: str,
) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        # get next order
        cur.execute(
            """
            SELECT COALESCE(MAX(section_order), 0) + 1
            FROM bonus_survey_sections
            WHERE bonus_survey_id = %s
            """,
            (bonus_survey_id,)
        )
        next_order = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO bonus_survey_sections (
                bonus_survey_id,
                section_key,
                display_name,
                section_order
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                bonus_survey_id,
                section_key,
                display_name,
                next_order,
            )
        )

        conn.commit()

    finally:
        conn.close()


# -------------------------
# UPDATE (rename)
# -------------------------
def update_bonus_survey_section_name(
    *,
    section_id: int,
    display_name: str,
) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_survey_sections
            SET display_name = %s
            WHERE section_id = %s
            """,
            (display_name, section_id)
        )

        conn.commit()

    finally:
        conn.close()


# -------------------------
# DELETE
# -------------------------
def delete_bonus_survey_section(
    *,
    section_id: int,
) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        # Remove section
        cur.execute(
            """
            DELETE FROM bonus_survey_sections
            WHERE section_id = %s
            """,
            (section_id,)
        )

        conn.commit()

    finally:
        conn.close()