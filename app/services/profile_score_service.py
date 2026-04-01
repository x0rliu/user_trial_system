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

def calculate_profile_score(user: dict, trial_profile: dict) -> dict:
    """
    Main entry point

    trial_profile structure:

    {
        "type": "internal" | "external",

        # For INTERNAL (3a)
        "criteria": [
            {
                "field": "CountryCode",
                "values": ["US", "TW"]
            },
            ...
        ],

        # For EXTERNAL (3b)
        "questions": [
            {
                "question_id": "q1",
                "weights": {
                    "A": 1.0,
                    "B": 0.5,
                    "C": 0.0
                }
            }
        ]
    }
    """

    if not trial_profile:
        return {
            "score": 0,
            "breakdown": {}
        }

    profile_type = trial_profile.get("type")

    if profile_type == "external":
        return _score_external(user, trial_profile)

    # default to internal
    return _score_internal(user, trial_profile)


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