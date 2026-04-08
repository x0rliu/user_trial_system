# app/services/profile_score_service.py

"""
Profile Score Service

Purpose:
- Calculate how well a user matches a specific trial profile
- Supports:
    3a. Internal profile matching (no external survey)
    3b. External survey scoring (weighted multiple choice)
- Returns score + breakdown for full transparency

DO NOT:
- Write to DB
- Hide logic
- Infer missing data silently
"""


# =========================
# CONFIG
# =========================

MATCH_SCORE = 1.0
UNKNOWN_SCORE = 0.2
NO_MATCH_SCORE = 0.0


# =========================
# CORE ENTRY
# =========================

def calculate_profile_score(
    user_profiles: dict,
    trial_profile: dict,
    display_name: str | None = None
) -> dict:
    """
    user_profiles:
        { CategoryID: set(ProfileUID) }

    trial_profile:
        {
            CategoryID: {
                "include": set() | dict(),
                "exclude": set() | dict(),
                "boost": {uid: weight} | {uid: {"label": ..., "weight": ...}},
                "deprioritize": {uid: weight} | {uid: {"label": ..., "weight": ...}}
            }
        }

    MVP additive scoring:
    - explicit wanted match   = 1.0
    - explicit unwanted match = 0.0
    - no data                 = 0.2

    IMPORTANT:
    - No hard fail for include/exclude in MVP additive mode
    - Score is normalized across configured categories
    """

    total_score = 0.0
    max_score = 0.0
    eligible = True

    breakdown = {}

    def _normalize_uid_set(value):
        if isinstance(value, dict):
            return set(value.keys())
        if isinstance(value, set):
            return value
        if isinstance(value, list):
            return set(value)
        return set()

    def _extract_weight(raw_value, default_value=1.0):
        if isinstance(raw_value, dict):
            return raw_value.get("weight", default_value)
        if raw_value is None:
            return default_value
        return raw_value

    # -------------------------
    # PER CATEGORY
    # -------------------------
    for category_id, rules in trial_profile.items():

        user_values = user_profiles.get(category_id, set()) or set()

        include_set = _normalize_uid_set(rules.get("include", set()))
        exclude_set = _normalize_uid_set(rules.get("exclude", set()))

        boost_map = rules.get("boost", {}) or {}
        deprioritize_map = rules.get("deprioritize", {}) or {}

        if display_name == "Richard Liu":
            print("CATEGORY:", category_id)
            print("USER VALUES:", user_values)
            print("INCLUDE SET:", include_set)
            print("EXCLUDE SET:", exclude_set)

        category_max = 1.0
        multiplier = 1.0

        # -------------------------
        # BASE CATEGORY SCORE
        # -------------------------
        # Rule:
        # - if no user data for this category -> UNKNOWN_SCORE
        # - if any explicit wanted match      -> MATCH_SCORE
        # - if any explicit unwanted match    -> NO_MATCH_SCORE
        # - otherwise explicit data but no wanted match -> NO_MATCH_SCORE
        #   (boring / transparent MVP rule)
        # -------------------------

        if not user_values:
            category_score = UNKNOWN_SCORE
            result = "unknown"

        elif include_set and user_values.intersection(include_set):
            category_score = MATCH_SCORE
            result = "include_match"

        elif exclude_set and user_values.intersection(exclude_set):
            category_score = NO_MATCH_SCORE
            result = "exclude_match"

        else:
            category_score = NO_MATCH_SCORE
            result = "explicit_no_match"

        # -------------------------
        # BOOST / DEPRIORITIZE
        # -------------------------
        for uid in user_values:
            if uid in boost_map:
                multiplier *= _extract_weight(boost_map[uid], 1.2)

            if uid in deprioritize_map:
                multiplier *= _extract_weight(deprioritize_map[uid], 0.8)

        category_score *= multiplier

        # -------------------------
        # ACCUMULATE
        # -------------------------
        total_score += category_score
        max_score += category_max

        breakdown[category_id] = {
            "result": result,
            "user_values": list(user_values),
            "base_score": category_score / multiplier if multiplier != 0 else category_score,
            "multiplier": multiplier,
            "final_category_score": category_score,
            "rules": rules
        }

    # -------------------------
    # NORMALIZE
    # -------------------------
    if max_score == 0:
        final_score = 0.0
    else:
        final_score = total_score / max_score

    return {
        "score": final_score,
        "eligible": eligible,
        "breakdown": breakdown
    }

# =========================
# INTERNAL PROFILE (3a)
# =========================

def _score_internal(user: dict, trial_profile: dict) -> dict:
    """
    Internal matching:
    MATCH = 1
    UNKNOWN = 0.2
    NO MATCH = 0
    """

    criteria = trial_profile.get("criteria", [])

    total_score = 0
    breakdown = {}

    for c in criteria:
        field = c.get("field")
        allowed_values = c.get("values", [])

        user_value = user.get(field)

        # UNKNOWN
        if user_value is None:
            score = UNKNOWN_SCORE
            reason = "unknown"

        # MATCH
        elif user_value in allowed_values:
            score = MATCH_SCORE
            reason = "match"

        # NO MATCH
        else:
            score = NO_MATCH_SCORE
            reason = "no_match"

        total_score += score

        breakdown[field] = {
            "user_value": user_value,
            "allowed": allowed_values,
            "score": score,
            "reason": reason
        }

    return {
        "score": total_score,
        "breakdown": breakdown
    }


# =========================
# EXTERNAL PROFILE (3b)
# =========================

def _score_external(user: dict, trial_profile: dict) -> dict:
    """
    External survey scoring:
    - Only multiple choice
    - UT Lead defines weights per answer
    """

    questions = trial_profile.get("questions", [])

    # Expect user["survey_answers"] = { "q1": "A", "q2": "B" }
    answers = user.get("survey_answers", {})

    total_score = 0
    breakdown = {}

    for q in questions:
        qid = q.get("question_id")
        weights = q.get("weights", {})

        user_answer = answers.get(qid)

        # UNKNOWN / NOT ANSWERED
        if user_answer is None:
            score = UNKNOWN_SCORE
            reason = "no_answer"

        else:
            score = weights.get(user_answer, NO_MATCH_SCORE)

            if score == 0:
                reason = "no_match"
            else:
                reason = "weighted_match"

        total_score += score

        breakdown[qid] = {
            "user_answer": user_answer,
            "weights": weights,
            "score": score,
            "reason": reason
        }

    return {
        "score": total_score,
        "breakdown": breakdown
    }