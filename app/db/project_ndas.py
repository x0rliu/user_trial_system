# app/db/project_ndas.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_round_nda_status(*, user_id: str, round_id: int) -> dict:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    sql = """
    SELECT
        NDAStatus,
        DateSigned,
        FilePath
    FROM project_ndas
    WHERE user_id = %s
      AND RoundID = %s
    ORDER BY UpdatedAt DESC
    LIMIT 1
    """

    cursor.execute(sql, (user_id, round_id))
    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if not row:
        return {
            "required": True,   # ✅ FIX
            "signed": False,
            "status": "Missing",
            "signed_at": None,
            "file_path": None,
        }

    status = row["NDAStatus"]

    return {
        "required": True,
        "signed": status == "Signed",
        "status": status,
        "signed_at": row["DateSigned"],
        "file_path": row["FilePath"],
    }

def insert_signed_round_nda(*, user_id: str, round_id: int):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO project_ndas (
            user_id,
            ProjectID,
            RoundID,
            NDAStatus,
            DocumentHash,
            FilePath,
            DateSent,
            DateSigned
        )
        SELECT
            %s,
            pr.ProjectID,
            %s,
            'Signed',
            'placeholder_hash',
            'placeholder_path',
            NOW(),
            NOW()
        FROM project_rounds pr
        WHERE pr.RoundID = %s
        """,
        (user_id, round_id, round_id),
    )

    conn.commit()
    cursor.close()
    conn.close()