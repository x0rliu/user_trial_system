# app/services/historical_ingestion.py

import csv
import hashlib
import json
from datetime import datetime

from app.db.connection import get_db_connection
from app.db.historical import (
    dataset_exists_for_context_with_cursor,
    delete_dataset_by_context_and_type_with_cursor,
    insert_historical_dataset_with_cursor,
    insert_historical_survey_answer_with_cursor,
)

from app.services.historical_metrics import compute_trial_metrics

def ingest_historical_csv(context_id, dataset_type, file_obj, filename, round_number=None):
    """
    Full ingestion pipeline.
    This is the ONLY place where ingestion logic lives.

    DB writes are committed as one unit:
    - existing dataset reset
    - new dataset row
    - inserted historical survey answers

    Derived metrics are computed after the upload transaction commits.
    """

    # -------------------------
    # Step 1: Save file to disk first
    # -------------------------
    import os
    import uuid

    upload_dir = "app/dev_data/historical_uploads"
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, f"{uuid.uuid4()}.csv")

    file_obj.seek(0)

    with open(filepath, "wb") as f:
        f.write(file_obj.read())

    # -------------------------
    # Step 2: Read CSV from disk
    # -------------------------
    with open(filepath, "r", encoding="utf-8-sig") as f:

        reader = csv.reader(f)

        try:
            headers = next(reader)
        except StopIteration:
            raise Exception("CSV is empty")

        headers = [h.strip() for h in headers]

        SYSTEM_COLUMNS = ["Timestamp", "Email Address"]

        METADATA_COLUMNS = [
            "Gender",
            "Age",
            "Country",
            "Location",
            "Operating System",
            "Experience Level",
        ]

        question_columns = [
            (idx, col)
            for idx, col in enumerate(headers)
            if col not in SYSTEM_COLUMNS and col not in METADATA_COLUMNS
        ]

        if not question_columns:
            raise Exception(f"No question columns detected. Headers: {headers}")

        # -------------------------
        # Step 3: Transactional DB rebuild
        # -------------------------
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            if dataset_exists_for_context_with_cursor(cursor, context_id, dataset_type):
                delete_dataset_by_context_and_type_with_cursor(
                    cursor,
                    context_id,
                    dataset_type,
                )

            dataset_id = insert_historical_dataset_with_cursor(
                cursor,
                context_id=context_id,
                dataset_type=dataset_type,
                source_file_name=filename,
                round_number=round_number,
            )

            respondent_rows = 0
            inserted_answer_rows = 0

            for row_idx, row_values in enumerate(reader, start=1):
                if not any(str(value or "").strip() for value in row_values):
                    continue

                respondent_rows += 1

                def get_value(col_name):
                    try:
                        idx = headers.index(col_name)
                        return row_values[idx] if idx < len(row_values) else ""
                    except ValueError:
                        return ""

                email = get_value("Email Address").strip()
                timestamp_str = get_value("Timestamp").strip()

                if email:
                    response_group_id = hashlib.sha256(email.encode()).hexdigest()
                else:
                    response_group_id = f"{dataset_id}_{row_idx}"

                response_submitted_at = None
                if timestamp_str:
                    try:
                        response_submitted_at = datetime.strptime(
                            timestamp_str,
                            "%m/%d/%Y %H:%M:%S",
                        )
                    except Exception:
                        pass

                metadata = {}
                for col in METADATA_COLUMNS:
                    value = get_value(col)
                    if value:
                        metadata[col.lower().replace(" ", "_")] = value

                metadata_json = json.dumps(metadata) if metadata else None

                for position, (col_index, question_text) in enumerate(question_columns):

                    raw_answer = row_values[col_index] if col_index < len(row_values) else ""

                    if raw_answer is None:
                        raw_answer = ""

                    answer = str(raw_answer).strip()

                    q_hash = hashlib.sha256(
                        f"{position}:{question_text.strip().lower()}".encode()
                    ).hexdigest()

                    answer_numeric = None
                    try:
                        answer_numeric = float(answer)
                    except Exception:
                        pass

                    insert_historical_survey_answer_with_cursor(
                        cursor,
                        dataset_id=dataset_id,
                        response_group_id=response_group_id,
                        question_text=question_text,
                        question_hash=q_hash,
                        question_position=position,
                        answer_text=answer,
                        answer_numeric=answer_numeric,
                        response_submitted_at=response_submitted_at,
                        metadata_json=metadata_json,
                    )

                    inserted_answer_rows += 1

            if respondent_rows <= 0:
                raise Exception("CSV has no respondent rows")

            if inserted_answer_rows <= 0:
                raise Exception("CSV produced no historical answer rows")

            conn.commit()

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    # -------------------------
    # Step 4: Metrics + Insights
    # -------------------------
    compute_trial_metrics(context_id)
    # generate_trial_insights(context_id)