# app/db/survey_upload_audit.py

"""Survey upload audit + duplicate protection.

We intentionally do NOT store uploaded CSV files on the server.
Instead, we store a SHA256 hash (and minimal context) so we can:

- Reject accidental re-uploads of the same file (wrong file / wrong project).
- Provide an audit breadcrumb (what was ingested, when, and by whom).

DB remains the source of truth.
"""

from __future__ import annotations

import mysql.connector

from app.config.config import DB_CONFIG


def ensure_table_exists() -> None:
    """Create the audit table if it doesn't exist.

    This is safe to call on every upload.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS survey_upload_audit (
              UploadID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
              FileHash CHAR(64) NOT NULL,
              OriginalFilename VARCHAR(255) DEFAULT NULL,
              UploadedByUserID VARCHAR(20) DEFAULT NULL,
              ProjectID VARCHAR(20) DEFAULT NULL,
              RoundID INT DEFAULT NULL,
              SurveyTypeID VARCHAR(20) DEFAULT NULL,
              SurveyID BIGINT UNSIGNED DEFAULT NULL,
              InsertedAnswerRows INT UNSIGNED DEFAULT NULL,
              UploadedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (UploadID),
              UNIQUE KEY uniq_filehash (FileHash)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        conn.commit()
    finally:
        conn.close()


def hash_exists(file_hash: str) -> bool:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM survey_upload_audit WHERE FileHash = %s LIMIT 1",
            (file_hash,),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def record_upload(
    *,
    file_hash: str,
    original_filename: str | None,
    uploaded_by_user_id: str | None,
    project_id: str | None,
    round_id: int | None,
    survey_type_id: str | None,
    survey_id: int | None,
    inserted_answer_rows: int | None,
) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO survey_upload_audit (
                FileHash,
                OriginalFilename,
                UploadedByUserID,
                ProjectID,
                RoundID,
                SurveyTypeID,
                SurveyID,
                InsertedAnswerRows
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                file_hash,
                original_filename,
                uploaded_by_user_id,
                project_id,
                round_id,
                survey_type_id,
                survey_id,
                inserted_answer_rows,
            ),
        )
        conn.commit()
    finally:
        conn.close()
