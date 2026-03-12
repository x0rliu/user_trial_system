# app/services/survey_results_upload.py

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from typing import Any

import mysql.connector

from app.config.config import DB_CONFIG
from app.db.user_pool import get_user_by_email
from app.db.survey_upload_audit import ensure_table_exists, hash_exists, record_upload


@dataclass(frozen=True)
class UploadContext:
    project_id: str
    round_id: int
    survey_type_id: str
    survey_title: str | None = None
    uploaded_by_user_id: str | None = None


@dataclass(frozen=True)
class UploadSummary:
    file_hash: str
    survey_id: int
    total_respondent_rows: int
    matched_users: int
    ignored_rows_no_user: int
    total_question_columns: int
    inserted_answer_rows: int
    blank_answer_cells: int
    numeric_answer_cells: int


class UploadError(Exception):
    pass


def _sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _parse_timestamp(raw: str) -> datetime:
    raw = (raw or "").strip()
    if not raw:
        return datetime.utcnow()

    # Google Forms typical: 1/20/2026 13:45:00
    fmts = [
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue

    # Last resort: deterministic, do not crash ingestion
    return datetime.utcnow()


def _question_id_for_text(question_text: str) -> str:
    """Deterministic QuestionID placeholder.

    We will replace this later with survey_questions table + real IDs.
    For now we generate a stable ID per exact question text.
    """
    h = hashlib.sha1(question_text.encode("utf-8", errors="ignore")).hexdigest()
    return f"Q_{h[:16]}"


def ingest_google_forms_csv(
    *,
    ctx: UploadContext,
    csv_bytes: bytes,
    original_filename: str | None,
) -> UploadSummary:
    """Parse a Google Forms CSV and write survey answers into the DB.

    Inserts:
      - 1 row into survey_tracker (one per upload)
      - 1 row into survey_distribution per matched user
      - 1 row into survey_answers per user-per-question column

    Duplicate protection:
      - Reject if SHA256 hash already exists in survey_upload_audit
    """

    ensure_table_exists()

    file_hash = _sha256_bytes(csv_bytes)
    if hash_exists(file_hash):
        raise UploadError(
            "Duplicate upload blocked: this file hash already exists in the system. "
            "If you meant to upload a different survey export, re-export and try again."
        )

    # Google exports are often Windows-1252.
    try:
        text = csv_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = csv_bytes.decode("cp1252", errors="replace")

    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise UploadError("CSV parse failed: no headers found.")

    fieldnames = [c.strip() for c in reader.fieldnames]

    # Minimal, explicit assumptions for now.
    timestamp_col = "Timestamp"
    email_col = "Email Address"
    if timestamp_col not in fieldnames:
        raise UploadError("CSV missing required column: Timestamp")
    if email_col not in fieldnames:
        raise UploadError("CSV missing required column: Email Address")

    metadata_cols = {timestamp_col, email_col}
    question_cols = [c for c in fieldnames if c not in metadata_cols]
    if not question_cols:
        raise UploadError("CSV has no question columns after metadata removal.")

    total_respondent_rows = 0
    matched_users = 0
    ignored_rows_no_user = 0
    inserted_answer_rows = 0
    blank_answer_cells = 0
    numeric_answer_cells = 0

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        conn.start_transaction()
        cur = conn.cursor()

        # --------------------------------------------------
        # Create Survey Tracker row (one per upload)
        # --------------------------------------------------
        survey_date = datetime.utcnow()
        cur.execute(
            """
            INSERT INTO survey_tracker (
                ProjectID,
                RoundID,
                SurveyTypeID,
                SurveyTitle,
                SurveyDate,
                Status
            ) VALUES (%s,%s,%s,%s,%s,'closed')
            """,
            (
                ctx.project_id,
                int(ctx.round_id),
                ctx.survey_type_id,
                ctx.survey_title,
                survey_date,
            ),
        )
        survey_id = int(cur.lastrowid)

        # --------------------------------------------------
        # Read each respondent and insert
        # --------------------------------------------------
        for row in reader:
            print("ROW:", row)
            total_respondent_rows += 1

            email = (row.get(email_col) or "").strip().lower()
            if not email:
                ignored_rows_no_user += 1
                continue

            user = get_user_by_email(email)
            print("EMAIL:", email, "USER:", user)
            if not user:
                ignored_rows_no_user += 1
                continue

            user_id = user["user_id"]
            matched_users += 1

            submitted_at = _parse_timestamp(row.get(timestamp_col) or "")

            # Distribution row per user per upload
            cur.execute(
                """
                INSERT INTO survey_distribution (
                    SurveyID,
                    ProjectID,
                    RoundID,
                    user_id,
                    SurveyTypeID,
                    SentAt,
                    CompletedAt,
                    Status
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,'completed')
                """,
                (
                    survey_id,
                    ctx.project_id,
                    int(ctx.round_id),
                    user_id,
                    ctx.survey_type_id,
                    submitted_at,
                    submitted_at,
                ),
            )
            distribution_id = int(cur.lastrowid)

            # Answers: one row per question column
            answer_rows: list[tuple[Any, ...]] = []
            for q in question_cols:
                q_text = q
                a_val_raw = row.get(q, "")
                a_val = "" if a_val_raw is None else str(a_val_raw).strip()

                if a_val == "":
                    blank_answer_cells += 1

                a_num = None
                if a_val != "":
                    try:
                        a_num = float(a_val)
                        numeric_answer_cells += 1
                    except ValueError:
                        a_num = None

                answer_rows.append(
                    (
                        survey_id,
                        distribution_id,
                        user_id,
                        ctx.project_id,
                        int(ctx.round_id),
                        ctx.survey_type_id,
                        _question_id_for_text(q_text),
                        q_text,
                        a_val if a_val != "" else None,
                        a_num,
                        submitted_at,
                    )
                )

            cur.executemany(
                """
                INSERT INTO survey_answers (
                    SurveyID,
                    DistributionID,
                    user_id,
                    ProjectID,
                    RoundID,
                    SurveyTypeID,
                    QuestionID,
                    QuestionText,
                    AnswerValue,
                    AnswerNumeric,
                    SubmittedAt
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                answer_rows,
            )

            inserted_answer_rows += len(answer_rows)

        # --------------------------------------------------
        # Record upload hash (duplicate guard)
        # --------------------------------------------------
        record_upload(
            file_hash=file_hash,
            original_filename=original_filename,
            uploaded_by_user_id=ctx.uploaded_by_user_id,
            project_id=ctx.project_id,
            round_id=int(ctx.round_id),
            survey_type_id=ctx.survey_type_id,
            survey_id=survey_id,
            inserted_answer_rows=inserted_answer_rows,
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return UploadSummary(
        file_hash=file_hash,
        survey_id=survey_id,
        total_respondent_rows=total_respondent_rows,
        matched_users=matched_users,
        ignored_rows_no_user=ignored_rows_no_user,
        total_question_columns=len(question_cols),
        inserted_answer_rows=inserted_answer_rows,
        blank_answer_cells=blank_answer_cells,
        numeric_answer_cells=numeric_answer_cells,
    )
