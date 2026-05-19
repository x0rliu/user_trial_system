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
from app.utils.upload_security import require_csv_upload


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
    matched_by_token_rows: int = 0
    matched_by_email_rows: int = 0
    anonymous_rows: int = 0
    unmatched_rows: int = 0
    needs_review_rows: int = 0


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


def _question_id_for_text(question_text: str, question_position: int | None = None) -> str:
    """Deterministic QuestionID placeholder.

    Google Forms exports can contain repeated question text such as
    "Can you elaborate?". Question identity must therefore include the
    position as well as the text, otherwise repeated follow-up questions
    collapse into the same reporting identity.
    """
    normalized_text = (question_text or "").strip()
    raw_key = f"{int(question_position or 0)}|{normalized_text}"
    h = hashlib.sha1(raw_key.encode("utf-8", errors="ignore")).hexdigest()
    return f"Q_{h[:16]}"


TOKEN_COLUMNS = {
    "user_token_here",
    "participation_token",
    "participation token",
    "here is the user token:",
}


def _is_recruiting_survey_type(survey_type_id: str) -> bool:
    """
    Recruiting remains identity-strict.

    UTSurveyType0001 is the canonical Recruiting survey type in the current DB.
    """
    return (survey_type_id or "").strip() == "UTSurveyType0001"


def _detect_token_column_index(*, fieldnames: list[str]) -> int | None:
    for index, col in enumerate(fieldnames):
        normalized = (col or "").strip().lower()
        if normalized in TOKEN_COLUMNS:
            return index

    return None


def _find_column_index(*, fieldnames: list[str], column_name: str) -> int | None:
    expected = (column_name or "").strip().lower()
    for index, col in enumerate(fieldnames):
        if (col or "").strip().lower() == expected:
            return index
    return None


def _cell(row_values: list[str], index: int | None) -> str:
    if index is None:
        return ""
    if index < 0 or index >= len(row_values):
        return ""
    return str(row_values[index] or "").strip()


def _source_response_key(*, survey_id: int, row_number: int, row_values: list[str]) -> str:
    values = [str(value or "").strip() for value in row_values]
    raw_key = f"{survey_id}|{row_number}|" + "|".join(values)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _find_token_user_id_for_context(
    *,
    cur,
    token: str,
    round_id: int,
    survey_type_id: str,
) -> str | None:
    """
    Token match is high confidence only when the token belongs to this round
    and this survey type. Do not guess across survey types.
    """

    token = (token or "").strip()
    if not token:
        return None

    cur.execute(
        """
        SELECT t.user_id
        FROM survey_participation_tokens t
        JOIN user_pool u
          ON u.user_id = t.user_id
        WHERE t.participation_token = %s
          AND t.round_id = %s
          AND t.survey_type = %s
        LIMIT 1
        """,
        (token, int(round_id), survey_type_id),
    )

    row = cur.fetchone()
    if not row:
        return None

    return row[0]


def _find_round_participant_user_id_by_email(
    *,
    cur,
    email: str,
    round_id: int,
) -> str | None:
    """
    Email fallback only links to a user who is an expected participant in
    this round. This avoids turning any random user_pool email into a
    medium-confidence PT result match.
    """

    email = (email or "").strip().lower()
    if not email:
        return None

    cur.execute(
        """
        SELECT pp.user_id
        FROM project_participants pp
        JOIN user_pool u
          ON u.user_id = pp.user_id
        WHERE pp.RoundID = %s
          AND LOWER(u.Email) = %s
          AND pp.ParticipantStatus IN ('Selected', 'Active', 'Completed')
        LIMIT 1
        """,
        (int(round_id), email),
    )

    row = cur.fetchone()
    if not row:
        return None

    return row[0]


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

    try:
        safe_original_filename = require_csv_upload(
            filename=original_filename or "survey_results.csv",
            file_bytes=csv_bytes,
        )
    except ValueError as err:
        raise UploadError(str(err))

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

    csv_reader = csv.reader(StringIO(text))
    try:
        raw_fieldnames = next(csv_reader)
    except StopIteration:
        raise UploadError("CSV parse failed: no headers found.")

    fieldnames = [str(c or "").strip() for c in raw_fieldnames]

    # Minimal, explicit assumptions for now.
    timestamp_col = "Timestamp"
    email_col = "Email Address"
    timestamp_idx = _find_column_index(fieldnames=fieldnames, column_name=timestamp_col)
    email_idx = _find_column_index(fieldnames=fieldnames, column_name=email_col)

    if timestamp_idx is None:
        raise UploadError("CSV missing required column: Timestamp")
    if email_idx is None:
        raise UploadError("CSV missing required column: Email Address")

    strict_identity_required = _is_recruiting_survey_type(ctx.survey_type_id)

    token_idx = None
    if not strict_identity_required:
        token_idx = _detect_token_column_index(fieldnames=fieldnames)

    metadata_indexes = {timestamp_idx, email_idx}
    if token_idx is not None:
        metadata_indexes.add(token_idx)

    question_cols: list[tuple[int, int, str]] = []
    for source_index, question_text in enumerate(fieldnames):
        if source_index in metadata_indexes:
            continue

        q_text = (question_text or "").strip()
        if not q_text:
            continue

        question_position = len(question_cols) + 1
        question_cols.append((source_index, question_position, q_text))

    if not question_cols:
        raise UploadError("CSV has no question columns after metadata removal.")

    total_respondent_rows = 0
    matched_users = 0
    ignored_rows_no_user = 0
    inserted_answer_rows = 0
    blank_answer_cells = 0
    numeric_answer_cells = 0

    matched_by_token_rows = 0
    matched_by_email_rows = 0
    anonymous_rows = 0
    unmatched_rows = 0
    needs_review_rows = 0

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
        for row_number, row_values in enumerate(csv_reader, start=1):
            total_respondent_rows += 1

            email = _cell(row_values, email_idx).lower()
            source_token = ""
            if token_idx is not None:
                source_token = _cell(row_values, token_idx)

            submitted_at = _parse_timestamp(_cell(row_values, timestamp_idx))

            user_id = None
            match_method = None
            match_confidence = None
            needs_review = 0
            match_notes = None

            # --------------------------------------------------
            # Recruiting remains strict
            # --------------------------------------------------
            if strict_identity_required:
                if not email:
                    ignored_rows_no_user += 1
                    unmatched_rows += 1
                    continue

                user = get_user_by_email(email)
                if not user:
                    ignored_rows_no_user += 1
                    unmatched_rows += 1
                    continue

                user_id = user["user_id"]
                matched_users += 1
                matched_by_email_rows += 1
                match_method = "email"
                match_confidence = "high"
                match_notes = "Recruiting upload matched by registered user email"

            # --------------------------------------------------
            # PT result uploads are feedback-first
            # --------------------------------------------------
            else:
                if source_token:
                    user_id = _find_token_user_id_for_context(
                        cur=cur,
                        token=source_token,
                        round_id=int(ctx.round_id),
                        survey_type_id=ctx.survey_type_id,
                    )

                    if user_id:
                        matched_users += 1
                        matched_by_token_rows += 1
                        match_method = "token"
                        match_confidence = "high"
                        match_notes = "Matched by participation token"

                if not user_id and email:
                    user_id = _find_round_participant_user_id_by_email(
                        cur=cur,
                        email=email,
                        round_id=int(ctx.round_id),
                    )

                    if user_id:
                        matched_users += 1
                        matched_by_email_rows += 1
                        match_method = "email"
                        match_confidence = "medium"
                        match_notes = "Matched by round participant email"

                if not user_id:
                    needs_review = 1
                    needs_review_rows += 1

                    if email or source_token:
                        unmatched_rows += 1
                        match_method = "unmatched"
                        match_confidence = "low"
                        match_notes = "Identity data present but no matching round participant found"
                    else:
                        anonymous_rows += 1
                        match_method = "anonymous"
                        match_confidence = "low"
                        match_notes = "No usable token or email found in uploaded response"

            source_response_key = _source_response_key(
                survey_id=survey_id,
                row_number=row_number,
                row_values=row_values,
            )

            # Distribution row per uploaded response
            cur.execute(
                """
                INSERT INTO survey_distribution (
                    SurveyID,
                    ProjectID,
                    RoundID,
                    user_id,
                    SourceEmail,
                    SourceToken,
                    SourceResponseKey,
                    MatchMethod,
                    MatchConfidence,
                    NeedsReview,
                    MatchNotes,
                    SurveyTypeID,
                    SentAt,
                    CompletedAt,
                    Status
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'completed')
                """,
                (
                    survey_id,
                    ctx.project_id,
                    int(ctx.round_id),
                    user_id,
                    email or None,
                    source_token or None,
                    source_response_key,
                    match_method,
                    match_confidence,
                    int(needs_review),
                    match_notes,
                    ctx.survey_type_id,
                    submitted_at,
                    submitted_at,
                ),
            )
            distribution_id = int(cur.lastrowid)

            # Answers: one row per question column. Use positional cells, not
            # DictReader, because Google Forms can export duplicate headers
            # such as "Can you elaborate?". DictReader collapses those values.
            answer_rows: list[tuple[Any, ...]] = []
            for source_index, question_position, q_text in question_cols:
                a_val_raw = _cell(row_values, source_index)
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
                        _question_id_for_text(q_text, question_position),
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
            original_filename=safe_original_filename,
            uploaded_by_user_id=ctx.uploaded_by_user_id,
            project_id=ctx.project_id,
            round_id=int(ctx.round_id),
            survey_type_id=ctx.survey_type_id,
            survey_id=survey_id,
            inserted_answer_rows=inserted_answer_rows,
            total_respondent_rows=total_respondent_rows,
            matched_by_token_rows=matched_by_token_rows,
            matched_by_email_rows=matched_by_email_rows,
            anonymous_rows=anonymous_rows,
            unmatched_rows=unmatched_rows,
            needs_review_rows=needs_review_rows,
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
        matched_by_token_rows=matched_by_token_rows,
        matched_by_email_rows=matched_by_email_rows,
        anonymous_rows=anonymous_rows,
        unmatched_rows=unmatched_rows,
        needs_review_rows=needs_review_rows,
    )