def get_project_for_review(*, project_id: str):
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT *
            FROM project_projects
            WHERE ProjectID = %s
            LIMIT 1
            """,
            (project_id,),
        )

        return cur.fetchone()

    finally:
        conn.close()