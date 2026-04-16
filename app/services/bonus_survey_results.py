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
    get_participation_by_token,
    list_participation_tokens_for_survey,
    mark_participation_completed_by_id,
    reset_bonus_survey_completion_state,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "bonus_survey_uploads")

SYSTEM_COLUMNS = {
    "Timestamp",
    "Email Address",
}


def _hash_question(text: str) -> str:
    return hashlib.md5(text.strip().encode("utf-8")).hexdigest()


def _is_ignored_column(column_name: str) -> bool:
    if not column_name:
        return True

    if column_name in SYSTEM_COLUMNS:
        return True

    if column_name.startswith("Unnamed:"):
        return True

    return False


def _detect_token_column(*, fieldnames: list[str], rows: list[dict], valid_tokens: set[str]) -> str:
    """
    Detect token column by exact value match against known participation tokens
    for this survey. No guessed header names.
    """
    best_column = None
    best_match_count = 0

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

    if not best_column or best_match_count == 0:
        raise RuntimeError("Could not detect participation token column from uploaded CSV")

    return best_column


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
    """

    # -------------------------
    # Save raw upload
    # -------------------------
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    survey_dir = os.path.join(UPLOAD_DIR, f"survey_{survey_id}")
    os.makedirs(survey_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_filename = filename.replace(" ", "_")
    stored_filename = f"{timestamp}__{uploaded_by_user_id}__{safe_filename}"
    file_path = os.path.join(survey_dir, stored_filename)

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # -------------------------
    # Parse CSV
    # -------------------------
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))

    if not reader.fieldnames:
        raise RuntimeError("Uploaded CSV has no header row")

    rows = list(reader)
    valid_tokens = list_participation_tokens_for_survey(bonus_survey_id=survey_id)

    if not valid_tokens:
        raise RuntimeError("No participation tokens exist for this survey")

    token_column = _detect_token_column(
        fieldnames=reader.fieldnames,
        rows=rows,
        valid_tokens=valid_tokens,
    )

    # -------------------------
    # Reset old interpreted state
    # -------------------------
    reset_bonus_survey_completion_state(bonus_survey_id=survey_id)
    delete_answers_for_bonus_survey(bonus_survey_id=survey_id)

    # -------------------------
    # Rebuild from latest CSV
    # -------------------------
    matched_rows = 0
    unmatched_rows = 0
    inserted_answers = 0

    for row in rows:
        token = str(row.get(token_column) or "").strip()
        if not token:
            continue

        participation = get_participation_by_token(
            bonus_survey_id=survey_id,
            participation_token=token,
        )

        if not participation:
            unmatched_rows += 1
            continue

        participation_id = participation["bonus_survey_participation_id"]

        mark_participation_completed_by_id(
            bonus_survey_participation_id=participation_id,
            confirmation_source="bonus_csv_upload",
        )

        matched_rows += 1

        for col in reader.fieldnames:
            if col == token_column:
                continue

            if _is_ignored_column(col):
                continue

            raw_answer = row.get(col)

            # Normalize answer (preserve blanks as NULL)
            if raw_answer is None:
                normalized_answer = None
            else:
                answer_text = str(raw_answer).strip()
                normalized_answer = answer_text if answer_text != "" else None

            insert_bonus_survey_answer(
                bonus_survey_participation_id=participation_id,
                question_text=col.strip(),
                question_hash=_hash_question(col),
                answer_text=normalized_answer,
            )
            inserted_answers += 1

    return {
        "file_path": file_path,
        "token_column": token_column,
        "matched_rows": matched_rows,
        "unmatched_rows": unmatched_rows,
        "inserted_answers": inserted_answers,
    }