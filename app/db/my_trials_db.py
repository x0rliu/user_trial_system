# app/db/my_trials_db.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def get_my_trials(user_id):
    """
    Participant-facing trial state projection.

    Display precedence for /my_trials:
    1. joined wins over applied
    2. applied wins over watching
    3. watching only appears for upcoming approved rounds

    This function is read-only. It does not mutate applicant,
    participant, or interest state.
    """

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    result = {
        "watching": [],
        "applied": [],
        "joined": [],
    }

    # -----------------------------
    # Joined / Active
    # -----------------------------
    cur.execute(
        """
        SELECT
            p.ProjectID,
            p.ProjectName,
            r.RoundID,
            r.RoundNumber,
            r.RoundName,
            r.Status AS RoundStatus,
            part.ParticipantStatus,
            part.SelectedAt,

            CASE
                WHEN nda.NDAStatus = 'Signed' THEN 1
                ELSE 0
            END AS nda_signed

        FROM project_participants part
        JOIN project_rounds r ON r.RoundID = part.RoundID
        JOIN project_projects p ON p.ProjectID = r.ProjectID

        LEFT JOIN project_ndas nda
            ON nda.user_id = part.user_id
            AND nda.ProjectID = p.ProjectID
            AND nda.RoundID = r.RoundID

        WHERE part.user_id = %s
          AND part.CompletedAt IS NULL
          AND part.ParticipantStatus IN ('Selected', 'Active')
        ORDER BY part.SelectedAt DESC, r.StartDate ASC, r.RoundID ASC
        """,
        (user_id,),
    )

    result["joined"] = cur.fetchall()

    # -----------------------------
    # Applied / Pending Applications
    # -----------------------------
    cur.execute(
        """
        SELECT
            p.ProjectID,
            p.ProjectName,
            r.RoundID,
            r.RoundNumber,
            r.RoundName,
            r.Status AS RoundStatus,
            a.AppliedAt,
            a.ScreeningStatus,
            a.ApplicationStatus
        FROM project_applicants a
        JOIN project_rounds r ON r.RoundID = a.RoundID
        JOIN project_projects p ON p.ProjectID = r.ProjectID
        WHERE a.user_id = %s
          AND a.FinalDecision IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM project_participants part
              WHERE part.user_id = a.user_id
                AND part.RoundID = a.RoundID
          )
        ORDER BY a.AppliedAt DESC, r.StartDate ASC, r.RoundID ASC
        """,
        (user_id,),
    )

    result["applied"] = cur.fetchall()

    # -----------------------------
    # Watching / Notify Me
    # -----------------------------
    cur.execute(
        """
        SELECT
            p.ProjectID,
            p.ProjectName,
            r.RoundID,
            r.RoundNumber,
            r.RoundName,
            r.Status AS RoundStatus,
            r.StartDate,
            i.CreatedAt AS WatchingSince,
            i.NotifiedAt
        FROM project_round_interest i
        JOIN project_rounds r ON r.RoundID = i.RoundID
        JOIN project_projects p ON p.ProjectID = r.ProjectID
        WHERE i.user_id = %s
          AND r.Status = 'approved'
          AND i.WithdrawnAt IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM project_applicants a
              WHERE a.user_id = i.user_id
                AND a.RoundID = i.RoundID
          )
          AND NOT EXISTS (
              SELECT 1
              FROM project_participants part
              WHERE part.user_id = i.user_id
                AND part.RoundID = i.RoundID
          )
        ORDER BY r.StartDate ASC, i.CreatedAt DESC, r.RoundID ASC
        """,
        (user_id,),
    )

    result["watching"] = cur.fetchall()

    conn.close()

    return result