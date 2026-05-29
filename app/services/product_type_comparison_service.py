# app/services/product_type_comparison_service.py

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from decimal import Decimal

from app.db.product_type_comparison_reports import (
    ProductTypeComparisonReportsTableMissing,
    list_published_report_objects_for_product_type,
    upsert_product_type_comparison_report,
)
from app.services.ai_service import call_ai

GENERATION_VERSION = "product_type_comparison_headset_v1"

SUPPORTED_PRODUCT_TYPE_COMPARISONS = {
    "headset": {
        "product_type_key": "headset",
        "product_type_display": "Headset",
        "minimum_reports": 2,
        "generator": "generate_headset_product_type_comparison",
    },
}

HEADSET_EVALUATION_CRITERIA = [
    "audio quality",
    "microphone quality and call confidence",
    "comfort over time",
    "fit and adjustability",
    "connection reliability",
    "wireless range and device switching",
    "mute/status/control confidence",
    "battery life and charging reliability",
    "setup/OOBE clarity",
    "software/app/firmware friction",
    "build quality and durability",
    "price/value expectation",
    "work/gaming/media use-case fit",
]


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _clip_text(value: object, *, limit: int = 240) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _safe_error_key(value: object) -> str:
    text = _clean_text(value).lower()
    if not text:
        return "unknown"
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:80] or "unknown"


def _json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _loads_json(value: object, fallback):
    try:
        parsed = json.loads(value or "")
        return parsed if parsed is not None else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def _extract_json_object(text: str) -> dict | None:
    clean = str(text or "").strip()
    if not clean:
        return None

    if clean.startswith("```"):
        clean = clean.strip("`").strip()
        if clean.lower().startswith("json"):
            clean = clean[4:].strip()

    try:
        parsed = json.loads(clean)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = clean.find("{")
    end = clean.rfind("}")
    if start < 0 or end <= start:
        return None

    try:
        parsed = json.loads(clean[start:end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _call_json_ai(*, prompt: str, system_prompt: str, max_tokens: int = 4500) -> dict:
    ai_result = call_ai(
        prompt=prompt,
        system_prompt=system_prompt,
        model="gpt-4o",
        temperature=0.2,
        max_tokens=max_tokens,
    )

    if not ai_result.get("success"):
        return {
            "success": False,
            "error": f"ai_failed__{_safe_error_key(ai_result.get('error'))}",
            "data": None,
        }

    raw_response = (
        ai_result.get("content")
        or ai_result.get("response")
        or ""
    ).strip()

    parsed = _extract_json_object(raw_response)
    if isinstance(parsed, dict):
        return {
            "success": True,
            "error": None,
            "data": parsed,
        }

    retry_prompt = prompt + """

The previous response did not parse as valid JSON.
Retry now. Return ONLY one valid JSON object. Do not include markdown, comments, explanation, or trailing text.
"""
    retry_result = call_ai(
        prompt=retry_prompt,
        system_prompt=system_prompt,
        model="gpt-4o",
        temperature=0,
        max_tokens=max_tokens,
    )

    if not retry_result.get("success"):
        return {
            "success": False,
            "error": f"ai_retry_failed__{_safe_error_key(retry_result.get('error'))}",
            "data": None,
        }

    raw_retry_response = (
        retry_result.get("content")
        or retry_result.get("response")
        or ""
    ).strip()

    parsed = _extract_json_object(raw_retry_response)
    if not isinstance(parsed, dict):
        return {
            "success": False,
            "error": "invalid_ai_response_json",
            "data": None,
        }

    return {
        "success": True,
        "error": None,
        "data": parsed,
    }


def _supported_config(product_type_display: str) -> dict | None:
    key = _clean_text(product_type_display).lower()
    return SUPPORTED_PRODUCT_TYPE_COMPARISONS.get(key)


def product_type_comparison_support_status(product_type_display: str, report_count: int) -> dict:
    """
    Small read helper for R&I row rendering.
    """

    config = _supported_config(product_type_display)
    if not config:
        return {
            "is_supported": False,
            "is_ready": False,
            "minimum_reports": None,
            "label": "Not configured yet",
            "reason": "No explicit comparison function exists for this product type yet.",
        }

    minimum_reports = int(config.get("minimum_reports") or 2)
    is_ready = int(report_count or 0) >= minimum_reports

    return {
        "is_supported": True,
        "is_ready": is_ready,
        "minimum_reports": minimum_reports,
        "label": "Ready for comparison" if is_ready else "Needs more reports",
        "reason": (
            "This product type has an explicit comparison function."
            if is_ready
            else f"At least {minimum_reports} published reports are required before generating a comparison."
        ),
    }


def generate_product_type_comparison(*, product_type_display: str, generated_by_user_id: str) -> dict:
    config = _supported_config(product_type_display)
    if not config:
        return {
            "success": False,
            "error": "unsupported_product_type",
            "report": None,
        }

    if config.get("generator") == "generate_headset_product_type_comparison":
        try:
            return generate_headset_product_type_comparison(
                generated_by_user_id=generated_by_user_id,
            )
        except ProductTypeComparisonReportsTableMissing:
            return {
                "success": False,
                "error": "table_missing",
                "report": None,
            }

    return {
        "success": False,
        "error": "unsupported_product_type",
        "report": None,
    }


def _report_label(row: dict, report: dict) -> str:
    product = report.get("product") if isinstance(report.get("product"), dict) else {}
    internal_name = _clean_text(product.get("internal_name") or row.get("internal_name"))
    market_name = _clean_text(product.get("market_name") or row.get("market_name"))
    round_number = row.get("round_number") or product.get("round_number")

    if internal_name and market_name:
        label = f"{internal_name} ({market_name})"
    elif internal_name:
        label = internal_name
    elif market_name:
        label = market_name
    else:
        label = "Unnamed headset report"

    if round_number not in (None, "", "-"):
        label = f"{label} · Round {round_number}"

    return label


def _is_first_impressions_source(source: dict) -> bool:
    text = " ".join([
        _clean_text(source.get("survey_name")),
        _clean_text(source.get("trial_purpose")),
        _clean_text(source.get("source_file_name")),
    ]).lower()

    first_markers = [
        "first impression",
        "first impressions",
        "oobe",
        "out of box",
        "unbox",
        "unboxing",
        "initial",
    ]
    return any(marker in text for marker in first_markers)


def _is_usage_source(source: dict) -> bool:
    text = " ".join([
        _clean_text(source.get("survey_name")),
        _clean_text(source.get("trial_purpose")),
        _clean_text(source.get("source_file_name")),
    ]).lower()

    usage_markers = [
        "usage",
        "experience",
        "kpi",
        "final",
        "follow-up",
        "long-term",
        "long term",
    ]
    return any(marker in text for marker in usage_markers)


def _classify_report_survey_ids(report: dict) -> tuple[set, set]:
    sources = report.get("source_surveys") or []
    if not isinstance(sources, list):
        sources = []

    first_ids = {
        source.get("dataset_id")
        for source in sources
        if isinstance(source, dict) and _is_first_impressions_source(source)
    }
    usage_ids = {
        source.get("dataset_id")
        for source in sources
        if isinstance(source, dict) and _is_usage_source(source)
    }

    if (not first_ids or not usage_ids) and len(sources) >= 2:
        sorted_sources = sorted(
            [source for source in sources if isinstance(source, dict)],
            key=lambda source: (
                str(source.get("survey_name") or ""),
                int(source.get("dataset_id") or 0),
            ),
        )
        if not first_ids and sorted_sources:
            first_ids.add(sorted_sources[0].get("dataset_id"))
        if not usage_ids and len(sorted_sources) > 1:
            usage_ids.update(source.get("dataset_id") for source in sorted_sources[1:])

    usage_ids = {dataset_id for dataset_id in usage_ids if dataset_id not in first_ids}
    return first_ids, usage_ids


def _summarize_quant_question(question: dict) -> dict:
    values = question.get("values") if isinstance(question.get("values"), list) else []
    option_counts = []

    if values:
        counts = Counter(_clean_text(value) for value in values if _clean_text(value))
        option_counts = [
            {"label": label, "count": count}
            for label, count in counts.most_common(8)
        ]

    return {
        "question": _clip_text(question.get("question"), limit=220),
        "type": _clean_text(question.get("type")),
        "average": _json_safe(question.get("average")),
        "response_count": len(values),
        "top_options": option_counts,
    }


def _summarize_qual_question(question: dict) -> dict:
    values = question.get("values") if isinstance(question.get("values"), list) else []
    cleaned_values = [_clip_text(value, limit=260) for value in values if _clean_text(value)]

    return {
        "question": _clip_text(question.get("question"), limit=220),
        "response_count": len(cleaned_values),
        "sample_comments": cleaned_values[:10],
    }


def _summarize_section(section: dict) -> dict:
    quant_questions = section.get("quant_questions") if isinstance(section.get("quant_questions"), list) else []
    qual_question = section.get("qual_question") if isinstance(section.get("qual_question"), dict) else {}
    swot = section.get("swot") if isinstance(section.get("swot"), dict) else {}

    return {
        "section_name": _clean_text(section.get("section_name")),
        "survey_name": _clean_text(section.get("survey_name")),
        "trial_purpose": _clean_text(section.get("trial_purpose")),
        "dataset_id": section.get("dataset_id"),
        "context_id": section.get("context_id"),
        "response_count": int(section.get("response_count") or 0),
        "quant_questions": [_summarize_quant_question(question) for question in quant_questions[:4] if isinstance(question, dict)],
        "qual_question": _summarize_qual_question(qual_question) if qual_question else {},
        "swot": {
            "strengths": [_clip_text(item, limit=220) for item in (swot.get("strengths") or [])[:5]],
            "weaknesses": [_clip_text(item, limit=220) for item in (swot.get("weaknesses") or [])[:5]],
            "opportunities": [_clip_text(item, limit=220) for item in (swot.get("opportunities") or [])[:5]],
            "threats": [_clip_text(item, limit=220) for item in (swot.get("threats") or [])[:5]],
        },
    }


def _summarize_insight(insight: dict) -> dict:
    evidence = insight.get("evidence") if isinstance(insight.get("evidence"), list) else []
    return {
        "section_name": _clean_text(insight.get("section_name")),
        "title": _clip_text(insight.get("title"), limit=180),
        "explanation": _clip_text(insight.get("explanation"), limit=420),
        "evidence": [_clip_text(item, limit=180) for item in evidence[:5]],
        "impact": _clean_text(insight.get("impact")),
        "sentiment": _clean_text(insight.get("sentiment")),
    }


def _extract_kpis(report: dict) -> dict:
    kpis = report.get("kpis") if isinstance(report.get("kpis"), dict) else {}
    ready_diagnostic = kpis.get("ready_for_sales_diagnostic") if isinstance(kpis.get("ready_for_sales_diagnostic"), dict) else {}
    classified_reasons = ready_diagnostic.get("classified_reasons") if isinstance(ready_diagnostic.get("classified_reasons"), list) else []

    return {
        "star_rating": _json_safe(kpis.get("star_rating")),
        "star_rating_count": kpis.get("star_rating_count"),
        "software_rating": _json_safe(kpis.get("software_rating")),
        "software_rating_count": kpis.get("software_rating_count"),
        "nps": _json_safe(kpis.get("nps")),
        "nps_count": kpis.get("nps_count"),
        "ready_for_sales": _json_safe(kpis.get("ready_for_sales")),
        "ready_for_sales_count": kpis.get("ready_for_sales_count"),
        "ready_for_sales_blocked_count": kpis.get("ready_for_sales_blocked_count"),
        "ready_for_sales_blocking_reasons": [
            {
                "interpretation": _clean_text(reason.get("interpretation")),
                "reason_summary": _clip_text(reason.get("reason_summary"), limit=260),
                "matched_keywords": reason.get("matched_keywords") if isinstance(reason.get("matched_keywords"), list) else [],
            }
            for reason in classified_reasons
            if isinstance(reason, dict) and _clean_text(reason.get("interpretation")).lower() == "blocking"
        ][:8],
    }


def _build_headset_comparison_payload(report_rows: list[dict]) -> dict:
    included_reports = []
    survey_1_sections = []
    survey_2_sections = []
    cross_report_insights = []

    for row in report_rows:
        report = _loads_json(row.get("report_json"), {})
        if not isinstance(report, dict):
            continue

        product = report.get("product") if isinstance(report.get("product"), dict) else {}
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        source_surveys = report.get("source_surveys") if isinstance(report.get("source_surveys"), list) else []
        sections = report.get("sections") if isinstance(report.get("sections"), list) else []
        insights = report.get("insights") if isinstance(report.get("insights"), list) else []
        first_ids, usage_ids = _classify_report_survey_ids(report)

        report_key = _clean_text(row.get("report_key"))
        report_label = _report_label(row, report)

        included_reports.append({
            "report_key": report_key,
            "report_label": report_label,
            "product_id": row.get("product_id") or product.get("product_id"),
            "round_number": row.get("round_number"),
            "internal_name": _clean_text(product.get("internal_name") or row.get("internal_name")),
            "market_name": _clean_text(product.get("market_name") or row.get("market_name")),
            "business_group": _clean_text(product.get("business_group") or row.get("business_group")),
            "product_type_display": _clean_text(product.get("product_type_display") or row.get("product_type_display")),
            "published_at": str(row.get("published_at") or ""),
            "report_updated_at": str(row.get("report_updated_at") or ""),
            "summary": {
                "executive_summary": _clip_text(summary.get("executive_summary"), limit=700),
                "response_count": summary.get("response_count"),
                "answer_count": summary.get("answer_count"),
                "survey_count": summary.get("survey_count"),
                "section_count": summary.get("section_count"),
                "insight_count": summary.get("insight_count"),
            },
            "kpis": _extract_kpis(report),
            "source_surveys": [
                {
                    "survey_name": _clean_text(source.get("survey_name")),
                    "trial_purpose": _clean_text(source.get("trial_purpose")),
                    "dataset_id": source.get("dataset_id"),
                    "response_count": source.get("response_count"),
                    "question_count": source.get("question_count"),
                    "stage": (
                        "survey_1_first_impressions"
                        if source.get("dataset_id") in first_ids
                        else "survey_2_usage" if source.get("dataset_id") in usage_ids else "unclassified"
                    ),
                }
                for source in source_surveys
                if isinstance(source, dict)
            ],
        })

        report_first_sections = []
        report_usage_sections = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            dataset_id = section.get("dataset_id")
            summarized_section = _summarize_section(section)
            summarized_section["report_key"] = report_key
            summarized_section["report_label"] = report_label

            if dataset_id in first_ids:
                report_first_sections.append(summarized_section)
            elif dataset_id in usage_ids:
                report_usage_sections.append(summarized_section)

        survey_1_sections.extend(report_first_sections[:10])
        survey_2_sections.extend(report_usage_sections[:14])

        for insight in insights[:8]:
            if not isinstance(insight, dict):
                continue
            summarized_insight = _summarize_insight(insight)
            summarized_insight["report_key"] = report_key
            summarized_insight["report_label"] = report_label
            cross_report_insights.append(summarized_insight)

    return {
        "comparison_type": "product_type_comparison",
        "product_type_key": "headset",
        "product_type_display": "Headset",
        "generation_version": GENERATION_VERSION,
        "headset_evaluation_criteria": HEADSET_EVALUATION_CRITERIA,
        "included_reports": included_reports,
        "survey_1_first_impressions": {
            "stage_label": "Survey 1 / OOBE / First Impressions",
            "analysis_goal": "Identify what headset users noticed immediately, including setup, first comfort, first audio/mic impressions, and early confidence gaps.",
            "sections": survey_1_sections,
        },
        "survey_2_usage": {
            "stage_label": "Survey 2 / Usage / KPI Feedback",
            "analysis_goal": "Identify what still mattered after real use, including comfort over time, audio/mic reliability, connection stability, battery, software, and market readiness.",
            "sections": survey_2_sections,
        },
        "cross_report_insights": cross_report_insights[:36],
    }


def _required_stage_schema(stage_name: str) -> str:
    return f"""
Return ONLY valid JSON with this exact top-level structure:
{{
  "stage_name": "{stage_name}",
  "summary": "2-4 sentence synthesis",
  "positives": [{{"theme": "", "why_it_matters": "", "evidence": [""]}}],
  "negatives": [{{"theme": "", "why_it_matters": "", "evidence": [""]}}],
  "positive_sentiment_drivers": [{{"driver": "", "behavioral_reason": "", "evidence": [""]}}],
  "negative_sentiment_drivers": [{{"driver": "", "behavioral_reason": "", "evidence": [""]}}],
  "open_questions": [""]
}}
"""


def _required_final_schema() -> str:
    return """
Return ONLY valid JSON with this exact top-level structure:
{
  "executive_summary": "2-4 sentence category-level synthesis",
  "what_headset_teams_should_remember": "durable product-team takeaway",
  "consistent_positives": [{"theme": "", "why_it_matters": "", "evidence": [""]}],
  "consistent_negatives": [{"theme": "", "why_it_matters": "", "evidence": [""]}],
  "positive_sentiment_drivers": [{"driver": "", "behavioral_reason": "", "evidence": [""]}],
  "negative_sentiment_drivers": [{"driver": "", "behavioral_reason": "", "evidence": [""]}],
  "must_haves": [{"item": "", "why": "", "evidence": [""], "confidence": "high|medium|low"}],
  "nice_to_haves": [{"item": "", "why": "", "evidence": [""], "confidence": "high|medium|low"}],
  "cannot_ship_without": [{"item": "", "why_blocking": "", "evidence": [""], "confidence": "high|medium|low"}],
  "what_users_forgive": [{"item": "", "conditions": "", "evidence": [""]}],
  "what_users_do_not_forgive": [{"item": "", "why": "", "evidence": [""]}],
  "use_case_differences": [{"use_case": "", "what_matters": [""], "evidence": [""]}],
  "product_team_questions_to_ask_next": [""]
}
"""


def _headset_system_prompt() -> str:
    return """
You are analyzing Logitech User Trial reporting data for headset products.
Use only the provided JSON evidence.
Be explicit about cross-report patterns versus product-specific issues.
Do not convert a one-off dramatic comment into a category-wide rule unless the evidence supports it.
Use headset-specific criteria: audio, microphone, comfort, fit, connection reliability, battery/charging, setup, controls/status confidence, software/firmware, work/gaming/media context, and market readiness.
Avoid repetitive section writing: the same theme may appear in more than one section only when its role is different. For example, comfort can be a positive, a must-have, or a blocker, but each section must explain the distinct role rather than restating the same sentence.
Do not use generic product language when headset-specific language is possible.
Return valid JSON only.
"""


def _run_headset_stage_analysis(*, payload: dict, stage_key: str, stage_label: str) -> dict:
    stage_payload = {
        "product_type_display": payload.get("product_type_display"),
        "included_reports": payload.get("included_reports"),
        "headset_evaluation_criteria": payload.get("headset_evaluation_criteria"),
        stage_key: payload.get(stage_key),
    }

    prompt = f"""
Analyze this headset product-type comparison stage.

Stage: {stage_label}

Rules:
- Discuss headset category patterns, not only individual products.
- Name uncertainty when evidence is thin.
- Separate positives, negatives, sentiment drivers, and open questions.
- Include short evidence notes from the JSON.

{_required_stage_schema(stage_label)}

Input JSON:
{json.dumps(stage_payload, ensure_ascii=False, default=_json_safe)}
"""

    return _call_json_ai(
        prompt=prompt,
        system_prompt=_headset_system_prompt(),
        max_tokens=5000,
    )


def _run_headset_final_synthesis(*, payload: dict, survey_1_analysis: dict, survey_2_analysis: dict) -> dict:
    final_payload = {
        "product_type_display": payload.get("product_type_display"),
        "included_reports": payload.get("included_reports"),
        "headset_evaluation_criteria": payload.get("headset_evaluation_criteria"),
        "survey_1_analysis": survey_1_analysis,
        "survey_2_analysis": survey_2_analysis,
        "cross_report_insights": payload.get("cross_report_insights"),
    }

    prompt = f"""
Create the final cross-headset product type comparison report from the staged analyses and source insight evidence.

Rules:
- This is a Headset category intelligence brief, not a generic summary.
- Executive summary: state the category-level conclusion once. Do not repeat the section list.
- Consistent positives/negatives: describe repeated observed strengths or weaknesses across reports.
- Sentiment drivers: explain what changes user confidence, trust, frustration, delight, willingness to recommend, or readiness perception. Do not duplicate positives/negatives unless you explain the behavioral mechanism.
- Must-haves: baseline expectations users punish when absent, even if they do not praise them when present.
- Nice-to-haves: delight or polish items that improve perception but are not blockers.
- Cannot-ship-without: issues severe enough to block launch/readiness because they undermine the headset's core promise.
- What users forgive / do not forgive: separate annoyances from dealbreakers.
- Use-case differences: only include differences supported by evidence.
- Product Team questions: keep these action-oriented and open-ended.
- Avoid repeating the same theme in multiple sections unless the section explains a different job that theme performs.
- Do not pretend unsupported evidence is conclusive.

{_required_final_schema()}

Input JSON:
{json.dumps(final_payload, ensure_ascii=False, default=_json_safe)}
"""

    return _call_json_ai(
        prompt=prompt,
        system_prompt=_headset_system_prompt(),
        max_tokens=7000,
    )


def _normalize_list_of_dicts(value, required_keys: list[str]) -> list[dict]:
    if not isinstance(value, list):
        return []

    normalized = []
    for item in value:
        if isinstance(item, dict):
            normalized_item = {key: item.get(key) for key in required_keys}
            for key in required_keys:
                if normalized_item.get(key) is None:
                    normalized_item[key] = [] if key == "evidence" else ""
            normalized.append(normalized_item)
        elif _clean_text(item):
            normalized.append({key: (_clean_text(item) if key != "evidence" else []) for key in required_keys})

    return normalized


def _build_saved_report(*, payload: dict, survey_1_analysis: dict, survey_2_analysis: dict, final_analysis: dict) -> dict:
    included_reports = payload.get("included_reports") if isinstance(payload.get("included_reports"), list) else []

    report = {
        "metadata": {
            "product_type_key": "headset",
            "product_type_display": "Headset",
            "generation_version": GENERATION_VERSION,
            "included_report_count": len(included_reports),
            "included_report_keys": [report.get("report_key") for report in included_reports if report.get("report_key")],
        },
        "included_reports": included_reports,
        "survey_1_first_impressions": survey_1_analysis,
        "survey_2_usage": survey_2_analysis,
        "executive_summary": _clean_text(final_analysis.get("executive_summary")),
        "what_headset_teams_should_remember": _clean_text(final_analysis.get("what_headset_teams_should_remember")),
        "consistent_positives": _normalize_list_of_dicts(final_analysis.get("consistent_positives"), ["theme", "why_it_matters", "evidence"]),
        "consistent_negatives": _normalize_list_of_dicts(final_analysis.get("consistent_negatives"), ["theme", "why_it_matters", "evidence"]),
        "positive_sentiment_drivers": _normalize_list_of_dicts(final_analysis.get("positive_sentiment_drivers"), ["driver", "behavioral_reason", "evidence"]),
        "negative_sentiment_drivers": _normalize_list_of_dicts(final_analysis.get("negative_sentiment_drivers"), ["driver", "behavioral_reason", "evidence"]),
        "must_haves": _normalize_list_of_dicts(final_analysis.get("must_haves"), ["item", "why", "evidence", "confidence"]),
        "nice_to_haves": _normalize_list_of_dicts(final_analysis.get("nice_to_haves"), ["item", "why", "evidence", "confidence"]),
        "cannot_ship_without": _normalize_list_of_dicts(final_analysis.get("cannot_ship_without"), ["item", "why_blocking", "evidence", "confidence"]),
        "what_users_forgive": _normalize_list_of_dicts(final_analysis.get("what_users_forgive"), ["item", "conditions", "evidence"]),
        "what_users_do_not_forgive": _normalize_list_of_dicts(final_analysis.get("what_users_do_not_forgive"), ["item", "why", "evidence"]),
        "use_case_differences": _normalize_list_of_dicts(final_analysis.get("use_case_differences"), ["use_case", "what_matters", "evidence"]),
        "product_team_questions_to_ask_next": final_analysis.get("product_team_questions_to_ask_next") if isinstance(final_analysis.get("product_team_questions_to_ask_next"), list) else [],
    }

    return report


def generate_headset_product_type_comparison(*, generated_by_user_id: str) -> dict:
    report_rows = list_published_report_objects_for_product_type(product_type_display="Headset")
    minimum_reports = int(SUPPORTED_PRODUCT_TYPE_COMPARISONS["headset"].get("minimum_reports") or 2)

    if len(report_rows) < minimum_reports:
        return {
            "success": False,
            "error": "not_enough_reports",
            "report": None,
        }

    payload = _build_headset_comparison_payload(report_rows)
    included_reports = payload.get("included_reports") if isinstance(payload.get("included_reports"), list) else []
    included_report_keys = [report.get("report_key") for report in included_reports if report.get("report_key")]

    if len(included_reports) < minimum_reports:
        return {
            "success": False,
            "error": "not_enough_valid_reports",
            "report": None,
        }

    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=_json_safe)
    data_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    survey_1_result = _run_headset_stage_analysis(
        payload=payload,
        stage_key="survey_1_first_impressions",
        stage_label="Survey 1 / OOBE / First Impressions",
    )
    if not survey_1_result.get("success"):
        return {
            "success": False,
            "error": survey_1_result.get("error") or "survey_1_ai_failed",
            "report": None,
        }

    survey_2_result = _run_headset_stage_analysis(
        payload=payload,
        stage_key="survey_2_usage",
        stage_label="Survey 2 / Usage / KPI Feedback",
    )
    if not survey_2_result.get("success"):
        return {
            "success": False,
            "error": survey_2_result.get("error") or "survey_2_ai_failed",
            "report": None,
        }

    final_result = _run_headset_final_synthesis(
        payload=payload,
        survey_1_analysis=survey_1_result.get("data") or {},
        survey_2_analysis=survey_2_result.get("data") or {},
    )
    if not final_result.get("success"):
        return {
            "success": False,
            "error": final_result.get("error") or "final_ai_failed",
            "report": None,
        }

    report = _build_saved_report(
        payload=payload,
        survey_1_analysis=survey_1_result.get("data") or {},
        survey_2_analysis=survey_2_result.get("data") or {},
        final_analysis=final_result.get("data") or {},
    )

    upsert_product_type_comparison_report(
        product_type_key="headset",
        product_type_display="Headset",
        report=report,
        input_payload=payload,
        included_report_keys=included_report_keys,
        generated_by_user_id=generated_by_user_id,
        generation_version=GENERATION_VERSION,
        data_hash=data_hash,
    )

    return {
        "success": True,
        "error": None,
        "report": report,
        "input_payload": payload,
        "data_hash": data_hash,
    }