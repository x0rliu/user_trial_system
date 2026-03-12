# app/cache/surveys_cache.py

import uuid
from typing import Dict
from .simple_cache import cache


# ---------------------------------------------------------
# In-memory cache for Bonus Survey drafts
# Keyed by: bonus_survey_draft:{user_id}:{draft_id}
# ---------------------------------------------------------

_SURVEY_CACHE: Dict[str, dict] = {}

CACHE_TTL_SECONDS = 60 * 60 * 24 * 7  # informational for now


def _key(user_id: str, draft_id: str) -> str:
    return f"bonus_survey_draft:{user_id}:{draft_id}"


def create_bonus_draft(user_id: str) -> str:
    draft_id = str(uuid.uuid4())
    print("[CACHE] create_bonus_draft:", _key(user_id, draft_id))
    _SURVEY_CACHE[_key(user_id, draft_id)] = {}
    return draft_id


def get_bonus_draft(user_id: str, draft_id: str) -> dict | None:
    """
    Fetch an existing draft.
    Returns None if missing.
    """
    return _SURVEY_CACHE.get(_key(user_id, draft_id))


def update_bonus_draft(user_id: str, draft_id: str, patch: dict) -> None:
    """
    Merge-save partial data into a draft.
    """
    key = _key(user_id, draft_id)
    existing = _SURVEY_CACHE.get(key, {})
    existing.update(patch)
    _SURVEY_CACHE[key] = existing


def delete_bonus_draft(*, user_id: str, draft_id: str) -> None:
    """
    Remove a draft completely.
    """
    _SURVEY_CACHE.pop(_key(user_id, draft_id), None)

def list_bonus_drafts_for_user(user_id: str) -> list[str]:
    """
    Return draft_ids for this user that are still editable drafts.
    Only drafts with status == 'draft' (or missing status) are included.
    """
    prefix = f"bonus_survey_draft:{user_id}:"

    draft_ids: list[str] = []

    for key, draft in _SURVEY_CACHE.items():
        if not key.startswith(prefix):
            continue

        status = draft.get("status", "draft")

        if status != "draft":
            continue

        draft_ids.append(key.split(":")[-1])

    print("[CACHE] list_bonus_drafts_for_user:", user_id, "->", draft_ids)
    return draft_ids
