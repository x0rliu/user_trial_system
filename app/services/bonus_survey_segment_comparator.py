# app/services/bonus_survey_segment_comparator.py

from collections import Counter

from app.services.bonus_survey_segment_builder import (
    build_segment_views,
    _build_user_segment_tags
)
from app.services.bonus_survey_signal_extractor import extract_signals_from_responses


MIN_USERS = 3
TOP_N_SIGNALS = 10
MIN_DIFF_THRESHOLD = 0.30  # 30% difference


def _collect_segment_responses(payload: dict, segment_key: str):
    """
    Rebuild responses for a given segment.
    """

    results = []

    for r in payload.get("responses", []):
        tags = _build_user_segment_tags(r)

        if segment_key in tags:
            results.append(r)

    return results


def _extract_signals_for_segment(responses: list):
    """
    Extract signals using existing signal extractor.
    """

    grouped = []

    for r in responses:
        answers = [
            a["answer_text"]
            for a in r.get("answers", [])
            if a.get("answer_text")
        ]

        if answers:
            grouped.append(answers)

    if not grouped:
        return []

    grouped = grouped[:100]

    result = extract_signals_from_responses(grouped)

    if not result.get("success"):
        return []

    signals = result.get("signals", [])

    return signals


def _normalize_counter(counter: Counter, total: int):
    """
    Convert counts to percentages.
    """

    if total == 0:
        return {}

    return {
        k: v / total
        for k, v in counter.items()
    }


def compare_segments(payload: dict):
    """
    Compare segments and return meaningful differences.
    """

    segments = build_segment_views(payload)

    # -------------------------
    # Filter segments
    # -------------------------
    segments = [
        s for s in segments
        if s.get("user_count", 0) >= MIN_USERS
    ]

    # limit to avoid explosion
    segments = segments[:8]

    segment_signal_maps = {}

    # -------------------------
    # Build signal maps
    # -------------------------
    for seg in segments:
        key = seg["segment_key"]

        responses = _collect_segment_responses(payload, key)

        signals = _extract_signals_for_segment(responses)

        if not signals:
            continue

        counter = Counter(signals)

        normalized = _normalize_counter(counter, len(signals))

        segment_signal_maps[key] = {
            "user_count": seg["user_count"],
            "signal_counts": counter,
            "signal_pct": normalized
        }

    # -------------------------
    # Compare segments
    # -------------------------
    comparisons = []

    keys = list(segment_signal_maps.keys())

    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a = keys[i]
            b = keys[j]

            map_a = segment_signal_maps[a]["signal_pct"]
            map_b = segment_signal_maps[b]["signal_pct"]

            all_signals = set(map_a.keys()) | set(map_b.keys())

            for sig in all_signals:
                a_val = map_a.get(sig, 0)
                b_val = map_b.get(sig, 0)

                diff = a_val - b_val

                if abs(diff) < MIN_DIFF_THRESHOLD:
                    continue

                comparisons.append({
                    "signal": sig,
                    "segment_a": a,
                    "segment_b": b,
                    "a_pct": round(a_val, 3),
                    "b_pct": round(b_val, 3),
                    "difference": round(diff, 3)
                })

    # -------------------------
    # Sort strongest differences
    # -------------------------
    comparisons = sorted(
        comparisons,
        key=lambda x: abs(x["difference"]),
        reverse=True
    )

    return {
        "success": True,
        "comparisons": comparisons[:20]  # top differences only
    }