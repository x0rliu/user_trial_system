import mysql.connector
from app.config.config import DB_CONFIG


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def get_trial_history(user_id: str):

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    events = []

    # --------------------------------
    # User asked to be notified
    # --------------------------------
    cur.execute("""
        SELECT
            i.CreatedAt AS EventTime,
            CONCAT('User requested notification for ', p.ProjectName) AS EventText
        FROM project_round_interest i
        JOIN project_rounds r ON r.RoundID = i.RoundID
        JOIN project_projects p ON p.ProjectID = r.ProjectID
        WHERE i.user_id = %s
    """, (user_id,))

    events += cur.fetchall()

    # --------------------------------
    # User applied
    # --------------------------------
    cur.execute("""
        SELECT
            a.AppliedAt AS EventTime,
            CONCAT('User applied for ', p.ProjectName) AS EventText
        FROM project_applicants a
        JOIN project_rounds r ON r.RoundID = a.RoundID
        JOIN project_projects p ON p.ProjectID = r.ProjectID
        WHERE a.user_id = %s
    """, (user_id,))

    events += cur.fetchall()

    # --------------------------------
    # User selected
    # --------------------------------
    cur.execute("""
        SELECT
            part.SelectedAt AS EventTime,
            CONCAT('User selected for ', p.ProjectName) AS EventText
        FROM project_participants part
        JOIN project_rounds r ON r.RoundID = part.RoundID
        JOIN project_projects p ON p.ProjectID = r.ProjectID
        WHERE part.user_id = %s
        AND part.SelectedAt IS NOT NULL
    """, (user_id,))

    events += cur.fetchall()

    # --------------------------------
    # Trial completed
    # --------------------------------
    cur.execute("""
        SELECT
            part.CompletedAt AS EventTime,
            CONCAT('User completed trial ', p.ProjectName) AS EventText
        FROM project_participants part
        JOIN project_rounds r ON r.RoundID = part.RoundID
        JOIN project_projects p ON p.ProjectID = r.ProjectID
        WHERE part.user_id = %s
        AND part.CompletedAt IS NOT NULL
    """, (user_id,))

    events += cur.fetchall()

    conn.close()

    # --------------------------------
    # Sort timeline
    # --------------------------------
    events = [e for e in events if e["EventTime"]]

    events.sort(
        key=lambda x: x["EventTime"],
        reverse=True
    )

    return events