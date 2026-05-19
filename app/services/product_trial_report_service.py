# app/services/product_trial_report_service.py

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from decimal import Decimal

from app.db.product_trial_reports import (
    get_product_trial_report_source_answers,
    upsert_product_trial_report,
)
from app.db.survey_kpis import get_round_product_kpis
from app.db.user_trial_lead import get_project_round_by_id
from app.services.ai_service import call_ai

REPORT_VERSION = "product_trial_report_historical_v1"


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _survey_display_name(row: dict) -> str:
    label = _normalize_text(row.get("SurveyTypeName"))
    return label.replace("_", " ") if label else "Survey"


def _answer_text(row: dict) -> str:
    return _normalize_text(row.get("AnswerValue"))


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


def _stable_response_group_id(row: dict) -> str:
    for key in ("DistributionID", "user_id", "SurveyID"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return f"answer:{row.get('AnswerID')}"


def _infer_question_positions(answer_rows: list[dict]) -> list[dict]:
    """
    survey_answers does not currently expose a dedicated QuestionOrder column.
    Infer the position from each participant distribution's AnswerID sequence.

    This mirrors Historical's question_position model and prevents repeated
    prompts like "Please elaborate" from collapsing into one question.
    """

    grouped_rows: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for row in answer_rows:
        key = (
            str(row.get("SurveyTypeID") or "unknown"),
            _stable_response_group_id(row),
        )
        grouped_rows[key].append(dict(row))

    positioned_rows = []
    for (_survey_type_id, _response_group_id), rows in grouped_rows.items():
        rows = sorted(rows, key=lambda r: int(r.get("AnswerID") or 0))
        for index, row in enumerate(rows, start=1):
            row["QuestionPosition"] = index
            positioned_rows.append(row)

    return sorted(
        positioned_rows,
        key=lambda row: (
            str(row.get("SurveyTypeID") or ""),
            int(row.get("QuestionPosition") or 0),
            _stable_response_group_id(row),
            int(row.get("AnswerID") or 0),
        ),
    )


def _as_historical_rows(rows: list[dict]) -> list[dict]:
    historical_rows = []

    for row in rows:
        historical_rows.append({
            "response_group_id": _stable_response_group_id(row),
            "question_position": int(row.get("QuestionPosition") or 0),
            "question_text": _normalize_text(row.get("QuestionText")) or "Untitled question",
            "answer_text": _answer_text(row),
        })

    return historical_rows


def _split_survey_rows(positioned_rows: list[dict]) -> list[dict]:
    survey_groups: dict[str, list[dict]] = defaultdict(list)

    for row in positioned_rows:
        survey_groups[str(row.get("SurveyTypeID") or "unknown")].append(row)

    surveys = []

    for survey_type_id, rows in survey_groups.items():
        first_row = rows[0] if rows else {}
        response_ids = {
            _stable_response_group_id(row)
            for row in rows
            if _stable_response_group_id(row)
        }
        question_positions = {
            int(row.get("QuestionPosition") or 0)
            for row in rows
            if int(row.get("QuestionPosition") or 0) > 0
        }

        surveys.append({
            "survey_type_id": survey_type_id,
            "survey_name": _survey_display_name(first_row),
            "response_count": len(response_ids),
            "answer_count": len(rows),
            "question_count": len(question_positions),
            "rows": rows,
        })

    return sorted(surveys, key=lambda survey: survey.get("survey_name") or "")


def _question_numeric_average(values: list[object]) -> float | None:
    numeric_values = []

    for value in values:
        text = _normalize_text(value)
        if not text:
            continue
        try:
            numeric_values.append(float(text))
        except ValueError:
            continue

    if not numeric_values:
        return None

    return round(sum(numeric_values) / len(numeric_values), 2)


def _normalize_section_for_storage(*, survey: dict, section: dict, section_index: int) -> dict:
    quant_questions = []

    for question in section.get("quant_questions") or []:
        values = [_normalize_text(value) for value in question.get("values") or [] if _normalize_text(value)]
        quant_questions.append({
            "question": _normalize_text(question.get("question")),
            "type": question.get("type") or "unknown",
            "values": values,
            "average": _question_numeric_average(values),
        })

    qual_question = section.get("qual_question")
    normalized_qual = None
    if qual_question:
        normalized_qual = {
            "question": _normalize_text(qual_question.get("question")),
            "values": [
                _normalize_text(value)
                for value in qual_question.get("values") or []
                if _normalize_text(value)
            ],
        }

    return {
        "section_index": section_index,
        "section_name": f"Section {section_index}",
        "survey_type_id": survey.get("survey_type_id"),
        "survey_name": survey.get("survey_name"),
        "response_count": survey.get("response_count") or 0,
        "quant_questions": quant_questions,
        "qual_question": normalized_qual,
        "swot_json": None,
        "swot": None,
    }


def _build_historical_style_sections(positioned_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Build Product Trial report sections by converting Product Trial answer rows
    into the exact row shape Historical uses, then delegating section formation
    to Historical's build_sections_from_rows helper.
    """

    from app.handlers.historical import build_sections_from_rows

    source_surveys = []
    report_sections = []
    global_section_index = 0

    for survey in _split_survey_rows(positioned_rows):
        source_surveys.append({
            "survey_type_id": survey.get("survey_type_id"),
            "survey_name": survey.get("survey_name"),
            "response_count": survey.get("response_count") or 0,
            "answer_count": survey.get("answer_count") or 0,
            "question_count": survey.get("question_count") or 0,
        })

        historical_rows = _as_historical_rows(survey.get("rows") or [])
        historical_rows = sorted(
            historical_rows,
            key=lambda row: (row["question_position"], row["response_group_id"]),
        )
        sections = build_sections_from_rows(historical_rows)

        for section in sections:
            global_section_index += 1
            report_sections.append(
                _normalize_section_for_storage(
                    survey=survey,
                    section=section,
                    section_index=global_section_index,
                )
            )

    return source_surveys, report_sections


def _build_source_hash(answer_rows: list[dict]) -> str:
    source_payload = []

    for row in answer_rows:
        source_payload.append({
            "AnswerID": row.get("AnswerID"),
            "SurveyID": row.get("SurveyID"),
            "DistributionID": row.get("DistributionID"),
            "QuestionID": row.get("QuestionID"),
            "QuestionText": row.get("QuestionText"),
            "QuestionPosition": row.get("QuestionPosition"),
            "AnswerValue": row.get("AnswerValue"),
            "AnswerNumeric": _json_safe(row.get("AnswerNumeric")),
            "UpdatedAt": _json_safe(row.get("UpdatedAt")),
        })

    encoded = json.dumps(source_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _extract_json_object(text: str) -> dict | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    if raw.startswith("```"):
        raw = raw.replace("```json", "", 1).replace("```", "").strip()

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


def _generate_section_name(section: dict) -> str | None:
    questions = [
        question.get("question")
        for question in section.get("quant_questions") or []
        if question.get("question")
    ]

    if not questions:
        qual = section.get("qual_question") or {}
        if qual.get("question"):
            questions = [qual.get("question")]

    if not questions:
        return None

    question_block = "\n".join(f"- {question}" for question in questions)

    prompt = f"""
You are naming a survey section.

Given the following questions, return a SHORT section name (2-4 words max).

Rules:
- No punctuation
- No full sentences
- Title case
- Focus on theme

Questions:
{question_block}

Return only the section name.
"""

    ai_result = call_ai(
        prompt=prompt,
        model="gpt-4o-mini",
        temperature=0.2,
        max_tokens=20,
    )

    if not ai_result.get("success"):
        return None

    name = (ai_result.get("response") or "").strip()
    if not name:
        return None

    return name.replace(".", "").strip()


def _generate_section_swot(section: dict) -> str | None:
    qual = section.get("qual_question") or {}
    raw_values = qual.get("values") or []
    answers = [str(value).strip() for value in raw_values if value and str(value).strip()]

    if not answers:
        return None

    answer_block = "\n".join(f"- {answer}" for answer in answers[:30])
    quant_questions = [
        question.get("question")
        for question in section.get("quant_questions") or []
        if question.get("question")
    ]
    context_block = "\n".join(f"- {question}" for question in quant_questions)

    prompt = f"""
        You are analyzing user feedback for a product survey section.

        SECTION QUESTIONS:
        {context_block}

        Return a SWOT analysis in JSON format:

        {{
        "strengths": ["..."],
        "weaknesses": ["..."],
        "opportunities": ["..."],
        "threats": ["..."]
        }}

        Definitions:
        - Strengths = what users consistently like
        - Weaknesses = what users consistently dislike
        - Opportunities = improvements or feature ideas
        - Threats = risks, frustrations that could lead to churn, or competitive disadvantages

        Rules:
        - Each item must be short (1 sentence max)
        - No markdown
        - No formatting symbols
        - No extra text outside JSON
        - Max 5 items per category

        IMPORTANT:
        Only consider feedback relevant to the SECTION QUESTIONS.

        User Responses:
        {answer_block}
        """

    ai_result = call_ai(
        prompt=prompt,
        model="gpt-4o-mini",
        temperature=0.3,
        max_tokens=800,
    )

    if not ai_result.get("success"):
        return None

    summary = (ai_result.get("response") or "").strip()
    return summary or None


def _apply_historical_ai_outputs(report: dict) -> dict:
    """
    Clone Historical's two-pass section treatment: first generate section names,
    then generate SWOT summaries from the qualitative follow-up values.
    """

    updated_sections = []
    name_success_count = 0
    summary_success_count = 0

    for section in report.get("sections") or []:
        updated = dict(section)

        generated_name = _generate_section_name(updated)
        if generated_name:
            updated["section_name"] = generated_name
            name_success_count += 1

        swot_json = _generate_section_swot(updated)
        if swot_json:
            updated["swot_json"] = swot_json
            updated["swot"] = _extract_json_object(swot_json)
            summary_success_count += 1

        updated_sections.append(updated)

    report["sections"] = updated_sections
    report.setdefault("metadata", {})
    report["metadata"]["generation_mode"] = "historical_report_clone"
    report["metadata"]["section_name_calls_succeeded"] = name_success_count
    report["metadata"]["section_summary_calls_succeeded"] = summary_success_count

    return report


def _build_executive_summary(*, round_data: dict, kpis: dict, source_surveys: list[dict], sections: list[dict]) -> str:
    total_responses = sum(survey.get("response_count") or 0 for survey in source_surveys)
    total_answers = sum(survey.get("answer_count") or 0 for survey in source_surveys)

    return (
        f"{_normalize_text(round_data.get('ProjectName')) or 'This product trial'} has "
        f"{len(sections)} Historical-style report section(s) built from "
        f"{len(source_surveys)} participant result survey(s), {total_responses} response records, "
        f"and {total_answers} stored answers. Current Product KPI signals show NPS at "
        f"{_format_metric(kpis.get('nps'))} and Ready for Sales at "
        f"{_format_metric(kpis.get('ready_for_sales'), suffix='%')}."
    )


def _build_report(*, round_data: dict, kpis: dict, source_surveys: list[dict], sections: list[dict], data_hash: str) -> dict:
    total_responses = sum(survey.get("response_count") or 0 for survey in source_surveys)
    total_answers = sum(survey.get("answer_count") or 0 for survey in source_surveys)

    return {
        "metadata": {
            "version": REPORT_VERSION,
            "generation_mode": "deterministic_historical_clone",
            "data_hash": data_hash,
        },
        "summary": {
            "executive_summary": _build_executive_summary(
                round_data=round_data,
                kpis=kpis,
                source_surveys=source_surveys,
                sections=sections,
            ),
            "response_count": total_responses,
            "answer_count": total_answers,
            "survey_count": len(source_surveys),
            "section_count": len(sections),
        },
        "kpis": kpis,
        "source_surveys": source_surveys,
        "sections": sections,
    }


def generate_product_trial_report(*, round_id: int, generated_by_user_id: str) -> dict:
    """
    Build and persist a Product Trial report for the UT Lead project page.

    This intentionally follows the Historical report model:
    - infer question_position
    - build sections from ordered rows
    - generate section names with the Historical prompt
    - generate section SWOT summaries with the Historical prompt

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

    positioned_answer_rows = _infer_question_positions(answer_rows)
    data_hash = _build_source_hash(positioned_answer_rows)
    source_surveys, sections = _build_historical_style_sections(positioned_answer_rows)
    kpis = get_round_product_kpis(round_id=int(round_id))

    report = _build_report(
        round_data=round_data,
        kpis=kpis,
        source_surveys=source_surveys,
        sections=sections,
        data_hash=data_hash,
    )
    report = _apply_historical_ai_outputs(report)

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