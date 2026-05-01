# app/services/global_nda_service.py

import mysql.connector

from app.config.config import DB_CONFIG
from app.db.global_nda import (
    mark_global_nda_signed_tx,
    record_global_nda_acceptance_tx,
)


def sign_global_nda(user_id: str, nda: dict):
    """
    Sign the active global NDA for a user.

    This service owns the transaction because both writes must succeed or fail
    together:
    1. user_pool global NDA state
    2. user_legal_acceptance audit record
    """

    if not user_id:
        raise ValueError("user_id is required")

    if not nda:
        raise ValueError("nda document is required")

    document_id = nda.get("id")
    if not document_id:
        raise ValueError("nda document id is required")

    document_version = nda.get("version")

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = None

    try:
        conn.start_transaction()
        cur = conn.cursor()

        mark_global_nda_signed_tx(
            cur=cur,
            user_id=user_id,
            document_version=document_version,
        )

        record_global_nda_acceptance_tx(
            cur=cur,
            user_id=user_id,
            document_id=document_id,
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        if cur:
            cur.close()

        conn.close()