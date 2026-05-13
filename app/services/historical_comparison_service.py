# app/services/historical_comparison_service.py

from app.db.historical_comparison import (
    get_historical_context_for_comparison,
    get_historical_metrics_for_contexts,
    get_latest_historical_insights_for_contexts,
    list_historical_context_candidates,
)


_NUMERIC_METRIC_FIELDS = [
    "total_responses",
    "survey_1_responses",
    "survey_2_responses",
    "completion_rate",
    "drop_off_rate",
    "response_window_days",
    "avg_response_length",
    "median_response_length",
    "empty_response_rate",
    "quant_question_count",
    "qual_question_count",
]


def _clean_text(value) -> str:
    return str(value or "").strip()


def _same_text(left, right) -> bool:
    return _clean_text(left).lower() == _clean_text(right).lower() and bool(_clean_text(left))


def _metric_number(value):
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_candidate(target: dict, candidate: dict) -> dict:
    score = 0
    match_reasons = []

    if _same_text(target.get("product_type_key"), candidate.get("product_type_key")):
        score += 100
        match_reasons.append("Same product type")

    if _same_text(target.get("business_group"), candidate.get("business_group")):
        score += 40
        match_reasons.append("Same business group")

    if _same_text(target.get("lifecycle_stage"), candidate.get("lifecycle_stage")):
        score += 20
        match_reasons.append("Same lifecycle stage")

    if _same_text(target.get("trial_purpose"), candidate.get("trial_purpose")):
        score += 20
        match_reasons.append("Same trial purpose")

    if target.get("round_number") and target.get("round_number") == candidate.get("round_number"):
        score += 5
        match_reasons.append("Same round number")

    if candidate.get("dataset_count", 0) <= 0:
        score -= 20
        match_reasons.append("No uploaded historical datasets detected")

    if score >= 100:
        match_strength = "strong"
    elif score >= 60:
        match_strength = "medium"
    elif score > 0:
        match_strength = "weak"
    else:
        match_strength = "none"

    return {
        "score": score,
        "match_strength": match_strength,
        "match_reasons": match_reasons,
    }


def _comparison_tier(matched_contexts: list[dict]) -> dict:
    if not matched_contexts:
        return {
            "tier": "none",
            "reason": "No comparable historical contexts were found.",
            "match_count": 0,
        }

    if any("Same product type" in item.get("match_reasons", []) for item in matched_contexts):
        return {
            "tier": "product_type",
            "reason": "At least one comparable context shares the same explicit product_type_key.",
            "match_count": len(matched_contexts),
        }

    if any("Same business group" in item.get("match_reasons", []) for item in matched_contexts):
        return {
            "tier": "business_group",
            "reason": "Comparable contexts share business_group, but not product_type_key.",
            "match_count": len(matched_contexts),
        }

    if any(
        "Same lifecycle stage" in item.get("match_reasons", [])
        or "Same trial purpose" in item.get("match_reasons", [])
        for item in matched_contexts
    ):
        return {
            "tier": "lifecycle",
            "reason": "Comparable contexts share lifecycle or trial purpose only.",
            "match_count": len(matched_contexts),
        }

    return {
        "tier": "broad",
        "reason": "Only broad historical context is available.",
        "match_count": len(matched_contexts),
    }


def _average_metrics(metrics_by_context: dict[int, dict], context_ids: list[int]) -> dict:
    baseline = {}

    for field in _NUMERIC_METRIC_FIELDS:
        values = []

        for context_id in context_ids:
            metric_row = metrics_by_context.get(context_id) or {}
            value = _metric_number(metric_row.get(field))

            if value is not None:
                values.append(value)

        if values:
            baseline[field] = round(sum(values) / len(values), 2)
        else:
            baseline[field] = None

    return baseline


def _metric_deltas(target_metrics: dict, baseline_metrics: dict) -> dict:
    deltas = {}

    for field in _NUMERIC_METRIC_FIELDS:
        target_value = _metric_number((target_metrics or {}).get(field))
        baseline_value = _metric_number((baseline_metrics or {}).get(field))

        if target_value is None or baseline_value is None:
            deltas[field] = None
        else:
            deltas[field] = round(target_value - baseline_value, 2)

    return deltas


def _normalize_pattern_key(value) -> str:
    return " ".join(_clean_text(value).lower().split())


def _build_repeated_patterns(
    *,
    matched_contexts: list[dict],
    insights_by_context: dict[int, list[dict]],
) -> list[dict]:
    pattern_map = {}

    matched_context_by_id = {
        item["context_id"]: item
        for item in matched_contexts
    }

    for context_id, insight_rows in insights_by_context.items():
        for row in insight_rows:
            insight_type = row.get("insight_type")

            if insight_type in {"summary", "ai_summary"}:
                continue

            summary = _clean_text(row.get("insight_summary"))
            pattern_key = _normalize_pattern_key(summary)

            if not pattern_key:
                continue

            if pattern_key not in pattern_map:
                pattern_map[pattern_key] = {
                    "pattern": summary,
                    "source_context_ids": set(),
                    "supporting_contexts": [],
                    "insight_types": set(),
                }

            pattern_map[pattern_key]["source_context_ids"].add(context_id)
            pattern_map[pattern_key]["insight_types"].add(insight_type)

            context = matched_context_by_id.get(context_id)
            if context:
                context_label = {
                    "context_id": context_id,
                    "product_name": context.get("product_name"),
                    "match_strength": context.get("match_strength"),
                }

                if context_label not in pattern_map[pattern_key]["supporting_contexts"]:
                    pattern_map[pattern_key]["supporting_contexts"].append(context_label)

    patterns = []

    for item in pattern_map.values():
        source_context_count = len(item["source_context_ids"])

        if source_context_count >= 3:
            confidence = "high"
        elif source_context_count == 2:
            confidence = "medium"
        else:
            confidence = "low"

        patterns.append({
            "pattern": item["pattern"],
            "source_context_count": source_context_count,
            "supporting_contexts": item["supporting_contexts"],
            "insight_types": sorted(item["insight_types"]),
            "confidence": confidence,
        })

    return sorted(
        patterns,
        key=lambda row: (
            row["source_context_count"],
            row["confidence"],
            row["pattern"],
        ),
        reverse=True,
    )[:10]


def build_historical_pattern_comparison(context_id: int, max_matches: int = 10) -> dict:
    """
    Build a read-only historical comparison packet.

    No AI.
    No recommendations.
    No DB mutation.
    No HTML.
    """

    limitations = []

    target_context = get_historical_context_for_comparison(context_id)

    if not target_context:
        return {
            "target_context": None,
            "comparison_basis": {
                "tier": "none",
                "reason": "Target historical context was not found.",
                "match_count": 0,
            },
            "matched_contexts": [],
            "metric_comparison": {
                "target": {},
                "baseline": {},
                "deltas": {},
            },
            "repeated_patterns": [],
            "limitations": ["Target historical context was not found."],
        }

    if not target_context.get("is_taxonomy_ready"):
        limitations.append(
            "Target product is missing product taxonomy fields, so strong product-type comparison may not be available."
        )

    candidates = list_historical_context_candidates(exclude_context_id=context_id)

    scored_candidates = []

    for candidate in candidates:
        score_info = _score_candidate(target_context, candidate)

        if score_info["match_strength"] == "none":
            continue

        scored = {
            **candidate,
            "match_score": score_info["score"],
            "match_strength": score_info["match_strength"],
            "match_reasons": score_info["match_reasons"],
        }
        scored_candidates.append(scored)

    scored_candidates.sort(
        key=lambda item: (
            item["match_score"],
            item.get("dataset_count") or 0,
            item.get("context_id") or 0,
        ),
        reverse=True,
    )

    matched_contexts = scored_candidates[:max_matches]

    if not matched_contexts:
        limitations.append("No comparable historical contexts were found using explicit DB-backed fields.")

    matched_context_ids = [
        item["context_id"]
        for item in matched_contexts
        if item.get("context_id")
    ]

    all_metric_context_ids = [context_id] + matched_context_ids
    metrics_by_context = get_historical_metrics_for_contexts(all_metric_context_ids)

    target_metrics = metrics_by_context.get(context_id) or {}
    baseline_metrics = _average_metrics(metrics_by_context, matched_context_ids)
    deltas = _metric_deltas(target_metrics, baseline_metrics)

    insights_by_context = get_latest_historical_insights_for_contexts(matched_context_ids)
    repeated_patterns = _build_repeated_patterns(
        matched_contexts=matched_contexts,
        insights_by_context=insights_by_context,
    )

    if not target_metrics:
        limitations.append("Target context has no historical metrics row yet.")

    if matched_contexts and not any(metrics_by_context.get(cid) for cid in matched_context_ids):
        limitations.append("Matched contexts have no historical metrics rows available for baseline comparison.")

    if matched_contexts and not repeated_patterns:
        limitations.append("No repeated insight patterns were found in the latest insight runs for matched contexts.")

    return {
        "target_context": target_context,
        "comparison_basis": _comparison_tier(matched_contexts),
        "matched_contexts": matched_contexts,
        "metric_comparison": {
            "target": target_metrics,
            "baseline": baseline_metrics,
            "deltas": deltas,
        },
        "repeated_patterns": repeated_patterns,
        "limitations": limitations,
    }