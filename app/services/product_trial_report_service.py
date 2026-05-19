# app/services/product_trial_report_service.py

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal

from app.db.product_trial_reports import (
    get_product_trial_report_source_answers,
    upsert_product_trial_report,
)
from app.db.survey_kpis import get_round_product_kpis
from app.db.user_trial_lead import get_project_round_by_id
from app.services.ai_service import call_ai


REPORT_VERSION = "product_trial_report_v1"


_STOPWORDS = {
    "about", "after", "again", "also", "because", "been", "being", "could",
    "device", "during", "experience", "from", "have", "into", "just", "like",
    "more", "most", "much", "need", "only", "product", "really", "should",
    "some", "than", "that", "their", "there", "these", "thing", "this",
    "trial", "using", "very", "were", "what", "when", "with", "would",
}


def _normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _display_value(value: object, fallback: str = "—") -> str:
    text = _normalize_text(value)
    return text if text else fallback


def _survey_display_name(row: dict) -> str:
    label = _display_value(row.get("SurveyTypeName"), "Survey")
    return label.replace("_", " ")


def _answer_text(row: dict) -> str:
    return _normalize_text(row.get("AnswerValue"))


def _is_empty_answer(value: object) -> bool:
    text = _normalize_text(value)
    return text == "" or text.lower() in {"none", "null", "nan"}


def _split_categorical_answer(answer: str) -> list[str]:
    text = _normalize_text(answer)
    if not text:
        return []

    if len(text) > 120:
        return [text]

    if "," not in text:
        return [text]

    if "(" in text and ")" in text:
        return [text]

    parts = [part.strip() for part in text.split(",") if part.strip()]
    return parts or [text]


def _extract_keywords(text_values: list[str], *, limit: int = 6) -> list[str]:
    counter: Counter[str] = Counter()

    for value in text_values:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9+\-']{2,}", value.lower()):
            token = token.strip("'-")
            if len(token) < 3 or token in _STOPWORDS:
                continue
            counter[token] += 1

    return [word for word, _count in counter.most_common(limit)]


def _choose_quotes(text_values: list[str], *, limit: int = 4) -> list[str]:
    seen = set()
    quotes = []

    for value in text_values:
        text = _normalize_text(value)
        if len(text) < 8:
            continue

        key = text.lower()
        if key in seen:
            continue

        seen.add(key)
        quotes.append(text[:260])

        if len(quotes) >= limit:
            break

    return quotes


def _question_summary(question_text: str, rows: list[dict]) -> dict:
    answer_values = [
        _answer_text(row)
        for row in rows
        if not _is_empty_answer(row.get("AnswerValue"))
    ]

    numeric_values = []
    for row in rows:
        numeric_value = _to_float(row.get("AnswerNumeric"))
        if numeric_value is not None:
            numeric_values.append(numeric_value)

    answered_count = len(answer_values)
    numeric_ratio = (len(numeric_values) / answered_count) if answered_count else 0

    if numeric_values and numeric_ratio >= 0.7:
        score_max = 10 if max(numeric_values) > 5 else 5
        average_score = round(sum(numeric_values) / len(numeric_values), 2)
        return {
            "question": question_text,
            "answer_type": "numeric",
            "response_count": len(numeric_values),
            "average_score": average_score,
            "min_score": min(numeric_values),
            "max_score": max(numeric_values),
            "scale_max": score_max,
            "bar_width": round((average_score / score_max) * 100, 1) if score_max else 0,
            "top_options": [],
            "notable_quotes": [],
            "keywords": [],
        }

    option_counter: Counter[str] = Counter()
    qualitative_values = []

    for value in answer_values:
        if len(value) <= 80:
            for option in _split_categorical_answer(value):
                option_counter[option] += 1
        else:
            qualitative_values.append(value)

    if option_counter and len(option_counter) <= 12 and answered_count >= 3:
        top_options = [
            {
                "label": label,
                "count": count,
                "percent": round((count / answered_count) * 100, 1) if answered_count else 0,
            }
            for label, count in option_counter.most_common(6)
        ]
        return {
            "question": question_text,
            "answer_type": "categorical",
            "response_count": answered_count,
            "average_score": None,
            "min_score": None,
            "max_score": None,
            "scale_max": None,
            "bar_width": None,
            "top_options": top_options,
            "notable_quotes": _choose_quotes(qualitative_values, limit=3),
            "keywords": _extract_keywords(qualitative_values, limit=5),
        }

    return {
        "question": question_text,
        "answer_type": "qualitative",
        "response_count": answered_count,
        "average_score": None,
        "min_score": None,
        "max_score": None,
        "scale_max": None,
        "bar_width": None,
        "top_options": [],
        "notable_quotes": _choose_quotes(answer_values, limit=4),
        "keywords": _extract_keywords(answer_values, limit=6),
    }


def _build_survey_summaries(answer_rows: list[dict]) -> list[dict]:
    survey_groups: dict[str, list[dict]] = defaultdict(list)

    for row in answer_rows:
        survey_groups[str(row.get("SurveyTypeID") or "unknown")].append(row)

    surveys = []

    for survey_type_id, rows in survey_groups.items():
        first_row = rows[0] if rows else {}
        question_groups: dict[str, list[dict]] = defaultdict(list)

        for row in rows:
            question_key = str(row.get("QuestionID") or row.get("QuestionText") or "")
            question_groups[question_key].append(row)

        question_order = sorted(
            question_groups.items(),
            key=lambda item: min(int(r.get("AnswerID") or 0) for r in item[1]),
        )

        question_summaries = []
        for _question_key, question_rows in question_order:
            question_text = _display_value(question_rows[0].get("QuestionText"), "Untitled question")
            question_summaries.append(_question_summary(question_text, question_rows))

        response_ids = {
            row.get("DistributionID")
            for row in rows
            if row.get("DistributionID") is not None
        }

        surveys.append({
            "survey_type_id": survey_type_id,
            "survey_name": _survey_display_name(first_row),
            "response_count": len(response_ids),
            "answer_count": len(rows),
            "question_count": len(question_summaries),
            "questions": question_summaries,
        })

    return surveys


def _build_source_hash(answer_rows: list[dict]) -> str:
    source_payload = []

    for row in answer_rows:
        source_payload.append({
            "AnswerID": row.get("AnswerID"),
            "SurveyID": row.get("SurveyID"),
            "DistributionID": row.get("DistributionID"),
            "QuestionID": row.get("QuestionID"),
            "AnswerValue": row.get("AnswerValue"),
            "AnswerNumeric": _json_safe(row.get("AnswerNumeric")),
            "UpdatedAt": _json_safe(row.get("UpdatedAt")),
        })

    encoded = json.dumps(source_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _format_metric(value: object, *, suffix: str = "") -> str:
    if value is None:
        return "not available"

    try:
        text = f"{float(value):.1f}"
    except (TypeError, ValueError):
        text = str(value)

    if text.endswith(".0"):
        text = text[:-2]

    return f"{text}{suffix}"


def _fallback_report(*, round_data: dict, kpis: dict, survey_summaries: list[dict], data_hash: str) -> dict:
    total_responses = sum(survey.get("response_count") or 0 for survey in survey_summaries)
    total_answers = sum(survey.get("answer_count") or 0 for survey in survey_summaries)

    strongest_questions = []
    weakest_questions = []

    for survey in survey_summaries:
        for question in survey.get("questions") or []:
            if question.get("answer_type") != "numeric":
                continue
            avg = question.get("average_score")
            if avg is None:
                continue
            item = {
                "survey_name": survey.get("survey_name"),
                "question": question.get("question"),
                "average_score": avg,
                "scale_max": question.get("scale_max"),
            }
            if avg >= 4:
                strongest_questions.append(item)
            elif avg <= 3:
                weakest_questions.append(item)

    strongest_questions = sorted(
        strongest_questions,
        key=lambda item: item.get("average_score") or 0,
        reverse=True,
    )[:4]
    weakest_questions = sorted(
        weakest_questions,
        key=lambda item: item.get("average_score") or 0,
    )[:4]

    key_strengths = [
        f"{item['question']} scored {_format_metric(item['average_score'])}/{item['scale_max']}."
        for item in strongest_questions
    ]
    key_weaknesses = [
        f"{item['question']} scored {_format_metric(item['average_score'])}/{item['scale_max']}."
        for item in weakest_questions
    ]

    if not key_strengths:
        key_strengths = ["No strong numeric pattern was detected yet."]
    if not key_weaknesses:
        key_weaknesses = ["No clear numeric weakness was detected yet."]

    ready_for_sales = kpis.get("ready_for_sales")
    nps = kpis.get("nps")

    executive_summary = (
        f"{_display_value(round_data.get('ProjectName'), 'This project')} has "
        f"{len(survey_summaries)} participant result survey section(s) with "
        f"{total_responses} response records and {total_answers} stored answers. "
        f"Current Product KPI signals show NPS at {_format_metric(nps)} and "
        f"Ready for Sales at {_format_metric(ready_for_sales, suffix='%')}."
    )

    section_insights = []
    for survey in survey_summaries:
        findings = []
        notable_quotes = []

        for question in survey.get("questions") or []:
            if question.get("answer_type") == "numeric" and question.get("average_score") is not None:
                findings.append(
                    f"{question.get('question')} averaged "
                    f"{_format_metric(question.get('average_score'))}/{question.get('scale_max')}."
                )

            if question.get("answer_type") == "categorical" and question.get("top_options"):
                top = question["top_options"][0]
                findings.append(
                    f"{question.get('question')} was led by '{top.get('label')}' "
                    f"at {top.get('count')} response(s)."
                )

            for quote in question.get("notable_quotes") or []:
                if len(notable_quotes) < 3:
                    notable_quotes.append(quote)

            if len(findings) >= 4 and len(notable_quotes) >= 3:
                break

        section_insights.append({
            "survey_type_id": survey.get("survey_type_id"),
            "survey_name": survey.get("survey_name"),
            "summary": (
                f"{survey.get('survey_name')} contains {survey.get('response_count')} "
                f"response records across {survey.get('question_count')} questions."
            ),
            "key_findings": findings[:5],
            "notable_quotes": notable_quotes[:3],
        })

    return {
        "metadata": {
            "version": REPORT_VERSION,
            "generation_mode": "deterministic_fallback",
            "data_hash": data_hash,
        },
        "summary": {
            "executive_summary": executive_summary,
            "response_count": total_responses,
            "answer_count": total_answers,
            "survey_count": len(survey_summaries),
        },
        "kpis": kpis,
        "swot": {
            "strengths": key_strengths[:5],
            "weaknesses": key_weaknesses[:5],
            "opportunities": [
                "Review qualitative comments attached to lower-scoring questions before final launch decisions."
            ],
            "threats": [
                "Unmatched respondent attribution may limit user-profile-level slicing until review is completed."
            ],
        },
        "recommended_actions": [
            "Review low-scoring quantitative questions and their nearby qualitative comments.",
            "Resolve unmatched response attribution before deeper profile-based cuts.",
            "Regenerate this report after additional software or KPI survey uploads.",
        ],
        "sections": section_insights,
        "source_surveys": survey_summaries,
    }


def _compact_ai_source(*, survey_summaries: list[dict], max_questions_per_survey: int = 12) -> list[dict]:
    compact = []

    for survey in survey_summaries:
        questions = []
        for question in (survey.get("questions") or [])[:max_questions_per_survey]:
            questions.append({
                "question": question.get("question"),
                "answer_type": question.get("answer_type"),
                "response_count": question.get("response_count"),
                "average_score": question.get("average_score"),
                "scale_max": question.get("scale_max"),
                "top_options": question.get("top_options"),
                "keywords": question.get("keywords"),
                "notable_quotes": question.get("notable_quotes"),
            })

        compact.append({
            "survey_type_id": survey.get("survey_type_id"),
            "survey_name": survey.get("survey_name"),
            "response_count": survey.get("response_count"),
            "answer_count": survey.get("answer_count"),
            "question_count": survey.get("question_count"),
            "questions": questions,
        })

    return compact


def _extract_json_object(text: str) -> dict | None:
    raw = _normalize_text(text)
    if not raw:
        return None

    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            return None

    return parsed if isinstance(parsed, dict) else None


def _ai_report_overlay(*, round_data: dict, kpis: dict, survey_summaries: list[dict]) -> dict | None:
    compact_source = _compact_ai_source(survey_summaries=survey_summaries)

    prompt = f"""
Create a Product Trial report from DB-backed survey aggregates.

Return JSON only. No markdown. No commentary outside JSON.

Required shape:
{{
  "executive_summary": "one concise paragraph",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "opportunities": ["..."],
  "threats": ["..."],
  "recommended_actions": ["..."],
  "sections": [
    {{
      "survey_type_id": "...",
      "survey_name": "...",
      "summary": "one concise paragraph",
      "key_findings": ["..."],
      "notable_quotes": ["..."]
    }}
  ]
}}

Rules:
- Do not invent numbers.
- Use only the provided aggregates and quotes.
- Keep every list to 3-5 items.
- If evidence is weak, say that the signal needs review.
- Product KPI context: Star Rating, NPS, Ready for Sales, Software Rating.

Project:
{json.dumps({
    "project_name": round_data.get("ProjectName"),
    "market_name": round_data.get("MarketName"),
    "business_group": round_data.get("BusinessGroup"),
    "product_type": round_data.get("ProductType"),
    "round_id": round_data.get("RoundID"),
}, ensure_ascii=False)}

KPIs:
{json.dumps(kpis, ensure_ascii=False, default=_json_safe)}

Survey aggregates:
{json.dumps(compact_source, ensure_ascii=False, default=_json_safe)}
"""

    result = call_ai(
        prompt=prompt,
        system_prompt=(
            "You generate concise product trial reports for Logitech User Trials. "
            "You must stay grounded in the supplied aggregate data."
        ),
        model="gpt-4o-mini",
        temperature=0.2,
        max_tokens=1800,
    )

    if not result.get("success"):
        return None

    return _extract_json_object(result.get("response") or "")


def _merge_ai_overlay(base_report: dict, ai_overlay: dict | None) -> dict:
    if not ai_overlay:
        return base_report

    report = dict(base_report)
    report["metadata"] = dict(report.get("metadata") or {})
    report["metadata"]["generation_mode"] = "ai_assisted"

    summary = dict(report.get("summary") or {})
    if ai_overlay.get("executive_summary"):
        summary["executive_summary"] = str(ai_overlay.get("executive_summary") or "")
    report["summary"] = summary

    swot = dict(report.get("swot") or {})
    for source_key, target_key in (
        ("strengths", "strengths"),
        ("weaknesses", "weaknesses"),
        ("opportunities", "opportunities"),
        ("threats", "threats"),
    ):
        values = ai_overlay.get(source_key)
        if isinstance(values, list) and values:
            swot[target_key] = [str(v) for v in values[:5] if str(v).strip()]
    report["swot"] = swot

    recommended_actions = ai_overlay.get("recommended_actions")
    if isinstance(recommended_actions, list) and recommended_actions:
        report["recommended_actions"] = [
            str(v) for v in recommended_actions[:5] if str(v).strip()
        ]

    ai_sections = ai_overlay.get("sections")
    if isinstance(ai_sections, list) and ai_sections:
        section_lookup = {
            str(section.get("survey_type_id") or ""): section
            for section in ai_sections
            if isinstance(section, dict)
        }

        merged_sections = []
        for section in report.get("sections") or []:
            key = str(section.get("survey_type_id") or "")
            ai_section = section_lookup.get(key)
            if not ai_section:
                merged_sections.append(section)
                continue

            merged = dict(section)
            for field in ("summary", "key_findings", "notable_quotes"):
                value = ai_section.get(field)
                if value:
                    merged[field] = value
            merged_sections.append(merged)

        report["sections"] = merged_sections

    return report


def generate_product_trial_report(*, round_id: int, generated_by_user_id: str) -> dict:
    """
    Build and persist a Product Trial report for the UT Lead project page.

    This function mutates only when called by a POST handler.
    """

    round_data = get_project_round_by_id(round_id=int(round_id))
    if not round_data:
        return {
            "success": False,
            "error": "round_not_found",
            "report": None,
        }

    answer_rows = get_product_trial_report_source_answers(round_id=int(round_id))
    if not answer_rows:
        return {
            "success": False,
            "error": "no_result_answers",
            "report": None,
        }

    kpis = get_round_product_kpis(round_id=int(round_id))
    survey_summaries = _build_survey_summaries(answer_rows)
    data_hash = _build_source_hash(answer_rows)

    report = _fallback_report(
        round_data=round_data,
        kpis=kpis,
        survey_summaries=survey_summaries,
        data_hash=data_hash,
    )

    ai_overlay = _ai_report_overlay(
        round_data=round_data,
        kpis=kpis,
        survey_summaries=survey_summaries,
    )
    report = _merge_ai_overlay(report, ai_overlay)

    project_id = str(round_data.get("ProjectID") or "").strip()
    if not project_id:
        return {
            "success": False,
            "error": "missing_project_id",
            "report": None,
        }

    upsert_product_trial_report(
        project_id=project_id,
        round_id=int(round_id),
        report=report,
        generated_by_user_id=generated_by_user_id,
        generation_version=REPORT_VERSION,
        data_hash=data_hash,
    )

    return {
        "success": True,
        "error": None,
        "report": report,
    }