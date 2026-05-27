# app/db/system_settings.py

import mysql.connector
from app.config.config import DB_CONFIG


DEBUG_ALLOW_UNMATCHED_SURVEY_IDENTITY_KEY = "debug_allow_unmatched_survey_identity"


def _normalize_boolean_value(value) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"1", "true", "yes", "on", "enabled"}:
        return "On"
    return "Off"


def ensure_system_setting_definition(
    *,
    setting_key: str,
    setting_name: str,
    setting_description: str,
    default_value: str,
    allowed_values: str = "On,Off",
    data_type: str = "boolean",
) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO settings_definition (
                SettingKey,
                SettingName,
                SettingDescription,
                DefaultValue,
                AllowedValues,
                DataType,
                Scope
            ) VALUES (%s,%s,%s,%s,%s,%s,'System')
            ON DUPLICATE KEY UPDATE
                SettingName = VALUES(SettingName),
                SettingDescription = VALUES(SettingDescription),
                DefaultValue = VALUES(DefaultValue),
                AllowedValues = VALUES(AllowedValues),
                DataType = VALUES(DataType),
                Scope = 'System'
            """,
            (
                setting_key,
                setting_name,
                setting_description,
                default_value,
                allowed_values,
                data_type,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def ensure_debug_survey_identity_setting() -> None:
    ensure_system_setting_definition(
        setting_key=DEBUG_ALLOW_UNMATCHED_SURVEY_IDENTITY_KEY,
        setting_name="Debug: Allow Unmatched Survey Identity",
        setting_description=(
            "Temporary debugging toggle. When On, Product Trial survey uploads "
            "ingest rows even when token/email attribution cannot link the "
            "response to a registered user. Rows remain marked NeedsReview."
        ),
        default_value="Off",
    )

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO system_settings (SettingKey, SettingValue)
            VALUES (%s, 'Off')
            ON DUPLICATE KEY UPDATE
                SettingValue = SettingValue
            """,
            (DEBUG_ALLOW_UNMATCHED_SURVEY_IDENTITY_KEY,),
        )
        conn.commit()
    finally:
        conn.close()


def get_system_setting_value(setting_key: str, default_value: str | None = None) -> str | None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT SettingValue
            FROM system_settings
            WHERE SettingKey = %s
            LIMIT 1
            """,
            (setting_key,),
        )
        row = cur.fetchone()
        if not row:
            return default_value
        return row.get("SettingValue") if row.get("SettingValue") is not None else default_value
    finally:
        conn.close()


def set_system_setting_value(setting_key: str, setting_value: str) -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO system_settings (SettingKey, SettingValue)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                SettingValue = VALUES(SettingValue)
            """,
            (setting_key, setting_value),
        )
        conn.commit()
    finally:
        conn.close()


def get_debug_survey_identity_setting() -> dict:
    value = _normalize_boolean_value(
        get_system_setting_value(
            DEBUG_ALLOW_UNMATCHED_SURVEY_IDENTITY_KEY,
            "Off",
        )
    )

    return {
        "key": DEBUG_ALLOW_UNMATCHED_SURVEY_IDENTITY_KEY,
        "value": value,
        "enabled": value == "On",
    }


def set_debug_survey_identity_setting(enabled: bool) -> dict:
    ensure_debug_survey_identity_setting()
    value = "On" if enabled else "Off"
    set_system_setting_value(DEBUG_ALLOW_UNMATCHED_SURVEY_IDENTITY_KEY, value)
    return {
        "key": DEBUG_ALLOW_UNMATCHED_SURVEY_IDENTITY_KEY,
        "value": value,
        "enabled": value == "On",
    }


def is_debug_unmatched_survey_identity_enabled() -> bool:
    return bool(get_debug_survey_identity_setting().get("enabled"))