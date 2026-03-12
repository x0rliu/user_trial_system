# app/db/user_legal_acceptance.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_user_signed_document(user_id: str, document_type: str):

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor(dictionary=True)

        query = """
        SELECT
            *
        FROM user_legal_acceptance
        WHERE user_id = %s
        AND document_type = %s
        ORDER BY accepted_at DESC
        LIMIT 1
        """

        cur.execute(query, (user_id, document_type))

        return cur.fetchone()

    finally:
        conn.close()


def record_user_legal_acceptance(
    user_id: str,
    document_id: int,
    document_type: str,
):
    """
    Record that a user accepted a legal document.
    """

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor()

        query = """
        INSERT INTO user_legal_acceptance
        (
            user_id,
            document_id,
            document_type,
            accepted_at
        )
        VALUES
        (
            %s,
            %s,
            %s,
            NOW()
        )
        """

        cur.execute(
            query,
            (
                user_id,
                document_id,
                document_type,
            ),
        )

        conn.commit()

    finally:
        conn.close()