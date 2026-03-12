# app/db/project_participants.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_active_trials_for_user(user_id: str) -> list[dict]:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    sql = """
    SELECT
        pp.ParticipantID,
        pp.TrialNickname,
        pr.RoundName,
        pr.StartDate,
        pr.EndDate,
        pj.ProjectName,
        pj.ProductType
    FROM project_participants pp
    JOIN project_rounds pr ON pp.RoundID = pr.RoundID
    JOIN project_projects pj ON pr.ProjectID = pj.ProjectID
    WHERE pp.user_id = %s
      AND pp.ParticipantStatus = 'Active'
      AND pr.Status = 'Active'
    """

    cursor.execute(sql, (user_id,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows

def remove_project_participant(*, round_id: int, user_id: str):
    from app.db import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM project_participants
                WHERE RoundID = %s AND user_id = %s
                """,
                (round_id, user_id),
            )
        conn.commit()
    finally:
        conn.close()

def get_past_trials_for_user(user_id: str) -> list[dict]:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    sql = """
    SELECT
        pp.ParticipantID,
        pp.RoundID,
        pj.ProjectName,
        pp.TrialNickname,
        pr.RoundName,
        pr.StartDate,
        pr.EndDate,

        COUNT(sd.DistributionID) AS surveys_issued,

        SUM(
            CASE
                WHEN sd.CompletedAt IS NOT NULL THEN 1
                ELSE 0
            END
        ) AS surveys_returned

    FROM project_participants pp

    JOIN project_rounds pr
        ON pp.RoundID = pr.RoundID

    JOIN project_projects pj
        ON pr.ProjectID = pj.ProjectID

    LEFT JOIN survey_distribution sd
        ON sd.RoundID = pp.RoundID
        AND sd.user_id = pp.user_id

    WHERE
        pp.user_id = %s
        AND pp.ParticipantStatus = 'Completed'

    GROUP BY
        pp.ParticipantID,
        pp.RoundID,
        pj.ProjectName,
        pp.TrialNickname,
        pr.RoundName,
        pr.StartDate,
        pr.EndDate

    ORDER BY
        pr.EndDate DESC
    """

    cursor.execute(sql, (user_id,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows