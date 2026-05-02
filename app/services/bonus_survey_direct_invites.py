# app/services/bonus_survey_direct_invites.py

import re

from app.db.bonus_survey_draft_recipients import (
    get_users_by_normalized_emails,
    replace_draft_recipients,
    delete_draft_recipients,
    get_draft_recipients,
    get_draft_recipient_counts,
)


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)


def _split_email_input(raw_text: str) -> list[str]:
    """
    Split pasted email input.

    Supports:
      - one email per line
      - comma-separated
      - semicolon-separated
      - space-separated
      - tab-separated

    Does not store raw pasted blobs.
    """

    if not raw_text:
        return []

    tokens = re.split(r"[\s,;]+", raw_text)

    cleaned = []

    for token in tokens:
        value = token.strip().strip("<>").strip()

        if not value:
            continue

        cleaned.append(value)

    return cleaned


def parse_direct_invite_emails(raw_text: str) -> dict:
    """
    Parse raw pasted text into normalized valid emails and invalid tokens.
    """

    tokens = _split_email_input(raw_text)

    seen_valid = set()
    seen_invalid = set()

    valid = []
    invalid = []

    for token in tokens:
        normalized = token.strip().lower()

        if EMAIL_PATTERN.match(normalized):
            if normalized in seen_valid:
                continue

            seen_valid.add(normalized)

            valid.append({
                "raw_email": token,
                "normalized_email": normalized,
            })

            continue

        invalid_key = token.strip().lower()

        if invalid_key in seen_invalid:
            continue

        seen_invalid.add(invalid_key)

        invalid.append({
            "raw_email": token,
            "normalized_email": None,
        })

    return {
        "valid": valid,
        "invalid": invalid,
    }


def save_direct_invite_recipients_for_draft(
    *,
    draft_uuid: str,
    raw_email_text: str,
) -> dict:
    """
    Parse, validate, match against user_pool, and replace saved draft recipients.

    Raw pasted text is never stored as a blob.
    """

    parsed = parse_direct_invite_emails(raw_email_text)

    valid = parsed["valid"]
    invalid = parsed["invalid"]

    normalized_emails = [
        item["normalized_email"]
        for item in valid
        if item.get("normalized_email")
    ]

    users_by_email = get_users_by_normalized_emails(normalized_emails)

    recipient_rows = []

    for item in valid:
        normalized_email = item["normalized_email"]
        user = users_by_email.get(normalized_email)

        if user:
            recipient_rows.append({
                "raw_email": item["raw_email"],
                "normalized_email": normalized_email,
                "matched_user_id": user["user_id"],
                "status": "matched",
            })
        else:
            recipient_rows.append({
                "raw_email": item["raw_email"],
                "normalized_email": normalized_email,
                "matched_user_id": None,
                "status": "unmatched",
            })

    for item in invalid:
        recipient_rows.append({
            "raw_email": item["raw_email"],
            "normalized_email": None,
            "matched_user_id": None,
            "status": "invalid",
        })

    replace_draft_recipients(
        draft_uuid=draft_uuid,
        recipients=recipient_rows,
    )

    return summarize_direct_invite_recipients(
        draft_uuid=draft_uuid,
    )


def clear_direct_invite_recipients_for_draft(*, draft_uuid: str) -> None:
    """
    Clear direct invite recipients when the draft is no longer direct invite.
    """

    delete_draft_recipients(
        draft_uuid=draft_uuid,
    )


def summarize_direct_invite_recipients(*, draft_uuid: str) -> dict:
    """
    Return counts and rows for review/rendering.
    """

    rows = get_draft_recipients(
        draft_uuid=draft_uuid,
    )

    counts = get_draft_recipient_counts(
        draft_uuid=draft_uuid,
    )

    return {
        "counts": counts,
        "recipients": rows,
    }


def draft_recipients_to_textarea_value(*, draft_uuid: str) -> str:
    """
    Rehydrate textarea from normalized saved rows.

    This is not the original pasted blob. It is a clean operational projection.
    """

    rows = get_draft_recipients(
        draft_uuid=draft_uuid,
    )

    emails = []

    for row in rows:
        if row.get("normalized_email"):
            emails.append(row["normalized_email"])
        else:
            emails.append(row.get("raw_email") or "")

    return "\n".join([
        email
        for email in emails
        if email
    ])