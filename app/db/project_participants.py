# app/db/project_participants.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_active_trials_for_user(user_id: str) -> list[dict]:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    sql = """
    SELECT
        pp.user_id,

        pr.RoundID,
        pr.RoundName,
        pr.StartDate,
        pr.EndDate,

        pj.ProjectName,
        pj.ProductType

    FROM project_participants pp
    JOIN project_rounds pr ON pp.RoundID = pr.RoundID
    JOIN project_projects pj ON pr.ProjectID = pj.ProjectID

    WHERE pp.user_id = %s
    AND pp.ParticipantStatus IN ('Selected', 'Active')
    AND pp.CompletedAt IS NULL
    """

    cursor.execute(sql, (user_id,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    results = []

    for r in rows:
        results.append({
            "RoundID": r["RoundID"],  # ✅ REQUIRED FOR NDA

            "ProjectName": r["ProjectName"],
            "RoundName": r["RoundName"],
            "ProductType": r["ProductType"],
            "StartDate": r["StartDate"],
            "EndDate": r["EndDate"],

            "Logistics": {},
            "NDARequired": False,
        })

    return results

def remove_project_participant(*, round_id: int, user_id: str) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    sql = """
    DELETE FROM project_participants
    WHERE RoundID = %s AND user_id = %s
    """

    cursor.execute(sql, (round_id, user_id))
    conn.commit()

    cursor.close()
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

def user_is_currently_in_trial(*, user_id: str) -> bool:
    """
    Returns True if the user is currently participating in a trial.

    Definition:
        - ParticipantStatus = 'Selected' OR 'Active'
        - CompletedAt is NULL
    """

    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT 1
            FROM project_participants
            WHERE user_id = %s
              AND CompletedAt IS NULL
              AND ParticipantStatus IN ('Selected', 'Active')
            LIMIT 1
            """,
            (user_id,),
        )

        return cur.fetchone() is not None

    finally:
        conn.close()