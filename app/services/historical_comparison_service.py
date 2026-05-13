# app/services/historical_comparison_service.py

import json

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


def _safe_max_matches(max_matches) -> int:
    try:
        value = int(max_matches)
    except (TypeError, ValueError):
        value = 10

    if value < 1:
        return 1

    if value > 25:
        return 25

    return value


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
        "reason": "Only broad historical baseline context is available.",
        "match_count": len(matched_contexts),
    }


def _select_broad_baseline_candidates(candidates: list[dict], max_matches: int) -> list[dict]:
    """
    Select broad historical baseline candidates only when no closer matches exist.

    This keeps broad baseline clearly weaker than product-type/business-group/lifecycle matches.
    """

    broad_candidates = []

    for candidate in candidates:
        if candidate.get("dataset_count", 0) <= 0:
            continue

        broad_candidates.append({
            **candidate,
            "match_score": 1,
            "match_strength": "weak",
            "match_reasons": ["Broad historical baseline"],
        })

    broad_candidates.sort(
        key=lambda item: (
            item.get("dataset_count") or 0,
            item.get("context_id") or 0,
        ),
        reverse=True,
    )

    return broad_candidates[:max_matches]


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


def _count_present_metric_values(metrics: dict) -> int:
    return len([
        value
        for value in (metrics or {}).values()
        if value is not None
    ])


def _build_data_quality_packet(
    *,
    target_metrics: dict,
    baseline_metrics: dict,
    matched_contexts: list[dict],
    matched_context_ids: list[int],
    metrics_by_context: dict[int, dict],
    insights_by_context: dict[int, list[dict]],
    repeated_patterns: list[dict],
    limitations: list[str],
) -> dict:
    matched_context_count = len(matched_contexts)

    matched_contexts_with_metrics = len([
        context_id
        for context_id in matched_context_ids
        if metrics_by_context.get(context_id)
    ])

    matched_contexts_with_insights = len([
        context_id
        for context_id in matched_context_ids
        if insights_by_context.get(context_id)
    ])

    target_metric_count = _count_present_metric_values(target_metrics)
    baseline_metric_count = _count_present_metric_values(baseline_metrics)
    repeated_pattern_count = len(repeated_patterns)
    limitation_count = len(limitations)

    coverage_note = "Comparison data is available."

    if matched_context_count <= 0:
        coverage_note = "No matched historical contexts are available yet."
    elif matched_contexts_with_metrics <= 0 and matched_contexts_with_insights <= 0:
        coverage_note = "Matched contexts exist, but saved metrics and saved insights are sparse."
    elif baseline_metric_count <= 0 and repeated_pattern_count <= 0:
        coverage_note = "Matched contexts exist, but baseline metrics and repeated patterns are sparse."
    elif baseline_metric_count <= 0:
        coverage_note = "Matched contexts exist, but baseline metrics are sparse."
    elif repeated_pattern_count <= 0:
        coverage_note = "Matched contexts exist, but repeated saved insight patterns are sparse."

    return {
        "target_metric_count": target_metric_count,
        "baseline_metric_count": baseline_metric_count,
        "matched_context_count": matched_context_count,
        "matched_contexts_with_metrics": matched_contexts_with_metrics,
        "matched_contexts_with_insights": matched_contexts_with_insights,
        "repeated_pattern_count": repeated_pattern_count,
        "limitation_count": limitation_count,
        "coverage_note": coverage_note,
    }


def _normalize_pattern_key(value) -> str:
    return " ".join(_clean_text(value).lower().split())


def _safe_insight_json(row: dict) -> dict:
    raw = row.get("insight_json")

    if not raw:
        return {}

    if isinstance(raw, dict):
        return raw

    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _pattern_labels_from_insight(row: dict) -> list[str]:
    """
    Extract conservative labels from persisted insight fields.

    This does not infer new product conclusions. It only reuses labels already
    stored in historical_trial_insights / insight_json.
    """

    labels = []
    summary = _clean_text(row.get("insight_summary"))

    if summary:
        labels.append(summary)

    payload = _safe_insight_json(row)

    title = _clean_text(payload.get("title"))
    if title:
        labels.append(title)

    pattern_type = _clean_text(payload.get("type"))
    if pattern_type and pattern_type not in labels:
        labels.append(pattern_type)

    # Deterministic pattern clusters often store useful phrase labels.
    phrases = payload.get("phrases")
    if isinstance(phrases, list):
        for phrase in phrases[:3]:
            phrase_text = _clean_text(phrase)
            if phrase_text:
                labels.append(phrase_text)

    # Preserve order while deduping normalized equivalents.
    deduped = []
    seen = set()

    for label in labels:
        key = _normalize_pattern_key(label)
        if not key or key in seen:
            continue

        seen.add(key)
        deduped.append(label)

    return deduped


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

            pattern_labels = _pattern_labels_from_insight(row)

            for pattern_label in pattern_labels:
                pattern_key = _normalize_pattern_key(pattern_label)

                if not pattern_key:
                    continue

                if pattern_key not in pattern_map:
                    pattern_map[pattern_key] = {
                        "pattern": pattern_label,
                        "source_context_ids": set(),
                        "supporting_contexts": [],
                        "insight_types": set(),
                    }

                pattern_map[pattern_key]["source_context_ids"].add(context_id)

                if insight_type:
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

    confidence_rank = {
        "high": 3,
        "medium": 2,
        "low": 1,
    }

    return sorted(
        patterns,
        key=lambda row: (
            row["source_context_count"],
            confidence_rank.get(row["confidence"], 0),
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
    max_matches = _safe_max_matches(max_matches)

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
            "data_quality": {
                "target_metric_count": 0,
                "baseline_metric_count": 0,
                "matched_context_count": 0,
                "matched_contexts_with_metrics": 0,
                "matched_contexts_with_insights": 0,
                "repeated_pattern_count": 0,
                "limitation_count": 1,
                "coverage_note": "Target historical context was not found.",
            },
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
        matched_contexts = _select_broad_baseline_candidates(
            candidates,
            max_matches,
        )

        if matched_contexts:
            limitations.append(
                "No close product-type, business-group, lifecycle, or purpose matches were found. Using broad historical baseline only."
            )
        else:
            limitations.append(
                "No comparable historical contexts were found using explicit DB-backed fields."
            )

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
        limitations.append(
            "No repeated insight patterns were found in the latest insight runs for matched contexts."
        )

    comparison_basis = _comparison_tier(matched_contexts)

    if matched_contexts and comparison_basis.get("tier") == "broad":
        limitations.append(
            "Broad baseline comparisons are useful for context only and should not be treated as close product matches."
        )

    data_quality = _build_data_quality_packet(
        target_metrics=target_metrics,
        baseline_metrics=baseline_metrics,
        matched_contexts=matched_contexts,
        matched_context_ids=matched_context_ids,
        metrics_by_context=metrics_by_context,
        insights_by_context=insights_by_context,
        repeated_patterns=repeated_patterns,
        limitations=limitations,
    )

    return {
        "target_context": target_context,
        "comparison_basis": comparison_basis,
        "matched_contexts": matched_contexts,
        "metric_comparison": {
            "target": target_metrics,
            "baseline": baseline_metrics,
            "deltas": deltas,
        },
        "repeated_patterns": repeated_patterns,
        "data_quality": data_quality,
        "limitations": limitations,
    }