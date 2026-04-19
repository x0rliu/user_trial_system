# app/services/bonus_survey_report_builder.py

from app.services.bonus_survey_overall_builder import build_overall_summary
from app.services.bonus_survey_insights_ai import generate_segment_insights
from app.services.bonus_survey_segment_comparator import compare_segments
from app.services.bonus_survey_section_scores import build_bonus_survey_section_scores
from app.services.bonus_survey_section_summaries import generate_bonus_survey_section_summaries
from app.services.bonus_survey_section_insights import generate_bonus_survey_section_insights


def build_bonus_survey_report(payload: dict):
    """
    Build full report output.

    Combines:
    - Overall summary
    - Section scores (quant)
    - Section summaries (qual, lightweight)
    - Segment insights (deep qual)
    - Comparisons
    """

    # -------------------------
    # Overall
    # -------------------------
    overall = build_overall_summary(payload)

    # -------------------------
    # Section Scores (quant)
    # -------------------------
    section_score_result = build_bonus_survey_section_scores(payload)

    section_scores = {}
    if section_score_result.get("success"):
        for s in section_score_result.get("sections", []):
            section_scores[s["section_key"]] = s["metrics"]

    # -------------------------
    # Section Summaries (qual - lightweight)
    # -------------------------
    section_summary_result = generate_bonus_survey_section_summaries(payload)

    section_summaries = {}
    if section_summary_result.get("success"):
        for s in section_summary_result.get("sections", []):
            section_summaries[s["section_key"]] = s.get("summary")

    # -------------------------
    # Section Insights (deep AI)
    # -------------------------
    section_insight_result = generate_bonus_survey_section_insights(payload)

    section_insights = {}
    if section_insight_result.get("success"):
        for s in section_insight_result.get("sections", []):
            section_insights[s["section_key"]] = s.get("insights")

    # -------------------------
    # Merge Sections (single structure)
    # -------------------------
    merged_sections = []

    all_section_keys = set(section_scores.keys()) | set(section_summaries.keys())

    for key in all_section_keys:
        metrics = section_scores.get(key, {})

        print("[DEBUG] SECTION METRICS:", key, metrics)

        merged_sections.append({
            "section_key": key,
            "metrics": metrics,
            "summary": section_summaries.get(key),
            "insights": section_insights.get(key),
        })

    # -------------------------
    # Enforce segmentation mode (BONUS surveys)
    # -------------------------
    payload["segmentation_mode"] = "survey"

    # -------------------------
    # Segment insights (deep AI)
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
    # Build final report
    # -------------------------
    report = {
        "overall": overall,
        "sections": merged_sections,
        "comparisons": comparisons[:5],
    }

    return {
        "success": True,
        "report": report
    }