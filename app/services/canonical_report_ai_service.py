# app/services/canonical_report_ai_service.py

from __future__ import annotations

import json
import re
from decimal import Decimal

from app.services.ai_service import call_ai


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _clip_text(value: object, *, limit: int = 220) -> str:
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


def _invalid_json_error_key(raw_response: object) -> str:
    text = _clean_text(raw_response)
    if not text:
        return "invalid_ai_response__empty"
    if "{" not in text or "}" not in text:
        return "invalid_ai_response__no_json_object"
    return "invalid_ai_response__malformed_json"


def _json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _extract_json_object(text: str) -> dict | None:
    if not text:
        return None

    clean = str(text).strip()
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


def _compact_question(question: dict) -> dict:
    values = question.get("values") or []
    return {
        "question": _clip_text(question.get("question"), limit=180),
        "type": _clean_text(question.get("type")),
        "average": question.get("average"),
        "sample_values": [
            _clip_text(value, limit=180)
            for value in values[:6]
            if _clean_text(value)
        ],
    }

def _compact_analysis_map(value: object) -> dict:
    if not isinstance(value, dict):
        return {}

    compact = {}
    for key, items in value.items():
        if isinstance(items, list):
            compact[key] = [
                _clip_text(item, limit=220)
                for item in items[:5]
                if _clean_text(item)
            ]
        elif _clean_text(items):
            compact[key] = _clip_text(items, limit=220)

    return compact

def _compact_section(section: dict) -> dict:
    qual = section.get("qual_question") if isinstance(section.get("qual_question"), dict) else {}

    section_analysis = section.get("section_analysis") if isinstance(section.get("section_analysis"), dict) else {}
    swot = section.get("swot") if isinstance(section.get("swot"), dict) else {}

    return {
        "section_name": _clean_text(section.get("section_name")),
        "report_group": _clean_text(section.get("report_group")),
        "survey_name": _clean_text(section.get("survey_name")),
        "average_score": section.get("average_score"),
        "quant_questions": [
            _compact_question(question)
            for question in section.get("quant_questions") or []
            if isinstance(question, dict)
        ],
        "qualitative_follow_up": {
            "question": _clip_text(qual.get("question"), limit=180),
            "sample_values": [
                _clip_text(value, limit=220)
                for value in (qual.get("values") or [])[:6]
                if _clean_text(value)
            ],
        },
        "swot": _compact_analysis_map(swot),
        "section_analysis": _compact_analysis_map(section_analysis),
    }


def _allowed_section_names(report: dict, *, blocked_section_names: set[str] | None = None) -> list[str]:
    blocked = blocked_section_names or set()
    names = []

    for section in report.get("sections") or []:
        if not isinstance(section, dict):
            continue

        name = _clean_text(section.get("section_name"))
        if not name or name in blocked:
            continue
        if name not in names:
            names.append(name)

    return names


def _build_canonical_ai_prompt(
    *,
    report: dict,
    report_type_label: str,
    allowed_section_names: list[str],
    max_insights: int,
) -> str:
    compact_sections = [
        _compact_section(section)
        for section in report.get("sections") or []
        if isinstance(section, dict)
    ]

    compact_profile = []
    participant_profile = report.get("participant_profile") if isinstance(report.get("participant_profile"), dict) else {}
    for question in participant_profile.get("questions") or []:
        if not isinstance(question, dict):
            continue
        compact_profile.append({
            "question": _clip_text(question.get("question"), limit=180),
            "top_options": [
                {
                    "label": _clip_text(option.get("label"), limit=120),
                    "count": option.get("count"),
                }
                for option in (question.get("options") or [])[:6]
                if isinstance(option, dict)
            ],
        })

    return f"""
You are generating the canonical executive summary and insights for a Logitech User Trials report.

Return JSON only. No markdown. No extra text.

Required JSON shape:
{{
  "executive_summary": "One strong executive summary paragraph. 110-170 words. It should synthesize the central user-experience story, use KPI evidence once near the end, and avoid marketing language.",
  "insights": [
    {{
      "section_name": "exact section name from Allowed Section Names",
      "title": "short insight title",
      "explanation": "2-3 sentence explanation grounded in the provided report data",
      "evidence": ["short evidence point from provided data"],
      "impact": "high|medium|low",
      "sentiment": "positive|negative|mixed|neutral"
    }}
  ]
}}

Rules:
- Generate 4-{max_insights} insights total.
- Every insight.section_name MUST be copied exactly from Allowed Section Names.
- Do not invent section names.
- Do not invent numbers.
- Do not invent quotes.
- Prefer insights that connect quantitative results with qualitative follow-up or synthesis.
- Avoid generic insights that would apply to any survey.
- The executive_summary must be feedback-led, not KPI-led.
- The first sentence must describe what users experienced, praised, struggled with, or trusted/distrusted.
- The first sentence must not use readiness, market release, launch, KPI, percentage, target, or score language.
- Begin the executive_summary with the strongest recurring user feedback themes from Sections, qualitative follow-up, SWOT, or section_analysis.
- Summarize the most important highs and lows from the body of the survey before referencing KPI outcomes.
- Use KPIs only as supporting evidence after the underlying user experience has been explained.
- Do not lead with KPI labels or values such as Ready for Sales, Star Rating, Net Promoter Score, or Software Rating.
- Do not summarize the KPI table.
- The executive_summary should explain what users experienced, what is working, what is risky, and what the product team should do next.
- If KPI scores are strong but section feedback contains material caveats, explicitly describe that tension.
- Avoid generic product-strategy language such as market readiness, market release, launch readiness, competitive landscape, churn risk, or broader appeal unless directly supported by the survey findings.
- Do not say the product demonstrates strong readiness, market readiness, or readiness for market release; describe the user-experience evidence instead.
- If the report is mostly positive, still mention the most important caveat or risk.
- If the report is mixed or negative, identify the highest-leverage improvement area.
- Executive Summary should not list every theme. It should synthesize the report into one central user-experience judgment, supported by the 2–3 strongest positive themes and the 2–3 highest-risk negative themes.
- The executive_summary should have this shape: user praise/theme -> main caveat/tension -> adoption or usability risk -> KPI support sentence -> highest-priority product-team action.
- Include exactly one KPI-support sentence near the end when KPI data is available; this sentence must support the user-experience read, not replace it.
- Do not omit KPI evidence entirely when KPI data is available.
- Avoid repeating the same feature in multiple sentences unless one mention is positive and the other explains a specific adoption barrier.
- Avoid marketing-positioning phrases such as market leader, solidify its position, best-in-class, category-leading, premium segment, and broaden appeal unless those ideas are directly supported by the provided survey findings.
- Do not call the product a tool for professionals, creators, gamers, or any other user segment unless the participant profile or survey findings directly support that segment.
- End with the 2–3 highest-priority fixes or product-team actions. Do not end with broad market-positioning language.

Report type:
{_clean_text(report_type_label)}

Allowed Section Names:
{json.dumps(allowed_section_names, ensure_ascii=False, default=_json_safe)}

Report Summary Metadata:
{json.dumps(report.get("summary") or {}, ensure_ascii=False, default=_json_safe)}

Primary survey feedback source — Sections:
{json.dumps(compact_sections, ensure_ascii=False, default=_json_safe)}

Participant Profile Context:
{json.dumps(compact_profile, ensure_ascii=False, default=_json_safe)}

Supporting evidence only — KPIs:
{json.dumps(report.get("kpis") or {}, ensure_ascii=False, default=_json_safe)}
"""


def generate_canonical_report_ai_outputs(
    *,
    report: dict,
    report_type_label: str,
    blocked_section_names: set[str] | None = None,
    max_insights: int = 7,
) -> dict:
    """
    Generate shared canonical report AI outputs.

    This service is source-agnostic and does not persist. Callers own storage.
    """

    if not isinstance(report, dict):
        return {
            "success": False,
            "error": "invalid_report",
            "report": report,
        }

    allowed_section_names = _allowed_section_names(
        report,
        blocked_section_names=blocked_section_names,
    )
    if not allowed_section_names:
        return {
            "success": False,
            "error": "no_allowed_sections",
            "report": report,
        }

    prompt = _build_canonical_ai_prompt(
        report=report,
        report_type_label=report_type_label,
        allowed_section_names=allowed_section_names,
        max_insights=max_insights,
    )

    system_prompt = (
        "You generate strict JSON for Logitech User Trials reports. "
        "Return only one valid JSON object and no markdown."
    )

    ai_result = call_ai(
        prompt=prompt,
        system_prompt=system_prompt,
        model="gpt-4o",
        temperature=0.2,
        max_tokens=3200,
    )

    if not ai_result.get("success"):
        return {
            "success": False,
            "error": f"ai_failed__{_safe_error_key(ai_result.get('error'))}",
            "report": report,
        }

    raw_response = (
        ai_result.get("content")
        or ai_result.get("response")
        or ""
    ).strip()

    parsed = _extract_json_object(raw_response)
    if not isinstance(parsed, dict):
        retry_prompt = prompt + """

The previous response did not parse as valid JSON.
Retry now. Return ONLY one valid JSON object with exactly these top-level keys:
- executive_summary
- insights
Do not include markdown, comments, explanation, or trailing text.
"""
        retry_result = call_ai(
            prompt=retry_prompt,
            system_prompt=system_prompt,
            model="gpt-4o",
            temperature=0,
            max_tokens=3200,
        )

        if not retry_result.get("success"):
            return {
                "success": False,
                "error": f"ai_retry_failed__{_safe_error_key(retry_result.get('error'))}",
                "report": report,
            }

        raw_response = (
            retry_result.get("content")
            or retry_result.get("response")
            or ""
        ).strip()
        parsed = _extract_json_object(raw_response)

    if not isinstance(parsed, dict):
        return {
            "success": False,
            "error": _invalid_json_error_key(raw_response),
            "report": report,
        }

    allowed_lookup = set(allowed_section_names)
    insights = parsed.get("insights") or []
    cleaned_insights = []
    rejected_count = 0

    if not isinstance(insights, list):
        insights = []

    for insight in insights[:max_insights + 3]:
        if not isinstance(insight, dict):
            rejected_count += 1
            continue

        section_name = _clean_text(insight.get("section_name"))
        if not section_name or section_name not in allowed_lookup:
            rejected_count += 1
            continue

        cleaned_insights.append({
            "section_name": section_name,
            "title": _clean_text(insight.get("title")) or "Untitled Insight",
            "explanation": _clean_text(insight.get("explanation")),
            "evidence": [
                _clean_text(item)
                for item in insight.get("evidence") or []
                if _clean_text(item)
            ][:4],
            "impact": (_clean_text(insight.get("impact")) or "medium").lower(),
            "sentiment": (_clean_text(insight.get("sentiment")) or "neutral").lower(),
        })

        if len(cleaned_insights) >= max_insights:
            break

    updated_report = dict(report)
    updated_summary = dict(updated_report.get("summary") or {})
    executive_summary = _clean_text(parsed.get("executive_summary"))
    if executive_summary:
        updated_summary["executive_summary"] = executive_summary
    updated_summary["insight_count"] = len(cleaned_insights)
    updated_report["summary"] = updated_summary
    updated_report["insights"] = cleaned_insights

    updated_metadata = dict(updated_report.get("metadata") or {})
    updated_metadata["canonical_ai_calls_succeeded"] = 1 if (executive_summary or cleaned_insights) else 0
    updated_metadata["canonical_ai_rejected_insight_count"] = rejected_count
    updated_report["metadata"] = updated_metadata

    return {
        "success": True,
        "error": None,
        "report": updated_report,
    }