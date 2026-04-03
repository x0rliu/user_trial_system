# services/selection_scoring_service.py

"""
Selection Scoring Service

Purpose:
- Combine quality score + profile score
- Apply dynamic soft gate scaling
- Produce final ranking score
- Return full breakdown (for explainability)

DO NOT:
- Write to DB
- Filter users
- Hide logic
"""

from app.services.user_score_service import calculate_user_score
from app.services.profile_score_service import calculate_profile_score


# =========================
# CONFIG (TUNE LATER)
# =========================

PROFILE_WEIGHT = 20  # scales profile into comparable range


# =========================
# PUBLIC API
# =========================

def score_user(user: dict, context: dict, trial_profile: dict) -> dict:
    """
    Score a single user.

    Returns:
        {
            "user_id": ...,
            "quality_score": int,
            "profile_score_raw": float,
            "profile_score_scaled": float,
            "soft_multiplier": float,
            "final_score": float,
            "breakdown": {...}
        }
    """

    # -------------------------
    # QUALITY
    # -------------------------
    quality_result = calculate_user_score(user, context)
    quality_score = quality_result["score"]

    # -------------------------
    # PROFILE
    # -------------------------
    from app.services.user_profile_service import get_user_profiles

    user_profiles = get_user_profiles(user["user_id"])

    profile_result = calculate_profile_score(
        user_profiles,
        trial_profile,
        display_name=user.get("display_name")
    )
    
    profile_raw = profile_result["score"]

    profile_scaled = profile_raw * PROFILE_WEIGHT

    # -------------------------
    # SOFT GATE MULTIPLIER
    # -------------------------
    soft_multiplier = _compute_soft_gate_multiplier(context)

    # -------------------------
    # FINAL SCORE
    # -------------------------
    # IMPORTANT:
    # Quality already includes penalties.
    # We SCALE its impact instead of re-applying penalties.
    final_score = (quality_score * soft_multiplier) + profile_scaled

    hard_gate_results = user.get("hard_gate_results", {})

    return {
        "user_id": user.get("user_id"),
        "display_name": user.get("display_name"),

        "motivation": user.get("motivation") or "",  # 🔥 ADD THIS

        "eligible": user.get("eligible", True),
        "exclusion_reason": user.get("exclusion_reason"),

        # 🔥 NEW STRUCTURED OUTPUT
        "hard_gate_results": hard_gate_results,

        "quality_score": quality_score,
        "profile_score_raw": profile_raw,
        "profile_score_scaled": profile_scaled,

        "soft_multiplier": soft_multiplier,

        "final_score": final_score,

        "breakdown": {
            "quality": quality_result["breakdown"],
            "profile": profile_result.get("breakdown", {}),
            "soft": {
                "multiplier": soft_multiplier,
                "pool_size": context.get("eligible_pool_size"),
                "target": context.get("target_users"),
            }
        }
    }


def score_users(users: list, context: dict, trial_profile: dict) -> list:
    """
    Score a list of users.

    Returns:
        sorted list (highest score first)
    """

    results = []

    for user in users:
        scored = score_user(user, context, trial_profile)
        results.append(scored)

    results.sort(
        key=lambda x: (
            x.get("eligible", True),          # False (ineligible) comes first
            -x.get("final_score", 0)          # then by score
        )
    )

    return results


# =========================
# INTERNAL HELPERS
# =========================

def _compute_soft_gate_multiplier(context: dict) -> float:
    """
    Dynamic scaling based on pool size.

    Behavior:
    - Large pool → strict (1.0)
    - Tight pool → lenient (~0.3)

    Context:
        {
            "eligible_pool_size": int,
            "target_users": int
        }
    """

    if not context:
        return 1.0

    pool = context.get("eligible_pool_size", 0)
    target = context.get("target_users", 0)

    if target <= 0:
        return 1.0

    ratio = pool / target

    # Normalize against "2x pool = ideal"
    normalized = ratio / 2

    # Clamp
    return max(0.3, min(normalized, 1.0))