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


REPORT_VERSION = "product_trial_report_v2"


_STOPWORDS = {
    "about", "after", "again", "also", "because", "been", "being", "could",
    "device", "during", "experience", "from", "have", "into", "just", "like",
    "more", "most", "much", "need", "only", "product", "really", "should",
    "some", "than", "that", "their", "there", "these", "thing", "this",
    "trial", "using", "very", "were", "what", "when", "with", "would",
    "your", "you", "are", "the", "and", "for", "was", "did", "use", "used",
}

_PROFILE_QUESTION_PATTERNS = (
    r"^what is your name\??$",
    r"^what is your gender\??$",
    r"^what is your age",
    r"^what country",
    r"^where are you located",
    r"^where do you live",
    r"^what os do you use",
    r"^what operating system",
    r"^which operating system",
)

_FOLLOWUP_PATTERNS = (
    "elaborate",
    "tell us more",
    "tell us about",
    "explain",
    "reasoning",
    "why did you",
    "why do you",
    "please tell us more",
)

_NEGATIVE_SIGNAL_WORDS = {
    "bad", "bug", "bugs", "confusing", "crash", "difficult", "fail", "failed",
    "frustrating", "hard", "issue", "issues", "problem", "problems", "poor",
    "slow", "unstable", "worse", "worst", "uncomfortable", "unclear",
}

_POSITIVE_SIGNAL_WORDS = {
    "comfortable", "easy", "excellent", "good", "great", "helpful", "intuitive",
    "love", "loved", "nice", "premium", "solid", "smooth", "useful", "works",
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


def _question_text(row_or_text: dict | str | None) -> str:
    if isinstance(row_or_text, dict):
        return _normalize_text(row_or_text.get("QuestionText"))
    return _normalize_text(row_or_text)


def _looks_like_profile_question(question_text: str) -> bool:
    lowered = question_text.lower().strip()
    return any(re.search(pattern, lowered) for pattern in _PROFILE_QUESTION_PATTERNS)


def _looks_like_followup_question(question_text: str) -> bool:
    lowered = question_text.lower().strip()
    return any(pattern in lowered for pattern in _FOLLOWUP_PATTERNS)


def _looks_like_rating_question(question_text: str) -> bool:
    lowered = question_text.lower()
    return any(
        token in lowered
        for token in (
            "on a scale", "rate", "rating", "recommend", "satisfied", "satisfaction",
            "how easy", "how intuitive", "how effective", "how natural", "how helpful",
            "how often", "ready for sales", "nps",
        )
    )


def _numeric_answer_value(row: dict) -> float | None:
    numeric_value = _to_float(row.get("AnswerNumeric"))
    if numeric_value is not None:
        return numeric_value

    answer = _answer_text(row)
    if not answer:
        return None

    question = _question_text(row)
    if not _looks_like_rating_question(question):
        return None

    match = re.match(r"^\s*(\d+(?:\.\d+)?)\b", answer)
    if not match:
        return None

    return _to_float(match.group(1))


def _clean_section_name(value: str) -> str:
    text = _normalize_text(value)
    if not text:
        return "Section"

    bracket_match = re.search(r"\[([^\]]+)\]", text)
    if bracket_match and bracket_match.group(1).strip():
        return bracket_match.group(1).strip()

    replacements = [
        r"(?i)^on a scale of\s*\d+\s*-\s*\d+,?\s*",
        r"(?i)^overall,?\s*",
        r"(?i)^how would you rate\s*",
        r"(?i)^how do you rate\s*",
        r"(?i)^can you rate\s*",
        r"(?i)^how satisfied are you with\s*",
        r"(?i)^how easy was it to\s*",
        r"(?i)^how easily were you able to\s*",
        r"(?i)^how intuitive was it to\s*",
        r"(?i)^how intuitive were\s*",
        r"(?i)^how effective was\s*",
        r"(?i)^please\s*",
        r"(?i)^what was your\s*",
        r"(?i)^what is one thing we could\s*",
        r"(?i)^did you\s*",
        r"(?i)^were you able to\s*",
        r"(?i)^which\s*",
        r"(?i)^what\s*",
    ]

    for pattern in replacements:
        text = re.sub(pattern, "", text).strip()

    text = re.sub(r"\(\s*1\s*=.*?\)", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\?+$", "", text).strip()
    text = re.sub(r"\s+", " ", text)

    if not text:
        return "Product Experience"

    words = text.split()
    if len(words) > 6:
        text = " ".join(words[:6])

    return text[:1].upper() + text[1:]


def _section_fallback_name(questions: list[dict]) -> str:
    meaningful_questions = [
        question for question in questions
        if not _looks_like_followup_question(question.get("question") or "")
    ]
    anchor = meaningful_questions[0] if meaningful_questions else (questions[0] if questions else {})
    return _clean_section_name(anchor.get("question") or "Product Experience")


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


def _question_summary(question_text: str, rows: list[dict], *, question_order: int) -> dict:
    answer_values = [
        _answer_text(row)
        for row in rows
        if not _is_empty_answer(row.get("AnswerValue"))
    ]

    numeric_values = []
    for row in rows:
        numeric_value = _numeric_answer_value(row)
        if numeric_value is not None:
            numeric_values.append(numeric_value)

    answered_count = len(answer_values)
    numeric_ratio = (len(numeric_values) / answered_count) if answered_count else 0

    if numeric_values and numeric_ratio >= 0.7:
        score_max = 10 if max(numeric_values) > 5 else 5
        average_score = round(sum(numeric_values) / len(numeric_values), 2)
        return {
            "question": question_text,
            "question_order": question_order,
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
            "question_order": question_order,
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
        "question_order": question_order,
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
        for index, (_question_key, question_rows) in enumerate(question_order, start=1):
            question_text = _display_value(question_rows[0].get("QuestionText"), "Untitled question")
            question_summaries.append(
                _question_summary(
                    question_text,
                    question_rows,
                    question_order=index,
                )
            )

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


def _build_analysis_sections(survey_summaries: list[dict]) -> list[dict]:
    sections = []

    for survey in survey_summaries:
        current_questions: list[dict] = []
        current_metric_questions: list[dict] = []
        current_qualitative_questions: list[dict] = []
        section_index = 0

        def flush_current():
            nonlocal current_questions, current_metric_questions, current_qualitative_questions, section_index

            if not current_questions:
                return

            section_index += 1
            section_id = f"{survey.get('survey_type_id')}_{section_index}"
            section_name = _section_fallback_name(current_questions)
            response_count = max(
                [q.get("response_count") or 0 for q in current_questions] or [survey.get("response_count") or 0]
            )

            sections.append({
                "section_id": section_id,
                "survey_type_id": survey.get("survey_type_id"),
                "survey_name": survey.get("survey_name"),
                "section_index": section_index,
                "section_name": section_name,
                "response_count": response_count,
                "metric_questions": list(current_metric_questions),
                "qualitative_questions": list(current_qualitative_questions),
                "questions": list(current_questions),
                "summary": f"{section_name} contains {len(current_metric_questions)} quantitative/categorical signal(s) and {len(current_qualitative_questions)} qualitative follow-up question(s).",
                "key_findings": [],
                "notable_quotes": [],
                "swot": {
                    "strengths": [],
                    "weaknesses": [],
                    "opportunities": [],
                    "threats": [],
                },
            })

            current_questions = []
            current_metric_questions = []
            current_qualitative_questions = []

        for question in survey.get("questions") or []:
            text = question.get("question") or ""
            if _looks_like_profile_question(text):
                continue

            answer_type = question.get("answer_type")
            is_followup = _looks_like_followup_question(text)

            if answer_type == "qualitative" or is_followup:
                if not current_questions:
                    current_questions.append(question)
                    current_qualitative_questions.append(question)
                    flush_current()
                    continue

                current_questions.append(question)
                current_qualitative_questions.append(question)
                flush_current()
                continue

            current_questions.append(question)
            current_metric_questions.append(question)

        flush_current()

    return sections


def _section_numeric_findings(section: dict) -> tuple[list[str], list[str]]:
    strengths = []
    weaknesses = []

    for question in section.get("metric_questions") or []:
        if question.get("answer_type") != "numeric":
            continue

        average = question.get("average_score")
        scale_max = question.get("scale_max")
        if average is None or not scale_max:
            continue

        normalized = float(average) / float(scale_max)
        finding = (
            f"{question.get('question')} averaged "
            f"{_format_metric(average)}/{scale_max}."
        )

        if normalized >= 0.8:
            strengths.append(finding)
        elif normalized <= 0.6:
            weaknesses.append(finding)

    return strengths, weaknesses


def _section_categorical_findings(section: dict) -> list[str]:
    findings = []

    for question in section.get("metric_questions") or []:
        if question.get("answer_type") != "categorical":
            continue
        options = question.get("top_options") or []
        if not options:
            continue
        top = options[0]
        findings.append(
            f"{question.get('question')} was led by '{top.get('label')}' "
            f"at {top.get('count')} response(s)."
        )

    return findings


def _section_quotes(section: dict, *, limit: int = 4) -> list[str]:
    quotes = []
    for question in section.get("qualitative_questions") or []:
        for quote in question.get("notable_quotes") or []:
            if quote not in quotes:
                quotes.append(quote)
            if len(quotes) >= limit:
                return quotes
    return quotes


def _section_keyword_signals(section: dict) -> tuple[list[str], list[str]]:
    all_quotes = _section_quotes(section, limit=12)
    positive = []
    negative = []

    for quote in all_quotes:
        lowered = quote.lower()
        if any(word in lowered for word in _POSITIVE_SIGNAL_WORDS):
            positive.append(quote)
        if any(word in lowered for word in _NEGATIVE_SIGNAL_WORDS):
            negative.append(quote)

    return positive[:3], negative[:3]


def _fallback_section_analysis(section: dict) -> dict:
    strengths, weaknesses = _section_numeric_findings(section)
    categorical_findings = _section_categorical_findings(section)
    positive_quotes, negative_quotes = _section_keyword_signals(section)
    notable_quotes = _section_quotes(section, limit=4)

    key_findings = (strengths + weaknesses + categorical_findings)[:5]
    if not key_findings:
        key_findings = [
            f"{section.get('section_name')} needs AI review because no strong numeric or categorical signal was detected."
        ]

    swot_strengths = strengths[:3]
    if not swot_strengths and positive_quotes:
        swot_strengths = [positive_quotes[0]]
    if not swot_strengths:
        swot_strengths = ["No clear strength was detected from the structured signals yet."]

    swot_weaknesses = weaknesses[:3]
    if not swot_weaknesses and negative_quotes:
        swot_weaknesses = [negative_quotes[0]]
    if not swot_weaknesses:
        swot_weaknesses = ["No clear weakness was detected from the structured signals yet."]

    summary = (
        f"{section.get('section_name')} combines "
        f"{len(section.get('metric_questions') or [])} quantitative/categorical question(s) "
        f"with {len(section.get('qualitative_questions') or [])} qualitative follow-up question(s)."
    )

    return {
        **section,
        "summary": summary,
        "key_findings": key_findings,
        "notable_quotes": notable_quotes,
        "swot": {
            "strengths": swot_strengths,
            "weaknesses": swot_weaknesses,
            "opportunities": [
                "Use the paired follow-up responses to understand why this section scored the way it did."
            ],
            "threats": [
                "This section needs review if the qualitative comments contradict the score direction."
            ],
        },
    }


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


def _fallback_report(
    *,
    round_data: dict,
    kpis: dict,
    survey_summaries: list[dict],
    analysis_sections: list[dict],
    data_hash: str,
) -> dict:
    total_responses = sum(survey.get("response_count") or 0 for survey in survey_summaries)
    total_answers = sum(survey.get("answer_count") or 0 for survey in survey_summaries)
    analyzed_sections = [_fallback_section_analysis(section) for section in analysis_sections]

    strengths = []
    weaknesses = []
    opportunities = []
    threats = []

    for section in analyzed_sections:
        section_swot = section.get("swot") or {}
        strengths.extend(section_swot.get("strengths") or [])
        weaknesses.extend(section_swot.get("weaknesses") or [])
        opportunities.extend(section_swot.get("opportunities") or [])
        threats.extend(section_swot.get("threats") or [])

    if not strengths:
        strengths = ["No strong positive pattern was detected yet."]
    if not weaknesses:
        weaknesses = ["No clear negative pattern was detected yet."]
    if not opportunities:
        opportunities = ["Review paired score/comment sections to identify improvement opportunities."]
    if not threats:
        threats = ["Unmatched respondent attribution may limit user-profile-level slicing until review is completed."]

    ready_for_sales = kpis.get("ready_for_sales")
    nps = kpis.get("nps")

    executive_summary = (
        f"{_display_value(round_data.get('ProjectName'), 'This project')} has "
        f"{len(analyzed_sections)} analyzed report section(s) built from "
        f"{len(survey_summaries)} participant result survey(s), {total_responses} response records, "
        f"and {total_answers} stored answers. Current Product KPI signals show NPS at "
        f"{_format_metric(nps)} and Ready for Sales at {_format_metric(ready_for_sales, suffix='%')}."
    )

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
            "section_count": len(analyzed_sections),
        },
        "kpis": kpis,
        "swot": {
            "strengths": strengths[:5],
            "weaknesses": weaknesses[:5],
            "opportunities": opportunities[:5],
            "threats": threats[:5],
        },
        "recommended_actions": [
            "Review each report section as a score-plus-comment bundle, not as isolated survey questions.",
            "Prioritize sections where quantitative scores and qualitative comments point in opposite directions.",
            "Resolve unmatched response attribution before profile-based cuts or segment comparisons.",
        ],
        "sections": analyzed_sections,
        "source_surveys": survey_summaries,
    }


def _compact_ai_sections(*, analysis_sections: list[dict], max_questions_per_section: int = 8) -> list[dict]:
    compact = []

    for section in analysis_sections:
        compact_questions = []
        for question in (section.get("questions") or [])[:max_questions_per_section]:
            compact_questions.append({
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
            "section_id": section.get("section_id"),
            "survey_type_id": section.get("survey_type_id"),
            "survey_name": section.get("survey_name"),
            "fallback_section_name": section.get("section_name"),
            "response_count": section.get("response_count"),
            "questions": compact_questions,
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


def _ai_report_overlay(
    *,
    round_data: dict,
    kpis: dict,
    analysis_sections: list[dict],
) -> dict | None:
    compact_sections = _compact_ai_sections(analysis_sections=analysis_sections)

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
      "section_id": "must match one provided section_id exactly",
      "section_name": "short purposeful name, 2-5 words",
      "analysis_purpose": "what this question group is trying to understand",
      "summary": "one concise paragraph connecting scores/options to comments",
      "key_findings": ["..."],
      "notable_quotes": ["quote from provided data only"],
      "swot": {{
        "strengths": ["..."],
        "weaknesses": ["..."],
        "opportunities": ["..."],
        "threats": ["..."]
      }}
    }}
  ]
}}

Rules:
- Do not invent numbers.
- Do not invent quotes. Use only provided notable_quotes.
- Preserve every section_id exactly.
- Treat each section as a purposeful group of related questions.
- If a numeric/categorical question is followed by an elaborate/tell-us-more question, analyze them together.
- Section names should describe the product theme, not the raw survey name.
- Keep each SWOT list to 2-4 items per section.
- If evidence is weak, say that the signal needs review.

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

Grouped report sections:
{json.dumps(compact_sections, ensure_ascii=False, default=_json_safe)}
"""

    result = call_ai(
        prompt=prompt,
        system_prompt=(
            "You generate concise, evidence-grounded product trial reports for Logitech User Trials. "
            "You connect quantitative scores with nearby qualitative follow-up responses."
        ),
        model="gpt-4o-mini",
        temperature=0.2,
        max_tokens=3500,
    )

    if not result.get("success"):
        return None

    return _extract_json_object(result.get("response") or "")


def _clean_list(value, *, limit: int = 5) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value[:limit] if str(item).strip()]


def _merge_ai_overlay(base_report: dict, ai_overlay: dict | None) -> dict:
    if not ai_overlay:
        return base_report

    report = dict(base_report)
    report["metadata"] = dict(report.get("metadata") or {})
    report["metadata"]["generation_mode"] = "ai_assisted_section_analysis"

    summary = dict(report.get("summary") or {})
    if ai_overlay.get("executive_summary"):
        summary["executive_summary"] = str(ai_overlay.get("executive_summary") or "").strip()
    report["summary"] = summary

    swot = dict(report.get("swot") or {})
    for source_key, target_key in (
        ("strengths", "strengths"),
        ("weaknesses", "weaknesses"),
        ("opportunities", "opportunities"),
        ("threats", "threats"),
    ):
        values = _clean_list(ai_overlay.get(source_key), limit=5)
        if values:
            swot[target_key] = values
    report["swot"] = swot

    recommended_actions = _clean_list(ai_overlay.get("recommended_actions"), limit=5)
    if recommended_actions:
        report["recommended_actions"] = recommended_actions

    ai_sections = ai_overlay.get("sections")
    if isinstance(ai_sections, list) and ai_sections:
        section_lookup = {
            str(section.get("section_id") or ""): section
            for section in ai_sections
            if isinstance(section, dict)
        }

        merged_sections = []
        for section in report.get("sections") or []:
            section_id = str(section.get("section_id") or "")
            ai_section = section_lookup.get(section_id)
            if not ai_section:
                merged_sections.append(section)
                continue

            merged = dict(section)
            for field in ("section_name", "analysis_purpose", "summary"):
                value = ai_section.get(field)
                if value:
                    merged[field] = str(value).strip()

            for field in ("key_findings", "notable_quotes"):
                values = _clean_list(ai_section.get(field), limit=5)
                if values:
                    merged[field] = values

            ai_swot = ai_section.get("swot")
            if isinstance(ai_swot, dict):
                merged_swot = dict(merged.get("swot") or {})
                for key in ("strengths", "weaknesses", "opportunities", "threats"):
                    values = _clean_list(ai_swot.get(key), limit=4)
                    if values:
                        merged_swot[key] = values
                merged["swot"] = merged_swot

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
    analysis_sections = _build_analysis_sections(survey_summaries)
    data_hash = _build_source_hash(answer_rows)

    report = _fallback_report(
        round_data=round_data,
        kpis=kpis,
        survey_summaries=survey_summaries,
        analysis_sections=analysis_sections,
        data_hash=data_hash,
    )

    ai_overlay = _ai_report_overlay(
        round_data=round_data,
        kpis=kpis,
        analysis_sections=analysis_sections,
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