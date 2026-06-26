"""
Weighted profile selection helpers.

This module is intentionally pure:
- no DB reads
- no DB writes
- no request/session access
- no HTML rendering

It normalizes round profile criteria into an explicit selection model.
"""


MATCH_MODE_WEIGHTED = "WEIGHTED"
MATCH_MODE_HARD_GATE = "HARD_GATE"

OPERATOR_INCLUDE = "INCLUDE"
OPERATOR_EXCLUDE = "EXCLUDE"


def _as_int(value, default=1):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    if parsed < 1:
        return default

    return parsed


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalized_match_mode(value):
    value = str(value or "").strip().upper()

    if value == MATCH_MODE_HARD_GATE:
        return MATCH_MODE_HARD_GATE

    return MATCH_MODE_WEIGHTED


def _normalized_operator(value):
    value = str(value or "").strip().upper()

    if value == OPERATOR_EXCLUDE:
        return OPERATOR_EXCLUDE

    return OPERATOR_INCLUDE


def _is_active(row):
    value = row.get("IsActive", 1)

    if value in (1, "1", True, "true", "TRUE", "yes", "YES"):
        return True

    return False


def calculate_weighted_profile_percent(criteria_rows):
    """
    Return normalized weights for active weighted criteria.

    Priority logic:
    - PriorityRank 1 is most important.
    - Equal ranks are treated as ties.
    - Weights are calculated using priority points.

    Example:
      ranks 1, 2, 3, 3

      points:
        rank 1 = 4
        rank 2 = 2
        rank 3 = 1
        rank 3 = 1

      weights:
        50.0, 25.0, 12.5, 12.5
    """

    weighted_rows = []

    for row in criteria_rows or []:
        if not _is_active(row):
            continue

        if _normalized_match_mode(row.get("MatchMode")) != MATCH_MODE_WEIGHTED:
            continue

        normalized_row = dict(row)
        normalized_row["MatchMode"] = MATCH_MODE_WEIGHTED
        normalized_row["Operator"] = _normalized_operator(row.get("Operator"))
        normalized_row["PriorityRank"] = _as_int(row.get("PriorityRank"), 1)
        weighted_rows.append(normalized_row)

    if not weighted_rows:
        return []

    max_priority = max(row["PriorityRank"] for row in weighted_rows)

    total_points = 0
    weighted_with_points = []

    for row in weighted_rows:
        points = 2 ** (max_priority - row["PriorityRank"])
        total_points += points

        row_with_points = dict(row)
        row_with_points["_PriorityPoints"] = points
        weighted_with_points.append(row_with_points)

    if total_points <= 0:
        equal_weight = round(100.0 / len(weighted_with_points), 3)

        for row in weighted_with_points:
            row["WeightPercent"] = equal_weight

        return weighted_with_points

    normalized_rows = []

    for row in weighted_with_points:
        weight_percent = round((row["_PriorityPoints"] / total_points) * 100.0, 3)

        normalized_row = dict(row)
        normalized_row["WeightPercent"] = weight_percent
        normalized_rows.append(normalized_row)

    return normalized_rows


def normalize_selection_criteria(criteria_rows):
    """
    Return active criteria with explicit MatchMode, Operator, PriorityRank,
    and WeightPercent values.

    HARD_GATE rows are returned with WeightPercent = 0.0.
    WEIGHTED rows receive calculated WeightPercent values.
    """

    active_rows = []

    for row in criteria_rows or []:
        if not _is_active(row):
            continue

        normalized_row = dict(row)
        normalized_row["MatchMode"] = _normalized_match_mode(row.get("MatchMode"))
        normalized_row["Operator"] = _normalized_operator(row.get("Operator"))
        normalized_row["PriorityRank"] = _as_int(row.get("PriorityRank"), 1)
        normalized_row["WeightPercent"] = _as_float(row.get("WeightPercent"), 0.0)
        active_rows.append(normalized_row)

    weighted_rows = calculate_weighted_profile_percent(active_rows)
    weighted_by_id = {}

    for row in weighted_rows:
        criteria_id = row.get("RoundCriteriaID")
        profile_uid = row.get("ProfileUID")
        weighted_by_id[(criteria_id, profile_uid)] = row

    normalized_rows = []

    for row in active_rows:
        if row["MatchMode"] == MATCH_MODE_HARD_GATE:
            hard_gate_row = dict(row)
            hard_gate_row["WeightPercent"] = 0.0
            normalized_rows.append(hard_gate_row)
            continue

        key = (row.get("RoundCriteriaID"), row.get("ProfileUID"))
        weighted_row = weighted_by_id.get(key)

        if weighted_row:
            normalized_rows.append(weighted_row)
        else:
            fallback_row = dict(row)
            fallback_row["WeightPercent"] = 0.0
            normalized_rows.append(fallback_row)

    normalized_rows.sort(
        key=lambda row: (
            0 if row.get("MatchMode") == MATCH_MODE_HARD_GATE else 1,
            _as_int(row.get("PriorityRank"), 1),
            str(row.get("CategoryName") or ""),
            str(row.get("LevelDescription") or ""),
        )
    )

    return normalized_rows


def build_trial_profile_from_criteria(criteria_rows):
    """
    Build a CategoryID-keyed trial profile map from criteria rows.

    This preserves the existing profile scoring shape while allowing later
    scoring code to inspect weighted criteria separately.

    Output shape:
      {
        CategoryID: {
          "include": set(ProfileUID),
          "exclude": set(ProfileUID),
        }
      }
    """

    trial_profile = {}

    for row in criteria_rows or []:
        if not _is_active(row):
            continue

        category_id = row.get("CategoryID")

        if category_id is None:
            continue

        profile_uid = row.get("ProfileUID")

        if not profile_uid:
            continue

        operator = _normalized_operator(row.get("Operator"))

        if category_id not in trial_profile:
            trial_profile[category_id] = {
                "include": set(),
                "exclude": set(),
            }

        if operator == OPERATOR_EXCLUDE:
            trial_profile[category_id]["exclude"].add(profile_uid)
        else:
            trial_profile[category_id]["include"].add(profile_uid)

    return trial_profile


def score_user_against_weighted_criteria(user_profile_uids, criteria_rows):
    """
    Calculate explainable weighted profile fit for one user.

    Returns:
      {
        "fit_percent": 87.5,
        "hard_gate_passed": True,
        "hard_gate_failures": [],
        "breakdown": [...]
      }

    Matching rules:
    - INCLUDE matches when the user has ProfileUID.
    - EXCLUDE matches when the user does not have ProfileUID.
    - HARD_GATE failure makes hard_gate_passed False.
    - WEIGHTED rows contribute WeightPercent only when matched.
    """

    user_profile_uids = set(user_profile_uids or [])
    normalized_criteria = normalize_selection_criteria(criteria_rows)

    fit_percent = 0.0
    hard_gate_failures = []
    breakdown = []

    for row in normalized_criteria:
        profile_uid = row.get("ProfileUID")
        operator = _normalized_operator(row.get("Operator"))
        match_mode = _normalized_match_mode(row.get("MatchMode"))
        weight_percent = _as_float(row.get("WeightPercent"), 0.0)

        if operator == OPERATOR_EXCLUDE:
            matched = profile_uid not in user_profile_uids
        else:
            matched = profile_uid in user_profile_uids

        contribution = 0.0

        if match_mode == MATCH_MODE_WEIGHTED and matched:
            contribution = weight_percent
            fit_percent += contribution

        if match_mode == MATCH_MODE_HARD_GATE and not matched:
            hard_gate_failures.append(row)

        breakdown.append({
            "RoundCriteriaID": row.get("RoundCriteriaID"),
            "ProfileUID": profile_uid,
            "CategoryID": row.get("CategoryID"),
            "CategoryName": row.get("CategoryName"),
            "LevelDescription": row.get("LevelDescription"),
            "ProfileCode": row.get("ProfileCode"),
            "Operator": operator,
            "MatchMode": match_mode,
            "PriorityRank": _as_int(row.get("PriorityRank"), 1),
            "WeightPercent": weight_percent,
            "Matched": matched,
            "ContributionPercent": round(contribution, 3),
        })

    return {
        "fit_percent": round(fit_percent, 3),
        "hard_gate_passed": len(hard_gate_failures) == 0,
        "hard_gate_failures": hard_gate_failures,
        "breakdown": breakdown,
    }