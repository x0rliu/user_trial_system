# app/services/product_type_comparison_service.py

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from decimal import Decimal

from app.db.product_type_comparison_reports import (
    ProductTypeComparisonReportsTableMissing,
    get_latest_product_type_comparison_report,
    list_published_report_objects_for_product_type,
    upsert_product_type_comparison_report,
)
from app.services.ai_service import call_ai

GENERATION_VERSION = "product_type_comparison_headset_v1"

MAX_THEME_SECTIONS = 14
MAX_THEME_REPORTS = 10
MAX_THEME_AI_CALLS = 9
MAX_COMMENT_SAMPLES_PER_SECTION = 3
MAX_CROSS_REPORT_INSIGHTS = 24

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


def _is_ai_length_failure(error: object) -> bool:
    error_text = _clean_text(error).lower()
    if not error_text:
        return False

    return (
        "finish_reason=length" in error_text
        or "finish_reason_length" in error_text
        or "empty_content" in error_text and "length" in error_text
    )


def _json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


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
        temperature=0.2,
        max_tokens=max_tokens,
    )

    if not ai_result.get("success"):
        ai_error = ai_result.get("error")
        if _is_ai_length_failure(ai_error):
            compact_retry_prompt = prompt + """

The previous response hit the output length limit before returning usable JSON.

Retry now with a compact JSON object:
- Return ONLY one valid JSON object.
- Do not include markdown, comments, explanation, or trailing text.
- Keep each prose field concise.
- Keep arrays short and representative.
- Use no more than 4 items per array unless the required schema clearly needs fewer.
- Use no more than 3 short evidence strings per item.
- Prefer category-level conclusions over exhaustive evidence.
"""
            compact_retry_max_tokens = max(max_tokens, min(max_tokens * 2, 8000))
            compact_retry_result = call_ai(
                prompt=compact_retry_prompt,
                system_prompt=system_prompt,
                temperature=0,
                max_tokens=compact_retry_max_tokens,
            )

            if not compact_retry_result.get("success"):
                return {
                    "success": False,
                    "error": f"ai_length_retry_failed__{_safe_error_key(compact_retry_result.get('error'))}",
                    "data": None,
                }

            raw_compact_retry_response = (
                compact_retry_result.get("content")
                or compact_retry_result.get("response")
                or ""
            ).strip()

            parsed = _extract_json_object(raw_compact_retry_response)
            if isinstance(parsed, dict):
                return {
                    "success": True,
                    "error": None,
                    "data": parsed,
                }

            return {
                "success": False,
                "error": "ai_length_retry_invalid_json",
                "data": None,
            }

        return {
            "success": False,
            "error": f"ai_failed__{_safe_error_key(ai_error)}",
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
        "question": _clip_text(question.get("question"), limit=180),
        "type": _clean_text(question.get("type")),
        "average": _json_safe(question.get("average")),
        "response_count": len(values),
        "top_options": option_counts[:6],
    }


def _summarize_qual_question(question: dict) -> dict:
    values = question.get("values") if isinstance(question.get("values"), list) else []

    return {
        "question": _clip_text(question.get("question"), limit=180),
        "response_count": len([value for value in values if _clean_text(value)]),
        "sample_comments": [],
    }


def _summarize_section_analysis(section: dict) -> dict:
    analysis = section.get("section_analysis") if isinstance(section.get("section_analysis"), dict) else {}
    key_findings = analysis.get("key_findings") if isinstance(analysis.get("key_findings"), list) else []
    evidence = analysis.get("evidence") if isinstance(analysis.get("evidence"), list) else []

    return {
        "key_findings": [_clip_text(item, limit=220) for item in key_findings[:4] if _clean_text(item)],
        "evidence": [_clip_text(item, limit=180) for item in evidence[:4] if _clean_text(item)],
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
        "response_count": _safe_int(section.get("response_count")),
        "quant_questions": [_summarize_quant_question(question) for question in quant_questions[:4] if isinstance(question, dict)],
        "qual_question": _summarize_qual_question(qual_question) if qual_question else {},
        "section_analysis": _summarize_section_analysis(section),
        "swot": {
            "strengths": [_clip_text(item, limit=180) for item in (swot.get("strengths") or [])[:3]],
            "weaknesses": [_clip_text(item, limit=180) for item in (swot.get("weaknesses") or [])[:3]],
            "opportunities": [_clip_text(item, limit=180) for item in (swot.get("opportunities") or [])[:3]],
            "threats": [_clip_text(item, limit=180) for item in (swot.get("threats") or [])[:3]],
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

HEADSET_THEME_DEFINITIONS = [
    {
        "theme_key": "comfort_fit",
        "theme_label": "Comfort and Fit",
        "keywords": ["comfort", "comfortable", "fit", "wear", "wearing", "headband", "ear cushion", "earcup", "ear cup", "clamp", "pressure", "weight", "adjust", "adjustment"],
    },
    {
        "theme_key": "audio_quality",
        "theme_label": "Audio Quality",
        "keywords": ["audio", "sound", "bass", "treble", "volume", "music", "game sound", "directional", "surround", "clarity", "speaker"],
    },
    {
        "theme_key": "microphone_quality",
        "theme_label": "Microphone Quality",
        "keywords": ["mic", "microphone", "boom", "voice", "call", "teams", "discord", "noise", "mute", "sidetone"],
    },
    {
        "theme_key": "connectivity",
        "theme_label": "Connectivity and Pairing",
        "keywords": ["connect", "connection", "bluetooth", "bt", "dongle", "usb", "receiver", "wireless", "pair", "pairing", "range", "latency", "switch"],
    },
    {
        "theme_key": "battery_power",
        "theme_label": "Battery and Charging",
        "keywords": ["battery", "charge", "charging", "power", "usb-c", "cable", "life", "run out"],
    },
    {
        "theme_key": "setup_oobe_qsg",
        "theme_label": "Setup, OOBE, and QSG",
        "keywords": ["setup", "oobe", "out of box", "unbox", "unboxing", "quick start", "qsg", "instruction", "manual", "packaging", "box", "install"],
    },
    {
        "theme_key": "software_firmware",
        "theme_label": "Software and Firmware",
        "keywords": ["software", "firmware", "app", "ghub", "g hub", "logi", "update", "driver", "mac", "windows", "compatibility"],
    },
    {
        "theme_key": "controls_status",
        "theme_label": "Controls and Status Clarity",
        "keywords": ["button", "control", "wheel", "scroll", "mute", "status", "indicator", "led", "light", "toggle", "gesture"],
    },
    {
        "theme_key": "market_readiness",
        "theme_label": "Market Readiness and Recommendation",
        "keywords": ["ready for sales", "ready", "recommend", "nps", "market", "launch", "buy", "purchase", "price", "value", "worth"],
    },
]


def _theme_text_blob(section: dict) -> str:
    bits = [
        _clean_text(section.get("section_name")),
        _clean_text(section.get("survey_name")),
        _clean_text(section.get("trial_purpose")),
    ]

    for question in section.get("quant_questions") or []:
        if isinstance(question, dict):
            bits.append(_clean_text(question.get("question")))

    qual_question = section.get("qual_question") if isinstance(section.get("qual_question"), dict) else {}
    bits.append(_clean_text(qual_question.get("question")))

    swot = section.get("swot") if isinstance(section.get("swot"), dict) else {}
    for key in ("strengths", "weaknesses", "opportunities", "threats"):
        for item in swot.get(key) or []:
            bits.append(_clean_text(item))

    section_analysis = section.get("section_analysis") if isinstance(section.get("section_analysis"), dict) else {}
    for key in ("key_findings", "evidence"):
        for item in section_analysis.get(key) or []:
            bits.append(_clean_text(item))

    return " ".join(bit for bit in bits if bit).lower()


def _classify_headset_theme(section: dict) -> dict:
    blob = _theme_text_blob(section)
    if not blob:
        return {
            "theme_key": "general_experience",
            "theme_label": "General Experience",
        }

    best_theme = None
    best_score = 0
    for theme in HEADSET_THEME_DEFINITIONS:
        score = sum(1 for keyword in theme["keywords"] if keyword in blob)
        if score > best_score:
            best_score = score
            best_theme = theme

    if best_theme:
        return {
            "theme_key": best_theme["theme_key"],
            "theme_label": best_theme["theme_label"],
        }

    return {
        "theme_key": "general_experience",
        "theme_label": "General Experience",
    }


def _weighted_average(items: list[dict], *, value_key: str, count_key: str) -> float | None:
    weighted_total = 0.0
    count_total = 0
    fallback_values = []

    for item in items:
        value = item.get(value_key)
        if value in (None, ""):
            continue

        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue

        try:
            count = int(item.get(count_key) or 0)
        except (TypeError, ValueError):
            count = 0

        if count > 0:
            weighted_total += numeric_value * count
            count_total += count
        else:
            fallback_values.append(numeric_value)

    if count_total > 0:
        return round(weighted_total / count_total, 2)

    if fallback_values:
        return round(sum(fallback_values) / len(fallback_values), 2)

    return None


def _kpi_range(items: list[dict], *, value_key: str) -> dict:
    values = []
    for item in items:
        value = item.get(value_key)
        if value in (None, ""):
            continue
        try:
            values.append({"label": item.get("report_label"), "value": float(value)})
        except (TypeError, ValueError):
            continue

    if not values:
        return {"min": None, "max": None, "lowest_report": None, "highest_report": None}

    lowest = min(values, key=lambda item: item["value"])
    highest = max(values, key=lambda item: item["value"])
    return {
        "min": round(lowest["value"], 2),
        "max": round(highest["value"], 2),
        "lowest_report": lowest.get("label"),
        "highest_report": highest.get("label"),
    }


def _build_category_kpi_snapshot(included_reports: list[dict]) -> dict:
    report_kpis = []
    for report in included_reports:
        kpis = report.get("kpis") if isinstance(report.get("kpis"), dict) else {}
        report_kpis.append({
            "report_key": report.get("report_key"),
            "report_label": report.get("report_label"),
            "business_group": report.get("business_group"),
            "round_number": report.get("round_number"),
            "star_rating": kpis.get("star_rating"),
            "star_rating_count": kpis.get("star_rating_count"),
            "software_rating": kpis.get("software_rating"),
            "software_rating_count": kpis.get("software_rating_count"),
            "nps": kpis.get("nps"),
            "nps_count": kpis.get("nps_count"),
            "ready_for_sales": kpis.get("ready_for_sales"),
            "ready_for_sales_count": kpis.get("ready_for_sales_count"),
            "ready_for_sales_blocked_count": kpis.get("ready_for_sales_blocked_count"),
        })

    return {
        "report_count": len(included_reports),
        "star_rating": {
            "weighted_average": _weighted_average(report_kpis, value_key="star_rating", count_key="star_rating_count"),
            "range": _kpi_range(report_kpis, value_key="star_rating"),
        },
        "software_rating": {
            "weighted_average": _weighted_average(report_kpis, value_key="software_rating", count_key="software_rating_count"),
            "range": _kpi_range(report_kpis, value_key="software_rating"),
        },
        "nps": {
            "weighted_average": _weighted_average(report_kpis, value_key="nps", count_key="nps_count"),
            "range": _kpi_range(report_kpis, value_key="nps"),
        },
        "ready_for_sales": {
            "weighted_average": _weighted_average(report_kpis, value_key="ready_for_sales", count_key="ready_for_sales_count"),
            "range": _kpi_range(report_kpis, value_key="ready_for_sales"),
            "total_blocking_no": sum(int(item.get("ready_for_sales_blocked_count") or 0) for item in report_kpis),
        },
        "reports": report_kpis,
    }


def _build_theme_packets(*, sections: list[dict], included_reports: list[dict]) -> list[dict]:
    reports_by_key = {
        report.get("report_key"): report
        for report in included_reports
        if isinstance(report, dict) and report.get("report_key")
    }

    theme_map = {}
    for section in sections:
        theme = _classify_headset_theme(section)
        theme_key = theme["theme_key"]
        theme_label = theme["theme_label"]
        packet = theme_map.setdefault(theme_key, {
            "theme_key": theme_key,
            "theme_label": theme_label,
            "reports_touched": set(),
            "sections": [],
        })

        report_key = section.get("report_key")
        if report_key:
            packet["reports_touched"].add(report_key)

        if len(packet["sections"]) < MAX_THEME_SECTIONS:
            packet["sections"].append(section)

    packets = []
    for packet in theme_map.values():
        reports_touched = sorted(packet.pop("reports_touched"))
        packet["report_count"] = len(reports_touched)
        packet["reports"] = [
            {
                "report_key": report_key,
                "report_label": reports_by_key.get(report_key, {}).get("report_label"),
                "business_group": reports_by_key.get(report_key, {}).get("business_group"),
                "round_number": reports_by_key.get(report_key, {}).get("round_number"),
            }
            for report_key in reports_touched[:MAX_THEME_REPORTS]
        ]
        packets.append(packet)

    packets.sort(key=lambda item: (item.get("report_count") or 0, len(item.get("sections") or [])), reverse=True)
    return packets[:MAX_THEME_AI_CALLS]


def _compact_included_report_for_ai(report: dict) -> dict:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "report_key": report.get("report_key"),
        "report_label": report.get("report_label"),
        "business_group": report.get("business_group"),
        "round_number": report.get("round_number"),
        "summary": {
            "response_count": summary.get("response_count"),
            "answer_count": summary.get("answer_count"),
            "survey_count": summary.get("survey_count"),
            "section_count": summary.get("section_count"),
            "insight_count": summary.get("insight_count"),
        },
        "kpis": report.get("kpis") if isinstance(report.get("kpis"), dict) else {},
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
                "executive_summary": _clip_text(summary.get("executive_summary"), limit=360),
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
                summarized_section["stage"] = "Survey 1 / OOBE / First Impressions"
                report_first_sections.append(summarized_section)
            elif dataset_id in usage_ids:
                summarized_section["stage"] = "Survey 2 / Usage / KPI Feedback"
                report_usage_sections.append(summarized_section)

        survey_1_sections.extend(report_first_sections)
        survey_2_sections.extend(report_usage_sections)

        for insight in insights[:8]:
            if not isinstance(insight, dict):
                continue
            summarized_insight = _summarize_insight(insight)
            summarized_insight["report_key"] = report_key
            summarized_insight["report_label"] = report_label
            cross_report_insights.append(summarized_insight)

    all_sections = survey_1_sections + survey_2_sections
    category_kpi_snapshot = _build_category_kpi_snapshot(included_reports)
    theme_packets = _build_theme_packets(
        sections=all_sections,
        included_reports=included_reports,
    )

    return {
        "comparison_type": "product_type_comparison",
        "product_type_key": "headset",
        "product_type_display": "Headset",
        "generation_version": GENERATION_VERSION,
        "headset_evaluation_criteria": HEADSET_EVALUATION_CRITERIA,
        "included_reports": included_reports,
        "category_kpi_snapshot": category_kpi_snapshot,
        "theme_packets": theme_packets,
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
        "cross_report_insights": cross_report_insights[:MAX_CROSS_REPORT_INSIGHTS],
    }


def _required_theme_schema(theme_name: str) -> str:
    return f"""
Return ONLY valid JSON with this exact top-level structure:
{{
  "theme_key": "",
  "theme_name": "{theme_name}",
  "summary": "2-4 sentence theme-level comparison",
  "category_pattern": "what appears category-wide versus isolated; mention products only as brief evidence examples when needed",
  "positives": [{{"theme": "", "why_it_matters": "", "evidence": [""]}}],
  "negatives": [{{"theme": "", "why_it_matters": "", "evidence": [""]}}],
  "user_expectation": "baseline expectation, delight factor, or tolerance boundary",
  "product_team_questions": [""],
  "evidence_gaps": [""]
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
Focus on Product Type category intelligence, not project-by-project reporting.
Be explicit about repeated cross-report patterns versus isolated examples.
Mention specific products only when they are necessary evidence examples for a category-level claim.
Do not create product-by-product mini reports.
Do not convert a one-off dramatic comment into a category-wide rule unless the evidence supports it.
Use headset-specific criteria: audio, microphone, comfort, fit, connection reliability, battery/charging, setup, controls/status confidence, software/firmware, work/gaming/media context, and market readiness.
Avoid repetitive section writing: the same theme may appear in more than one section only when its role is different.
Do not do arithmetic. KPI arithmetic has already been calculated by the system; interpret what the KPI snapshot means.
Do not use generic product language when headset-specific language is possible.
Return valid JSON only.
"""


def _run_headset_theme_analysis(*, payload: dict, theme_packet: dict) -> dict:
    theme_payload = {
        "product_type_display": payload.get("product_type_display"),
        "theme_key": theme_packet.get("theme_key"),
        "theme_label": theme_packet.get("theme_label"),
        "reports": theme_packet.get("reports"),
        "category_kpi_snapshot": payload.get("category_kpi_snapshot"),
        "included_reports": [
            _compact_included_report_for_ai(report)
            for report in payload.get("included_reports", [])
            if isinstance(report, dict)
        ],
        "sections": theme_packet.get("sections"),
    }

    prompt = f"""
Analyze this headset product-type theme across the category.

Theme: {theme_packet.get('theme_label')}

Rules:
- Compare this theme across published headset reports.
- This is a Product Type category report, not a product-by-product report.
- The input is structured report JSON: summaries, KPIs, SWOT, section findings, and stored evidence snippets.
- Do not ask for or assume raw survey comments.
- Focus on category-wide patterns, repeated positives, repeated negatives, expectations, tolerance boundaries, and evidence gaps.
- Mention specific products only as short evidence examples when needed to explain whether a pattern is repeated or isolated.
- Do not generate a dedicated product-specific pattern section.
- Use the KPI snapshot only as broad context; do not recalculate it.
- Name uncertainty when evidence is thin.
- Include short evidence notes from the JSON.

{_required_theme_schema(str(theme_packet.get('theme_label') or 'Theme'))}

Input JSON:
{json.dumps(theme_payload, ensure_ascii=False, default=_json_safe)}
"""

    return _call_json_ai(
        prompt=prompt,
        system_prompt=_headset_system_prompt(),
        max_tokens=3600,
    )


def _strip_product_specific_patterns_from_theme(theme: object) -> dict:
    if not isinstance(theme, dict):
        return {}

    cleaned_theme = dict(theme)
    cleaned_theme.pop("product_specific_patterns", None)
    return cleaned_theme


def _run_headset_final_synthesis(*, payload: dict, theme_analyses: list[dict]) -> dict:
    final_payload = {
        "product_type_display": payload.get("product_type_display"),
        "category_kpi_snapshot": payload.get("category_kpi_snapshot"),
        "included_reports": [
            _compact_included_report_for_ai(report)
            for report in payload.get("included_reports", [])
            if isinstance(report, dict)
        ],
        "theme_analyses": [
            _strip_product_specific_patterns_from_theme(theme)
            for theme in theme_analyses
            if isinstance(theme, dict)
        ],
        "cross_report_insights": payload.get("cross_report_insights"),
    }

    prompt = f"""
Create the final cross-headset Product Type comparison report from category KPIs and theme-level analyses.

Rules:
- This is a Headset category intelligence brief, not a generic summary.
- Use structured lower-level report outputs as the evidence layer; do not infer from raw comments.
- Start from the KPI snapshot: explain broad category performance, spread, and outliers.
- Use theme analyses to explain why the KPI pattern likely exists.
- Consistent positives/negatives: describe repeated observed strengths or weaknesses across reports.
- Sentiment drivers: explain what changes user confidence, trust, frustration, delight, willingness to recommend, or readiness perception.
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
        max_tokens=6500,
    )

def _fallback_theme_analysis(*, theme_packet: dict, error: str) -> dict:
    theme_label = _clean_text(theme_packet.get("theme_label")) or "Theme"
    theme_key = _clean_text(theme_packet.get("theme_key")) or _safe_error_key(theme_label)
    section_count = len(theme_packet.get("sections") or [])
    report_count = int(theme_packet.get("report_count") or 0)

    return {
        "theme_key": theme_key,
        "theme_name": theme_label,
        "ai_status": "failed",
        "ai_error": _clean_text(error) or "unknown",
        "summary": (
            f"{theme_label} could not be analyzed by AI in this run. "
            f"The source packet still contained {section_count} section(s) across {report_count} report(s), "
            "so this theme should be retried rather than treated as absent."
        ),
        "category_pattern": "Theme AI generation failed for this chunk; no category-wide claim was generated.",
        "positives": [],
        "negatives": [],
        "user_expectation": "Not generated because this theme chunk failed.",
        "product_team_questions": [
            f"Retry {theme_label} analysis after reducing or inspecting this theme packet."
        ],
        "evidence_gaps": [
            f"AI error: {_clean_text(error) or 'unknown'}"
        ],
        "source_section_count": section_count,
        "source_report_count": report_count,
    }


def _fallback_final_analysis(*, payload: dict, theme_analyses: list[dict], error: str) -> dict:
    category_kpis = payload.get("category_kpi_snapshot") if isinstance(payload.get("category_kpi_snapshot"), dict) else {}
    included_reports = payload.get("included_reports") if isinstance(payload.get("included_reports"), list) else []
    successful_themes = [
        theme for theme in theme_analyses
        if isinstance(theme, dict) and theme.get("ai_status") != "failed"
    ]
    failed_themes = [
        theme for theme in theme_analyses
        if isinstance(theme, dict) and theme.get("ai_status") == "failed"
    ]

    star_rating = (category_kpis.get("star_rating") or {}).get("weighted_average") if isinstance(category_kpis.get("star_rating"), dict) else None
    ready_for_sales = (category_kpis.get("ready_for_sales") or {}).get("weighted_average") if isinstance(category_kpis.get("ready_for_sales"), dict) else None

    kpi_parts = []
    if star_rating not in (None, ""):
        kpi_parts.append(f"category star rating averages {star_rating}/5")
    if ready_for_sales not in (None, ""):
        kpi_parts.append(f"ready-for-sales averages {ready_for_sales}%")
    kpi_copy = "; ".join(kpi_parts) if kpi_parts else "category KPI values are available in the KPI snapshot"

    return {
        "executive_summary": (
            f"This Headset comparison includes {len(included_reports)} published report(s). "
            f"The system generated {len(successful_themes)} theme analysis chunk(s); "
            f"{len(failed_themes)} theme chunk(s) need retry. Broadly, {kpi_copy}. "
            "The final AI synthesis failed, so this report preserves deterministic KPI context and available theme outputs instead of inventing conclusions."
        ),
        "what_headset_teams_should_remember": "This run is partially generated. Review successful theme cards and retry failed chunks before using it as a final category readout.",
        "consistent_positives": [],
        "consistent_negatives": [],
        "positive_sentiment_drivers": [],
        "negative_sentiment_drivers": [],
        "must_haves": [],
        "nice_to_haves": [],
        "cannot_ship_without": [],
        "what_users_forgive": [],
        "what_users_do_not_forgive": [],
        "use_case_differences": [],
        "product_team_questions_to_ask_next": [
            "Which failed theme chunks should be retried before this Product Type report is treated as final?",
            "Which category KPI outliers should be investigated by project or round?",
        ],
        "ai_status": "final_synthesis_failed",
        "ai_error": _clean_text(error) or "unknown",
    }

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


def _build_saved_report(*, payload: dict, theme_analyses: list[dict], final_analysis: dict) -> dict:
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
        "category_kpi_snapshot": payload.get("category_kpi_snapshot") if isinstance(payload.get("category_kpi_snapshot"), dict) else {},
        "theme_analyses": [
            _strip_product_specific_patterns_from_theme(theme)
            for theme in theme_analyses
            if isinstance(theme, dict)
        ],
        "survey_1_first_impressions": {
            "stage_name": "Survey 1 / OOBE / First Impressions",
            "summary": "This comparison now uses theme-level analysis rather than one broad Survey 1 AI pass.",
            "positives": [],
            "negatives": [],
            "positive_sentiment_drivers": [],
            "negative_sentiment_drivers": [],
            "open_questions": [],
        },
        "survey_2_usage": {
            "stage_name": "Survey 2 / Usage / KPI Feedback",
            "summary": "This comparison now uses theme-level analysis rather than one broad Survey 2 AI pass.",
            "positives": [],
            "negatives": [],
            "positive_sentiment_drivers": [],
            "negative_sentiment_drivers": [],
            "open_questions": [],
        },
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


def _is_generated_theme_analysis(theme: object) -> bool:
    return isinstance(theme, dict) and theme.get("ai_status") != "failed"


def _saved_theme_analysis_map(report: dict) -> dict[str, dict]:
    theme_analyses = report.get("theme_analyses") if isinstance(report.get("theme_analyses"), list) else []
    mapped = {}

    for theme in theme_analyses:
        if not isinstance(theme, dict):
            continue

        theme_key = _clean_text(theme.get("theme_key"))
        if not theme_key:
            continue

        mapped[theme_key] = theme

    return mapped


def _final_analysis_from_saved_report(report: dict) -> dict:
    return {
        "ai_status": _clean_text(report.get("final_ai_status")) or "reused",
        "executive_summary": _clean_text(report.get("executive_summary")),
        "what_headset_teams_should_remember": _clean_text(report.get("what_headset_teams_should_remember")),
        "consistent_positives": report.get("consistent_positives") if isinstance(report.get("consistent_positives"), list) else [],
        "consistent_negatives": report.get("consistent_negatives") if isinstance(report.get("consistent_negatives"), list) else [],
        "positive_sentiment_drivers": report.get("positive_sentiment_drivers") if isinstance(report.get("positive_sentiment_drivers"), list) else [],
        "negative_sentiment_drivers": report.get("negative_sentiment_drivers") if isinstance(report.get("negative_sentiment_drivers"), list) else [],
        "must_haves": report.get("must_haves") if isinstance(report.get("must_haves"), list) else [],
        "nice_to_haves": report.get("nice_to_haves") if isinstance(report.get("nice_to_haves"), list) else [],
        "cannot_ship_without": report.get("cannot_ship_without") if isinstance(report.get("cannot_ship_without"), list) else [],
        "what_users_forgive": report.get("what_users_forgive") if isinstance(report.get("what_users_forgive"), list) else [],
        "what_users_do_not_forgive": report.get("what_users_do_not_forgive") if isinstance(report.get("what_users_do_not_forgive"), list) else [],
        "use_case_differences": report.get("use_case_differences") if isinstance(report.get("use_case_differences"), list) else [],
        "product_team_questions_to_ask_next": (
            report.get("product_team_questions_to_ask_next")
            if isinstance(report.get("product_team_questions_to_ask_next"), list)
            else []
        ),
    }


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

    theme_packets = payload.get("theme_packets") if isinstance(payload.get("theme_packets"), list) else []
    if not theme_packets:
        return {
            "success": False,
            "error": "no_theme_packets",
            "report": None,
        }

    latest_result = get_latest_product_type_comparison_report(product_type_display="Headset")
    latest_report = latest_result.get("report") if latest_result.get("success") else {}
    latest_metadata = latest_report.get("metadata") if isinstance(latest_report, dict) else {}
    can_reuse_saved_themes = (
        isinstance(latest_report, dict)
        and latest_metadata.get("data_hash") == data_hash
        and latest_metadata.get("generation_version") == GENERATION_VERSION
    )
    saved_theme_map = _saved_theme_analysis_map(latest_report) if can_reuse_saved_themes else {}

    theme_analyses = []
    reused_theme_count = 0
    retried_theme_count = 0
    newly_generated_theme_count = 0

    for theme_packet in theme_packets:
        if not isinstance(theme_packet, dict):
            continue

        theme_key = _clean_text(theme_packet.get("theme_key"))
        saved_theme = saved_theme_map.get(theme_key)
        if _is_generated_theme_analysis(saved_theme):
            theme_analyses.append(saved_theme)
            reused_theme_count += 1
            continue

        if can_reuse_saved_themes and isinstance(saved_theme, dict) and saved_theme.get("ai_status") == "failed":
            retried_theme_count += 1

        theme_result = _run_headset_theme_analysis(
            payload=payload,
            theme_packet=theme_packet,
        )
        if not theme_result.get("success"):
            theme_data = _fallback_theme_analysis(
                theme_packet=theme_packet,
                error=theme_result.get("error") or "unknown",
            )
            theme_analyses.append(theme_data)
            continue

        theme_data = theme_result.get("data") or {}
        theme_data.setdefault("theme_key", theme_packet.get("theme_key"))
        theme_data.setdefault("theme_name", theme_packet.get("theme_label"))
        theme_data.setdefault("ai_status", "generated")
        theme_data["source_section_count"] = len(theme_packet.get("sections") or [])
        theme_data["source_report_count"] = theme_packet.get("report_count") or 0
        theme_analyses.append(theme_data)
        newly_generated_theme_count += 1

    generated_theme_count = sum(
        1 for theme in theme_analyses
        if _is_generated_theme_analysis(theme)
    )
    if generated_theme_count <= 0:
        final_analysis = _fallback_final_analysis(
            payload=payload,
            theme_analyses=theme_analyses,
            error="all_theme_ai_failed",
        )
    elif can_reuse_saved_themes and newly_generated_theme_count <= 0:
        final_analysis = _final_analysis_from_saved_report(latest_report)
    else:
        final_result = _run_headset_final_synthesis(
            payload=payload,
            theme_analyses=theme_analyses,
        )
        if final_result.get("success"):
            final_analysis = final_result.get("data") or {}
            final_analysis.setdefault("ai_status", "generated")
        elif can_reuse_saved_themes:
            final_analysis = _final_analysis_from_saved_report(latest_report)
            final_analysis["ai_status"] = "reused_after_final_ai_failed"
        else:
            final_analysis = _fallback_final_analysis(
                payload=payload,
                theme_analyses=theme_analyses,
                error=final_result.get("error") or "final_ai_failed",
            )

    report = _build_saved_report(
        payload=payload,
        theme_analyses=theme_analyses,
        final_analysis=final_analysis,
    )
    report.setdefault("metadata", {})
    report["metadata"].update({
        "theme_generation_mode": "retry_failed_only" if can_reuse_saved_themes else "full_generation",
        "reused_theme_count": reused_theme_count,
        "retried_theme_count": retried_theme_count,
        "newly_generated_theme_count": newly_generated_theme_count,
    })

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