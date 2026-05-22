# app/services/bonus_survey_canonical_report_adapter.py

from __future__ import annotations

from app.utils.report_answer_values import split_countable_answer_value


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _question_key(*, question_hash: object, question_order: object) -> str:
    return f"{question_hash}__{question_order}"


def _is_numeric_value(value: object) -> bool:
    try:
        float(_clean_text(value))
        return True
    except (TypeError, ValueError):
        return False


def _is_open_text_answer(value: object) -> bool:
    text = _clean_text(value)
    if not text:
        return False

    if _is_numeric_value(text):
        return False

    if len(text.split()) >= 7:
        return True

    if len(text) >= 60:
        return True

    return False


def _answer_values_by_question(payload: dict) -> dict[str, list[str]]:
    values_by_question: dict[str, list[str]] = {}

    for response in payload.get("responses") or []:
        for answer in response.get("answers") or []:
            question_hash = answer.get("question_hash")
            question_order = answer.get("question_order")
            answer_text = _clean_text(answer.get("answer_text"))

            if not question_hash or question_order is None or not answer_text:
                continue

            key = _question_key(
                question_hash=question_hash,
                question_order=question_order,
            )
            values_by_question.setdefault(key, []).append(answer_text)

    return values_by_question


def _structured_section_by_key(structured: dict) -> dict[str, dict]:
    by_key = {}

    for section in structured.get("sections") or []:
        section_key = _clean_text(section.get("section_key") or section.get("section_name"))
        if section_key:
            by_key[section_key] = section

    return by_key


def _saved_section_by_key(saved_report: dict) -> dict[str, dict]:
    by_key = {}

    if not isinstance(saved_report, dict):
        return by_key

    for section in saved_report.get("sections") or []:
        if not isinstance(section, dict):
            continue

        section_key = _clean_text(
            section.get("section_key")
            or section.get("section_name")
            or section.get("display_name")
        )
        if section_key:
            by_key[section_key] = section

    return by_key


def _section_display_name(*, section_key: str, section_meta_by_key: dict, saved_section: dict | None) -> str:
    saved_section = saved_section if isinstance(saved_section, dict) else {}

    for key in ("display_name", "section_name"):
        value = _clean_text(saved_section.get(key))
        if value:
            return value

    metadata = section_meta_by_key.get(section_key) or {}
    value = _clean_text(metadata.get("display_name"))
    if value:
        return value

    if section_key:
        return section_key.replace("_", " ").replace("-", " ").title()

    return "Untitled Section"


def _build_participant_profile(*, structure_rows: list[dict], values_by_question: dict[str, list[str]]) -> dict:
    profile_questions = []

    profile_rows = sorted(
        [
            row for row in structure_rows
            if row.get("question_hash") and row.get("placement_type") == "profile"
        ],
        key=lambda row: int(row.get("question_order") or 0),
    )

    for row in profile_rows:
        key = _question_key(
            question_hash=row.get("question_hash"),
            question_order=row.get("question_order"),
        )
        values = values_by_question.get(key) or []

        counts: dict[str, int] = {}
        for raw_value in values:
            for value in split_countable_answer_value(raw_value):
                clean_value = _clean_text(value)
                if not clean_value:
                    continue
                counts[clean_value] = counts.get(clean_value, 0) + 1

        if not counts:
            continue

        options = [
            {"label": label, "count": count}
            for label, count in sorted(
                counts.items(),
                key=lambda item: (-int(item[1] or 0), item[0].lower()),
            )
        ]

        profile_questions.append({
            "question": _clean_text(row.get("question_text")) or "Profile question",
            "total_count": sum(option["count"] for option in options),
            "options": options,
        })

    return {
        "title": "Participant Profile / User Context",
        "questions": profile_questions,
    }


def _build_source_surveys(*, survey: dict, payload: dict, structure_rows: list[dict], values_by_question: dict[str, list[str]]) -> list[dict]:
    answered_values = sum(len(values) for values in values_by_question.values())
    question_count = len([
        row for row in structure_rows
        if row.get("question_hash") and row.get("placement_type") in {"profile", "section"}
    ])

    return [{
        "survey_name": survey.get("survey_title") or payload.get("survey_title") or "Bonus Survey",
        "response_count": payload.get("response_count") or 0,
        "question_count": question_count,
        "answer_count": answered_values,
        "source_file_name": "Bonus Survey results",
    }]


def _section_analysis_as_swot(saved_section: dict | None) -> dict:
    saved_section = saved_section if isinstance(saved_section, dict) else {}

    key_findings = saved_section.get("key_findings") or []
    qualitative_insights = saved_section.get("qualitative_insights") or []
    notable_quotes = saved_section.get("notable_quotes") or []

    if not isinstance(key_findings, list):
        key_findings = [key_findings] if key_findings else []
    if not isinstance(qualitative_insights, list):
        qualitative_insights = [qualitative_insights] if qualitative_insights else []
    if not isinstance(notable_quotes, list):
        notable_quotes = [notable_quotes] if notable_quotes else []

    if not key_findings and not qualitative_insights and not notable_quotes:
        return {}

    return {
        "strengths": [_clean_text(value) for value in key_findings if _clean_text(value)],
        "weaknesses": [],
        "opportunities": [_clean_text(value) for value in qualitative_insights if _clean_text(value)],
        "threats": [_clean_text(value) for value in notable_quotes if _clean_text(value)],
    }


def _build_sections(
    *,
    structure_rows: list[dict],
    structured: dict,
    values_by_question: dict[str, list[str]],
    section_meta_by_key: dict,
    saved_report: dict,
) -> list[dict]:
    structured_by_key = _structured_section_by_key(structured)
    saved_by_key = _saved_section_by_key(saved_report)

    avg_by_question_key = {}
    for structured_section in structured.get("sections") or []:
        for question in structured_section.get("questions") or []:
            q_hash = question.get("question_hash")
            q_order = question.get("question_order") or question.get("QuestionOrder")
            if q_hash and q_order is not None:
                avg_by_question_key[_question_key(question_hash=q_hash, question_order=q_order)] = question.get("avg")

    section_rows = sorted(
        [
            row for row in structure_rows
            if row.get("question_hash") and row.get("placement_type") == "section"
        ],
        key=lambda row: (
            int(row.get("section_order") or 0),
            int(row.get("question_order") or 0),
        ),
    )

    sections_by_key: dict[str, dict] = {}
    section_order = []

    for row in section_rows:
        section_key = _clean_text(row.get("section_key")) or "unknown"
        if section_key not in sections_by_key:
            saved_section = saved_by_key.get(section_key)
            structured_section = structured_by_key.get(section_key) or {}
            section_name = _section_display_name(
                section_key=section_key,
                section_meta_by_key=section_meta_by_key,
                saved_section=saved_section,
            )
            section_order.append(section_key)
            sections_by_key[section_key] = {
                "section_key": section_key,
                "section_name": section_name,
                "survey_name": "Bonus Survey",
                "report_group": "Survey Sections",
                "section_index": len(section_order),
                "quant_questions": [],
                "qual_question": None,
                "swot": _section_analysis_as_swot(saved_section),
                "average_score": structured_section.get("section_avg"),
            }

        question_key = _question_key(
            question_hash=row.get("question_hash"),
            question_order=row.get("question_order"),
        )
        values = values_by_question.get(question_key) or []
        if not values:
            continue

        question_text = _clean_text(row.get("question_text")) or "Untitled question"
        non_empty_values = [_clean_text(value) for value in values if _clean_text(value)]
        if not non_empty_values:
            continue

        numeric_values = [value for value in non_empty_values if _is_numeric_value(value)]
        open_text_values = [value for value in non_empty_values if _is_open_text_answer(value)]

        if open_text_values and len(open_text_values) >= max(2, int(len(non_empty_values) * 0.5)):
            existing_qual = sections_by_key[section_key].get("qual_question") or {}
            existing_values = existing_qual.get("values") or []
            sections_by_key[section_key]["qual_question"] = {
                "question": question_text if not existing_qual else existing_qual.get("question") or question_text,
                "values": existing_values + open_text_values,
            }
            continue

        q_type = "numeric" if numeric_values and len(numeric_values) == len(non_empty_values) else "categorical"
        question_payload = {
            "question": question_text,
            "type": q_type,
            "values": non_empty_values,
        }
        if question_key in avg_by_question_key:
            question_payload["average"] = avg_by_question_key.get(question_key)

        sections_by_key[section_key]["quant_questions"].append(question_payload)

    return [sections_by_key[key] for key in section_order if sections_by_key.get(key)]


def _build_executive_summary(saved_report: dict, payload: dict) -> str:
    summary = saved_report.get("summary") if isinstance(saved_report, dict) else {}
    summary = summary if isinstance(summary, dict) else {}

    key_patterns = [
        _clean_text(pattern)
        for pattern in summary.get("key_patterns") or []
        if _clean_text(pattern)
    ]

    response_count = payload.get("response_count")

    if key_patterns:
        return f"{response_count} response(s) analyzed. Key patterns: " + "; ".join(key_patterns)

    if response_count is not None:
        return f"{response_count} response(s) analyzed. No executive summary patterns have been generated yet."

    return ""


def _build_insights(saved_report: dict) -> list[dict]:
    insights = []

    if not isinstance(saved_report, dict):
        return insights

    for segment in saved_report.get("segments") or []:
        if not isinstance(segment, dict):
            continue

        segment_name = _clean_text(segment.get("segment")) or "Segment"
        for insight in segment.get("insights") or []:
            clean_insight = _clean_text(insight)
            if not clean_insight:
                continue

            insights.append({
                "title": segment_name,
                "section_name": "Segment Insights",
                "insight_type": "segment_insight",
                "impact": "medium",
                "sentiment": "mixed",
                "explanation": clean_insight,
                "evidence": [],
            })

    return insights


def build_bonus_canonical_report(
    *,
    survey: dict,
    payload: dict,
    structure_rows: list[dict],
    structured: dict,
    saved_report: dict,
    section_meta_by_key: dict,
) -> dict:
    """
    Adapt the current Bonus Survey / BSC report data into the shared canonical
    report object consumed by app.services.canonical_report_renderer.

    This is render-only. It does not generate analysis and does not persist.
    """

    values_by_question = _answer_values_by_question(payload)
    source_surveys = _build_source_surveys(
        survey=survey,
        payload=payload,
        structure_rows=structure_rows,
        values_by_question=values_by_question,
    )
    sections = _build_sections(
        structure_rows=structure_rows,
        structured=structured,
        values_by_question=values_by_question,
        section_meta_by_key=section_meta_by_key,
        saved_report=saved_report,
    )
    participant_profile = _build_participant_profile(
        structure_rows=structure_rows,
        values_by_question=values_by_question,
    )
    insights = _build_insights(saved_report)

    return {
        "metadata": {
            "version": "bonus_canonical_report_v1",
            "generation_mode": "bonus_survey_adapter",
        },
        "summary": {
            "executive_summary": _build_executive_summary(saved_report, payload),
            "response_count": payload.get("response_count") or 0,
            "answer_count": sum(survey.get("answer_count") or 0 for survey in source_surveys),
            "survey_count": 1,
            "section_count": len(sections),
            "insight_count": len(insights),
        },
        "kpis": {},
        "source_surveys": source_surveys,
        "participant_profile": participant_profile,
        "sections": sections,
        "insights": insights,
    }