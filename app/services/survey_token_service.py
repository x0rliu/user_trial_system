import uuid
from app.db import survey_tokens as db


def ensure_token(user_id: str, round_id: int, survey_type: str) -> str:
    """
    Returns an existing token if one exists for (user_id, round_id, survey_type),
    otherwise creates a new one.

    This function MUST be used everywhere tokens are needed.
    """

    # 1. Check existing
    existing = db.get_token_by_user_round_survey(user_id, round_id, survey_type)
    if existing:
        return existing["participation_token"]

    # 2. Create new token
    token = uuid.uuid4().hex

    db.insert_token(
        user_id=user_id,
        round_id=round_id,
        survey_type=survey_type,
        token=token
    )

    return token


def get_by_token(token: str) -> dict | None:
    """
    Lookup token → returns row with user_id, round_id, survey_type
    """
    return db.get_by_token(token)


def mark_token_used(token: str) -> None:
    """
    Marks a token as used (optional for MVP, but useful later)
    """
    db.mark_token_used(token)