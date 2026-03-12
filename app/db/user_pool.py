import mysql.connector
import uuid
from app.config.config import DB_CONFIG


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def user_exists_by_email(email: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM user_pool WHERE Email = %s LIMIT 1",
            (email.lower(),),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def insert_user_pool(
    email: str,
    password_hash: str,
    internal_user: int,
    status: int = 0,
    global_nda_status: str = "Not Sent",
    email_verified: int = 0,
):
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO user_pool (
                user_id,
                Email,
                PasswordHash,
                InternalUser,
                Status,
                GlobalNDA_Status,
                EmailVerified
            )
            VALUES (
                CONCAT('userid_', REPLACE(UUID(), '-', '')),
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """, (
            email,
            password_hash,
            internal_user,
            status,
            global_nda_status,
            email_verified
        ))

        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email: str):
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT *
            FROM user_pool
            WHERE Email = %s
            LIMIT 1
            """,
            (email,)
        )
        return cur.fetchone()
    finally:
        conn.close()

def get_user_by_userid(user_id: str):
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT *
            FROM user_pool
            WHERE user_id = %s
            LIMIT 1
            """,
            (user_id,),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def update_last_login(user_id: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE user_pool
            SET LastLoginAt = NOW()
            WHERE user_id = %s
            """,
            (user_id,)
        )
        conn.commit()
    finally:
        conn.close()

def mark_global_nda_signed(user_id: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE user_pool
            SET
                GlobalNDA_Status = 'Signed',
                GlobalNDA_SignedAt = NOW()
            WHERE user_id = %s
            """,
            (user_id,)
        )
        conn.commit()
    finally:
        conn.close()

def mark_email_verified(user_id: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE user_pool
            SET
                EmailVerified = 1,
                EmailVerificationSentAt = NOW()
            WHERE user_id = %s
            """,
            (user_id,)
        )
        conn.commit()
    finally:
        conn.close()

def mark_welcome_seen(user_id: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE user_pool
            SET WelcomeSeenAt = NOW()
            WHERE user_id = %s
            """,
            (user_id,)
        )
        conn.commit()
    finally:
        conn.close()

def update_user_demographics(
    *,
    user_id: str,
    first_name: str,
    last_name: str,
    gender: str,
    birth_year: int,
    country: str,
    city: str,
    mobile_country_code: str | None,
    mobile_national: str | None,
    mobile_e164: str | None,
):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE user_pool
            SET
                FirstName = %s,
                LastName = %s,
                Gender = %s,
                BirthYear = %s,
                Country = %s,
                City = %s,
                MobileCountryCode = %s,
                MobileNational = %s,
                MobileE164 = %s,
                UpdatedAt = NOW()
            WHERE user_id = %s
            """,
            (
                first_name,
                last_name,
                gender,
                birth_year,
                country,
                city,
                mobile_country_code,
                mobile_national,
                mobile_e164,
                user_id,
            )
        )

        conn.commit()
    finally:
        conn.close()

def mark_guidelines_completed(user_id: str):
    """
    Marks participation guidelines as completed.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE user_pool
            SET
                GuidelinesCompletedAt = NOW(),
                UpdatedAt = NOW()
            WHERE user_id = %s
            """,
            (user_id,)
        )
        conn.commit()
    finally:
        conn.close()

def get_profile_wizard_step(user_id: str) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ProfileWizardStep
            FROM user_pool
            WHERE user_id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    finally:
        conn.close()


def advance_profile_wizard_step(user_id: str, step: int):
    """
    Sets ProfileWizardStep to max(current, step).
    Prevents regressions when revisiting earlier steps.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE user_pool
            SET
                ProfileWizardStep = GREATEST(ProfileWizardStep, %s),
                UpdatedAt = NOW()
            WHERE user_id = %s
            """,
            (step, user_id),
        )
        conn.commit()
    finally:
        conn.close()

def get_display_name_by_user_id(user_id: str) -> str:
    """
    Resolve user_id to display name.
    Falls back to user_id if not found.
    """

    from app.db.connection import get_db_connection

    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT FirstName, LastName
            FROM user_pool
            WHERE user_id = %s
            LIMIT 1
            """,
            (user_id,)
        )

        row = cursor.fetchone()

        if not row:
            return user_id

        first = row.get("FirstName") or ""
        last = row.get("LastName") or ""

        full_name = f"{first} {last}".strip()

        return full_name if full_name else user_id

    finally:
        conn.close()