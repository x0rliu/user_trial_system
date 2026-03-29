import mysql.connector
from app.config.config import DB_CONFIG


def get_token_by_user_round_survey(user_id, round_id, survey_type):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT *
            FROM survey_participation_tokens
            WHERE user_id = %s
              AND round_id = %s
              AND survey_type = %s
            LIMIT 1
        """, (user_id, round_id, survey_type))

        return cur.fetchone()
    finally:
        conn.close()


def insert_token(user_id, round_id, survey_type, token):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO survey_participation_tokens
            (user_id, round_id, survey_type, participation_token)
            VALUES (%s, %s, %s, %s)
        """, (user_id, round_id, survey_type, token))

        conn.commit()
    finally:
        conn.close()


def get_by_token(token):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT *
            FROM survey_participation_tokens
            WHERE participation_token = %s
            LIMIT 1
        """, (token,))

        return cur.fetchone()
    finally:
        conn.close()


def mark_token_used(token):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute("""
            UPDATE survey_participation_tokens
            SET used_at = NOW()
            WHERE participation_token = %s
        """, (token,))

        conn.commit()
    finally:
        conn.close()