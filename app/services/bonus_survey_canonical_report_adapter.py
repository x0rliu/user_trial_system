# app/services/bonus_survey_canonical_report_adapter.py

from __future__ import annotations

import re

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


def _is_qualitative_followup_question(question_text: object) -> bool:
    q = _clean_text(question_text).lower()
    if not q:
        return False

    qualitative_markers = (
        "can you elaborate",
        "please elaborate",
        "tell us more",
        "tell me more",
        "can you tell us why",
        "can you briefly tell us why",
        "why did you",
        "why do you",
        "why was",
        "why were",
        "what was the reason",
        "anything else",
        "additional feedback",
        "other feedback",
        "comments",
        "comment",
    )

    if any(marker in q for marker in qualitative_markers):
        return True

    return bool(re.search(r"\bwhy\??$", q))


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


def _is_explicit_multi_select_question(question_text: object) -> bool:
    q = _clean_text(question_text).lower()
    if not q:
        return False

    multi_select_markers = (
        "check all that apply",
        "select all that apply",
        "choose all that apply",
        "pick all that apply",
        "mark all that apply",
        "multiple answers",
        "multiple selections",
        "select any that apply",
        "check any that apply",
    )

    return any(marker in q for marker in multi_select_markers)


def _force_split_countable_answer_value(value: object) -> list[str]:
    raw = _clean_text(value)
    if not raw:
        return []

    if "," not in raw:
        return [raw]

    return [
        _clean_text(part)
        for part in raw.split(",")
        if _clean_text(part)
    ]


def _split_answer_value_for_question(*, question_text: object, value: object) -> list[str]:
    if _is_explicit_multi_select_question(question_text):
        return _force_split_countable_answer_value(value)

    return split_countable_answer_value(value)


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

        section_key = _clean_text(section.get("section_key"))
        if section_key:
            by_key[section_key] = section

    return by_key


def _section_display_name(*, section_key: str, section_meta_by_key: dict, saved_section: dict | None) -> str:
    section_key = _clean_text(section_key)
    saved_section = saved_section if isinstance(saved_section, dict) else {}

    metadata = section_meta_by_key.get(section_key) or {}
    metadata_name = _clean_text(metadata.get("display_name"))
    if metadata_name and not _is_generic_section_label(metadata_name):
        return metadata_name

    for key in ("display_name", "section_name"):
        value = _clean_text(saved_section.get(key))
        if value and not _is_generic_section_label(value):
            return value

    if section_key and not _is_generic_section_key(section_key):
        return section_key.replace("_", " ").replace("-", " ").title()

    return "Untitled Section"


def _is_generic_section_key(value: object) -> bool:
    text = _clean_text(value).lower().replace("-", "_").replace(" ", "_")
    return bool(re.fullmatch(r"section_?\d+", text))


def _is_generic_section_label(value: object) -> bool:
    text = _clean_text(value).lower().replace("-", " ").replace("_", " ")
    return bool(re.fullmatch(r"section\s+\d+", text))


def _should_regroup_generic_sections(section_rows: list[dict], section_meta_by_key: dict) -> bool:
    section_keys = [
        _clean_text(row.get("section_key"))
        for row in section_rows
        if _clean_text(row.get("section_key"))
    ]

    if not section_keys:
        return False

    if not all(_is_generic_section_key(section_key) for section_key in section_keys):
        return False

    for section_key in set(section_keys):
        metadata = section_meta_by_key.get(section_key) or {}
        display_name = _clean_text(metadata.get("display_name"))
        if display_name and not _is_generic_section_label(display_name):
            return False

    return True


def _group_section_rows_for_bonus_report(*, section_rows: list[dict], section_meta_by_key: dict) -> list[dict]:
    """
    Return render-time section groups for BSC canonical reports.

    Current structured sections are respected when they use meaningful section
    keys/names. Older Bonus Survey reports may have generic section_1,
    section_2, etc. In that case, rebuild display groups using the original
    survey cadence: 1-4 limited/numeric questions followed by their qualitative
    follow-up. This is a read-only adapter step; it does not mutate the saved
    structure or report.
    """

    if not _should_regroup_generic_sections(section_rows, section_meta_by_key):
        grouped_by_key: dict[str, dict] = {}
        ordered_keys = []

        for row in section_rows:
            section_key = _clean_text(row.get("section_key")) or "unknown"
            if section_key not in grouped_by_key:
                ordered_keys.append(section_key)
                grouped_by_key[section_key] = {
                    "group_key": section_key,
                    "source_section_keys": [],
                    "rows": [],
                }

            if section_key not in grouped_by_key[section_key]["source_section_keys"]:
                grouped_by_key[section_key]["source_section_keys"].append(section_key)
            grouped_by_key[section_key]["rows"].append(row)

        return [grouped_by_key[key] for key in ordered_keys]

    groups = []
    current_rows = []
    current_source_keys = []

    def close_group() -> None:
        if not current_rows:
            return

        group_index = len(groups) + 1
        groups.append({
            "group_key": f"semantic_section_{group_index}",
            "source_section_keys": list(current_source_keys),
            "rows": list(current_rows),
        })
        current_rows.clear()
        current_source_keys.clear()

    for row in section_rows:
        section_key = _clean_text(row.get("section_key")) or "unknown"
        current_rows.append(row)
        if section_key not in current_source_keys:
            current_source_keys.append(section_key)

        if _is_qualitative_followup_question(row.get("question_text")):
            close_group()

    close_group()
    return groups


def _merge_saved_sections_for_group(*, source_section_keys: list[str], saved_by_key: dict) -> dict:
    merged = {
        "key_findings": [],
        "qualitative_insights": [],
        "notable_quotes": [],
    }

    for section_key in source_section_keys or []:
        saved_section = saved_by_key.get(section_key)
        if not isinstance(saved_section, dict):
            continue

        for field in ("key_findings", "qualitative_insights", "notable_quotes"):
            for value in _listify_analysis_values(saved_section.get(field)):
                if value and value not in merged[field]:
                    merged[field].append(value)

    return merged


def _section_name_from_question_group(*, rows: list[dict], fallback_name: str) -> str:
    question_texts = [
        _clean_text(row.get("question_text"))
        for row in rows or []
        if _clean_text(row.get("question_text"))
        and not _is_qualitative_followup_question(row.get("question_text"))
    ]
    joined = " ".join(question_texts).lower()

    if not joined:
        return fallback_name

    if "support site" in joined and ("overall" in joined or "rate" in joined):
        return "Support Site Rating"

    if "navigation" in joined and "site map" in joined:
        return "Navigation & Site Map"

    if "navigation" in joined:
        return "Navigation"

    if "site map" in joined:
        return "Site Map"

    if any(marker in joined for marker in ("solve your issue", "answers to your issue", "native language", "phrasing")):
        return "Support Content Quality"

    if "content" in joined and "issue" in joined:
        return "Issue Resolution"

    if "read" in joined and "understand" in joined:
        return "Readability"

    first_question = question_texts[0]
    cleaned = re.sub(r"^(overall,?\s*)?how (easily|effective|would|easy|intuitive).*?\b(to|the|your)\b", "", first_question, flags=re.IGNORECASE).strip(" ?")
    cleaned = re.sub(r"^(how would you rate|please rate|can you rate)\s+", "", cleaned, flags=re.IGNORECASE).strip(" ?")

    words = [word for word in re.split(r"\s+", cleaned) if word]
    if 2 <= len(words) <= 5:
        return " ".join(word.capitalize() for word in words)

    return fallback_name


def _section_sort_key(*, section_key: str, fallback_order: object, section_meta_by_key: dict) -> tuple[int, str]:
    metadata = section_meta_by_key.get(section_key) or {}
    section_order = metadata.get("section_order")
    if section_order is None:
        section_order = fallback_order

    try:
        safe_order = int(section_order or 0)
    except (TypeError, ValueError):
        safe_order = 0

    return (safe_order, section_key)


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

        question_text = _clean_text(row.get("question_text")) or "Profile question"

        counts: dict[str, int] = {}
        for raw_value in values:
            for value in _split_answer_value_for_question(
                question_text=question_text,
                value=raw_value,
            ):
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
            "question": question_text,
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


def _listify_analysis_values(value: object) -> list[str]:
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]

    clean_value = _clean_text(value)
    return [clean_value] if clean_value else []


def _section_analysis_from_saved(saved_section: dict | None) -> dict:
    saved_section = saved_section if isinstance(saved_section, dict) else {}

    key_findings = _listify_analysis_values(saved_section.get("key_findings"))
    qualitative_insights = _listify_analysis_values(saved_section.get("qualitative_insights"))
    notable_quotes = _listify_analysis_values(saved_section.get("notable_quotes"))

    if not key_findings and not qualitative_insights and not notable_quotes:
        return {}

    return {
        "key_findings": key_findings,
        "qualitative_insights": qualitative_insights,
        "notable_quotes": notable_quotes,
    }


def _split_countable_values(*, question_text: object, values: list[str]) -> list[str]:
    split_values = []

    for raw_value in values or []:
        for value in _split_answer_value_for_question(
            question_text=question_text,
            value=raw_value,
        ):
            clean_value = _clean_text(value)
            if clean_value:
                split_values.append(clean_value)

    return split_values


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
            _section_sort_key(
                section_key=_clean_text(row.get("section_key")) or "unknown",
                fallback_order=row.get("section_order"),
                section_meta_by_key=section_meta_by_key,
            ),
            int(row.get("question_order") or 0),
        ),
    )

    grouped_sections = _group_section_rows_for_bonus_report(
        section_rows=section_rows,
        section_meta_by_key=section_meta_by_key,
    )

    sections = []

    for group_index, group in enumerate(grouped_sections, start=1):
        group_rows = group.get("rows") or []
        if not group_rows:
            continue

        group_key = _clean_text(group.get("group_key")) or f"section_{group_index}"
        source_section_keys = group.get("source_section_keys") or []
        primary_section_key = source_section_keys[0] if source_section_keys else group_key
        saved_section = saved_by_key.get(primary_section_key)
        structured_section = structured_by_key.get(primary_section_key) or {}
        fallback_name = _section_display_name(
            section_key=primary_section_key,
            section_meta_by_key=section_meta_by_key,
            saved_section=saved_section,
        )
        if _is_generic_section_label(fallback_name) or fallback_name == "Untitled Section":
            fallback_name = f"Section {group_index}"

        section_name = _section_name_from_question_group(
            rows=group_rows,
            fallback_name=fallback_name,
        )
        merged_analysis = _merge_saved_sections_for_group(
            source_section_keys=source_section_keys,
            saved_by_key=saved_by_key,
        )

        section_payload = {
            "section_key": group_key,
            "source_section_keys": source_section_keys,
            "section_name": section_name,
            "survey_name": "Bonus Survey",
            "report_group": "Survey Sections",
            "section_index": group_index,
            "quant_questions": [],
            "qual_question": None,
            "section_analysis": _section_analysis_from_saved(merged_analysis),
            "average_score": structured_section.get("section_avg"),
        }

        for row in group_rows:
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
            is_qualitative_followup = _is_qualitative_followup_question(question_text)

            if is_qualitative_followup or (
                open_text_values
                and len(open_text_values) >= max(2, int(len(non_empty_values) * 0.5))
                and not numeric_values
            ):
                existing_qual = section_payload.get("qual_question") or {}
                existing_values = existing_qual.get("values") or []
                section_payload["qual_question"] = {
                    "question": question_text if not existing_qual else existing_qual.get("question") or question_text,
                    "values": existing_values + non_empty_values,
                }
                continue

            if numeric_values and len(numeric_values) == len(non_empty_values):
                question_payload = {
                    "question": question_text,
                    "type": "numeric",
                    "values": non_empty_values,
                }
            else:
                question_payload = {
                    "question": question_text,
                    "type": "categorical",
                    "values": _split_countable_values(
                        question_text=question_text,
                        values=non_empty_values,
                    ),
                }

            if question_key in avg_by_question_key:
                question_payload["average"] = avg_by_question_key.get(question_key)

            section_payload["quant_questions"].append(question_payload)

        sections.append(section_payload)

    return sections


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
    if not isinstance(saved_report, dict):
        return []

    grouped: dict[str, dict] = {}

    for segment in saved_report.get("segments") or []:
        if not isinstance(segment, dict):
            continue

        segment_name = _clean_text(segment.get("segment")) or "Segment"
        group_key = segment_name.lower()
        if group_key not in grouped:
            grouped[group_key] = {
                "title": segment_name,
                "items": [],
            }

        for insight in segment.get("insights") or []:
            clean_insight = _clean_text(insight)
            if clean_insight and clean_insight not in grouped[group_key]["items"]:
                grouped[group_key]["items"].append(clean_insight)

    insights = []
    for group in grouped.values():
        items = group.get("items") or []
        if not items:
            continue

        if len(items) == 1:
            explanation = items[0]
            evidence = []
        else:
            explanation = "Multiple related observations were found for this segment."
            evidence = items

        insights.append({
            "title": group.get("title") or "Segment",
            "section_name": "Segment Insights",
            "insight_type": "segment_insight",
            "impact": "medium",
            "sentiment": "mixed",
            "explanation": explanation,
            "evidence": evidence,
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
            "version": "bonus_canonical_report_v2",
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