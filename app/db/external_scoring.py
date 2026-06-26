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


def get_external_scoring_context(*, round_id: int) -> dict:
    """
    Returns external scoring config in the shape expected by
    app.services.selection_scoring_service._score_external_survey_fit.

    This is round-local scoring config.
    It does NOT read or create the future reusable question bank.
    """

    questions = get_external_scoring_config(round_id=round_id)

    return {
        "questions": [
            {
                "question_id": question.get("question_id"),
                "question_text": question.get("question_text"),
                "weight": question.get("weight") or 0,
                "answers": [
                    {
                        "value": answer.get("value"),
                        "score": answer.get("score") or 0,
                    }
                    for answer in question.get("answers", [])
                ],
            }
            for question in questions
        ]
    }


def get_external_survey_answers_by_user(*, round_id: int, user_ids=None) -> dict:
    """
    Loads recruiting survey answers grouped by user and question.

    Return shape:
        {
            "user_123": {
                "Q_abc": ["Answer A", "Answer B"]
            }
        }

    Notes:
    - Uses survey_answers as the source of truth.
    - Splits comma-separated multi-select answers to match the existing
      observed-answer extraction behavior.
    - Only reads UTSurveyType0001 recruiting answers.
    """

    user_id_list = None

    if user_ids is not None:
        user_id_list = [
            str(user_id).strip()
            for user_id in user_ids
            if str(user_id or "").strip()
        ]

        if not user_id_list:
            return {}

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cursor = conn.cursor(dictionary=True)

        params = [round_id]

        user_filter_sql = ""

        if user_id_list is not None:
            placeholders = ", ".join(["%s"] * len(user_id_list))
            user_filter_sql = f" AND user_id IN ({placeholders})"
            params.extend(user_id_list)

        cursor.execute(
            f"""
            SELECT
                user_id,
                QuestionID,
                AnswerValue
            FROM survey_answers
            WHERE RoundID = %s
              AND SurveyTypeID = 'UTSurveyType0001'
              AND user_id IS NOT NULL
              AND AnswerValue IS NOT NULL
              AND TRIM(AnswerValue) <> ''
              {user_filter_sql}
            """,
            tuple(params),
        )

        rows = cursor.fetchall()

        answers_by_user = {}

        for row in rows:
            user_id = str(row.get("user_id") or "").strip()
            question_id = str(row.get("QuestionID") or "").strip()
            raw_answer = row.get("AnswerValue") or ""

            if not user_id or not question_id:
                continue

            answers_by_user.setdefault(user_id, {})
            answers_by_user[user_id].setdefault(question_id, [])

            for value in str(raw_answer).split(","):
                clean_value = value.strip()

                if clean_value:
                    answers_by_user[user_id][question_id].append(clean_value)

        return answers_by_user

    finally:
        conn.close()


def hydrate_candidates_with_external_survey_answers(*, round_id: int, candidates: list) -> list:
    """
    Returns candidate dicts with external_survey_answers attached.

    This does not score candidates.
    It only prepares the input expected by selection_scoring_service.
    """

    if not candidates:
        return []

    user_ids = [
        candidate.get("user_id")
        for candidate in candidates
        if candidate.get("user_id")
    ]

    answers_by_user = get_external_survey_answers_by_user(
        round_id=round_id,
        user_ids=user_ids,
    )

    hydrated_candidates = []

    for candidate in candidates:
        hydrated = dict(candidate)
        user_id = hydrated.get("user_id")

        hydrated["external_survey_answers"] = answers_by_user.get(user_id, {})

        hydrated_candidates.append(hydrated)

    return hydrated_candidates


def update_answer_score(validated_round: dict, answer_config_id: int, score: float):
    from app.db import get_connection

    if not validated_round or "RoundID" not in validated_round:
        raise ValueError("Invalid validated_round context")

    round_id = int(validated_round["RoundID"])

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE round_external_scoring_answers
                SET Score = %s
                WHERE AnswerConfigID = %s
                  AND AnswerConfigID IN (
                      SELECT a.AnswerConfigID
                      FROM round_external_scoring_answers a
                      JOIN round_external_scoring_questions q
                        ON q.QuestionConfigID = a.QuestionConfigID
                      WHERE q.RoundID = %s
                  )
                """,
                (score, answer_config_id, round_id),
            )
        conn.commit()
    finally:
        conn.close()


def update_question_weight(validated_round: dict, question_config_id: int, weight: float):
    from app.db import get_connection

    if not validated_round or "RoundID" not in validated_round:
        raise ValueError("Invalid validated_round context")

    round_id = int(validated_round["RoundID"])

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE round_external_scoring_questions
                SET Weight = %s
                WHERE QuestionConfigID = %s
                  AND RoundID = %s
                """,
                (weight, question_config_id, round_id),
            )
        conn.commit()
    finally:
        conn.close()