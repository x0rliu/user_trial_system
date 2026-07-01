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
from app.utils.report_answer_values import split_countable_answer_value

REPORT_VERSION = "product_trial_report_historical_v2"

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

def _to_float_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clip_text(value: object, *, limit: int = 420) -> str:
    text = _normalize_text(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _clean_bucket_label(value: object) -> str:
    label = _normalize_text(value)
    label = re.sub(r"^```(?:text|json)?", "", label, flags=re.IGNORECASE).strip()
    label = label.replace("```", "").strip()
    label = label.strip(" .:-—–_\"'")
    label = re.sub(r"\s+", " ", label)

    if not label:
        return ""

    if len(label.split()) > 8:
        label = " ".join(label.split()[:8])

    return label[:80]


def _bucket_sentiment(value: object) -> str:
    sentiment = _normalize_text(value).lower()
    if sentiment in {"positive", "negative", "mixed", "neutral"}:
        return sentiment
    return "neutral"


def _bucket_metric_label_for_question(question_text: object) -> str:
    q = _normalize_text(question_text).lower()

    if "eco" in q and ("box" in q or "packag" in q):
        return "Eco"
    if "unbox" in q or "unboxing" in q:
        return "Unbox"
    if "look and feel" in q and ("box" in q or "packag" in q):
        return "Rating"
    if "recommend" in q or "net promoter" in q or "nps" in q:
        return "NPS"
    if "ready for sales" in q or "ready for market" in q or "go to market" in q:
        return "RFS"
    if "software" in q or "g hub" in q or "logitune" in q or "logi tune" in q:
        return "Software"
    if "audio quality" in q:
        return "Audio"
    if "microphone" in q and "quality" in q:
        return "Mic"
    if "comfort" in q:
        return "Comfort"
    if "connection" in q or "connectivity" in q:
        return "Connection"
    if "battery" in q:
        return "Battery"
    if "size" in q:
        return "Size"
    if "weight" in q:
        return "Weight"
    if "design" in q:
        return "Design"
    if "color" in q:
        return "Color"

    fallback = _fallback_section_name_from_questions([_normalize_text(question_text)])
    if fallback:
        return fallback[:28]

    clean = _normalize_text(question_text).strip(" ?")
    return clean[:28] or "Metric"

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

    product_targets = (
        "this product",
        "the product",
        "this device",
        "the device",
        "this headset",
        "the headset",
        "this keyboard",
        "the keyboard",
        "this mouse",
        "the mouse",
        "this webcam",
        "the webcam",
        "this camera",
        "the camera",
        "this speaker",
        "the speaker",
        "this microphone",
        "the microphone",
    )

    product_submetric_markers = (
        "audio",
        "sound",
        "connection",
        "connectivity",
        "battery",
        "charging",
        "dock",
        "docking",
        "stand",
        "microphone experience",
        "mic experience",
        "ability to improve",
        "following experiences",
        "live streaming",
        "in-game voice chat",
        "calls/meetings",
        "recording videos",
        "sound isolation",
        "noise isolation",
        "volume",
        "comfort",
        "packaging",
        "package",
        "box",
        "unboxing",
        "eco-friendliness",
        "color",
        "design",
        "materials",
        "earpads",
        "headband",
        "hinge",
        "range",
        "distance",
        "sturdiness",
        "damage",
        "typing",
        "responsiveness",
        "usefulness",
        "onboarding",
        "feature",
        "function",
        "button",
        "key",
    )

    has_product_target = any(target in joined for target in product_targets)
    is_product_submetric = any(marker in joined for marker in product_submetric_markers)

    if "overall" in joined and "how would you rate" in joined and has_product_target and not is_product_submetric:
        return "Star Rating"

    if "on a scale of" in joined and "overall" in joined and "how would you rate" in joined and has_product_target and not is_product_submetric:
        return "Star Rating"

    if re.search(
        r"\bhow would you rate (this|the) "
        r"(product|device|headset|keyboard|mouse|webcam|camera|speaker|microphone)\b",
        joined,
    ) and not is_product_submetric:
        return "Star Rating"

    if "why" in joined and "rated" in joined and ("this way" in joined or "that way" in joined) and not is_product_submetric:
        return "Star Rating"

    if "recommend this product to a colleague or friend" in joined:
        return "Net Promoter Score"

    if "net promoter" in joined or "nps" in joined:
        return "Net Promoter Score"

    if "ready for sales" in joined:
        return "Ready For Sales"

    if "ready for market release" in joined:
        return "Ready For Sales"

    if "ready for a market release" in joined:
        return "Ready For Sales"

    if "ready to go to market" in joined:
        return "Ready For Sales"

    if "go to market" in joined and "ready" in joined:
        return "Ready For Sales"

    if "ready to launch" in joined or "ready for launch" in joined:
        return "Ready For Sales"

    if "launch" in joined and "ready" in joined:
        return "Ready For Sales"

    software_terms = ("software", "g hub", "logitune", "logi tune")
    software_submetric_markers = (
        "install",
        "installation",
        "instructions",
        "instruction",
        "field of view",
        "fov",
        "zoom",
        "pan",
        "tilt",
        "color adjustment",
        "auto focus",
        "autofocus",
        "manual focus",
        "mute",
        "feature",
        "features",
        "function",
        "functions",
        "used with",
        "which software",
        "what software",
        "refer to",
        "try adjusting",
    )
    has_software_target = any(term in joined for term in software_terms)
    is_software_submetric = any(marker in joined for marker in software_submetric_markers)

    if "software rating" in joined and not is_software_submetric:
        return "Software Rating"

    if has_software_target and "overall" in joined and ("rate" in joined or "rating" in joined) and not is_software_submetric:
        return "Software Rating"

    if re.search(r"\bhow would you rate (the|this|your)?\s*(software|g hub|logitune|logi tune)\b", joined) and not is_software_submetric:
        return "Software Rating"

    if re.search(r"\brate (the|this|your)?\s*(software|g hub|logitune|logi tune)\b", joined) and not is_software_submetric:
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
        r"^name\s*:?\??$",
        r"^what is your name",
        r"^gender\s*:?\??$",
        r"^gender\?",
        r"^what is your gender",
        r"^which gender",
        r"^age range\s*:?\??$",
        r"^what is your age",
        r"^what is your age range",
        r"^where are you based\s*:?\??$",
        r"^where are you",
        r"^where do you live",
        r"^what country",
        r"^what os",
        r"^which os",
        r"operating system",
        r"^what kind of phone",
        r"^what type of phone",
        r"^what phone",
        r"^which phone",
        r"^what kind of computer",
        r"^what type of computer",
        r"^what computer",
        r"^which computer",
        r"external monitor",
        r"external monitors",
        r"additional monitor",
        r"second monitor",
        r"^on average how many hours a day did you use",
        r"^how many hours a day did you use",
        r"^how many hours per day did you use",
        r"^during testing.*how many hours.*use",
        r"what platforms? (do|to) you stream",
        r"what platform",
        r"have you ever used an external microphone before",
        r"^how often do you like to play games",
        r"^how do you like to game",
        r"^what genre or genres of games do you play",
        r"^what genres of games do you play",
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


def _section_bucket_response_rows(raw_section: dict) -> list[dict]:
    qual_question = raw_section.get("qual_question") or {}
    qual_responses = [
        response for response in qual_question.get("responses") or []
        if _normalize_text(response.get("answer"))
    ]
    if not qual_responses:
        return []

    quant_maps = []
    for question in raw_section.get("quant_questions") or []:
        question_text = _normalize_text(question.get("question"))
        if not question_text:
            continue

        metric_label = _bucket_metric_label_for_question(question_text)
        response_map = {}
        for response in question.get("responses") or []:
            response_group_id = _normalize_text(response.get("response_group_id"))
            if not response_group_id:
                continue

            numeric_value = _to_float_or_none(response.get("answer_numeric"))
            if numeric_value is None:
                numeric_value = _to_float_or_none(response.get("answer"))

            response_map[response_group_id] = {
                "raw_answer": _normalize_text(response.get("answer")),
                "numeric_value": numeric_value,
            }

        if response_map:
            quant_maps.append({
                "metric_label": metric_label,
                "question": question_text,
                "response_map": response_map,
            })

    response_rows = []
    for response_index, response in enumerate(qual_responses, start=1):
        response_group_id = _normalize_text(response.get("response_group_id"))
        if not response_group_id:
            continue

        quant_answers = {}
        for quant_map in quant_maps:
            answer = quant_map["response_map"].get(response_group_id)
            if not answer:
                continue
            quant_answers[quant_map["metric_label"]] = answer.get("numeric_value")

        response_rows.append({
            "response_index": response_index,
            "comment": _normalize_text(response.get("answer")),
            "quant_answers": quant_answers,
        })

    return response_rows


def _profile_question_is_displayable(question_text: object) -> bool:
    q = _normalize_text(question_text).lower()
    if not q:
        return False

    if q in {"name", "your name"}:
        return False

    if "what is your name" in q:
        return False

    return _question_is_profile(question_text)


def _build_participant_profile_from_rows(answer_rows: list[dict]) -> dict:
    """
    Build a canonical participant profile block from profile/screener answers.

    Profile questions should not leak into Section Results, but they are still
    important context for interpreting the report. This helper summarizes
    non-PII profile/screener questions into countable distributions.
    """

    question_map: dict[str, dict] = {}

    for row in answer_rows or []:
        question_text = _normalize_text(row.get("QuestionText"))
        if not _profile_question_is_displayable(question_text):
            continue

        answer_text = _normalize_text(row.get("AnswerValue"))
        if not answer_text:
            continue

        question_key = question_text.lower()
        if question_key not in question_map:
            question_map[question_key] = {
                "question": question_text,
                "position": int(row.get("QuestionPosition") or 0),
                "counts": {},
            }

        for value in split_countable_answer_value(answer_text):
            clean_value = _normalize_text(value)
            if not clean_value:
                continue
            counts = question_map[question_key]["counts"]
            counts[clean_value] = counts.get(clean_value, 0) + 1

    questions = []
    for item in sorted(question_map.values(), key=lambda value: value.get("position") or 0):
        counts = item.get("counts") or {}
        if not counts:
            continue

        options = [
            {"label": label, "count": count}
            for label, count in sorted(
                counts.items(),
                key=lambda pair: (-int(pair[1] or 0), str(pair[0]).lower()),
            )
        ]

        questions.append({
            "question": item.get("question"),
            "total_count": sum(int(option.get("count") or 0) for option in options),
            "options": options,
        })

    return {
        "title": "Participant Profile / User Context",
        "questions": questions,
    }


def _section_has_usable_qualitative_signal(section: dict) -> bool:
    qual = section.get("qual_question") or {}
    return bool(_clean_values(qual.get("values") or []))


def _question_is_canonical_kpi_anchor(question_text: object) -> bool:
    return bool(_canonical_section_name_from_questions([_normalize_text(question_text)]))


def _open_quant_is_canonical_kpi(quant_questions: list[dict]) -> bool:
    if len(quant_questions) != 1:
        return False

    return _question_is_canonical_kpi_anchor(quant_questions[0].get("question"))


def _section_is_canonical_kpi(section: dict) -> bool:
    """
    KPI sections are structural, not just semantic.

    Default Product Trial rule:
    - exactly 1 canonical KPI quant/categorical question
    - paired with exactly 1 qualitative follow-up
    - not from Survey 1 / OOBE / first-impression surveys

    This prevents rating-like supporting questions from being promoted into
    duplicate KPI cards simply because their wording resembles a KPI.
    Combo-product multi-device KPI exceptions should be handled explicitly later
    with product/round context rather than inferred from wording alone.
    """

    survey_type_id = str(section.get("survey_type_id") or "").strip()
    if survey_type_id == "UTSurveyType1001":
        return False

    quant_questions = section.get("quant_questions") or []
    if not _open_quant_is_canonical_kpi(quant_questions):
        return False

    return bool(section.get("qual_question"))


def _section_name_is_reserved_kpi(value: object) -> bool:
    return _normalize_text(value).lower() in {
        "star rating",
        "net promoter score",
        "ready for sales",
        "software rating",
    }


def _section_safe_mapped_name(section: dict) -> str | None:
    mapped_name = _mapped_section_name_from_questions(_section_question_texts(section))
    if not mapped_name:
        return None

    if _section_name_is_reserved_kpi(mapped_name) and not _section_is_canonical_kpi(section):
        return None

    return mapped_name


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

    if _section_is_canonical_kpi(section):
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
        "comment_buckets": [],
        "_bucket_response_rows": _section_bucket_response_rows(section),
        "swot_json": None,
        "swot": None,
    }

    mapped_name = _section_safe_mapped_name(normalized_section)
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
                "responses": [],
            }

        answer_text = _answer_text(row)
        question_map[position]["values"].append(answer_text)
        question_map[position]["responses"].append({
            "response_group_id": _stable_response_group_id(row),
            "answer": answer_text,
            "answer_numeric": _json_safe(row.get("AnswerNumeric")),
        })

    return [question_map[position] for position in sorted(question_map)]


def _build_product_trial_sections_for_survey(survey: dict, *, starting_index: int) -> list[dict]:
    """
    Product Trial surveys use an explicit section rhythm:
    - normal section = 2-4 quant/categorical questions followed by 1 qualitative question
    - KPI section = exactly 1 KPI quant/categorical question, optionally followed by 1 qualitative question
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
            is_kpi_anchor = _question_is_canonical_kpi_anchor(question_text)
            open_section_is_kpi = _open_quant_is_canonical_kpi(current_quant_questions)

            if is_kpi_anchor or open_section_is_kpi:
                current_quant_questions = []

            current_quant_questions.append({
                "question": question_text,
                "values": values,
                "responses": question.get("responses") or [],
                "type": q_type,
            })
            continue

        if q_type == "qualitative":
            close_section({
                "question": question_text,
                "values": values,
                "responses": question.get("responses") or [],
            })

    # Drop trailing quant-only sections. A Product Trial report section needs
    # the paired qualitative explanation to be analytically useful. KPI cards
    # follow the same structural rule: 1 KPI quant + 1 qualitative follow-up.
    return sections


def _renumber_report_sections(sections: list[dict]) -> list[dict]:
    cleaned_sections = []

    for source_order, section in enumerate(sections or [], start=1):
        normalized = dict(section)
        mapped_name = _section_safe_mapped_name(normalized)
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
        mapped_name = _section_safe_mapped_name(section)
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
                mapped_name = _section_safe_mapped_name(section)
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

    mapped_name = _section_safe_mapped_name(section)
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
        temperature=0.2,
        max_tokens=20,
    )

    if ai_result.get("success"):
        generated_name = _clean_section_name(
            ai_result.get("content")
            or ai_result.get("response")
            or ""
        )
        if generated_name and not (
            _section_name_is_reserved_kpi(generated_name)
            and not _section_is_canonical_kpi(section)
        ):
            return generated_name

    fallback_name = _fallback_section_name_from_questions(questions)
    if fallback_name and _section_name_is_reserved_kpi(fallback_name) and not _section_is_canonical_kpi(section):
        return None

    return fallback_name


def _generate_section_swot(section: dict) -> str | None:
    """
    Product Trial deliberately reuses Historical's SWOT analysis method.

    Do not maintain a separate Product Trial SWOT prompt here. Historical is
    the source of truth for section-level SWOT analysis behavior.
    """

    from app.handlers.historical import generate_historical_section_swot_summary

    return generate_historical_section_swot_summary(section=section)


def _build_comment_bucket_prompt(section: dict, response_rows: list[dict]) -> str:
    section_name = _normalize_text(section.get("section_name")) or "Survey Section"
    qual = section.get("qual_question") or {}
    qual_question = _normalize_text(qual.get("question")) or "Qualitative follow-up"

    comment_rows = []
    for row in response_rows[:80]:
        comment_rows.append({
            "response_index": row.get("response_index"),
            "comment": _clip_text(row.get("comment"), limit=520),
        })

    return f"""
You are clustering Logitech User Trial comments into old-style report buckets.

Return JSON only. No markdown. No extra text.

Required JSON shape:
{{
  "buckets": [
    {{
      "label": "short concrete bucket label",
      "sentiment": "positive|negative|mixed|neutral",
      "response_indexes": [1, 4, 7],
      "subpoints": ["optional short nuance"]
    }}
  ]
}}

Rules:
- Use only response_index values from the provided comments.
- Do not invent comments, counts, scores, averages, or user totals.
- The label should look like a report bucket, not an insight headline.
- Good labels: "Typical packaging", "Paper packaging", "Opened both sides", "Difficult to open", "Eco-friendly", "No reason stated".
- Bad labels: "Positive feedback", "User sentiment", "Packaging insights", "Overall satisfaction".
- Prefer concrete repeated themes, but preserve actionable one-off issues.
- One response may appear in multiple buckets only if it clearly mentions multiple distinct themes.
- Return no more than 8 buckets.
- Keep subpoints short and only include them when they clarify the bucket.

Section: {section_name}
Qualitative question: {qual_question}

Comments JSON:
{json.dumps(comment_rows, ensure_ascii=False)}
"""


def _metric_summary_for_bucket(response_rows_by_index: dict[int, dict], response_indexes: list[int]) -> list[dict]:
    metric_values: dict[str, list[float]] = defaultdict(list)

    for response_index in response_indexes:
        row = response_rows_by_index.get(int(response_index))
        if not row:
            continue

        for label, value in (row.get("quant_answers") or {}).items():
            metric_label = _normalize_text(label)
            numeric_value = _to_float_or_none(value)
            if metric_label and numeric_value is not None:
                metric_values[metric_label].append(numeric_value)

    summaries = []
    for label, values in metric_values.items():
        if not values:
            continue
        summaries.append({
            "label": label,
            "average": round(sum(values) / len(values), 1),
            "count": len(values),
        })

    return summaries[:5]


def _sanitize_comment_buckets(parsed: dict, response_rows: list[dict]) -> list[dict]:
    rows_by_index = {
        int(row.get("response_index")): row
        for row in response_rows or []
        if row.get("response_index") not in (None, "")
    }
    if not rows_by_index:
        return []

    raw_buckets = parsed.get("buckets") if isinstance(parsed, dict) else []
    if not isinstance(raw_buckets, list):
        return []

    buckets = []
    seen_signatures = set()

    for raw_bucket in raw_buckets[:10]:
        if not isinstance(raw_bucket, dict):
            continue

        label = _clean_bucket_label(raw_bucket.get("label"))
        if not label:
            continue

        clean_indexes = []
        for raw_index in raw_bucket.get("response_indexes") or []:
            try:
                response_index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if response_index in rows_by_index and response_index not in clean_indexes:
                clean_indexes.append(response_index)

        if not clean_indexes:
            continue

        signature = (label.lower(), tuple(clean_indexes))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)

        evidence = [
            _clip_text(rows_by_index[index].get("comment"), limit=180)
            for index in clean_indexes[:3]
            if _normalize_text(rows_by_index[index].get("comment"))
        ]
        subpoints = [
            _clip_text(item, limit=120)
            for item in raw_bucket.get("subpoints") or []
            if _normalize_text(item)
        ][:3]

        buckets.append({
            "label": label,
            "sentiment": _bucket_sentiment(raw_bucket.get("sentiment")),
            "user_count": len(clean_indexes),
            "comment_count": len(clean_indexes),
            "metric_summary": _metric_summary_for_bucket(rows_by_index, clean_indexes),
            "evidence": evidence,
            "subpoints": subpoints,
        })

    return sorted(
        buckets,
        key=lambda bucket: (-int(bucket.get("user_count") or 0), str(bucket.get("label") or "").lower()),
    )[:8]


def _generate_comment_buckets(section: dict) -> list[dict]:
    response_rows = [
        row for row in section.get("_bucket_response_rows") or []
        if isinstance(row, dict) and _normalize_text(row.get("comment"))
    ]
    if not response_rows:
        return []

    ai_result = call_ai(
        prompt=_build_comment_bucket_prompt(section, response_rows),
        temperature=0.2,
        max_tokens=1400,
    )

    if not ai_result.get("success"):
        return []

    parsed = _extract_json_object(
        ai_result.get("response")
        or ai_result.get("content")
        or ""
    )
    if not isinstance(parsed, dict):
        return []

    return _sanitize_comment_buckets(parsed, response_rows)


def _remove_transient_bucket_rows(section: dict) -> dict:
    cleaned = dict(section or {})
    cleaned.pop("_bucket_response_rows", None)
    return cleaned


def _apply_historical_ai_outputs(report: dict) -> dict:
    """
    Clone Historical's two-pass section treatment: first generate section names,
    then generate SWOT summaries from the qualitative follow-up values.
    """

    updated_sections = []
    name_success_count = 0
    summary_success_count = 0
    bucket_success_count = 0

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

        comment_buckets = _generate_comment_buckets(updated)
        if comment_buckets:
            updated["comment_buckets"] = comment_buckets
            bucket_success_count += 1

        updated_sections.append(_remove_transient_bucket_rows(updated))

    report["sections"] = updated_sections
    report.setdefault("metadata", {})
    report["metadata"]["generation_mode"] = "historical_report_clone"
    report["metadata"]["section_name_calls_succeeded"] = name_success_count
    report["metadata"]["section_summary_calls_succeeded"] = summary_success_count
    report["metadata"]["section_comment_bucket_calls_succeeded"] = bucket_success_count

    return report


def _apply_canonical_ai_insights(report: dict) -> dict:
    """
    Generate Product Trial insights as part of the single report generation action.

    Insight generation is intentionally non-blocking. If the insight pass fails,
    the deterministic report, generated section names, and generated summaries are
    still saved, and the failure is recorded in report metadata for visibility.
    """

    from app.services.canonical_report_ai_service import generate_canonical_report_ai_outputs

    report.setdefault("metadata", {})

    ai_result = generate_canonical_report_ai_outputs(
        report=report,
        report_type_label="Product Trial Report",
        blocked_section_names={
            "Star Rating",
            "Net Promoter Score",
            "Ready for Sales",
            "Software Rating",
        },
        max_insights=7,
    )

    if not ai_result.get("success"):
        report["metadata"]["insight_generation_succeeded"] = False
        report["metadata"]["insight_generation_error"] = ai_result.get("error") or "ai_failed"
        return report

    updated_report = ai_result.get("report")
    if not isinstance(updated_report, dict):
        report["metadata"]["insight_generation_succeeded"] = False
        report["metadata"]["insight_generation_error"] = "invalid_ai_report_shape"
        return report

    updated_report.setdefault("metadata", {})
    updated_report["metadata"]["insight_generation_succeeded"] = True
    return updated_report


def _build_executive_summary(*, round_data: dict, kpis: dict, source_surveys: list[dict], sections: list[dict]) -> str:
    # Product Trial executive summaries should be analytic, not a restatement
    # of counts and KPI values already shown elsewhere on the page. Leave this
    # empty until a dedicated summary generation step creates real synthesis.
    return ""


def _build_report(*, round_data: dict, kpis: dict, source_surveys: list[dict], sections: list[dict], participant_profile: dict, data_hash: str) -> dict:
    total_responses = sum(survey.get("response_count") or 0 for survey in source_surveys)
    total_answers = sum(survey.get("answer_count") or 0 for survey in source_surveys)

    return {
        "metadata": {
            "version": REPORT_VERSION,
            "generation_mode": "deterministic_historical_clone",
            "data_hash": data_hash,
        },
        "product": {
            "project_id": round_data.get("ProjectID"),
            "round_id": round_data.get("RoundID"),
            "round_number": round_data.get("RoundNumber"),
            "internal_name": round_data.get("ProjectName"),
            "market_name": round_data.get("MarketName"),
            "product_type_display": round_data.get("ProductType"),
            "business_group": round_data.get("BusinessGroup"),
            "business_subgroup": round_data.get("BusinessSubGroup"),
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
        "participant_profile": participant_profile,
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
    - generate canonical report insights from the completed report payload

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
    participant_profile = _build_participant_profile_from_rows(positioned_answer_rows)
    kpis = get_round_product_kpis(round_id=int(round_id))

    report = _build_report(
        round_data=round_data,
        kpis=kpis,
        source_surveys=source_surveys,
        sections=sections,
        participant_profile=participant_profile,
        data_hash=data_hash,
    )
    report = _apply_historical_ai_outputs(report)
    report = _apply_canonical_ai_insights(report)

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
    cleaned["sections"] = [
        _remove_transient_bucket_rows(section)
        for section in cleaned.get("sections") or []
        if isinstance(section, dict)
    ]
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
        return loaded

    report = loaded["report"]

    # Product Trial summaries must use the same Historical SWOT helper, but the
    # section payload must first be rebuilt from DB-backed survey_answers. The
    # saved report JSON can be stale because the PT report builder has changed
    # during implementation passes. DB rows are the source of truth.
    answer_rows = get_product_trial_report_source_answers(round_id=int(round_id))

    if answer_rows:
        positioned_answer_rows = _infer_question_positions(answer_rows)
        source_surveys, rebuilt_sections = _build_historical_style_sections(positioned_answer_rows)

        if rebuilt_sections:
            report["source_surveys"] = source_surveys
            report["participant_profile"] = _build_participant_profile_from_rows(positioned_answer_rows)
            report["sections"] = rebuilt_sections
            report["kpis"] = get_round_product_kpis(round_id=int(round_id))

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

    updated_sections = []
    success_count = 0
    bucket_success_count = 0
    sections_with_qual = 0
    sections_with_qual_answers = 0

    normalized_sections = _renumber_report_sections(report.get("sections") or [])

    for section in normalized_sections:
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

        swot_json = _generate_section_swot(updated)
        parsed_swot = _extract_json_object(swot_json) if swot_json else None

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

        comment_buckets = _generate_comment_buckets(updated)
        if comment_buckets:
            updated["comment_buckets"] = comment_buckets
            bucket_success_count += 1

        updated_sections.append(_remove_transient_bucket_rows(updated))

    report["sections"] = updated_sections
    report.setdefault("metadata", {})
    report["metadata"]["generation_mode"] = "historical_report_clone"
    report["metadata"]["section_summary_calls_succeeded"] = success_count
    report["metadata"]["section_summary_sections_attempted"] = len(updated_sections)
    report["metadata"]["section_summary_sections_with_qual"] = sections_with_qual
    report["metadata"]["section_summary_sections_with_qual_answers"] = sections_with_qual_answers
    report["metadata"]["section_comment_bucket_calls_succeeded"] = bucket_success_count

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


def generate_product_trial_insights(*, round_id: int, generated_by_user_id: str) -> dict:
    loaded = _load_existing_product_trial_report(round_id=int(round_id))
    if not loaded.get("success"):
        return loaded

    report = loaded["report"]

    from app.services.canonical_report_ai_service import generate_canonical_report_ai_outputs

    ai_result = generate_canonical_report_ai_outputs(
        report=report,
        report_type_label="Product Trial Report",
        blocked_section_names={
            "Star Rating",
            "Net Promoter Score",
            "Ready for Sales",
            "Software Rating",
        },
        max_insights=7,
    )

    if not ai_result.get("success"):
        return {
            "success": False,
            "error": ai_result.get("error") or "ai_failed",
            "report": report,
        }

    updated_report = ai_result.get("report") or report

    return _save_existing_product_trial_report(
        round_id=int(round_id),
        generated_by_user_id=generated_by_user_id,
        report=updated_report,
    )