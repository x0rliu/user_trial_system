# app/services/bonus_survey_report_builder.py

from app.services.bonus_survey_overall_builder import build_overall_summary
from app.services.bonus_survey_insights_ai import generate_segment_insights
from app.services.bonus_survey_segment_comparator import compare_segments


def build_bonus_survey_report(payload: dict):
    """
    Build full report output.

    Combines:
    - Overall summary
    - Segment insights
    - Comparisons
    """

    # -------------------------
    # Overall
    # -------------------------
    overall = build_overall_summary(payload)

    # -------------------------
    # Segment insights
    # -------------------------
    segment_result = generate_segment_insights(payload)

    segments = []
    if segment_result.get("success"):
        segments = segment_result.get("segments", [])

    # -------------------------
    # Comparisons
    # -------------------------
    comparison_result = compare_segments(payload)

    comparisons = []
    if comparison_result.get("success"):
        comparisons = comparison_result.get("comparisons", [])

    # -------------------------
    # Build report structure
    # -------------------------
    report = {
        "overall": overall,
        "segments": segments[:5],  # keep it readable
        "comparisons": comparisons[:5],
    }

    return {
        "success": True,
        "report": report
    }