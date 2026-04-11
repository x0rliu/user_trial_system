import mysql.connector
from app.config.config import DB_CONFIG


def validate_round_object_binding(
    *,
    round_id: int,
    answer_id: int | None = None,
    question_id: int | None = None,
    participant_id: str | None = None,
) -> bool:
    if not round_id:
        return False

    try:
        round_id = int(round_id)
    except (TypeError, ValueError):
        return False

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        if question_id is not None:
            try:
                question_id = int(question_id)
            except (TypeError, ValueError):
                return False

            cur.execute(
                """
                SELECT 1
                FROM round_external_scoring_questions
                WHERE QuestionConfigID = %s
                  AND RoundID = %s
                LIMIT 1
                """,
                (question_id, round_id),
            )
            if not cur.fetchone():
                return False

        if answer_id is not None:
            try:
                answer_id = int(answer_id)
            except (TypeError, ValueError):
                return False

            cur.execute(
                """
                SELECT 1
                FROM round_external_scoring_answers a
                JOIN round_external_scoring_questions q
                  ON q.QuestionConfigID = a.QuestionConfigID
                WHERE a.AnswerConfigID = %s
                  AND q.RoundID = %s
                LIMIT 1
                """,
                (answer_id, round_id),
            )
            if not cur.fetchone():
                return False

        if participant_id is not None:
            cur.execute(
                """
                SELECT 1
                FROM project_participants
                WHERE RoundID = %s
                  AND user_id = %s
                LIMIT 1
                """,
                (round_id, participant_id),
            )
            if not cur.fetchone():
                return False

        return True

    finally:
        conn.close()
