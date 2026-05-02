# app/cache/surveys_cache.py

"""
Compatibility wrapper for Bonus Survey draft state.

Historically, Bonus Survey drafts were stored in memory here.
That broke resumability because drafts disappeared across refreshes/restarts.

The public function names remain unchanged so existing handlers do not need to
be refactored in the same pass, but the source of truth is now MySQL via
app.db.bonus_survey_drafts.
"""

from app.db.bonus_survey_drafts import (
    create_bonus_survey_draft,
    get_bonus_survey_draft,
    update_bonus_survey_draft,
    delete_bonus_survey_draft,
    list_bonus_survey_drafts_for_user,
)


def create_bonus_draft(user_id: str) -> str:
    draft_id = create_bonus_survey_draft(
        user_id=user_id,
    )

    print("[DB] create_bonus_draft:", user_id, "->", draft_id)

    return draft_id


def get_bonus_draft(user_id: str, draft_id: str) -> dict | None:
    """
    Fetch an existing draft.
    Returns None if missing.
    """

    return get_bonus_survey_draft(
        user_id=user_id,
        draft_id=draft_id,
    )


def update_bonus_draft(user_id: str, draft_id: str, patch: dict) -> None:
    """
    Merge-save partial data into a DB-backed draft.
    """

    update_bonus_survey_draft(
        user_id=user_id,
        draft_id=draft_id,
        patch=patch,
    )


def delete_bonus_draft(*, user_id: str, draft_id: str) -> None:
    """
    Remove a draft completely.
    """

    delete_bonus_survey_draft(
        user_id=user_id,
        draft_id=draft_id,
    )


def list_bonus_drafts_for_user(user_id: str) -> list[str]:
    """
    Return draft UUIDs for this user that are still editable drafts.
    """

    draft_ids = list_bonus_survey_drafts_for_user(
        user_id=user_id,
    )

    print("[DB] list_bonus_drafts_for_user:", user_id, "->", draft_ids)

    return draft_ids