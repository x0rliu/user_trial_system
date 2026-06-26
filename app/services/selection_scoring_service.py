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
EXTERNAL_WEIGHT = 20  # scales recruiting survey fit into comparable range


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
            "external_score_raw": float,
            "external_score_scaled": float,
            "soft_multiplier": float,
            "final_score": float,
            "breakdown": {...}
        }
    """

    context = context or {}

    # -------------------------
    # QUALITY / RELIABILITY
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
    # EXTERNAL RECRUITING SURVEY
    # -------------------------
    external_result = _score_external_survey_fit(user, context)

    external_raw = external_result["score"]
    external_scaled = external_raw * EXTERNAL_WEIGHT

    # -------------------------
    # PROFILE ELIGIBILITY
    # -------------------------
    profile_eligible = bool(profile_result.get("eligible", True))
    profile_breakdown = profile_result.get("breakdown", {}) or {}

    profile_gate_detail = profile_breakdown.get("weighted_profile", {}) or {}
    profile_hard_gate_failures = profile_gate_detail.get("hard_gate_failures", []) or []

    profile_failure_labels = []

    for failure in profile_hard_gate_failures:
        category_name = failure.get("CategoryName") or "Profile"
        level_description = failure.get("LevelDescription") or failure.get("ProfileUID") or "criterion"
        operator = failure.get("Operator") or "INCLUDE"

        if operator == "EXCLUDE":
            profile_failure_labels.append(f"{category_name}: must not match {level_description}")
        else:
            profile_failure_labels.append(f"{category_name}: must match {level_description}")

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
    #
    # External survey fit only affects ranking when scoring config + user answers
    # are provided in context/user data. Otherwise it contributes 0.
    final_score = (quality_score * soft_multiplier) + profile_scaled + external_scaled

    hard_gate_results = dict(user.get("hard_gate_results", {}) or {})

    hard_gate_results["profile"] = {
        "passed": profile_eligible,
        "failures": profile_failure_labels,
    }

    base_eligible = bool(user.get("eligible", True))
    final_eligible = base_eligible and profile_eligible

    exclusion_reason = user.get("exclusion_reason")

    if base_eligible and not profile_eligible:
        if profile_failure_labels:
            exclusion_reason = "Profile hard gate: " + "; ".join(profile_failure_labels)
        else:
            exclusion_reason = "Profile hard gate"

    return {
        "user_id": user.get("user_id"),
        "display_name": user.get("display_name"),

        "motivation": user.get("motivation") or "",

        "eligible": final_eligible,
        "exclusion_reason": exclusion_reason,

        "hard_gate_results": hard_gate_results,

        "quality_score": quality_score,
        "profile_score_raw": profile_raw,
        "profile_score_scaled": profile_scaled,
        "external_score_raw": external_raw,
        "external_score_scaled": external_scaled,

        "soft_multiplier": soft_multiplier,

        "final_score": final_score,

        "breakdown": {
            "quality": quality_result["breakdown"],
            "profile": profile_result.get("breakdown", {}),
            "external": external_result.get("breakdown", {}),
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

def _score_external_survey_fit(user: dict, context: dict) -> dict:
    """
    Score round-local external recruiting survey fit.

    Expected context shape:
        {
            "external_scoring": {
                "questions": [
                    {
                        "question_id": "Q_...",
                        "question_text": "...",
                        "weight": 1.0,
                        "answers": [
                            {"value": "Answer A", "score": 100},
                            {"value": "Answer B", "score": 50},
                        ]
                    }
                ]
            }
        }

    Expected user shape:
        {
            "external_survey_answers": {
                "Q_...": ["Answer A", "Answer B"]
            }
        }

    Scoring rules:
    - Questions with weight <= 0 are ignored.
    - Questions with no positive configured answer score are ignored.
    - For multi-select answers, use the highest matching answer score for now.
      This avoids inflated scores from users selecting many options.
    - Returns a normalized 0.0–1.0 fit score.
    """

    external_context = (context or {}).get("external_scoring") or {}
    questions = external_context.get("questions") or []
    user_answers = user.get("external_survey_answers") or {}

    if not questions or not user_answers:
        return {
            "score": 0.0,
            "breakdown": {
                "available": bool(questions),
                "answered": bool(user_answers),
                "fit_percent": 0.0,
                "questions": [],
            }
        }

    earned_weighted_score = 0.0
    max_weighted_score = 0.0
    question_breakdown = []

    for question in questions:
        question_id = str(question.get("question_id") or "").strip()
        question_text = question.get("question_text") or ""

        try:
            question_weight = float(question.get("weight") or 0.0)
        except (TypeError, ValueError):
            question_weight = 0.0

        if not question_id or question_weight <= 0:
            continue

        configured_answers = question.get("answers") or []

        score_by_answer = {}

        for answer in configured_answers:
            answer_value = answer.get("value")

            try:
                answer_score = float(answer.get("score") or 0.0)
            except (TypeError, ValueError):
                answer_score = 0.0

            normalized_answer = _normalize_external_answer_value(answer_value)

            if not normalized_answer:
                continue

            score_by_answer[normalized_answer] = max(
                score_by_answer.get(normalized_answer, 0.0),
                answer_score,
            )

        max_answer_score = max(score_by_answer.values(), default=0.0)

        # If the UT Lead has not configured any positive answer score,
        # do not let this question drag everyone down.
        if max_answer_score <= 0:
            continue

        raw_values = user_answers.get(question_id) or []

        if isinstance(raw_values, str):
            raw_values = [raw_values]

        normalized_user_answers = [
            _normalize_external_answer_value(value)
            for value in raw_values
            if _normalize_external_answer_value(value)
        ]

        matched_scores = [
            score_by_answer.get(value, 0.0)
            for value in normalized_user_answers
        ]

        earned_answer_score = max(matched_scores, default=0.0)

        earned = earned_answer_score * question_weight
        possible = max_answer_score * question_weight

        earned_weighted_score += earned
        max_weighted_score += possible

        question_breakdown.append({
            "question_id": question_id,
            "question_text": question_text,
            "weight": question_weight,
            "user_answers": raw_values,
            "earned_score": earned_answer_score,
            "max_score": max_answer_score,
            "contribution": earned,
            "possible": possible,
            "matched": earned_answer_score > 0,
        })

    if max_weighted_score <= 0:
        fit_score = 0.0
    else:
        fit_score = earned_weighted_score / max_weighted_score

    fit_score = max(0.0, min(fit_score, 1.0))

    return {
        "score": fit_score,
        "breakdown": {
            "available": bool(questions),
            "answered": bool(user_answers),
            "fit_percent": fit_score * 100,
            "earned": earned_weighted_score,
            "possible": max_weighted_score,
            "questions": question_breakdown,
        }
    }


def _normalize_external_answer_value(value) -> str:
    return str(value or "").strip().casefold()


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