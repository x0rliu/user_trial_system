# app/db/bonus_survey_drafts.py

import json
import uuid
from datetime import date, datetime
from typing import Any

import mysql.connector

from app.config.config import DB_CONFIG


def _connect():
    return mysql.connector.connect(**DB_CONFIG)


def _date_to_string(value) -> str:
    if not value:
        return ""

    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    return str(value)


def _datetime_to_string(value) -> str | None:
    if not value:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


def _blank_to_none(value):
    if value is None:
        return None

    if isinstance(value, str) and not value.strip():
        return None

    return value


def _normalize_datetime_for_db(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        # datetime.utcnow().isoformat() uses "T"; MySQL prefers a space.
        return value.replace("T", " ").split(".")[0]

    return value


def _decode_targeting(raw_value) -> dict:
    if not raw_value:
        return {}

    if isinstance(raw_value, dict):
        return raw_value

    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            return {}

        return parsed if isinstance(parsed, dict) else {}

    return {}


def _encode_targeting(value: dict | None) -> str:
    if not isinstance(value, dict):
        value = {}

    return json.dumps(value, ensure_ascii=False)


def _row_to_draft(row: dict | None) -> dict | None:
    if not row:
        return None

    return {
        "draft_id": row.get("draft_uuid"),
        "bonus_survey_draft_id": row.get("bonus_survey_draft_id"),
        "status": row.get("status") or "draft",
        "basics": {
            "survey_name": row.get("title") or "",
            "start_date": _date_to_string(row.get("start_date")),
            "end_date": _date_to_string(row.get("end_date")),
            "purpose": row.get("description") or "",
        },
        "template": {
            "survey_link": row.get("survey_link") or "",
        },
        "targeting": _decode_targeting(row.get("targeting_json")),
        "bonus_survey_id": row.get("submitted_bonus_survey_id"),
        "submitted_at": _datetime_to_string(row.get("submitted_at")),
    }


def create_bonus_survey_draft(*, user_id: str) -> str:
    """
    Create a resumable DB-backed bonus survey draft.
    Returns draft_uuid because existing routes use UUID draft IDs.
    """

    draft_uuid = str(uuid.uuid4())

    conn = _connect()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bonus_survey_drafts (
                draft_uuid,
                created_by_user_id,
                status,
                title,
                description,
                start_date,
                end_date,
                survey_link,
                targeting_json
            )
            VALUES (%s, %s, 'draft', %s, %s, NULL, NULL, NULL, %s)
            """,
            (
                draft_uuid,
                user_id,
                "",
                "",
                _encode_targeting({}),
            ),
        )

        conn.commit()

        return draft_uuid

    finally:
        conn.close()


def get_bonus_survey_draft(*, user_id: str, draft_id: str) -> dict | None:
    """
    Fetch a draft by user and draft UUID.
    """

    conn = _connect()
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                bonus_survey_draft_id,
                draft_uuid,
                created_by_user_id,
                status,
                title,
                description,
                start_date,
                end_date,
                survey_link,
                targeting_json,
                submitted_bonus_survey_id,
                submitted_at,
                created_at,
                updated_at
            FROM bonus_survey_drafts
            WHERE created_by_user_id = %s
              AND draft_uuid = %s
            LIMIT 1
            """,
            (user_id, draft_id),
        )

        return _row_to_draft(cur.fetchone())

    finally:
        conn.close()


def update_bonus_survey_draft(
    *,
    user_id: str,
    draft_id: str,
    patch: dict,
) -> None:
    """
    Merge-save partial draft state into the DB.

    Expected patch shapes from handlers:
      {"basics": {...}}
      {"template": {...}}
      {"targeting": {...}}
      {"status": "...", "submitted_at": "...", "bonus_survey_id": 123}
    """

    existing = get_bonus_survey_draft(
        user_id=user_id,
        draft_id=draft_id,
    )

    if existing is None:
        raise RuntimeError("Draft not found")

    basics = dict(existing.get("basics") or {})
    template = dict(existing.get("template") or {})
    targeting = dict(existing.get("targeting") or {})

    if isinstance(patch.get("basics"), dict):
        basics.update(patch["basics"])

    if isinstance(patch.get("template"), dict):
        template.update(patch["template"])

    if isinstance(patch.get("targeting"), dict):
        targeting.update(patch["targeting"])

    status = patch.get("status", existing.get("status") or "draft")
    submitted_bonus_survey_id = patch.get(
        "bonus_survey_id",
        existing.get("bonus_survey_id"),
    )
    submitted_at = patch.get(
        "submitted_at",
        existing.get("submitted_at"),
    )

    conn = _connect()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bonus_survey_drafts
            SET
                status = %s,
                title = %s,
                description = %s,
                start_date = %s,
                end_date = %s,
                survey_link = %s,
                targeting_json = %s,
                submitted_bonus_survey_id = %s,
                submitted_at = %s
            WHERE created_by_user_id = %s
              AND draft_uuid = %s
            """,
            (
                status,
                basics.get("survey_name") or "",
                basics.get("purpose") or "",
                _blank_to_none(basics.get("start_date")),
                _blank_to_none(basics.get("end_date")),
                _blank_to_none(template.get("survey_link")),
                _encode_targeting(targeting),
                submitted_bonus_survey_id,
                _normalize_datetime_for_db(submitted_at),
                user_id,
                draft_id,
            ),
        )

        conn.commit()

    finally:
        conn.close()


def delete_bonus_survey_draft(*, user_id: str, draft_id: str) -> None:
    """
    Delete a draft row.
    """

    conn = _connect()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM bonus_survey_drafts
            WHERE created_by_user_id = %s
              AND draft_uuid = %s
            """,
            (user_id, draft_id),
        )

        conn.commit()

    finally:
        conn.close()


def list_bonus_survey_drafts_for_user(*, user_id: str) -> list[str]:
    """
    Return UUID draft IDs for active drafts owned by this user.
    """

    conn = _connect()
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT draft_uuid
            FROM bonus_survey_drafts
            WHERE created_by_user_id = %s
              AND status = 'draft'
            ORDER BY updated_at DESC, created_at DESC
            """,
            (user_id,),
        )

        rows = cur.fetchall()

        return [
            row["draft_uuid"]
            for row in rows
            if row.get("draft_uuid")
        ]

    finally:
        conn.close()