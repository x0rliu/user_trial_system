# app/db/round_stakeholders.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_round_stakeholders(round_id: int) -> list[dict]:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                RoundStakeholderID,
                RoundID,
                Email,
                DisplayName,
                user_id,
                StakeholderRole,
                IsPrimary,
                Active,
                AssignedAt,
                Notes
            FROM round_stakeholders
            WHERE RoundID = %s
              AND Active = 1
            ORDER BY IsPrimary DESC, AssignedAt ASC, RoundStakeholderID ASC
            """,
            (round_id,),
        )
        return cur.fetchall() or []
    finally:
        conn.close()

def seed_round_stakeholders_from_project(*, project_id: str, round_id: int) -> None:
    """
    One-time seed: copy project-level stakeholders into this round as defaults.
    After this, edits should be round-scoped only.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO round_stakeholders (
                RoundID, Email, DisplayName, user_id, StakeholderRole,
                IsPrimary, Active, AssignedAt, Notes, CreatedAt
            )
            SELECT
                %s,
                ps.Email,
                ps.DisplayName,
                ps.user_id,
                ps.StakeholderRole,
                COALESCE(ps.IsPrimary, 0),
                COALESCE(ps.Active, 1),
                COALESCE(ps.AssignedAt, NOW()),
                ps.Notes,
                NOW()
            FROM project_stakeholders ps
            WHERE ps.ProjectID = %s
              AND COALESCE(ps.Active, 1) = 1
            """,
            (round_id, project_id),
        )

        conn.commit()
    finally:
        conn.close()
