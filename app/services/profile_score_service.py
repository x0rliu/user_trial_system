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
                "include": set(),
                "exclude": set(),
                "boost": {uid: weight},
                "deprioritize": {uid: weight}
            }
        }

    Returns:
        {
            "score": float,
            "eligible": bool,
            "breakdown": {...}
        }
    """

    total_score = 0.0
    max_score = 0.0
    eligible = True

    breakdown = {}

    # -------------------------
    # PER CATEGORY
    # -------------------------
    for category_id, rules in trial_profile.items():

        user_values = user_profiles.get(category_id, set())
        include_set = rules.get("include", set())
        exclude_set = rules.get("exclude", set())

        if display_name == "Richard Liu":
            print("CATEGORY:", category_id)
            print("USER VALUES:", user_values)
            print("EXCLUDE SET:", exclude_set)

        boost_map = rules.get("boost", {})
        deprioritize_map = rules.get("deprioritize", {})

        category_score = 1.0
        category_max = 1.0

        reason = []

        # -------------------------
        # EXCLUDE (HARD FAIL)
        # -------------------------
        if exclude_set and user_values.intersection(exclude_set):
            eligible = False
            reason.append("excluded_match")

            breakdown[category_id] = {
                "result": "fail_exclude",
                "user_values": list(user_values),
                "rules": rules
            }

            continue

        # -------------------------
        # INCLUDE (MUST MATCH)
        # -------------------------
        if include_set:
            if not user_values.intersection(include_set):
                eligible = False
                reason.append("missing_include")

                breakdown[category_id] = {
                    "result": "fail_include",
                    "user_values": list(user_values),
                    "rules": rules
                }

                continue
            else:
                reason.append("include_match")

        # -------------------------
        # BOOST / DEPRIORITIZE
        # -------------------------
        multiplier = 1.0

        for uid in user_values:
            if uid in boost_map:
                multiplier *= boost_map[uid]

            if uid in deprioritize_map:
                multiplier *= deprioritize_map[uid]

        category_score *= multiplier

        # -------------------------
        # ACCUMULATE
        # -------------------------
        total_score += category_score
        max_score += category_max

        breakdown[category_id] = {
            "result": "pass",
            "user_values": list(user_values),
            "multiplier": multiplier,
            "rules": rules
        }

    # -------------------------
    # NORMALIZE
    # -------------------------
    if max_score == 0:
        final_score = 0
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