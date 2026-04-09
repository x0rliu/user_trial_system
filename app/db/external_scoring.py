# app/db/external_scoring.py

import mysql.connector
from app.config.config import DB_CONFIG


def ensure_external_scoring_config(*, round_id: int):
    """
    Ensures external scoring config exists for a round.
    - Extracts questions + answers from survey_answers
    - Seeds missing questions
    - Seeds missing answers (split for multi-select)
    """

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cursor = conn.cursor(dictionary=True)

        # ---------------------------------------------
        # 1. Fetch all recruiting survey answers
        # ---------------------------------------------
        cursor.execute(
            """
            SELECT QuestionID, QuestionText, AnswerValue
            FROM survey_answers
            WHERE RoundID = %s
              AND SurveyTypeID = 'UTSurveyType0001'
            """,
            (round_id,),
        )

        rows = cursor.fetchall()

        if not rows:
            return

        # ---------------------------------------------
        # 2. Build question → answer set
        # ---------------------------------------------
        question_map = {}

        for row in rows:

            qid = row["QuestionID"]
            qtext = (row.get("QuestionText") or "").lower()

            # ---------------------------------
            # IGNORE / EXCLUDE FROM SCORING
            # ---------------------------------
            IGNORE_KEYWORDS = [
                "email",
                "phone",
                "address",
                "shipping",
                "recipient",
                "contact number",
                "full name",
                "guardian",
                "token",
                "office",
                "pick up",
                "conflict",
                "guardian",
                "booster",
                "receive",
                "minor",
                "your name",
                "consent",
                "direct competitor",
            ]

            PROFILE_KEYWORDS = [
                "age range",
                "gender",
                "located",
            ]


            # Ignore system/logistics
            if any(k in qtext for k in IGNORE_KEYWORDS):
                continue

            # Ignore profile (already handled elsewhere)
            if any(k in qtext for k in PROFILE_KEYWORDS):
                continue

            # Skip empty/junk
            if not qtext.strip():
                continue

            # NOTE:
            # We are NOT removing FILTER questions yet
            # (we will classify them later)
            raw_answer = row.get("AnswerValue") or ""

            if qid not in question_map:
                question_map[qid] = {
                    "question_text": qtext,
                    "answers": set(),
                }

            # Split multi-select answers
            for val in raw_answer.split(","):
                clean = val.strip()
                if clean:
                    question_map[qid]["answers"].add(clean)

        # ---------------------------------------------
        # 3. Ensure questions exist
        # ---------------------------------------------
        for qid, qdata in question_map.items():

            cursor.execute(
                """
                SELECT QuestionConfigID
                FROM round_external_scoring_questions
                WHERE RoundID = %s AND QuestionID = %s
                """,
                (round_id, qid),
            )

            existing = cursor.fetchone()

            if not existing:
                cursor.execute(
                    """
                    INSERT INTO round_external_scoring_questions
                    (RoundID, QuestionID, QuestionText, Weight)
                    VALUES (%s, %s, %s, 1.0)
                    """,
                    (round_id, qid, qdata["question_text"]),
                )

                question_config_id = cursor.lastrowid

            else:
                question_config_id = existing["QuestionConfigID"]

            # ---------------------------------------------
            # 4. Ensure answers exist
            # ---------------------------------------------
            for answer in qdata["answers"]:

                cursor.execute(
                    """
                    SELECT AnswerConfigID
                    FROM round_external_scoring_answers
                    WHERE QuestionConfigID = %s
                      AND AnswerValue = %s
                    """,
                    (question_config_id, answer),
                )

                exists = cursor.fetchone()

                if not exists:
                    cursor.execute(
                        """
                        INSERT INTO round_external_scoring_answers
                        (QuestionConfigID, AnswerValue, Score)
                        VALUES (%s, %s, 0)
                        """,
                        (question_config_id, answer),
                    )

        conn.commit()

    finally:
        conn.close()


def get_external_scoring_config(*, round_id: int):
    """
    Returns structured config for UI rendering
    """

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                q.QuestionConfigID,
                q.QuestionID,
                q.QuestionText,
                q.Weight,
                q.Intent,
                a.AnswerConfigID,
                a.AnswerValue,
                a.Score
            FROM round_external_scoring_questions q
            LEFT JOIN round_external_scoring_answers a
                ON q.QuestionConfigID = a.QuestionConfigID
            WHERE q.RoundID = %s
            ORDER BY q.QuestionConfigID, a.AnswerConfigID
            """,
            (round_id,),
        )

        rows = cursor.fetchall()

        result = {}
        for row in rows:

            qid = row["QuestionID"]

            if qid not in result:
                result[qid] = {
                    "question_config_id": row["QuestionConfigID"],
                    "question_id": qid,
                    "question_text": row["QuestionText"],
                    "weight": float(row["Weight"] or 1.0),
                    "intent": row["Intent"] or "",
                    "answers": [],
                }

            if row["AnswerValue"] is not None:
                result[qid]["answers"].append({
                    "answer_config_id": row["AnswerConfigID"],
                    "value": row["AnswerValue"],
                    "score": float(row["Score"] or 0),
                })

        return list(result.values())

    finally:
        conn.close()

def update_answer_score(answer_config_id: int, score: float):
    from app.db import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE round_external_scoring_answers
                SET Score = %s
                WHERE AnswerConfigID = %s
                """,
                (score, answer_config_id),
            )
        conn.commit()
    finally:
        conn.close()


def update_question_weight(question_config_id: int, weight: float):
    from app.db import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE round_external_scoring_questions
                SET Weight = %s
                WHERE QuestionConfigID = %s
                """,
                (weight, question_config_id),
            )
        conn.commit()
    finally:
        conn.close()