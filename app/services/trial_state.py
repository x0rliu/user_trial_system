# app/services/trial_state.py

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import mysql.connector
from app.config.config import DB_CONFIG


# -------------------------------------------------
# Constants (tune later, not now)
# -------------------------------------------------

COOLDOWN_DAYS = 60


# -------------------------------------------------
# DB helpers (read-only)
# -------------------------------------------------

def _get_active_trial(user_id: str) -> Optional[dict]:
    """
    Returns the active trial row if the user is currently in an active trial.
    """
    query = """
        SELECT *
        FROM user_trials
        WHERE user_id = %s
          AND Status = 'ACTIVE'
        LIMIT 1
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, (user_id,))
        return cur.fetchone()
    finally:
        conn.close()


def _get_accepted_trial(user_id: str) -> Optional[dict]:
    """
    Returns a trial the user has accepted but not yet activated.
    """
    query = """
        SELECT *
        FROM user_trials
        WHERE user_id = %s
          AND Status = 'ACCEPTED'
        LIMIT 1
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, (user_id,))
        return cur.fetchone()
    finally:
        conn.close()


def _get_signed_nda_trial(user_id: str) -> Optional[dict]:
    """
    Returns a trial where NDA is signed but trial not yet active.
    """
    query = """
        SELECT *
        FROM user_trials
        WHERE user_id = %s
          AND Status = 'NDA_SIGNED'
        LIMIT 1
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, (user_id,))
        return cur.fetchone()
    finally:
        conn.close()


def _get_pending_invites(user_id: str) -> int:
    """
    Returns number of pending trial invitations.
    """
    query = """
        SELECT COUNT(*)
        FROM user_trials
        WHERE user_id = %s
          AND Status = 'INVITED'
          AND InviteExpiresAt > NOW()
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(query, (user_id,))
        return int(cur.fetchone()[0])
    finally:
        conn.close()


def _get_last_trial_end(user_id: str) -> Optional[datetime]:
    """
    Returns the end time of the most recent completed trial.
    """
    query = """
        SELECT MAX(EndedAt)
        FROM user_trials
        WHERE user_id = %s
          AND Status = 'COMPLETED'
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(query, (user_id,))
        row = cur.fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


# -------------------------------------------------
# Authoritative resolver
# -------------------------------------------------

def get_trial_state(user_id: str) -> str:
    """
    Single authoritative trial participation state resolver.

    Possible states:
      - not_in_trial
      - applied
      - invited
      - accepted
      - nda_signed
      - active
      - cooldown
    """

    if not user_id:
        return "unknown"

    # 1️⃣ Active trial (hard lock)
    if _get_active_trial(user_id):
        return "active"

    # 2️⃣ Accepted but not yet active (hard lock)
    if _get_accepted_trial(user_id):
        return "accepted"

    # 3️⃣ NDA signed, awaiting logistics
    if _get_signed_nda_trial(user_id):
        return "nda_signed"

    # 4️⃣ Pending invitations (can be multiple)
    if _get_pending_invites(user_id) > 0:
        return "invited"

    # 5️⃣ Cooldown window after last completed trial
    last_end = _get_last_trial_end(user_id)
    if last_end:
        cooldown_until = last_end + timedelta(days=COOLDOWN_DAYS)
        if datetime.utcnow() < cooldown_until:
            return "cooldown"

    # 6️⃣ Default free-agent state
    return "not_in_trial"
