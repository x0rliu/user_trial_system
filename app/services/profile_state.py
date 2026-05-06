# app/services/profile_state.py

from __future__ import annotations


# --------------------------------------------------
# Profile state ownership
# --------------------------------------------------
#
# DB source of truth:
# - user_pool.ProfileWizardStep owns profile wizard routing state.
#
# Supporting data:
# - user_interest_map stores interest selections only.
# - user_profile_map stores profile selections only.
#
# Metadata only:
# - user_pool.profile_completed_at
# - user_pool.profile_updated_at
#
# Legacy / non-authoritative for routing:
# - user_pool.InterestsWizardCompleted
#
# Do not infer completion from selected profile rows. A user may explicitly
# continue through a step with sparse data, and that decision must remain
# resumable from ProfileWizardStep.
# --------------------------------------------------


PROFILE_STATE_INTERESTS = "interests"
PROFILE_STATE_BASIC = "basic_profile"
PROFILE_STATE_ADVANCED = "advanced_profile"
PROFILE_STATE_COMPLETE = "complete"


def get_profile_state(user_id: str) -> str:
    """
    Resolve the user's profile wizard state.

    This is read-only. It performs no writes and does not mutate profile data.

    ProfileWizardStep meaning:
    - 0 or NULL: interests step
    - 1: basic profile step
    - 2: advanced profile step
    - 3 or greater: complete
    """

    from app.db.user_pool import get_profile_wizard_step

    step = get_profile_wizard_step(user_id)

    if step < 1:
        return PROFILE_STATE_INTERESTS

    if step < 2:
        return PROFILE_STATE_BASIC

    if step < 3:
        return PROFILE_STATE_ADVANCED

    return PROFILE_STATE_COMPLETE