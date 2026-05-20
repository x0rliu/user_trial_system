# app/services/product_trial_report_service.py

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from decimal import Decimal

from app.db.product_trial_reports import (
    get_product_trial_report,
    get_product_trial_report_source_answers,
    upsert_product_trial_report,
)
from app.db.survey_kpis import get_round_product_kpis
from app.db.user_trial_lead import get_project_round_by_id
from app.services.ai_service import call_ai

REPORT_VERSION = "product_trial_report_historical_v1"


_DB_METADATA_KEYS = {
    "report_id",
    "project_id",
    "round_id",
    "generated_by_user_id",
    "generation_version",
    "created_at",
    "updated_at",
}


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


def _question_value_profile(values: list[object]) -> dict:
    cleaned = [_normalize_text(value) for value in values if _normalize_text(value)]
    numeric_values = []

    for value in cleaned:
        try:
            numeric_values.append(float(value))
        except ValueError:
            pass

    unique_values = {value for value in cleaned}

    return {
        "cleaned_count": len(cleaned),
        "unique_count": len(unique_values),
        "numeric_count": len(numeric_values),
        "numeric_ratio": (len(numeric_values) / len(cleaned)) if cleaned else 0,
    }


def _is_followup_question(question_text: object) -> bool:
    q = _normalize_text(question_text).lower()
    if not q:
        return False

    followup_phrases = [
        "can you elaborate",
        "please elaborate",
        "tell us more",
        "can you tell us more",
        "can you let us know more",
        "let us know more",
        "briefly, can you tell us why",
        "can you briefly tell us why",
        "why you rated it",
        "why you rated this",
        "why did you rate",
    ]

    return any(phrase in q for phrase in followup_phrases)


def _classify_product_trial_question(question_text: object, values: list[object]) -> str:
    q = _normalize_text(question_text).lower()

    if _is_followup_question(q):
        return "qualitative"

    profile = _question_value_profile(values)
    if profile["cleaned_count"] == 0:
        return "qualitative"

    if profile["numeric_ratio"] >= 0.7:
        return "numeric"

    if profile["unique_count"] <= 12 and profile["cleaned_count"] >= 5:
        return "categorical"

    return "qualitative"


def _section_question_texts(section: dict) -> list[str]:
    questions = [
        _normalize_text(question.get("question"))
        for question in section.get("quant_questions") or []
        if _normalize_text(question.get("question"))
    ]

    qual = section.get("qual_question") or {}
    qual_text = _normalize_text(qual.get("question"))
    if qual_text:
        questions.append(qual_text)

    return questions


def _clean_section_name(value: object) -> str:
    name = _normalize_text(value)
    if not name:
        return ""

    name = re.sub(r"^```(?:text)?", "", name, flags=re.IGNORECASE).strip()
    name = name.replace("```", "").strip()
    name = name.strip(" .:-—–_\"'")
    name = re.sub(r"\s+", " ", name)

    if not name:
        return ""

    # Reject sentence-like AI output, but do not chop deterministic names.
    if len(name.split()) > 8 and not any(char in name for char in "[/&]"):
        return ""

    return name[:90]


def _canonical_section_name_from_questions(questions: list[str]) -> str | None:
    joined = " ".join(questions).lower()

    if "overall" in joined and "how would you rate" in joined and ("this product" in joined or "this device" in joined):
        return "Star Rating"

    if "why" in joined and "rated" in joined and ("this way" in joined or "that way" in joined):
        return "Star Rating"

    if "recommend this product to a colleague or friend" in joined:
        return "Net Promoter Score"

    if "net promoter" in joined or "nps" in joined:
        return "Net Promoter Score"

    if "ready for sales" in joined:
        return "Ready For Sales"

    if "g hub" in joined and ("rate" in joined or "experience" in joined):
        return "Software Rating"

    if "software" in joined and ("rate" in joined or "rating" in joined or "experience" in joined):
        return "Software Rating"

    return None


def _mapped_section_name_from_questions(questions: list[str]) -> str | None:
    joined = " ".join(questions).lower()
    canonical = _canonical_section_name_from_questions(questions)
    if canonical:
        return canonical

    mappings = [
        (("look and feel of the box", "eco-friendliness of the box"), "Box Appearance"),
        (("unboxing", "secured properly"), "Unboxing Experience"),
        (("components", "placement inside the package"), "Component Placement"),
        (("included cable", "cable length"), "Cable Experience"),
        (("quick start guide", "successfully set up"), "Quick Start Guide"),
        (("color of the microphone", "design of the microphone"), "Microphone Design"),
        (("size of the device", "weight of this product"), "Device Size And Weight"),
        (("lcd screen", "knob"), "LCD Screen And Knob"),
        (("material used feels premium", "comfortable to the touch"), "Materials And Comfort"),
        (("connect your device", "record yourself"), "Device Connection"),
        (("changing the settings", "which experience did you prefer"), "Device Settings"),
        (("customize your polar pattern", "change the polar pattern"), "Polar Pattern Customization"),
        (("which polar pattern", "most useful"), "Polar Pattern Use"),
        (("adjust the gain", "denoiser"), "Gain And EQ Controls"),
        (("recording videos", "live streaming", "calls/meetings"), "Experience Improvements"),
        (("mount your microphone", "ideal position"), "Microphone Placement"),
        (("microphone audio quality", "assess the audio quality"), "Audio Quality"),
        (("blue voice", "audio effects", "controls"), "Blue Voice Controls"),
        (("functional hurdles", "quality issues"), "Functional Issues"),
    ]

    for required_terms, section_name in mappings:
        if all(term in joined for term in required_terms):
            return section_name

    return None


def _question_is_profile(question_text: object) -> bool:
    q = _normalize_text(question_text).lower()
    if not q:
        return True

    profile_patterns = [
        r"^what is your name",
        r"^what is your gender",
        r"^what is your age",
        r"^where are you",
        r"^where do you live",
        r"^what country",
        r"^what os",
        r"^which os",
        r"operating system",
        r"what platforms? (do|to) you stream",
        r"what platform",
        r"have you ever used an external microphone before",
    ]

    return any(re.search(pattern, q) for pattern in profile_patterns)


def _question_is_admin_or_upload(question_text: object) -> bool:
    q = _normalize_text(question_text).lower()
    if not q:
        return True

    admin_patterns = [
        r"^do you agree",
        r"agree to be contacted",
        r"user token",
        r"please upload",
        r"videos / photos",
        r"photo",
        r"what price would",
        r"at what price",
    ]

    return any(re.search(pattern, q) for pattern in admin_patterns)


def _question_is_reportable_candidate(question_text: object) -> bool:
    return not _question_is_profile(question_text) and not _question_is_admin_or_upload(question_text)


def _clean_values(values: list[object]) -> list[str]:
    return [_normalize_text(value) for value in values or [] if _normalize_text(value)]


def _make_quant_question(question_text: object, values: list[object], q_type: str) -> dict:
    cleaned_values = _clean_values(values)
    return {
        "question": _normalize_text(question_text),
        "type": q_type,
        "values": cleaned_values,
        "average": _question_numeric_average(cleaned_values),
    }


def _make_qual_question(question_text: object, values: list[object]) -> dict:
    return {
        "question": _normalize_text(question_text),
        "values": _clean_values(values),
    }


def _section_has_usable_qualitative_signal(section: dict) -> bool:
    qual = section.get("qual_question") or {}
    return bool(_clean_values(qual.get("values") or []))


def _section_is_canonical_kpi(section: dict) -> bool:
    return bool(_canonical_section_name_from_questions(_section_question_texts(section)))


def _section_should_be_reported(section: dict) -> bool:
    quant_questions = section.get("quant_questions") or []
    if not quant_questions:
        return False

    if _section_is_canonical_kpi(section):
        return True

    if not _section_has_usable_qualitative_signal(section):
        return False

    return any(_question_is_reportable_candidate(q.get("question")) for q in quant_questions)


def _report_group_for_section(section: dict) -> str:
    name = _normalize_text(section.get("section_name")).lower()
    survey_name = _normalize_text(section.get("survey_name")).lower()
    joined = " ".join(_section_question_texts(section)).lower()

    if _section_is_canonical_kpi(section) or name in {
        "star rating",
        "net promoter score",
        "ready for sales",
        "software rating",
    }:
        return "KPIs"

    oobe_markers = [
        "box",
        "package",
        "packaging",
        "unbox",
        "unboxing",
        "component placement",
        "included cable",
        "quick start guide",
        "setup guide",
    ]
    if any(marker in name or marker in joined for marker in oobe_markers):
        return "OOBE"

    if "survey 1" in survey_name or "first impression" in survey_name or "oobe" in survey_name:
        return "First Impressions"

    if "survey 2" in survey_name or "experience" in survey_name or "usage" in survey_name or "kpi" in survey_name:
        return "Usage"

    return "Other"


def _section_group_sort_key(section: dict, source_order: int) -> tuple[int, int]:
    group_order = {
        "KPIs": 10,
        "OOBE": 20,
        "First Impressions": 30,
        "Usage": 40,
        "Other": 90,
    }
    group = _report_group_for_section(section)
    return (group_order.get(group, 90), source_order)


def _fallback_section_name_from_questions(questions: list[str]) -> str | None:
    if not questions:
        return None

    mapped = _mapped_section_name_from_questions(questions)
    if mapped:
        return mapped

    text = questions[0]

    bracket_match = re.search(r"\[([^\]]+)\]", text)
    if bracket_match and bracket_match.group(1).strip():
        return _clean_section_name(bracket_match.group(1).strip())

    replacements = [
        r"(?i)^on a scale of\s*\d+\s*-\s*\d+,?\s*",
        r"(?i)^overall,?\s*",
        r"(?i)^how would you rate\s*",
        r"(?i)^how do you rate\s*",
        r"(?i)^how would you describe\s*",
        r"(?i)^how do you feel about\s*",
        r"(?i)^how easy was it to\s*",
        r"(?i)^how intuitive was it to\s*",
        r"(?i)^how intuitive were\s*",
        r"(?i)^how satisfied are you with\s*",
        r"(?i)^please rate\s*",
        r"(?i)^please\s*",
        r"(?i)^can you briefly tell us why\s*",
        r"(?i)^can you tell us why\s*",
        r"(?i)^tell us why\s*",
        r"(?i)^did you\s*",
        r"(?i)^were you able to\s*",
    ]

    for pattern in replacements:
        text = re.sub(pattern, "", text).strip()

    text = re.sub(r"\(\s*1\s*=.*?\)", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\?+$", "", text).strip()
    text = re.sub(r"\s+", " ", text)

    if not text:
        return None

    return _clean_section_name(text.title()) or None


def _normalize_section_for_storage(*, survey: dict, section: dict, section_index: int) -> dict:
    quant_questions = []

    for question in section.get("quant_questions") or []:
        question_text = _normalize_text(question.get("question"))
        if not _question_is_reportable_candidate(question_text):
            continue

        quant_questions.append(
            _make_quant_question(
                question_text,
                question.get("values") or [],
                question.get("type") or "unknown",
            )
        )

    qual_question = None
    if section.get("qual_question"):
        qual_question = _make_qual_question(
            section["qual_question"].get("question"),
            section["qual_question"].get("values") or [],
        )

    normalized_section = {
        "section_index": section_index,
        "section_name": f"Section {section_index}",
        "report_group": "Other",
        "survey_type_id": survey.get("survey_type_id"),
        "survey_name": survey.get("survey_name"),
        "response_count": survey.get("response_count") or 0,
        "quant_questions": quant_questions,
        "qual_question": qual_question,
        "swot_json": None,
        "swot": None,
    }

    mapped_name = _mapped_section_name_from_questions(_section_question_texts(normalized_section))
    if mapped_name:
        normalized_section["section_name"] = mapped_name

    normalized_section["report_group"] = _report_group_for_section(normalized_section)
    return normalized_section


def _build_questions_by_position(rows: list[dict]) -> list[dict]:
    question_map: dict[int, dict] = {}

    for row in rows:
        position = int(row.get("QuestionPosition") or 0)
        if position <= 0:
            continue

        if position not in question_map:
            question_map[position] = {
                "position": position,
                "question": _normalize_text(row.get("QuestionText")) or "Untitled question",
                "values": [],
            }

        question_map[position]["values"].append(_answer_text(row))

    return [question_map[position] for position in sorted(question_map)]


def _build_product_trial_sections_for_survey(survey: dict, *, starting_index: int) -> list[dict]:
    """
    Product Trial surveys use an explicit section rhythm:
    - normal section = 2-4 quant/categorical questions followed by 1 qualitative question
    - KPI section = 1 quant/categorical question followed by 1 qualitative question
    - profile/setup/upload/price questions are not report sections
    """

    sections = []
    current_quant_questions = []
    section_index = starting_index

    def close_section(qual_question: dict | None):
        nonlocal current_quant_questions, section_index

        if not current_quant_questions:
            return

        raw_section = {
            "quant_questions": list(current_quant_questions),
            "qual_question": qual_question,
        }
        section_index += 1
        normalized = _normalize_section_for_storage(
            survey=survey,
            section=raw_section,
            section_index=section_index,
        )

        if _section_should_be_reported(normalized):
            sections.append(normalized)

        current_quant_questions = []

    for question in _build_questions_by_position(survey.get("rows") or []):
        question_text = question.get("question")
        values = question.get("values") or []

        if not _question_is_reportable_candidate(question_text):
            continue

        q_type = _classify_product_trial_question(question_text, values)

        if q_type in {"numeric", "categorical"}:
            current_quant_questions.append({
                "question": question_text,
                "values": values,
                "type": q_type,
            })
            continue

        if q_type == "qualitative":
            close_section({
                "question": question_text,
                "values": values,
            })

    # Drop non-KPI trailing quant-only sections. A Product Trial report section
    # needs the paired qualitative explanation to be analytically useful.
    for trailing in list(current_quant_questions):
        raw_section = {
            "quant_questions": [trailing],
            "qual_question": None,
        }
        normalized = _normalize_section_for_storage(
            survey=survey,
            section=raw_section,
            section_index=section_index + 1,
        )
        if _section_is_canonical_kpi(normalized):
            section_index += 1
            sections.append(normalized)

    return sections


def _renumber_report_sections(sections: list[dict]) -> list[dict]:
    cleaned_sections = []

    for source_order, section in enumerate(sections or [], start=1):
        normalized = dict(section)
        mapped_name = _mapped_section_name_from_questions(_section_question_texts(normalized))
        if mapped_name:
            normalized["section_name"] = mapped_name
        normalized["report_group"] = _report_group_for_section(normalized)

        if not _section_should_be_reported(normalized):
            continue

        normalized["_source_order"] = source_order
        cleaned_sections.append(normalized)

    cleaned_sections.sort(key=lambda section: _section_group_sort_key(section, int(section.get("_source_order") or 0)))

    for index, section in enumerate(cleaned_sections, start=1):
        section["section_index"] = index
        section.pop("_source_order", None)
        mapped_name = _mapped_section_name_from_questions(_section_question_texts(section))
        if mapped_name:
            section["section_name"] = mapped_name
        elif _normalize_text(section.get("section_name")).lower().startswith("section "):
            section["section_name"] = f"Section {index}"
        section["report_group"] = _report_group_for_section(section)

    return cleaned_sections


def _build_historical_style_sections(positioned_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Build Product Trial report sections with the same output shape as Historical,
    but with Product Trial's stronger survey contract:
    sections are quant/categorical runs closed by the next qualitative follow-up.
    """

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

        survey_sections = _build_product_trial_sections_for_survey(
            survey,
            starting_index=global_section_index,
        )

        for section in survey_sections:
            global_section_index += 1
            section["section_index"] = global_section_index
            section["report_group"] = _report_group_for_section(section)
            if _normalize_text(section.get("section_name")).lower().startswith("section "):
                mapped_name = _mapped_section_name_from_questions(_section_question_texts(section))
                if mapped_name:
                    section["section_name"] = mapped_name
                else:
                    section["section_name"] = f"Section {global_section_index}"
            report_sections.append(section)

    return source_surveys, _renumber_report_sections(report_sections)


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
    questions = _section_question_texts(section)
    if not questions:
        return None

    mapped_name = _mapped_section_name_from_questions(questions)
    if mapped_name:
        return mapped_name

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

    if ai_result.get("success"):
        generated_name = _clean_section_name(
            ai_result.get("content")
            or ai_result.get("response")
            or ""
        )
        if generated_name:
            return generated_name

    return _fallback_section_name_from_questions(questions)


def _debug_product_trial_summary(message: str, **fields) -> None:
    """Temporary server-console diagnostics for Product Trial summary generation."""

    try:
        field_text = " ".join(
            f"{key}={repr(value)}"
            for key, value in fields.items()
        )
        if field_text:
            print(f"[PT_SUMMARY_DEBUG] {message} | {field_text}", flush=True)
        else:
            print(f"[PT_SUMMARY_DEBUG] {message}", flush=True)
    except Exception:
        print("[PT_SUMMARY_DEBUG] debug print failed", flush=True)


def _generate_section_swot(section: dict) -> str | None:
    """
    Product Trial deliberately reuses Historical's SWOT analysis method.

    Do not maintain a separate Product Trial SWOT prompt here. Historical is
    the source of truth for section-level SWOT analysis behavior.
    """

    from app.handlers.historical import generate_historical_section_swot_summary

    return generate_historical_section_swot_summary(
        section=section,
        debug_callback=_debug_product_trial_summary,
    )


def _debug_product_trial_summary(message: str, **fields) -> None:
    """Temporary server-console diagnostics for Product Trial summary generation."""

    try:
        field_text = " ".join(
            f"{key}={repr(value)}"
            for key, value in fields.items()
        )
        if field_text:
            print(f"[PT_SUMMARY_DEBUG] {message} | {field_text}", flush=True)
        else:
            print(f"[PT_SUMMARY_DEBUG] {message}", flush=True)
    except Exception:
        print("[PT_SUMMARY_DEBUG] debug print failed", flush=True)


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
    # Product Trial executive summaries should be analytic, not a restatement
    # of counts and KPI values already shown elsewhere on the page. Leave this
    # empty until a dedicated summary generation step creates real synthesis.
    return ""


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


def _storage_safe_report(report: dict) -> dict:
    cleaned = dict(report or {})
    metadata = dict(cleaned.get("metadata") or {})

    for key in _DB_METADATA_KEYS:
        metadata.pop(key, None)

    cleaned["metadata"] = metadata
    return cleaned


def _save_existing_product_trial_report(*, round_id: int, generated_by_user_id: str, report: dict) -> dict:
    round_data = get_project_round_by_id(round_id=int(round_id))
    if not round_data:
        return {
            "success": False,
            "error": "round_not_found",
            "report": None,
        }

    project_id = str(round_data.get("ProjectID") or "").strip()
    if not project_id:
        return {
            "success": False,
            "error": "missing_project_id",
            "report": None,
        }

    safe_report = _storage_safe_report(report)
    metadata = safe_report.get("metadata") or {}

    upsert_product_trial_report(
        project_id=project_id,
        round_id=int(round_id),
        report=safe_report,
        generated_by_user_id=generated_by_user_id,
        generation_version=REPORT_VERSION,
        data_hash=metadata.get("data_hash"),
    )

    return {
        "success": True,
        "error": None,
        "report": safe_report,
    }


def _load_existing_product_trial_report(*, round_id: int) -> dict:
    report_result = get_product_trial_report(round_id=int(round_id))
    if not report_result.get("success"):
        return {
            "success": False,
            "error": report_result.get("error") or "report_not_found",
            "report": None,
        }

    report = report_result.get("report")
    if not isinstance(report, dict):
        return {
            "success": False,
            "error": "invalid_report_shape",
            "report": None,
        }

    return {
        "success": True,
        "error": None,
        "report": report,
    }


def generate_product_trial_section_names(*, round_id: int, generated_by_user_id: str) -> dict:
    loaded = _load_existing_product_trial_report(round_id=int(round_id))
    if not loaded.get("success"):
        return loaded

    report = loaded["report"]
    updated_sections = []
    success_count = 0

    for section in _renumber_report_sections(report.get("sections") or []):
        updated = dict(section)
        generated_name = _generate_section_name(updated)

        if generated_name:
            updated["section_name"] = generated_name
            success_count += 1

        updated_sections.append(updated)

    report["sections"] = updated_sections
    report.setdefault("metadata", {})
    report["metadata"]["generation_mode"] = "historical_report_clone"
    report["metadata"]["section_name_calls_succeeded"] = success_count

    return _save_existing_product_trial_report(
        round_id=int(round_id),
        generated_by_user_id=generated_by_user_id,
        report=report,
    )


def generate_product_trial_section_summaries(*, round_id: int, generated_by_user_id: str) -> dict:
    loaded = _load_existing_product_trial_report(round_id=int(round_id))
    if not loaded.get("success"):
        _debug_product_trial_summary(
            "load_existing_report_failed",
            round_id=round_id,
            error=loaded.get("error"),
        )
        return loaded

    report = loaded["report"]
    _debug_product_trial_summary(
        "summary_generation_started",
        round_id=round_id,
        saved_sections=len(report.get("sections") or []),
    )

    # Product Trial summaries must use the same Historical SWOT helper, but the
    # section payload must first be rebuilt from DB-backed survey_answers. The
    # saved report JSON can be stale because the PT report builder has changed
    # during this implementation pass. DB rows are the source of truth.
    answer_rows = get_product_trial_report_source_answers(round_id=int(round_id))
    _debug_product_trial_summary(
        "source_answers_loaded",
        round_id=round_id,
        answer_rows=len(answer_rows or []),
    )

    if answer_rows:
        positioned_answer_rows = _infer_question_positions(answer_rows)
        source_surveys, rebuilt_sections = _build_historical_style_sections(positioned_answer_rows)

        _debug_product_trial_summary(
            "sections_rebuilt_from_db",
            round_id=round_id,
            positioned_rows=len(positioned_answer_rows),
            source_surveys=len(source_surveys),
            rebuilt_sections=len(rebuilt_sections),
        )

        if rebuilt_sections:
            report["source_surveys"] = source_surveys
            report["sections"] = rebuilt_sections

            report.setdefault("summary", {})
            report["summary"].update({
                "response_count": sum(survey.get("response_count") or 0 for survey in source_surveys),
                "answer_count": sum(survey.get("answer_count") or 0 for survey in source_surveys),
                "survey_count": len(source_surveys),
                "section_count": len(rebuilt_sections),
            })

            report.setdefault("metadata", {})
            report["metadata"]["data_hash"] = _build_source_hash(positioned_answer_rows)
            report["metadata"]["rebuilt_before_summary_generation"] = True
        else:
            _debug_product_trial_summary(
                "no_rebuilt_sections",
                round_id=round_id,
            )

    updated_sections = []
    success_count = 0
    sections_with_qual = 0
    sections_with_qual_answers = 0

    normalized_sections = _renumber_report_sections(report.get("sections") or [])
    _debug_product_trial_summary(
        "sections_ready_for_summary",
        round_id=round_id,
        normalized_sections=len(normalized_sections),
    )

    for index, section in enumerate(normalized_sections, start=1):
        updated = dict(section)

        qual = updated.get("qual_question") or {}
        qual_values = [
            _normalize_text(value)
            for value in qual.get("values") or []
            if _normalize_text(value)
        ]

        if qual:
            sections_with_qual += 1
        if qual_values:
            sections_with_qual_answers += 1

        _debug_product_trial_summary(
            "section_summary_attempt",
            index=index,
            section_name=updated.get("section_name"),
            report_group=updated.get("report_group"),
            quant_questions=len(updated.get("quant_questions") or []),
            has_qual=bool(qual),
            qual_answer_count=len(qual_values),
        )

        swot_json = _generate_section_swot(updated)
        parsed_swot = _extract_json_object(swot_json) if swot_json else None

        _debug_product_trial_summary(
            "section_summary_result",
            index=index,
            section_name=updated.get("section_name"),
            swot_text_length=len(swot_json or ""),
            parsed=bool(parsed_swot),
        )

        # Reuse Historical's generation behavior: any non-empty AI response is
        # worth preserving. Parsing supports the current renderer, but parsing
        # failure should not make the generation look like it never ran.
        if swot_json:
            updated["swot_json"] = swot_json
            if isinstance(parsed_swot, dict):
                updated["swot"] = parsed_swot
            else:
                updated.pop("swot", None)
            success_count += 1

        updated_sections.append(updated)

    report["sections"] = updated_sections
    report.setdefault("metadata", {})
    report["metadata"]["generation_mode"] = "historical_report_clone"
    report["metadata"]["section_summary_calls_succeeded"] = success_count
    report["metadata"]["section_summary_sections_attempted"] = len(updated_sections)
    report["metadata"]["section_summary_sections_with_qual"] = sections_with_qual
    report["metadata"]["section_summary_sections_with_qual_answers"] = sections_with_qual_answers

    _debug_product_trial_summary(
        "summary_generation_finished",
        round_id=round_id,
        attempted=len(updated_sections),
        with_qual=sections_with_qual,
        with_qual_answers=sections_with_qual_answers,
        summaries_saved=success_count,
    )

    save_result = _save_existing_product_trial_report(
        round_id=int(round_id),
        generated_by_user_id=generated_by_user_id,
        report=report,
    )

    if success_count <= 0:
        return {
            "success": False,
            "error": "no_summaries_generated",
            "report": save_result.get("report") or report,
        }

    return save_result


def _build_insights_prompt(report: dict) -> str:
    compact_sections = []

    for section in report.get("sections") or []:
        if isinstance(section.get("swot"), dict):
            swot = section.get("swot")
        else:
            swot = _extract_json_object(section.get("swot_json") or "")

        qual = section.get("qual_question") or {}
        compact_sections.append({
            "section_name": section.get("section_name"),
            "survey_name": section.get("survey_name"),
            "quant_questions": section.get("quant_questions") or [],
            "qual_question": {
                "question": qual.get("question"),
                "sample_values": (qual.get("values") or [])[:12],
            },
            "swot": swot or {},
        })

    return f"""
You are generating Product Trial insights in the same spirit as the Historical report insights section.

Return JSON only. No markdown. No extra text.

Required shape:
{{
  "insights": [
    {{
      "section_name": "section name from provided data",
      "title": "short insight title",
      "explanation": "2-3 sentence explanation grounded in the provided section data",
      "evidence": ["short evidence point from the provided data"],
      "impact": "high|medium|low",
      "sentiment": "positive|negative|mixed|neutral"
    }}
  ]
}}

Rules:
- Generate 3-6 insights total.
- Prefer insights that connect quantitative/categorical signals with qualitative follow-up.
- Do not invent numbers.
- Do not invent quotes.
- Use only provided section names.
- Evidence must come from provided questions, SWOT, or qualitative samples.
- Avoid generic observations.

Report Summary:
{json.dumps(report.get("summary") or {}, ensure_ascii=False, default=_json_safe)}

KPIs:
{json.dumps(report.get("kpis") or {}, ensure_ascii=False, default=_json_safe)}

Sections:
{json.dumps(compact_sections, ensure_ascii=False, default=_json_safe)}
"""


def generate_product_trial_insights(*, round_id: int, generated_by_user_id: str) -> dict:
    loaded = _load_existing_product_trial_report(round_id=int(round_id))
    if not loaded.get("success"):
        return loaded

    report = loaded["report"]
    prompt = _build_insights_prompt(report)

    ai_result = call_ai(
        prompt=prompt,
        model="gpt-4o-mini",
        temperature=0.25,
        max_tokens=1800,
    )

    if not ai_result.get("success"):
        return {
            "success": False,
            "error": "ai_failed",
            "report": report,
        }

    raw_response = (
        ai_result.get("content")
        or ai_result.get("response")
        or ""
    ).strip()

    parsed = _extract_json_object(raw_response)
    insights = parsed.get("insights") if isinstance(parsed, dict) else None

    if not isinstance(insights, list):
        return {
            "success": False,
            "error": "invalid_ai_response",
            "report": report,
        }

    cleaned_insights = []
    for insight in insights[:8]:
        if not isinstance(insight, dict):
            continue

        cleaned_insights.append({
            "section_name": _normalize_text(insight.get("section_name")) or "General",
            "title": _normalize_text(insight.get("title")) or "Untitled Insight",
            "explanation": _normalize_text(insight.get("explanation")),
            "evidence": [
                _normalize_text(item)
                for item in insight.get("evidence") or []
                if _normalize_text(item)
            ][:4],
            "impact": (_normalize_text(insight.get("impact")) or "medium").lower(),
            "sentiment": (_normalize_text(insight.get("sentiment")) or "neutral").lower(),
        })

    report["insights"] = cleaned_insights
    report.setdefault("metadata", {})
    report["metadata"]["insight_calls_succeeded"] = 1 if cleaned_insights else 0

    return _save_existing_product_trial_report(
        round_id=int(round_id),
        generated_by_user_id=generated_by_user_id,
        report=report,
    )