import csv
import hashlib
import mysql.connector
from app.config.config import DB_CONFIG
from datetime import datetime


def _parse_timestamp(ts: str):
    if not ts:
        return None

    try:
        # Google Forms format: M/D/YYYY HH:MM:SS
        return datetime.strptime(ts, "%m/%d/%Y %H:%M:%S")
    except Exception:
        return None

def _hash_question(text: str) -> str:
    normalized = text.strip().lower()
    return hashlib.md5(normalized.encode()).hexdigest()


def ingest_google_form_csv(*, filepath, survey_type, source_filename):
    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        with conn.cursor() as cursor:
            with open(filepath, newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    raw_timestamp = row.get("Timestamp")
                    submitted_at = _parse_timestamp(raw_timestamp)

                    for column, answer in row.items():
                        if column == "Timestamp":
                            continue

                        question = column.strip()
                        answer = (answer or "").strip()

                        if not question:
                            continue

                        q_hash = _hash_question(question)

                        # -------------------------
                        # Ensure mapping exists
                        # -------------------------
                        cursor.execute(
                            """
                            INSERT INTO survey_question_map (QuestionHash, ExampleText)
                            VALUES (%s, %s)
                            ON DUPLICATE KEY UPDATE
                                ExampleText = VALUES(ExampleText)
                            """,
                            (q_hash, question)
                        )

                        # -------------------------
                        # Insert response
                        # -------------------------
                        cursor.execute(
                            """
                            INSERT INTO survey_responses
                            (
                                ProjectID,
                                RoundID,
                                SurveyType,
                                QuestionText,
                                QuestionHash,
                                AnswerText,
                                SubmittedAt
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                None,
                                None,
                                survey_type,
                                question,
                                q_hash,
                                answer,
                                submitted_at if submitted_at else None,
                            )
                        )

        conn.commit()

    finally:
        conn.close()