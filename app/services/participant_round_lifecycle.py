# ut_site/app/services/participant_round_lifecycle.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.db.project_rounds import get_rounds_by_status
from app.db.project_participants import get_active_trials_for_user
# TODO: create app/db/project_applicants.py and import here


ROUND_PHASE_BY_OPERATIONAL_STATUS = {
    "Draft": "UPCOMING",
    "Recruiting": "RECRUITING",
    "Screening": "SELECTION",
    "Active": "IN_PROGRESS",
    "Closed": "COMPLETED",
    "Cancelled": "CANCELLED",
}


def get_round_phase(round_row: dict) -> str:
    status = (round_row.get("Status") or "").strip()
    return ROUND_PHASE_BY_OPERATIONAL_STATUS.get(status, "UNKNOWN")


def get_user_round_state(round_id: int, user_id: str) -> str:
    """
    Authoritative per-user state resolver for a single round.

    Precedence:
      1) project_participants (Selected/Active/Completed/...)
      2) project_applicants (Applied/Invited/Rejected/...)
      3) notification interest (Notified)
      4) None
    """
    # 1) participants (authoritative if exists)
    # NOTE: implement a get_participant_row_for_user_round() in app/db/project_participants.py
    # if participant_row:
    #     return participant_row["ParticipantStatus"].upper()

    # 2) applicants
    # NOTE: implement get_applicant_row(user_id, round_id) in app/db/project_applicants.py
    # if applicant_row:
    #     return applicant_row["ScreeningStatus"].upper()

    return "NONE"


def compute_primary_cta(round_phase: str, user_state: str) -> Optional[dict]:
    """
    CTA contract: {label, url} or None
    """
    if round_phase == "UPCOMING" and user_state == "NONE":
        return {"label": "Notify me", "url": "/trials/notify"}  # include round_id in real routing
    if round_phase == "RECRUITING" and user_state == "NONE":
        return {"label": "Apply", "url": "/trials/apply"}
    if user_state == "INVITED":
        return {"label": "Respond", "url": "/trials/invite"}
    if user_state in ("SELECTED", "ACTIVE") and round_phase == "IN_PROGRESS":
        return {"label": "Go to trial", "url": "/trials/active"}
    return None


def build_round_card(round_row: dict, user_state: str) -> dict:
    phase = get_round_phase(round_row)
    cta = compute_primary_cta(phase, user_state)

    # Participant-visible “chip” label (short, predictable)
    chip = None
    if phase == "CANCELLED":
        chip = "Cancelled"
    elif user_state == "APPLIED":
        chip = "Applied"
    elif user_state == "INVITED":
        chip = "Invited"
    elif user_state == "SELECTED":
        chip = "Selected"
    elif user_state == "ACTIVE":
        chip = "In trial"
    elif user_state == "COMPLETED" or phase == "COMPLETED":
        chip = "Completed"
    elif phase == "UPCOMING":
        chip = "Upcoming"
    elif phase == "RECRUITING":
        chip = "Recruiting"
    elif phase == "SELECTION":
        chip = "In review"

    return {
        "RoundID": round_row["RoundID"],
        "RoundName": round_row.get("RoundName"),
        "StartDate": round_row.get("StartDate"),
        "EndDate": round_row.get("EndDate"),
        "OperationalStatus": round_row.get("Status"),
        "RoundPhase": phase,
        "UserState": user_state,
        "StatusChip": chip,
        "PrimaryCTA": cta,
        # badges computed elsewhere from metrics you store
        "Badges": [],
    }


def list_participant_round_cards(user_id: str, mode: str) -> list[dict]:
    """
    mode: upcoming | recruiting | in_progress | completed
    Explicit list function so routes remain boring.
    """
    if mode == "upcoming":
        rounds = get_rounds_by_status("Draft")
    elif mode == "recruiting":
        rounds = get_rounds_by_status("Recruiting")
    elif mode == "in_progress":
        rounds = get_rounds_by_status("Active")
    elif mode == "completed":
        rounds = get_rounds_by_status("Closed")
    else:
        raise ValueError(f"unknown mode: {mode}")

    cards = []
    for r in rounds:
        user_state = get_user_round_state(r["RoundID"], user_id)
        cards.append(build_round_card(r, user_state))

    return cards