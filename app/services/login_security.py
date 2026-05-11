# app/services/login_security.py

import hashlib
import time

import mysql.connector

from app.config.config import DB_CONFIG

# ----------------------------------------
# CONFIG
# ----------------------------------------

MAX_ATTEMPTS_PER_ACCOUNT = 5
ACCOUNT_LOCK_SECONDS = 60

MAX_ATTEMPTS_PER_IP = 30
IP_LOCK_SECONDS = 300

ATTEMPT_WINDOW_SECONDS = 300


def _now() -> float:
    return time.time()


def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def _normalize_ip(ip: str) -> str:
    return str(ip or "").strip()[:128]


def _rate_key_hash(*, key_type: str, value: str) -> str:
    raw = f"{key_type}:{value}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _ensure_table_exists() -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS login_rate_limits (
              RateKeyHash CHAR(64) NOT NULL,
              RateType VARCHAR(20) NOT NULL,
              AttemptCount INT UNSIGNED NOT NULL DEFAULT 0,
              WindowStartedAt DOUBLE NOT NULL DEFAULT 0,
              LockedUntil DOUBLE NOT NULL DEFAULT 0,
              UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              PRIMARY KEY (RateKeyHash),
              KEY idx_rate_type (RateType),
              KEY idx_locked_until (LockedUntil)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        conn.commit()
    finally:
        conn.close()


def _get_limit_row(*, key_hash: str):
    _ensure_table_exists()

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT AttemptCount, WindowStartedAt, LockedUntil
            FROM login_rate_limits
            WHERE RateKeyHash = %s
            LIMIT 1
            """,
            (key_hash,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def _record_failure_for_key(
    *,
    key_type: str,
    key_hash: str,
    max_attempts: int,
    lock_seconds: int,
) -> None:
    _ensure_table_exists()
    now = _now()

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        conn.start_transaction()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT AttemptCount, WindowStartedAt, LockedUntil
            FROM login_rate_limits
            WHERE RateKeyHash = %s
            LIMIT 1
            FOR UPDATE
            """,
            (key_hash,),
        )
        row = cur.fetchone()

        if row and now - float(row.get("WindowStartedAt") or 0) <= ATTEMPT_WINDOW_SECONDS:
            attempt_count = int(row.get("AttemptCount") or 0) + 1
            window_started_at = float(row.get("WindowStartedAt") or now)
        else:
            attempt_count = 1
            window_started_at = now

        locked_until = now + lock_seconds if attempt_count >= max_attempts else 0

        cur.execute(
            """
            INSERT INTO login_rate_limits (
                RateKeyHash, RateType, AttemptCount, WindowStartedAt, LockedUntil
            ) VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                RateType = VALUES(RateType),
                AttemptCount = VALUES(AttemptCount),
                WindowStartedAt = VALUES(WindowStartedAt),
                LockedUntil = VALUES(LockedUntil)
            """,
            (
                key_hash,
                key_type,
                attempt_count,
                window_started_at,
                locked_until,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _delete_limit_rows(key_hashes: list[str]) -> None:
    if not key_hashes:
        return

    _ensure_table_exists()

    placeholders = ",".join(["%s"] * len(key_hashes))
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            f"DELETE FROM login_rate_limits WHERE RateKeyHash IN ({placeholders})",
            tuple(key_hashes),
        )
        conn.commit()
    finally:
        conn.close()


def _account_key_hash(email: str) -> str:
    return _rate_key_hash(
        key_type="account",
        value=_normalize_email(email),
    )


def _ip_key_hash(ip: str) -> str:
    return _rate_key_hash(
        key_type="ip",
        value=_normalize_ip(ip),
    )


def check_login_allowed(email: str, ip: str) -> tuple[bool, str]:
    now = _now()

    ip_row = _get_limit_row(key_hash=_ip_key_hash(ip))
    if ip_row and float(ip_row.get("LockedUntil") or 0) > now:
        return False, "Too many attempts. Try again later."

    account_row = _get_limit_row(key_hash=_account_key_hash(email))
    if account_row and float(account_row.get("LockedUntil") or 0) > now:
        return False, "Too many attempts for this account. Try again later."

    return True, ""


def record_failure(email: str, ip: str):
    _record_failure_for_key(
        key_type="account",
        key_hash=_account_key_hash(email),
        max_attempts=MAX_ATTEMPTS_PER_ACCOUNT,
        lock_seconds=ACCOUNT_LOCK_SECONDS,
    )
    _record_failure_for_key(
        key_type="ip",
        key_hash=_ip_key_hash(ip),
        max_attempts=MAX_ATTEMPTS_PER_IP,
        lock_seconds=IP_LOCK_SECONDS,
    )


def record_success(email: str, ip: str):
    _delete_limit_rows([
        _account_key_hash(email),
        _ip_key_hash(ip),
    ])