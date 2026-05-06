# app/db/user_pool.py

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

# ============================================================================
# USER DEMOGRAPHICS STORAGE CONTRACT
# ----------------------------------------------------------------------------
# Canonical account country / eligibility field:
#
# - user_pool.CountryCode
#
# CountryCode is the ONLY supported source of truth for a user's account-level
# country/region. It is used for onboarding demographics, Settings, eligibility,
# targeting, and trial visibility.
#
# Do not confuse this with:
#
# - home_addresses.Country
# - project_participants.ShippingCountry
# - system_office_locations.Country
#
# Those fields represent delivery addresses or office geography. They must not
# overwrite user_pool.CountryCode and must not become account eligibility state.
#
# ----------------------------------------------------------------------------
# Canonical mobile fields:
#
# - user_pool.MobileCountryCode
# - user_pool.MobileNational
# - user_pool.MobileE164
#
# These fields are the ONLY supported source of truth for user mobile data.
#
# Legacy field:
#
# - user_pool.PhoneNumber
#
# PhoneNumber remains in the schema temporarily for backward compatibility
# and historical migrations only.
#
# New code MUST NOT:
# - read from PhoneNumber
# - write to PhoneNumber
# - use PhoneNumber for normalization
# - use PhoneNumber as a fallback source
#
# All new mobile workflows must use the normalized Mobile* fields exclusively.
# ============================================================================

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
                CountryCode = %s,
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
    Advance the user's profile wizard cursor.

    Routing source of truth:
    - user_pool.ProfileWizardStep

    Metadata only:
    - user_pool.profile_updated_at
    - user_pool.profile_completed_at

    This function never infers completion from selected profile rows.
    It only advances the explicit DB cursor and records timestamps.
    """

    normalized_step = int(step)

    if normalized_step < 0:
        raise ValueError("Profile wizard step cannot be negative.")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE user_pool
            SET
                ProfileWizardStep = GREATEST(COALESCE(ProfileWizardStep, 0), %s),
                profile_updated_at = NOW(),
                profile_completed_at = CASE
                    WHEN GREATEST(COALESCE(ProfileWizardStep, 0), %s) >= 3
                         AND profile_completed_at IS NULL
                    THEN NOW()
                    ELSE profile_completed_at
                END,
                UpdatedAt = NOW()
            WHERE user_id = %s
            """,
            (
                normalized_step,
                normalized_step,
                user_id,
            ),
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

import mysql.connector
from app.config.config import DB_CONFIG


def get_all_users():

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT
                user_id,
                FirstName,
                LastName,
                Email,
                CountryCode
            FROM user_pool
        """)

        return cur.fetchall()

    finally:
        conn.close()

def update_password_hash(user_id: str, password_hash: str):
    """
    Update a user's password hash.

    DB is the source of truth.
    This function performs one DB mutation and commits it.
    """

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE user_pool
            SET
                PasswordHash = %s,
                UpdatedAt = NOW()
            WHERE user_id = %s
            """,
            (
                password_hash,
                user_id,
            ),
        )

        if cur.rowcount == 0:
            raise RuntimeError(f"Password update failed: user not found: {user_id}")

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()