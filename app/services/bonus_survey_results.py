# app/services/bonus_survey_results.py

import csv
import hashlib
import os
from datetime import datetime
from io import StringIO

from app.db.bonus_survey_answers import (
    delete_answers_for_bonus_survey,
    insert_bonus_survey_answer,
)

from app.db.bonus_survey_participation import (
    create_upload_only_participation,
    get_participation_by_email,
    get_participation_by_token,
    list_participation_tokens_for_survey,
    mark_participation_completed_with_attribution,
    reset_bonus_survey_completion_state,
)

from app.utils.upload_security import require_csv_upload

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "bonus_survey_uploads")

SYSTEM_COLUMNS = {
    "Timestamp",
    "Email Address",
}

TOKEN_COLUMNS = {
    "user_token_here",
    "participation_token",
    "participation token",
}


def _hash_question(text: str, order: int) -> str:
    key = f"{text.strip()}|{order}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def _is_ignored_column(column_name: str) -> bool:
    if not column_name:
        return True

    if column_name in SYSTEM_COLUMNS:
        return True

    if column_name.startswith("Unnamed:"):
        return True

    return False


def _detect_token_column(*, fieldnames: list[str], rows: list[dict], valid_tokens: set[str]) -> str | None:
    """
    Detect token column by exact value match first, then by known exact token
    header names.

    Feedback-first ingestion does not require matching token values. If a token
    column is present but none of its values match this survey, the uploaded
    responses should still be ingested as unmatched/low-confidence instead of
    treating the token column as a survey question.
    """

    best_column = None
    best_match_count = 0

    if valid_tokens:
        for col in fieldnames:
            if not col:
                continue

            match_count = 0

            for row in rows:
                raw_value = row.get(col)
                if raw_value is None:
                    continue

                value = str(raw_value).strip()
                if value in valid_tokens:
                    match_count += 1

            if match_count > best_match_count:
                best_match_count = match_count
                best_column = col

        if best_column and best_match_count > 0:
            return best_column

    for col in fieldnames:
        normalized_col = (col or "").strip().lower()
        if normalized_col in TOKEN_COLUMNS:
            return col

    return None


def _detect_email_column(*, fieldnames: list[str]) -> str | None:
    """Return the standard Google Forms email column when present."""

    for col in fieldnames:
        if (col or "").strip().lower() == "email address":
            return col

    return None


def _row_has_any_value(row: list[str]) -> bool:
    return any(str(value).strip() for value in row if value is not None)


def _source_response_key(*, survey_id: int, row_number: int, row: list[str]) -> str:
    normalized_values = [str(value or "").strip() for value in row]
    raw_key = f"{survey_id}|{row_number}|" + "|".join(normalized_values)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def save_bonus_results_upload(
    *,
    survey_id: int,
    uploaded_by_user_id: str,
    filename: str,
    file_bytes: bytes,
) -> dict:
    """
    Save uploaded CSV to disk, then ingest it into bonus survey participation
    and answers tables.

    Feedback-first rule:
    - token match links to a known participant with high confidence
    - email match links to a known participant with medium confidence
    - missing/unmatched identity still creates an upload-only participation row
      so valid submitted feedback is not discarded
    """

    # -------------------------
    # Save raw upload
    # -------------------------
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    survey_dir = os.path.join(UPLOAD_DIR, f"survey_{survey_id}")
    os.makedirs(survey_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_filename = require_csv_upload(
        filename=filename,
        file_bytes=file_bytes,
    )
    stored_filename = f"{timestamp}__{uploaded_by_user_id}__{safe_filename}"
    file_path = os.path.join(survey_dir, stored_filename)

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # -------------------------
    # Parse CSV
    # -------------------------
    text = file_bytes.decode("utf-8-sig")

    raw_reader = csv.reader(StringIO(text))
    rows = list(raw_reader)

    if not rows or not rows[0]:
        raise RuntimeError("Uploaded CSV has no header row")

    headers = rows[0]
    data_rows = [row for row in rows[1:] if _row_has_any_value(row)]

    valid_tokens = list_participation_tokens_for_survey(bonus_survey_id=survey_id)

    # Convert rows to dict-like format ONLY for token detection
    dict_rows = [
        {headers[i]: row[i] if i < len(row) else None for i in range(len(headers))}
        for row in data_rows
    ]

    token_column = _detect_token_column(
        fieldnames=headers,
        rows=dict_rows,
        valid_tokens=valid_tokens,
    )

    email_column = _detect_email_column(fieldnames=headers)

    # -------------------------
    # Reset old interpreted state
    # -------------------------
    reset_bonus_survey_completion_state(bonus_survey_id=survey_id)
    delete_answers_for_bonus_survey(bonus_survey_id=survey_id)

    # -------------------------
    # Rebuild from latest CSV
    # -------------------------
    matched_rows = 0
    matched_by_token_rows = 0
    matched_by_email_rows = 0
    anonymous_rows = 0
    unmatched_rows = 0
    needs_review_rows = 0
    inserted_answers = 0

    token_idx = headers.index(token_column) if token_column else None
    email_idx = headers.index(email_column) if email_column else None

    for row_number, row in enumerate(data_rows, start=1):
        source_token = ""
        if token_idx is not None and token_idx < len(row):
            source_token = str(row[token_idx] or "").strip()

        source_email = ""
        if email_idx is not None and email_idx < len(row):
            source_email = str(row[email_idx] or "").strip().lower()

        source_response_key = _source_response_key(
            survey_id=survey_id,
            row_number=row_number,
            row=row,
        )

        participation = None
        match_method = None
        match_confidence = None
        needs_review = 0
        match_notes = None

        if source_token:
            participation = get_participation_by_token(
                bonus_survey_id=survey_id,
                participation_token=source_token,
            )

            if participation:
                match_method = "token"
                match_confidence = "high"
                match_notes = "Matched by participation token"
                matched_rows += 1
                matched_by_token_rows += 1

        if not participation and source_email:
            participation = get_participation_by_email(
                bonus_survey_id=survey_id,
                source_email=source_email,
            )

            if participation:
                match_method = "email"
                match_confidence = "medium"
                match_notes = "Matched by registered participant email"
                matched_rows += 1
                matched_by_email_rows += 1

        if not participation:
            needs_review = 1
            needs_review_rows += 1

            if source_email or source_token:
                match_method = "unmatched"
                match_confidence = "low"
                match_notes = "Identity data present but no matching survey participant found"
                unmatched_rows += 1
            else:
                match_method = "anonymous"
                match_confidence = "low"
                match_notes = "No usable token or email found in uploaded response"
                anonymous_rows += 1

            participation = create_upload_only_participation(
                bonus_survey_id=survey_id,
                source_email=source_email or None,
                source_token=source_token or None,
                source_response_key=source_response_key,
                match_method=match_method,
                match_confidence=match_confidence,
                needs_review=needs_review,
                match_notes=match_notes,
                confirmation_source="bonus_csv_upload",
            )
        else:
            mark_participation_completed_with_attribution(
                bonus_survey_participation_id=participation["bonus_survey_participation_id"],
                confirmation_source="bonus_csv_upload",
                source_email=source_email or None,
                source_token=source_token or None,
                source_response_key=source_response_key,
                match_method=match_method,
                match_confidence=match_confidence,
                needs_review=needs_review,
                match_notes=match_notes,
            )

        participation_id = participation["bonus_survey_participation_id"]

        question_order = 0

        for idx, col in enumerate(headers):
            if token_column and col == token_column:
                continue

            if _is_ignored_column(col):
                continue

            question_order += 1

            raw_answer = row[idx] if idx < len(row) else None

            # Normalize answer (preserve blanks as NULL)
            if raw_answer is None:
                normalized_answer = None
            else:
                answer_text = str(raw_answer).strip()
                normalized_answer = answer_text if answer_text != "" else None

            insert_bonus_survey_answer(
                bonus_survey_participation_id=participation_id,
                bonus_survey_id=survey_id,
                question_text=col.strip(),
                question_hash=_hash_question(col, question_order),
                answer_text=normalized_answer,
                question_order=question_order,
            )

            inserted_answers += 1

    return {
        "file_path": file_path,
        "token_column": token_column,
        "email_column": email_column,
        "matched_rows": matched_rows,
        "matched_by_token_rows": matched_by_token_rows,
        "matched_by_email_rows": matched_by_email_rows,
        "anonymous_rows": anonymous_rows,
        "unmatched_rows": unmatched_rows,
        "needs_review_rows": needs_review_rows,
        "total_respondent_rows": len(data_rows),
        "inserted_answers": inserted_answers,
    }