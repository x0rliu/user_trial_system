# app/services/user_score_service.py

"""
User Score Service

Purpose:
- Calculate a user's trial suitability score
- Apply soft gates (cooldown, performance penalties)
- Return both score AND debug breakdown (critical for transparency)

DO NOT:
- Write to DB
- Hide logic
- Infer missing data silently
"""

from datetime import datetime


# =========================
# CONFIG (KEEP EXPLICIT)
# =========================

BASE_SCORE = 100

# Penalties
COOLDOWN_PENALTY_HIGH = 30
COOLDOWN_PENALTY_LOW = 10

MISSED_DEADLINE_PENALTY = 20
REMINDER_PENALTY = 5
LOW_QUALITY_PENALTY = 10

# Bonuses
APPLICATION_BONUS = 2
COMPLETION_BONUS = 10
MONTHLY_RECOVERY = 5

# Bounds
MIN_SCORE = 0
MAX_SCORE = 200


# =========================
# CORE FUNCTION
# =========================

def calculate_user_score(user: dict, context: dict | None = None) -> dict:
    """
    Calculate user score with full debug output.

    Args:
        user (dict): user data (must include relevant fields)
        context (dict): optional context (e.g. pool size for dynamic cooldown)

    Returns:
        dict:
        {
            "score": int,
            "breakdown": {...}
        }
    """

    now = datetime.utcnow()

    breakdown = {
        "base": BASE_SCORE,
        "penalties": {},
        "bonuses": {},
        "final": None
    }

    score = BASE_SCORE

    # =========================
    # NEGATIVE SIGNALS
    # =========================

    missed_deadlines = user.get("missed_deadlines", 0)
    if missed_deadlines:
        penalty = missed_deadlines * MISSED_DEADLINE_PENALTY
        score -= penalty
        breakdown["penalties"]["missed_deadlines"] = penalty

    reminders = user.get("reminders_needed", 0)
    if reminders:
        penalty = reminders * REMINDER_PENALTY
        score -= penalty
        breakdown["penalties"]["reminders"] = penalty

    low_quality_flags = user.get("low_quality_flags", 0)
    if low_quality_flags:
        penalty = low_quality_flags * LOW_QUALITY_PENALTY
        score -= penalty
        breakdown["penalties"]["low_quality"] = penalty

    # =========================
    # POSITIVE SIGNALS
    # =========================

    applications = user.get("applications_count", 0)
    if applications:
        bonus = applications * APPLICATION_BONUS
        score += bonus
        breakdown["bonuses"]["applications"] = bonus

    completions = user.get("completed_trials", 0)
    if completions:
        bonus = completions * COMPLETION_BONUS
        score += bonus
        breakdown["bonuses"]["completed_trials"] = bonus

    bonus_points = user.get("bonus_points", 0)
    if bonus_points:
        score += bonus_points
        breakdown["bonuses"]["bonus_points"] = bonus_points

    # =========================
    # TIME RECOVERY
    # =========================

    last_trial_date = user.get("last_trial_date")  # expected datetime or None

    if last_trial_date:
        months_elapsed = _months_between(last_trial_date, now)
        if months_elapsed > 0:
            bonus = months_elapsed * MONTHLY_RECOVERY
            score += bonus
            breakdown["bonuses"]["time_recovery"] = bonus

    # =========================
    # COOLDOWN (SOFT GATE)
    # =========================

    in_cooldown = user.get("in_cooldown", False)

    if in_cooldown:
        penalty = _get_cooldown_penalty(context)
        score -= penalty
        breakdown["penalties"]["cooldown"] = penalty

    # =========================
    # CLAMP SCORE
    # =========================

    score = max(MIN_SCORE, min(score, MAX_SCORE))
    breakdown["final"] = score

    return {
        "score": score,
        "breakdown": breakdown
    }


# =========================
# HELPERS
# =========================

def _months_between(start_date: datetime, end_date: datetime) -> int:
    """
    Rough month difference (good enough for scoring)
    """
    return max(
        0,
        (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    )


def _get_cooldown_penalty(context: dict | None) -> int:
    """
    Dynamic cooldown penalty based on pool size.

    Context expected:
        {
            "eligible_pool_size": int,
            "target_users": int
        }
    """

    if not context:
        return COOLDOWN_PENALTY_HIGH

    pool_size = context.get("eligible_pool_size", 0)
    target = context.get("target_users", 0)

    if target == 0:
        return COOLDOWN_PENALTY_HIGH

    # If pool is tight (<2x), soften penalty
    if pool_size < target * 2:
        return COOLDOWN_PENALTY_LOW

    return COOLDOWN_PENALTY_HIGH