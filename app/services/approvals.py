# app/services/approvals.py

from typing import List, Dict


def get_pending_approvals() -> List[Dict]:
    """
    Returns a chronological list of approval items.
    Each item MUST include:
      - approval_type
      - approval_id
      - submitted_at
      - payload (domain-specific)
    """

    approvals: list[dict] = []

    # -----------------------------
    # Bonus survey approvals
    # -----------------------------
    from app.db.bonus_survey_tracker import get_pending_bonus_survey_approvals

    for a in get_pending_bonus_survey_approvals():
        approvals.append({
            "approval_type": "bonus_survey",
            "approval_id": a["tracker_id"],
            "submitted_at": a["submitted_at"],
            "payload": a,
        })

    # -----------------------------
    # Product trial approvals
    # -----------------------------
    from app.db.project_rounds import get_pending_project_trial_approvals

    for p in get_pending_project_trial_approvals():
        approvals.append({
            "approval_type": "product_trial",
            "approval_id": p["ProjectID"],     # canonical project identifier
            "submitted_at": p["submitted_at"], # already normalized in SQL
            "payload": p,
        })

    # -----------------------------
    # Sort newest-first
    # -----------------------------
    approvals.sort(
        key=lambda x: x["submitted_at"],
        reverse=True,
    )

    return approvals
