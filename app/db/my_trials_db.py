import mysql.connector
from app.config.config import DB_CONFIG


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def get_my_trials(user_id):

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    result = {
        "watching": [],
        "applied": [],
        "joined": [],
    }

    # -----------------------------
    # Watching (interest)
    # -----------------------------
    cur.execute(
        """
        SELECT
            p.ProjectID,
            p.ProjectName,
            r.RoundID
        FROM project_round_interest i
        JOIN project_rounds r ON r.RoundID = i.RoundID
        JOIN project_projects p ON p.ProjectID = r.ProjectID
        WHERE i.user_id = %s
        """,
        (user_id,)
    )

    result["watching"] = cur.fetchall()

    # -----------------------------
    # Applied
    # -----------------------------
    cur.execute(
        """
        SELECT
            p.ProjectID,
            p.ProjectName,
            r.RoundID,
            a.AppliedAt
        FROM project_applicants a
        JOIN project_rounds r ON r.RoundID = a.RoundID
        JOIN project_projects p ON p.ProjectID = r.ProjectID
        WHERE a.user_id = %s
        AND (a.FinalDecision IS NULL)
        ORDER BY a.AppliedAt DESC
        """,
        (user_id,)
    )

    result["applied"] = cur.fetchall()

    # -----------------------------
    # Joined / Active
    # -----------------------------
    cur.execute(
        """
        SELECT
            p.ProjectID,
            p.ProjectName,
            r.RoundID,
            part.ParticipantStatus,
            part.SelectedAt,

            CASE 
                WHEN nda.NDAStatus = 'Signed' THEN 1
                ELSE 0
            END AS nda_signed

        FROM project_participants part
        JOIN project_rounds r ON r.RoundID = part.RoundID
        JOIN project_projects p ON p.ProjectID = r.ProjectID

        LEFT JOIN user_ndas nda
            ON nda.user_id = part.user_id
            AND nda.ProjectID = p.ProjectID
            AND nda.RoundID = r.RoundID

        WHERE part.user_id = %s
        AND part.ParticipantStatus IN ('Selected','Active')
        """,
        (user_id,)
    )

    result["joined"] = cur.fetchall()

    conn.close()

    return result