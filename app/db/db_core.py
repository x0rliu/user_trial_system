# app/db/db_core.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def fetch_all(query, params=None):
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        rows = cursor.fetchall()
        return rows
    finally:
        conn.close()


def fetch_one(query, params=None):
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        row = cursor.fetchone()
        return row
    finally:
        conn.close()


def execute(query, params=None):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        conn.commit()
    finally:
        conn.close()