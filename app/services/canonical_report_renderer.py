# app/services/canonical_report_renderer.py

from __future__ import annotations

import json

from app.utils.html_escape import escape_html as e
from app.utils.report_answer_values import split_countable_answer_value

_REPORT_GROUP_ORDER = {
    "KPIs": 10,
    "OOBE": 20,
    "First Impressions": 30,
    "Usage": 40,
    "Other": 90,
}


_TIER_1_PRODUCT_TYPE_TOKENS = {
    "combo",
    "keyboard",
    "mouse",
}

_KPI_TARGETS_BY_TIER = {
    "tier_1": {
        "star_rating": 4.4,
        "software_rating": 4.2,
        "nps": 50.0,
        "ready_for_sales": 95.0,
    },
    "tier_2": {
        "star_rating": 4.2,
        "software_rating": 4.2,
        "nps": 45.0,
        "ready_for_sales": 95.0,
    },
}

_KPI_DEFINITIONS = [
    {
        "key": "star_rating",
        "label": "Star Rating",
        "count_key": "star_rating_count",
        "suffix": " / 5",
        "target": 4.2,
        "direction": "higher",
    },
    {
        "key": "software_rating",
        "label": "Software Rating",
        "count_key": "software_rating_count",
        "suffix": " / 5",
        "target": 4.2,
        "direction": "higher",
    },
    {
        "key": "nps",
        "label": "NPS",
        "count_key": "nps_count",
        "suffix": "",
        "target": 45.0,
        "direction": "higher",
    },
    {
        "key": "ready_for_sales",
        "label": "Ready for Sales",
        "count_key": "ready_for_sales_count",
        "suffix": "%",
        "target": 95.0,
        "direction": "higher",
    },
]

_AVERAGE_METER_GREEN = "#7bd7c5"
_AVERAGE_METER_YELLOW = "#fbf3db"
_AVERAGE_METER_PINK = "#ebcdca"
_AVERAGE_METER_MUTED = "#98a2b3"

def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _is_project_report(report: dict) -> bool:
    if not isinstance(report, dict):
        return False

    metadata = report.get("metadata") if isinstance(report.get("metadata"), dict) else {}
    generation_mode = _clean_text(metadata.get("generation_mode"))
    version = _clean_text(metadata.get("version"))

    return (
        generation_mode in {
            "deterministic_project_synthesis_from_saved_source_json",
            "deterministic_project_synthesis_from_saved_source_json_and_validation_kpis",
        }
        or version in {
            "reporting_project_report_v2_saved_source_json",
            "reporting_project_report_v3_validation_kpis",
        }
    )


def _metric_display(value: object, *, suffix: str = "", decimals: int = 1) -> str:
    if value in (None, ""):
        return "—"

    try:
        text = f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        text = str(value)

    if text.endswith(".0"):
        text = text[:-2]

    return f"{text}{suffix}"


def _count_display(value: object) -> str:
    try:
        count = int(value or 0)
    except (TypeError, ValueError):
        count = 0

    return f"n={count}" if count else "No data"


def _bar_width(value: object, *, max_value: float = 5.0) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0

    if max_value <= 0:
        return 0

    width = int((numeric / max_value) * 100)
    return max(0, min(100, width))


def _balanced_grid_column_count(item_count: int, *, max_columns: int = 4) -> int:
    """
    Choose deterministic report grid columns so cards are distributed as evenly
    as possible instead of relying on browser auto-fit behavior.
    """

    try:
        count = int(item_count or 0)
    except (TypeError, ValueError):
        count = 0

    if count <= 1:
        return 1
    if count == 2:
        return 2
    if count == 3:
        return 3
    if count == 4:
        return 2
    if count in {5, 6, 9}:
        return 3

    return min(max_columns, count)


def _balanced_grid_style(item_count: int, *, max_columns: int = 4, gap: int = 12, align: str = "stretch") -> str:
    columns = _balanced_grid_column_count(item_count, max_columns=max_columns)
    return (
        "display:grid; "
        f"grid-template-columns:repeat({columns}, minmax(0, 1fr)); "
        f"gap:{gap}px; "
        f"align-items:{align};"
    )


def _status_for_kpi(value: object, *, target: object, direction: str) -> tuple[str, str]:
    if value in (None, ""):
        return "Insufficient data", "is-muted"

    try:
        numeric_value = float(value)
        numeric_target = float(target)
    except (TypeError, ValueError):
        return "Reported", "is-neutral"

    if direction == "lower":
        if numeric_value <= numeric_target:
            return "Meets target", "is-positive"
        return "Below target", "is-negative"

    if numeric_value >= numeric_target:
        return "Meets target", "is-positive"

    near_threshold = numeric_target * 0.9 if numeric_target else numeric_target - 5
    if numeric_value >= near_threshold:
        return "Near target", "is-warning"

    return "Below target", "is-negative"


def _rfs_status_for_value(value: object) -> tuple[str, str]:
    numeric_value = _to_float_or_none(value)
    if numeric_value is None:
        return "Insufficient data", "is-muted"

    if numeric_value >= 95.0:
        return "Meets target", "is-positive"

    if numeric_value >= 80.0:
        return "Needs validation", "is-warning"

    return "Below target", "is-negative"


def _target_tier_for_report(report: dict) -> str:
    if not isinstance(report, dict):
        return "tier_2"

    product = report.get("product") if isinstance(report.get("product"), dict) else {}
    metadata = report.get("metadata") if isinstance(report.get("metadata"), dict) else {}

    product_type = _clean_text(
        product.get("product_type_display")
        or product.get("ProductType")
        or product.get("product_type")
        or metadata.get("product_type_display")
        or metadata.get("ProductType")
        or metadata.get("product_type")
    ).lower()

    if any(token in product_type for token in _TIER_1_PRODUCT_TYPE_TOKENS):
        return "tier_1"

    return "tier_2"


def _kpi_definitions_for_report(report: dict) -> list[dict]:
    targets = _KPI_TARGETS_BY_TIER.get(_target_tier_for_report(report)) or _KPI_TARGETS_BY_TIER["tier_2"]

    definitions = []
    for definition in _KPI_DEFINITIONS:
        item = dict(definition)
        key = item.get("key")
        if key in targets:
            item["target"] = targets[key]
        definitions.append(item)

    return definitions


def _to_float_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int_or_none(value: object) -> int | None:
    numeric = _to_float_or_none(value)
    if numeric is None:
        return None

    try:
        return int(numeric)
    except (TypeError, ValueError):
        return None


def _average_meter_color(value: object) -> str:
    numeric = _to_float_or_none(value)
    if numeric is None:
        return _AVERAGE_METER_MUTED

    if numeric >= 4.0:
        return _AVERAGE_METER_GREEN

    if numeric <= 2.0:
        return _AVERAGE_METER_PINK

    return _AVERAGE_METER_YELLOW


def _question_numeric_scale(question: dict, numeric_values: list[float]) -> int:
    question_text = _clean_text(question.get("question")).lower() if isinstance(question, dict) else ""

    if "net promoter" in question_text or "nps" in question_text or "recommend" in question_text:
        return 10

    if numeric_values and max(numeric_values) > 5:
        return 10

    return 5


def _question_numeric_suffix(max_value: int) -> str:
    return " / 10" if int(max_value or 5) == 10 else " / 5"


def _question_is_nps(question: dict) -> bool:
    question_text = _clean_text(question.get("question")).lower() if isinstance(question, dict) else ""
    return "net promoter" in question_text or "nps" in question_text or "recommend" in question_text


def _percent_display(value: object) -> str:
    numeric = _to_float_or_none(value)
    if numeric is None:
        return "—"

    text = f"{numeric:.1f}"
    if text.endswith(".0"):
        text = text[:-2]
    return f"{text}%"


def _nps_summary_from_values(numeric_values: list[float]) -> dict:
    valid_scores = []
    for value in numeric_values or []:
        numeric = _to_float_or_none(value)
        if numeric is None:
            continue
        if numeric < 0 or numeric > 10:
            continue
        valid_scores.append(int(numeric))

    total = len(valid_scores)
    if total <= 0:
        return {}

    promoters = len([score for score in valid_scores if score >= 9])
    passives = len([score for score in valid_scores if 7 <= score <= 8])
    detractors = len([score for score in valid_scores if score <= 6])
    promoter_pct = (promoters / total) * 100
    passive_pct = (passives / total) * 100
    detractor_pct = (detractors / total) * 100

    return {
        "nps": int(round(promoter_pct - detractor_pct)),
        "total": total,
        "promoters": promoters,
        "passives": passives,
        "detractors": detractors,
        "promoter_pct": promoter_pct,
        "passive_pct": passive_pct,
        "detractor_pct": detractor_pct,
    }


def _nps_sentiment(value: object) -> tuple[str, str]:
    numeric = _to_float_or_none(value)
    if numeric is None:
        return "No score", _AVERAGE_METER_MUTED

    if numeric >= 0:
        return "Positive", _AVERAGE_METER_GREEN

    if numeric <= -50:
        return "Needs attention", _AVERAGE_METER_PINK

    return "Mixed", _AVERAGE_METER_YELLOW


def _render_nps_question_summary(numeric_values: list[float]) -> str:
    summary = _nps_summary_from_values(numeric_values)
    if not summary:
        return ""

    total = int(summary.get("total") or 0)
    promoters = int(summary.get("promoters") or 0)
    passives = int(summary.get("passives") or 0)
    detractors = int(summary.get("detractors") or 0)
    nps = int(summary.get("nps") or 0)

    return f'''
        <div style="
            margin-top:12px;
            border:1px solid #eef2f6;
            border-radius:10px;
            background:#fcfcfd;
            padding:10px 12px;
        ">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
                <div style="min-width:0;">
                    <div style="font-size:11px; color:#667085; text-transform:uppercase; letter-spacing:0.04em; font-weight:800; margin-bottom:4px;">
                        NPS calculation
                    </div>
                    <div style="font-size:13px; color:#344054; line-height:1.45;">
                        {_percent_display(summary.get("promoter_pct"))} promoters − {_percent_display(summary.get("detractor_pct"))} detractors = <strong>{e(nps)}</strong>
                    </div>
                </div>
                <div style="text-align:right; min-width:86px;">
                    <div style="font-size:11px; color:#667085; text-transform:uppercase; letter-spacing:0.04em; font-weight:800;">NPS</div>
                    <div style="font-size:24px; color:#101828; font-weight:800; line-height:1; font-variant-numeric:tabular-nums;">{e(nps)}</div>
                </div>
            </div>
            <div style="
                margin-top:9px;
                display:grid;
                grid-template-columns:repeat(3, minmax(0, 1fr));
                gap:8px;
            ">
                <div style="border-left:3px solid {_AVERAGE_METER_PINK}; padding-left:8px; font-size:12px; color:#667085;">
                    <strong style="color:#344054;">Detractors</strong><br>{e(detractors)} / {e(total)} ({_percent_display(summary.get("detractor_pct"))})
                </div>
                <div style="border-left:3px solid {_AVERAGE_METER_YELLOW}; padding-left:8px; font-size:12px; color:#667085;">
                    <strong style="color:#344054;">Passives</strong><br>{e(passives)} / {e(total)} ({_percent_display(summary.get("passive_pct"))})
                </div>
                <div style="border-left:3px solid {_AVERAGE_METER_GREEN}; padding-left:8px; font-size:12px; color:#667085;">
                    <strong style="color:#344054;">Promoters</strong><br>{e(promoters)} / {e(total)} ({_percent_display(summary.get("promoter_pct"))})
                </div>
            </div>
        </div>
    '''


def _numeric_distribution_counts(numeric_values: list[float]) -> dict[int, int]:
    counts: dict[int, int] = {}

    for value in numeric_values or []:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue

        if not numeric.is_integer():
            continue

        bucket = int(numeric)
        counts[bucket] = counts.get(bucket, 0) + 1

    return counts


def _ordered_numeric_distribution_items(counts: dict[int, int], *, max_value: int) -> list[tuple[int, int]]:
    if not counts:
        return []

    scale_max = int(max_value or 5)
    scale_min = 0 if scale_max == 10 or counts.get(0) else 1
    ordered_items = [
        (bucket, int(counts.get(bucket) or 0))
        for bucket in range(scale_min, scale_max + 1)
    ]

    extra_buckets = [
        bucket for bucket in counts
        if bucket < scale_min or bucket > scale_max
    ]
    for bucket in sorted(extra_buckets):
        ordered_items.append((bucket, int(counts.get(bucket) or 0)))

    return ordered_items


def _render_numeric_distribution(numeric_values: list[float], *, max_value: int, compact: bool = False) -> str:
    counts = _numeric_distribution_counts(numeric_values)
    items = _ordered_numeric_distribution_items(counts, max_value=max_value)
    if not items:
        return ""

    max_count = max([count for _bucket, count in items] or [1])
    bar_height = 28 if compact else 42
    label_size = 10 if compact else 11
    count_size = 11 if compact else 12
    gap = 4 if compact else 6
    min_column_width = 24 if compact else 34

    bars_html = ""
    for bucket, count in items:
        height = int((count / max_count) * 100) if max_count else 0
        visible_height = max(height, 6) if count else 0
        bars_html += f"""
            <div style="min-width:0; display:flex; flex-direction:column; gap:4px;">
                <div style="
                    height:14px;
                    display:flex;
                    align-items:center;
                    justify-content:center;
                    color:#344054;
                    font-size:{count_size}px;
                    font-weight:800;
                    line-height:1;
                    font-variant-numeric:tabular-nums;
                ">{e(count) if count else ""}</div>
                <div style="
                    height:{bar_height}px;
                    display:flex;
                    align-items:flex-end;
                    justify-content:center;
                    background:#f9fafb;
                    border:1px solid #e5e7eb;
                    border-radius:8px 8px 4px 4px;
                    overflow:hidden;
                    box-shadow:inset 0 1px 0 rgba(16, 24, 40, 0.03);
                ">
                    <div style="
                        height:{visible_height}%;
                        width:72%;
                        background:{_AVERAGE_METER_GREEN};
                        border-radius:5px 5px 0 0;
                    "></div>
                </div>
                <div style="
                    color:#667085;
                    text-align:center;
                    font-size:{label_size}px;
                    font-weight:700;
                    line-height:1;
                    font-variant-numeric:tabular-nums;
                ">{e(bucket)}</div>
            </div>
        """

    return f"""
        <div style="margin-top:{8 if compact else 12}px;">
            <div style="
                display:flex;
                justify-content:space-between;
                align-items:center;
                gap:8px;
                margin-bottom:6px;
            ">
                <div style="
                    font-size:11px;
                    color:#667085;
                    text-transform:uppercase;
                    letter-spacing:0.04em;
                    font-weight:800;
                ">Distribution</div>
                <div style="
                    font-size:10px;
                    color:#98a2b3;
                    text-transform:uppercase;
                    letter-spacing:0.04em;
                    font-weight:800;
                ">Count / Rating</div>
            </div>
            <div style="
                background:#fcfcfd;
                border:1px solid #eef2f6;
                border-radius:10px;
                padding:{6 if compact else 8}px {6 if compact else 8}px {5 if compact else 7}px;
            ">
                <div style="
                    display:grid;
                    grid-template-columns:repeat(auto-fit, minmax({min_column_width}px, 1fr));
                    gap:{gap}px;
                    align-items:end;
                ">
                    {bars_html}
                </div>
            </div>
        </div>
    """


def _render_count_distribution_rows(rows: list[tuple[str, int, str]]) -> str:
    clean_rows = [
        (label, int(count or 0), color or _AVERAGE_METER_GREEN)
        for label, count, color in rows
        if _clean_text(label)
    ]
    if not clean_rows:
        return ""

    max_count = max([count for _label, count, _color in clean_rows] or [1])
    rows_html = ""
    for label, count, color in clean_rows:
        width = _bar_width(count, max_value=float(max_count or 1))
        rows_html += f'''
            <div style="margin-top:7px;">
                <div style="display:flex; justify-content:space-between; gap:8px; font-size:11px; color:#667085; margin-bottom:3px;">
                    <span>{e(label)}</span>
                    <span style="font-weight:700; color:#344054; font-variant-numeric:tabular-nums;">{e(count)}</span>
                </div>
                <div style="background:#eef2f6; height:6px; border-radius:999px; overflow:hidden;">
                    <div style="width:{width}%; background:{color}; height:100%;"></div>
                </div>
            </div>
        '''

    return f'''
        <div style="margin-top:10px; padding-top:8px; border-top:1px solid #eef2f6;">
            <div style="font-size:11px; color:#667085; text-transform:uppercase; letter-spacing:0.04em; font-weight:800;">
                Distribution
            </div>
            {rows_html}
        </div>
    '''

def _section_nps_summary(section: dict) -> dict:
    for question in section.get("quant_questions") or []:
        if not isinstance(question, dict):
            continue
        if not _question_is_nps(question):
            continue

        numeric_values = [
            numeric
            for numeric in (_to_float_or_none(value) for value in question.get("values") or [])
            if numeric is not None
        ]
        summary = _nps_summary_from_values(numeric_values)
        if summary:
            return summary

    return {}


def _section_score_suffix(section: dict) -> str:
    for question in section.get("quant_questions") or []:
        if not isinstance(question, dict):
            continue

        numeric_values = [
            numeric
            for numeric in (_to_float_or_none(value) for value in question.get("values") or [])
            if numeric is not None
        ]
        if numeric_values:
            return _question_numeric_suffix(_question_numeric_scale(question, numeric_values))

    return " / 5"


def _average_numeric_values(values: list[object]) -> float | None:
    numeric_values = [
        numeric
        for numeric in (_to_float_or_none(value) for value in values or [])
        if numeric is not None
    ]
    if not numeric_values:
        return None

    return sum(numeric_values) / len(numeric_values)


def _section_score(section: dict) -> float | None:
    score = _to_float_or_none(section.get("average_score"))
    if score is not None:
        return score

    question_scores = []
    for question in section.get("quant_questions") or []:
        if not isinstance(question, dict):
            continue

        question_score = _to_float_or_none(question.get("average"))
        if question_score is None and question.get("type") == "numeric":
            question_score = _average_numeric_values(question.get("values") or [])

        if question_score is not None:
            question_scores.append(question_score)

    return _average_numeric_values(question_scores)


def _section_sentiment(score: float | None) -> tuple[str, str]:
    if score is None:
        return "No score", _AVERAGE_METER_MUTED

    if score >= 4.0:
        return "Positive", _AVERAGE_METER_GREEN

    if score <= 2.0:
        return "Needs attention", _AVERAGE_METER_PINK

    return "Mixed", _AVERAGE_METER_YELLOW


def _section_analysis_item_count(section: dict) -> int:
    section_analysis = section.get("section_analysis")
    if isinstance(section_analysis, dict):
        return sum(
            len(section_analysis.get(key) or [])
            for key in ("key_findings", "qualitative_insights", "notable_quotes")
        )

    parsed = _parse_swot(section)
    if isinstance(parsed, dict):
        return sum(
            len(parsed.get(key) or [])
            for key in ("strengths", "weaknesses", "opportunities", "threats")
        )

    return 0


def _section_qualitative_value_count(section: dict) -> int:
    qual = section.get("qual_question") if isinstance(section.get("qual_question"), dict) else {}
    return len([
        value for value in qual.get("values") or []
        if _clean_text(value)
    ])


def _section_comment_bucket_count(section: dict) -> int:
    return len([
        bucket for bucket in section.get("comment_buckets") or []
        if isinstance(bucket, dict) and _clean_text(bucket.get("label"))
    ])


def _section_preview_html(section: dict) -> tuple[str, str]:
    nps_summary = _section_nps_summary(section)
    if nps_summary:
        score = None
        sentiment_label, border_color = _nps_sentiment(nps_summary.get("nps"))
    else:
        score = _section_score(section)
        sentiment_label, border_color = _section_sentiment(score)

    preview_bits = []
    if nps_summary:
        preview_bits.append(f"NPS {nps_summary.get('nps')}")
    elif score is not None:
        preview_bits.append(f"Avg {_metric_display(score, suffix=_section_score_suffix(section))}")
    preview_bits.append(sentiment_label)

    bucket_count = _section_comment_bucket_count(section)
    if bucket_count:
        preview_bits.append(f"{bucket_count} comment bucket(s)")
    else:
        analysis_count = _section_analysis_item_count(section)
        if analysis_count:
            preview_bits.append(f"{analysis_count} synthesis item(s)")
        else:
            qualitative_count = _section_qualitative_value_count(section)
            if qualitative_count:
                preview_bits.append(f"{qualitative_count} qualitative response(s)")

    preview_html = ""
    if preview_bits:
        preview_html = f'''
            <div style="font-size:12px; color:#667085; line-height:1.3; text-align:right;">
                {e(" · ".join(preview_bits))}
            </div>
        '''

    return preview_html, border_color


def _section_report_group(section: dict) -> str:
    group = _clean_text(section.get("report_group"))
    if group:
        return group

    section_name = _clean_text(section.get("section_name")).lower()
    survey_name = _clean_text(section.get("survey_name")).lower()
    question_text = " ".join(
        _clean_text(question.get("question"))
        for question in section.get("quant_questions") or []
        if isinstance(question, dict)
    ).lower()

    if section_name in {
        "star rating",
        "net promoter score",
        "ready for sales",
        "software rating",
    }:
        return "KPIs"

    if any(marker in section_name or marker in question_text for marker in (
        "box", "package", "packaging", "unbox", "unboxing", "component", "cable", "quick start"
    )):
        return "OOBE"

    if "survey 1" in survey_name or "first impression" in survey_name or "oobe" in survey_name:
        return "First Impressions"

    if "survey 2" in survey_name or "usage" in survey_name or "experience" in survey_name or "kpi" in survey_name:
        return "Usage"

    return "Other"


def _sort_sections(sections: list[dict]) -> list[dict]:
    return [
        section for _source_index, section in sorted(
            enumerate(sections or [], start=1),
            key=lambda item: (
                _REPORT_GROUP_ORDER.get(_section_report_group(item[1]), 90),
                item[0],
            ),
        )
    ]


def _parse_swot(section: dict) -> dict:
    parsed = section.get("swot") if isinstance(section.get("swot"), dict) else None

    if not parsed and section.get("summary_json"):
        parsed = section.get("summary_json") if isinstance(section.get("summary_json"), dict) else None
        if not parsed:
            raw_summary = str(section.get("summary_json") or "").strip()
            try:
                parsed = json.loads(raw_summary)
            except (TypeError, json.JSONDecodeError):
                parsed = None

    raw_json = section.get("swot_json")
    if not parsed and raw_json:
        raw = str(raw_json or "").strip()
        if raw.startswith("```"):
            raw = raw.replace("```json", "", 1).replace("```", "").strip()

        try:
            parsed = json.loads(raw)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(raw[start:end + 1])
                except Exception:
                    parsed = {}
            else:
                parsed = {}

    return parsed if isinstance(parsed, dict) else {}


def _render_swot_items(items: object) -> str:
    if not isinstance(items, list):
        items = [items] if items else []

    html_items = ""
    for index, item in enumerate(items):
        if not item:
            continue
        weight = "font-weight:600;" if index == 0 else "color:#667085;"
        html_items += f"<li style='{weight}'>{e(item)}</li>"

    if not html_items:
        html_items = "<li style='color:#98a2b3;'>No saved summary yet.</li>"

    return html_items


def _render_swot_card(title: str, items: object) -> str:
    return f"""
        <div style="
            border:1px solid #e5e7eb;
            border-radius:10px;
            padding:12px 14px;
            background:#ffffff;
            min-width:0;
        ">
            <div style="
                font-size:12px;
                color:#667085;
                text-transform:uppercase;
                letter-spacing:0.04em;
                font-weight:700;
                margin-bottom:8px;
            ">{e(title)}</div>
            <ul style="margin:0; padding-left:18px; font-size:14px; line-height:1.5;">
                {_render_swot_items(items)}
            </ul>
        </div>
    """


def _render_section_analysis_card(title: str, items: object) -> str:
    return f"""
        <div style="
            border:1px solid #e5e7eb;
            border-radius:10px;
            padding:12px 14px;
            background:#ffffff;
            min-width:0;
        ">
            <div style="
                font-size:12px;
                color:#667085;
                text-transform:uppercase;
                letter-spacing:0.04em;
                font-weight:700;
                margin-bottom:8px;
            ">{e(title)}</div>
            <ul style="margin:0; padding-left:18px; font-size:14px; line-height:1.5;">
                {_render_swot_items(items)}
            </ul>
        </div>
    """


def _render_section_analysis_grid(section: dict) -> str:
    section_analysis = section.get("section_analysis")
    if not isinstance(section_analysis, dict):
        return ""

    analysis_cards = []

    key_findings = section_analysis.get("key_findings") or []
    qualitative_insights = section_analysis.get("qualitative_insights") or []
    notable_quotes = section_analysis.get("notable_quotes") or []

    if key_findings:
        analysis_cards.append(_render_section_analysis_card("Key Findings", key_findings))
    if qualitative_insights:
        analysis_cards.append(_render_section_analysis_card("Qualitative Insights", qualitative_insights))
    if notable_quotes:
        analysis_cards.append(_render_section_analysis_card("Notable Quotes", notable_quotes))

    if not analysis_cards:
        return ""

    return f"""
        <div style="{_balanced_grid_style(len(analysis_cards), max_columns=3, gap=12)} margin-top:12px;">
            {''.join(analysis_cards)}
        </div>
    """


def _render_swot_grid(section: dict) -> str:
    parsed = _parse_swot(section)
    if parsed:
        return f"""
            <div style="
                display:grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap:12px;
                margin-top:12px;
            ">
                {_render_swot_card("Strengths", parsed.get("strengths") or [])}
                {_render_swot_card("Weaknesses", parsed.get("weaknesses") or [])}
                {_render_swot_card("Opportunities", parsed.get("opportunities") or [])}
                {_render_swot_card("Threats", parsed.get("threats") or [])}
            </div>
        """

    section_analysis_html = _render_section_analysis_grid(section)
    if section_analysis_html:
        return section_analysis_html

    return """
        <div style="font-size:13px; color:#667085; margin-top:10px;">
            No saved qualitative synthesis for this section yet.
        </div>
    """


def _sentiment_bucket_color(sentiment: object) -> str:
    value = _clean_text(sentiment).lower()
    if value == "positive":
        return _AVERAGE_METER_GREEN
    if value == "negative":
        return _AVERAGE_METER_PINK
    if value == "mixed":
        return _AVERAGE_METER_YELLOW
    return "#d0d5dd"


def _render_comment_bucket_metrics(metrics: object) -> str:
    if not isinstance(metrics, list):
        return ""

    parts = []
    for metric in metrics[:5]:
        if not isinstance(metric, dict):
            continue
        label = _clean_text(metric.get("label"))
        average = _to_float_or_none(metric.get("average"))
        if not label or average is None:
            continue
        parts.append(f"{label}: {_metric_display(average, decimals=1)}")

    if not parts:
        return ""

    return f"<span style='color:#667085;'>({e(', '.join(parts))})</span>"


def _render_comment_buckets(section: dict) -> str:
    buckets = [
        bucket for bucket in section.get("comment_buckets") or []
        if isinstance(bucket, dict) and _clean_text(bucket.get("label"))
    ]
    if not buckets:
        return ""

    bucket_rows = ""
    for bucket in buckets[:10]:
        label = _clean_text(bucket.get("label"))
        user_count = _to_int_or_none(bucket.get("user_count")) or 0
        comment_count = _to_int_or_none(bucket.get("comment_count")) or user_count
        sentiment = _clean_text(bucket.get("sentiment")) or "neutral"
        border_color = _sentiment_bucket_color(sentiment)
        metric_html = _render_comment_bucket_metrics(bucket.get("metric_summary") or [])

        subpoints_html = ""
        for subpoint in bucket.get("subpoints") or []:
            if _clean_text(subpoint):
                subpoints_html += f"<li>{e(subpoint)}</li>"

        evidence_html = ""
        for evidence in bucket.get("evidence") or []:
            if _clean_text(evidence):
                evidence_html += f"<li>{e(evidence)}</li>"

        detail_html = ""
        if subpoints_html or evidence_html:
            detail_html = f"""
                <details style="margin-top:8px; color:#667085; font-size:12px; line-height:1.45;">
                    <summary style="cursor:pointer; color:#667085; font-weight:700;">View examples</summary>
                    <div style="margin-top:6px; display:grid; grid-template-columns:1fr; gap:8px;">
                        <div>
                            <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.04em; font-weight:800; margin-bottom:4px;">Nuance</div>
                            <ul style="margin:0; padding-left:17px;">{subpoints_html or '<li>No subpoints stored.</li>'}</ul>
                        </div>
                        <div>
                            <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.04em; font-weight:800; margin-bottom:4px;">Evidence</div>
                            <ul style="margin:0; padding-left:17px;">{evidence_html or '<li>No evidence examples stored.</li>'}</ul>
                        </div>
                    </div>
                </details>
            """

        count_label = f"Users: {user_count}"
        if comment_count != user_count:
            count_label += f" / Comments: {comment_count}"

        bucket_rows += f"""
            <div style="
                border:1px solid #e5e7eb;
                border-left:4px solid {border_color};
                border-radius:10px;
                padding:10px 12px;
                background:#ffffff;
            ">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
                    <div style="min-width:0; font-size:14px; color:#344054; line-height:1.45;">
                        <strong>{e(label)}</strong>
                        <span style="color:#667085;"> // {e(count_label)}</span>
                        {metric_html}
                    </div>
                    <div style="font-size:11px; color:#667085; text-transform:uppercase; letter-spacing:0.04em; font-weight:800; white-space:nowrap;">
                        {e(sentiment)}
                    </div>
                </div>
                {detail_html}
            </div>
        """

    return f"""
        <div style="margin-top:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:8px;">
                <div style="font-size:12px; color:#667085; text-transform:uppercase; letter-spacing:0.04em; font-weight:800;">
                    Comment Buckets
                </div>
                <div style="font-size:12px; color:#667085;">
                    {e(len(buckets))} bucket(s)
                </div>
            </div>
            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(420px, 1fr)); gap:8px; align-items:start;">
                {bucket_rows}
            </div>
        </div>
    """


def _render_question_card(question: dict) -> str:
    question_text = e(question.get("question") or "Untitled question")
    values = question.get("values") or []

    numeric_vals = []
    counts = {}

    for value in values:
        if value is None:
            continue

        text = str(value).strip()
        if not text:
            continue

        try:
            numeric_vals.append(float(text))
            continue
        except ValueError:
            pass

        counts[text] = counts.get(text, 0) + 1

    if numeric_vals:
        average = sum(numeric_vals) / len(numeric_vals)
        max_value = _question_numeric_scale(question, numeric_vals)
        distribution_html = _render_numeric_distribution(numeric_vals, max_value=max_value)

        if _question_is_nps(question):
            nps_summary_html = _render_nps_question_summary(numeric_vals)
            return f"""
                <div style="
                    min-height:112px;
                    padding:12px 14px;
                    border:1px solid #e5e7eb;
                    border-radius:10px;
                    box-sizing:border-box;
                    background:white;
                ">
                    <div style="font-size:14px; line-height:1.4; color:#344054; min-width:0; font-weight:700;">
                        {question_text}
                    </div>
                    {nps_summary_html}
                    {distribution_html}
                </div>
            """

        width = _bar_width(average, max_value=float(max_value))
        meter_color = _average_meter_color(average)
        return f"""
            <div style="
                min-height:112px;
                padding:12px 14px;
                border:1px solid #e5e7eb;
                border-radius:10px;
                box-sizing:border-box;
                background:white;
            ">
                <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:14px;">
                    <div style="font-size:14px; flex:1; line-height:1.4; color:#344054; min-width:0;">
                        {question_text}
                    </div>
                    <div style="min-width:156px;">
                        <div style="display:flex; align-items:center; gap:8px; justify-content:flex-end;">
                            <div style="background:#eef2f6; height:7px; width:96px; border-radius:999px; overflow:hidden;">
                                <div style="width:{width}%; background:{meter_color}; height:100%;"></div>
                            </div>
                            <div style="font-size:13px; color:#475467; width:48px; text-align:right; font-variant-numeric:tabular-nums;">
                                {_metric_display(average, suffix=_question_numeric_suffix(max_value), decimals=2)}
                            </div>
                        </div>
                    </div>
                </div>
                {distribution_html}
            </div>
        """

    split_counts = {}
    for option, count in counts.items():
        for part in split_countable_answer_value(option):
            split_counts[part] = split_counts.get(part, 0) + count

    if split_counts:
        max_value = max(split_counts.values()) if split_counts else 1
        options_html = ""
        for option, count in sorted(split_counts.items(), key=lambda item: item[1], reverse=True):
            width = int((count / max_value) * 100) if max_value else 0
            options_html += f"""
                <div style="margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; font-size:13px; color:#344054; margin-bottom:3px; gap:8px;">
                        <div>{e(option)}</div>
                        <div style="font-variant-numeric:tabular-nums;">{e(count)}</div>
                    </div>
                    <div style="background:#eef2f6; height:7px; border-radius:999px; overflow:hidden;">
                        <div style="width:{width}%; background:{_AVERAGE_METER_GREEN}; height:100%;"></div>
                    </div>
                </div>
            """

        return f"""
            <div style="
                min-height:92px;
                padding:12px 14px;
                border:1px solid #e5e7eb;
                border-radius:10px;
                box-sizing:border-box;
                background:white;
            ">
                <div style="font-size:14px; margin-bottom:10px; line-height:1.4; color:#344054;">
                    {question_text}
                </div>
                {options_html}
            </div>
        """

    return f"""
        <div style="
            min-height:92px;
            padding:12px 14px;
            border:1px dashed #d0d5dd;
            border-radius:10px;
            box-sizing:border-box;
            background:white;
            color:#667085;
            font-size:14px;
        ">
            {question_text}<br>
            <span style="font-size:13px;">No reportable quantitative values stored.</span>
        </div>
    """


def _rfs_status_color(status_class: str) -> str:
    if status_class == "is-positive":
        return "#12b76a"
    if status_class == "is-warning":
        return "#f79009"
    if status_class == "is-negative":
        return "#f04438"
    return "#98a2b3"


def _sorted_rfs_classified_reasons(diagnostic: dict) -> list[dict]:
    rows = [
        item for item in diagnostic.get("classified_reasons") or []
        if isinstance(item, dict)
    ]

    def sort_key(item: dict) -> tuple[int, int]:
        interpretation = _clean_text(item.get("interpretation")).lower()
        is_blocking = 0 if interpretation == "blocking" else 1
        try:
            response_index = int(item.get("response_index") or 0)
        except (TypeError, ValueError):
            response_index = 0
        return (is_blocking, response_index)

    return sorted(rows, key=sort_key)


def _legacy_ready_for_sales_diagnostic_from_kpis(kpis: dict) -> dict:
    """
    Build a display-only diagnostic for reports generated before detailed RFS
    diagnostics were saved in report.kpis.ready_for_sales_diagnostic.

    This does not recalculate the KPI. It only prevents old reports from showing
    misleading 0 / 0 interpretation details beside a valid stored RFS score.
    """

    total_count = _to_int_or_none(kpis.get("ready_for_sales_count"))
    ready_count = _to_int_or_none(kpis.get("ready_for_sales_ready_count"))
    blocking_no = _to_int_or_none(kpis.get("ready_for_sales_blocked_count"))
    non_blocking_no = _to_int_or_none(kpis.get("ready_for_sales_invalid_no_reason_count"))

    if total_count is None and ready_count is None and blocking_no is None and non_blocking_no is None:
        return {}

    total_count = int(total_count or 0)
    ready_count = int(ready_count or 0)
    blocking_no = int(blocking_no or 0)
    non_blocking_no = int(non_blocking_no or 0)

    raw_no = blocking_no + non_blocking_no
    raw_yes = max(ready_count - non_blocking_no, 0)

    return {
        "raw_yes": raw_yes,
        "raw_no": raw_no,
        "blocking_no": blocking_no,
        "non_blocking_no": non_blocking_no,
        "adjusted_ready_count": ready_count,
        "total_count": total_count,
        "excluded_count": None,
        "is_legacy_display_fallback": True,
        "rules": [
            "This report was generated before detailed Ready for Sales diagnostics were stored.",
            "The displayed counts are reconstructed from the saved KPI totals to avoid showing misleading 0 / 0 context.",
            "Regenerate the report to store full Ready for Sales diagnostic details and per-response interpretation rows.",
        ],
        "classified_reasons": [],
    }


def _ready_for_sales_diagnostic_for_display(kpis: dict) -> dict:
    diagnostic = kpis.get("ready_for_sales_diagnostic")
    if isinstance(diagnostic, dict) and diagnostic:
        return diagnostic

    return _legacy_ready_for_sales_diagnostic_from_kpis(kpis)


def _render_ready_for_sales_diagnostic(kpis: dict) -> str:
    diagnostic = _ready_for_sales_diagnostic_for_display(kpis)
    if not diagnostic:
        return ""

    raw_yes = diagnostic.get("raw_yes")
    raw_no = diagnostic.get("raw_no")
    blocking_no = diagnostic.get("blocking_no")
    non_blocking_no = diagnostic.get("non_blocking_no")
    adjusted_ready_count = diagnostic.get("adjusted_ready_count")
    total_count = diagnostic.get("total_count")
    is_legacy_display_fallback = bool(diagnostic.get("is_legacy_display_fallback"))

    rules_html = ""
    for rule in diagnostic.get("rules") or []:
        if _clean_text(rule):
            rules_html += f"<li>{e(rule)}</li>"

    reason_rows = ""
    for row_index, item in enumerate(_sorted_rfs_classified_reasons(diagnostic), start=1):
        interpretation = _clean_text(item.get("interpretation")) or "-"
        matched_keywords = item.get("matched_keywords") or []
        matched_label = ", ".join(
            _clean_text(keyword)
            for keyword in matched_keywords
            if _clean_text(keyword)
        ) or "-"
        row_bg = "#ffffff" if row_index % 2 else "#f9fafb"
        interpretation_color = "#b42318" if interpretation.lower() == "blocking" else "#08756a"

        reason_rows += f"""
            <tr style="background:{row_bg}; border-bottom:1px solid #eef2f6;">
                <td style="padding:8px 6px; vertical-align:top; font-variant-numeric:tabular-nums;">{e(item.get("response_index") or "-")}</td>
                <td style="padding:8px 6px; vertical-align:top;">{e(item.get("raw_answer") or "-")}</td>
                <td style="padding:8px 6px; vertical-align:top; font-weight:700; color:{interpretation_color};">{e(interpretation)}</td>
                <td style="padding:8px 6px; vertical-align:top;">{e(matched_label)}</td>
                <td style="padding:8px 6px; vertical-align:top; min-width:260px; line-height:1.45;">{e(item.get("reason_summary") or "-")}</td>
            </tr>
        """

    reason_table_html = ""
    if reason_rows:
        reason_table_html = f"""
            <div style="overflow-x:auto; margin-top:12px; border:1px solid #e5e7eb; border-radius:10px;">
                <table style="width:100%; border-collapse:collapse; font-size:12px; color:#475467;">
                    <thead>
                        <tr style="border-bottom:1px solid #e5e7eb; background:#f9fafb; color:#667085; text-align:left;">
                            <th style="padding:8px 6px;">#</th>
                            <th style="padding:8px 6px;">Raw</th>
                            <th style="padding:8px 6px;">Interpretation</th>
                            <th style="padding:8px 6px;">Trigger</th>
                            <th style="padding:8px 6px;">Reason</th>
                        </tr>
                    </thead>
                    <tbody>
                        {reason_rows}
                    </tbody>
                </table>
            </div>
        """

    legacy_notice_html = ""
    if is_legacy_display_fallback:
        legacy_notice_html = """
            <div style="margin:10px 0 12px; padding:10px 12px; border:1px solid #fedf89; border-radius:10px; background:#fffaeb; color:#92400e; font-size:12px; line-height:1.45;">
                This report was generated before detailed Ready for Sales diagnostics were stored.
                Regenerate the report to show full per-response interpretation.
            </div>
        """

    return f"""
        <details style="margin-top:14px; border:1px solid #d9f3ee; border-radius:12px; background:#ffffff; padding:12px 14px;">
            <summary style="cursor:pointer; font-size:13px; font-weight:800; color:#08756a;">
                View Ready for Sales interpretation
            </summary>
            <div style="margin-top:12px; font-size:12px; color:#475467; line-height:1.45;">
                <div style="display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:10px; margin-bottom:12px;">
                    <div><strong>Raw answers</strong><br>{e(raw_yes or 0)} Yes / {e(raw_no or 0)} No</div>
                    <div><strong>Adjusted ready</strong><br>{e(adjusted_ready_count or 0)} / {e(total_count or 0)} ready-equivalent</div>
                    <div><strong>Blocking No</strong><br>{e(blocking_no or 0)}</div>
                    <div><strong>Non-blocking No</strong><br>{e(non_blocking_no or 0)}</div>
                </div>
                {legacy_notice_html}
                <div style="font-weight:700; color:#344054; margin-bottom:4px;">How this KPI is interpreted</div>
                <ul style="margin:0; padding-left:18px;">
                    {rules_html}
                </ul>
                {reason_table_html}
            </div>
        </details>
    """


def _is_ready_for_sales_section(section: dict) -> bool:
    section_name = _clean_text(section.get("section_name")).lower()
    if not section_name:
        return False

    return (
        "ready for sales" in section_name
        or "ready for sale" in section_name
        or "go to market" in section_name
        or "market readiness" in section_name
    )


def _ready_for_sales_section_preview_html(kpis: dict) -> tuple[str, str]:
    value = _to_float_or_none(kpis.get("ready_for_sales"))
    status_label, status_class = _rfs_status_for_value(value)
    border_color = _rfs_status_color(status_class)
    diagnostic = _ready_for_sales_diagnostic_for_display(kpis)
    blocking_no = diagnostic.get("blocking_no")

    preview_bits = []
    if value is not None:
        preview_bits.append(f"RFS {_metric_display(value, suffix='%')}")
    preview_bits.append(status_label)
    if blocking_no not in (None, ""):
        preview_bits.append(f"{blocking_no} blocking No")

    preview_html = f"""
        <div style="font-size:12px; color:#667085; line-height:1.3; text-align:right;">
            {e(" · ".join(preview_bits))}
        </div>
    """
    return preview_html, border_color


def _render_ready_for_sales_section_result(kpis: dict) -> str:
    value = _to_float_or_none(kpis.get("ready_for_sales"))
    if value is None:
        return ""

    diagnostic = _ready_for_sales_diagnostic_for_display(kpis)
    raw_yes = int(diagnostic.get("raw_yes") or 0)
    raw_no = int(diagnostic.get("raw_no") or 0)
    blocking_no = int(diagnostic.get("blocking_no") or 0)
    non_blocking_no = int(diagnostic.get("non_blocking_no") or 0)
    adjusted_ready = int(diagnostic.get("adjusted_ready_count") or 0)
    total_count = int(diagnostic.get("total_count") or 0)
    raw_total = raw_yes + raw_no

    status_label, status_class = _rfs_status_for_value(value)
    status_color = _rfs_status_color(status_class)
    value_width = _bar_width(value, max_value=100.0)
    yes_width = _bar_width(raw_yes, max_value=float(raw_total or 1))
    no_width = _bar_width(raw_no, max_value=float(raw_total or 1))
    blocking_width = _bar_width(blocking_no, max_value=float(raw_no or 1))
    non_blocking_width = _bar_width(non_blocking_no, max_value=float(raw_no or 1))

    return f"""
        <div style="
            border:1px solid #e5e7eb;
            border-left:4px solid {status_color};
            border-radius:10px;
            box-sizing:border-box;
            background:white;
            padding:14px;
        ">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:12px;">
                <div>
                    <div style="font-size:12px; color:#667085; text-transform:uppercase; letter-spacing:0.04em; font-weight:800; margin-bottom:6px;">
                        Interpreted Ready for Sales Result
                    </div>
                    <div style="font-size:26px; color:#101828; font-weight:800; line-height:1;">
                        {_metric_display(value, suffix='%')}
                    </div>
                </div>
                <div style="font-size:12px; color:#667085; text-align:right; line-height:1.4;">
                    <div><strong>{e(status_label)}</strong></div>
                    <div>{e(adjusted_ready)} / {e(total_count)} ready-equivalent</div>
                    <div>Target: 95%</div>
                </div>
            </div>
            <div style="background:#eef2f6; height:8px; border-radius:999px; overflow:hidden; margin-bottom:14px;">
                <div style="width:{value_width}%; background:#7bd7c5; height:100%;"></div>
            </div>

            <div style="display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:12px;">
                <div style="border:1px solid #eef2f6; border-radius:10px; padding:12px;">
                    <div style="font-size:12px; color:#667085; font-weight:800; text-transform:uppercase; margin-bottom:10px;">
                        Raw answer context
                    </div>
                    <div style="margin-bottom:9px;">
                        <div style="display:flex; justify-content:space-between; font-size:13px; color:#344054; margin-bottom:3px;"><span>Yes</span><span>{e(raw_yes)}</span></div>
                        <div style="background:#eef2f6; height:7px; border-radius:999px; overflow:hidden;"><div style="width:{yes_width}%; background:#7bd7c5; height:100%;"></div></div>
                    </div>
                    <div>
                        <div style="display:flex; justify-content:space-between; font-size:13px; color:#344054; margin-bottom:3px;"><span>No</span><span>{e(raw_no)}</span></div>
                        <div style="background:#eef2f6; height:7px; border-radius:999px; overflow:hidden;"><div style="width:{no_width}%; background:#98a2b3; height:100%;"></div></div>
                    </div>
                </div>

                <div style="border:1px solid #eef2f6; border-radius:10px; padding:12px;">
                    <div style="font-size:12px; color:#667085; font-weight:800; text-transform:uppercase; margin-bottom:10px;">
                        No-answer interpretation
                    </div>
                    <div style="margin-bottom:9px;">
                        <div style="display:flex; justify-content:space-between; font-size:13px; color:#344054; margin-bottom:3px;"><span>Blocking No</span><span>{e(blocking_no)}</span></div>
                        <div style="background:#eef2f6; height:7px; border-radius:999px; overflow:hidden;"><div style="width:{blocking_width}%; background:#f04438; height:100%;"></div></div>
                    </div>
                    <div>
                        <div style="display:flex; justify-content:space-between; font-size:13px; color:#344054; margin-bottom:3px;"><span>Non-blocking No</span><span>{e(non_blocking_no)}</span></div>
                        <div style="background:#eef2f6; height:7px; border-radius:999px; overflow:hidden;"><div style="width:{non_blocking_width}%; background:#7bd7c5; height:100%;"></div></div>
                    </div>
                </div>
            </div>
        </div>
    """


def _kpi_numeric_values_from_sections(report: dict, key: str) -> tuple[list[float], dict]:
    markers = {
        "star_rating": ("star rating", "overall, how would you rate", "overall how would you rate"),
        "software_rating": ("software rating", "software"),
        "nps": ("net promoter score", "nps", "recommend"),
    }.get(key, ())

    if not markers:
        return [], {}

    fallback_values: list[float] = []
    fallback_question: dict = {}

    for section in report.get("sections") or []:
        if not isinstance(section, dict):
            continue

        section_name = _clean_text(section.get("section_name")).lower()
        for question in section.get("quant_questions") or []:
            if not isinstance(question, dict):
                continue

            question_text = _clean_text(question.get("question")).lower()
            haystack = f"{section_name} {question_text}"
            if not any(marker in haystack for marker in markers):
                continue

            numeric_values = [
                numeric
                for numeric in (_to_float_or_none(value) for value in question.get("values") or [])
                if numeric is not None
            ]
            if numeric_values:
                if any(marker in section_name for marker in markers):
                    return numeric_values, question
                if not fallback_values:
                    fallback_values = numeric_values
                    fallback_question = question

    return fallback_values, fallback_question


def _render_kpi_distribution_html(report: dict, kpis: dict, definition: dict) -> str:
    key = definition.get("key")

    if key in {"star_rating", "software_rating"}:
        numeric_values, question = _kpi_numeric_values_from_sections(report, str(key))
        if numeric_values:
            max_value = _question_numeric_scale(question or {"question": definition.get("label")}, numeric_values)
            return _render_numeric_distribution(numeric_values, max_value=max_value, compact=True)

    if key == "nps":
        promoters = _to_int_or_none(kpis.get("nps_promoters"))
        passives = _to_int_or_none(kpis.get("nps_passives"))
        detractors = _to_int_or_none(kpis.get("nps_detractors"))
        if promoters is not None or passives is not None or detractors is not None:
            return _render_count_distribution_rows([
                ("Detractors", int(detractors or 0), _AVERAGE_METER_PINK),
                ("Passives", int(passives or 0), _AVERAGE_METER_YELLOW),
                ("Promoters", int(promoters or 0), _AVERAGE_METER_GREEN),
            ])

        numeric_values, question = _kpi_numeric_values_from_sections(report, "nps")
        if numeric_values:
            max_value = _question_numeric_scale(question or {"question": definition.get("label")}, numeric_values)
            return _render_numeric_distribution(numeric_values, max_value=max_value, compact=True)

    if key == "ready_for_sales":
        diagnostic = _ready_for_sales_diagnostic_for_display(kpis)
        if diagnostic:
            adjusted_ready = int(diagnostic.get("adjusted_ready_count") or 0)
            blocking_no = int(diagnostic.get("blocking_no") or 0)
            non_blocking_no = int(diagnostic.get("non_blocking_no") or 0)
            return _render_count_distribution_rows([
                ("Ready", adjusted_ready, _AVERAGE_METER_GREEN),
                ("Blocking No", blocking_no, _AVERAGE_METER_PINK),
                ("Non-blocking No", non_blocking_no, _AVERAGE_METER_YELLOW),
            ])

    return ""


def _render_kpi_summary(report: dict) -> str:
    if _is_project_report(report):
        return ""

    kpis = report.get("kpis") if isinstance(report, dict) else {}
    if not isinstance(kpis, dict) or not kpis:
        return ""

    cards_html = ""
    visible_card_count = 0
    for definition in _kpi_definitions_for_report(report):
        value = kpis.get(definition["key"])
        count = kpis.get(definition["count_key"])
        if value in (None, ""):
            continue

        if definition["key"] == "ready_for_sales":
            status_label, status_class = _rfs_status_for_value(value)
        else:
            status_label, status_class = _status_for_kpi(
                value,
                target=definition.get("target"),
                direction=definition.get("direction") or "higher",
            )
        width = _bar_width(
            value,
            max_value=100.0 if definition["key"] == "ready_for_sales" else (10.0 if definition["key"] == "nps" else 5.0),
        )
        meter_color = (
            _average_meter_color(value)
            if definition["key"] in {"star_rating", "software_rating"}
            else _AVERAGE_METER_GREEN
        )
        distribution_html = _render_kpi_distribution_html(report, kpis, definition)

        visible_card_count += 1
        cards_html += f"""
            <div style="
                border:1px solid #e5e7eb;
                border-radius:12px;
                padding:14px;
                background:#ffffff;
                min-width:0;
            ">
                <div style="font-size:12px; color:#667085; text-transform:uppercase; letter-spacing:0.04em; font-weight:700;">
                    {e(definition["label"])}
                </div>
                <div style="display:flex; align-items:flex-end; justify-content:space-between; gap:8px; margin-top:8px;">
                    <div style="font-size:28px; font-weight:750; color:#101828; line-height:1;">
                        {_metric_display(value, suffix=definition.get("suffix") or "")}
                    </div>
                    <div style="font-size:12px; color:#667085; white-space:nowrap;">
                        {_count_display(count)}
                    </div>
                </div>
                <div style="background:#eef2f6; height:7px; border-radius:999px; overflow:hidden; margin-top:12px;">
                    <div style="width:{width}%; background:{meter_color}; height:100%;"></div>
                </div>
                <div style="margin-top:10px; display:flex; justify-content:space-between; gap:8px; font-size:12px; color:#667085;">
                    <span class="canonical-report-kpi-status {e(status_class)}">{e(status_label)}</span>
                    <span>Target: {_metric_display(definition.get("target"), suffix=definition.get("suffix") or "")}</span>
                </div>
                {distribution_html}
            </div>
        """

    if visible_card_count <= 0:
        return ""

    rfs_diagnostic_html = _render_ready_for_sales_diagnostic(kpis)

    return f"""
        <section class="card" style="margin-top:16px;">
            <h3 style="margin-bottom:10px;">KPI Summary</h3>
            <div style="{_balanced_grid_style(visible_card_count, max_columns=4, gap=12)}">
                {cards_html}
            </div>
            {rfs_diagnostic_html}
        </section>
    """


def _render_source_surveys(report: dict, *, title: str = "Included Data") -> str:
    if _is_project_report(report):
        return ""

    source_surveys = report.get("source_surveys") or []
    summary = report.get("summary") or {}
    metadata = report.get("metadata") or {}

    if not source_surveys:
        source_rows = """
            <div style="font-size:14px; color:#667085;">No source surveys stored for this report.</div>
        """
    else:
        source_rows = ""
        for survey in source_surveys:
            survey_name = survey.get("survey_name") or survey.get("dataset_type") or "Survey"
            secondary_bits = []
            if survey.get("question_count") not in (None, ""):
                secondary_bits.append(f"{survey.get('question_count')} questions")
            if survey.get("answer_count") not in (None, ""):
                secondary_bits.append(f"{survey.get('answer_count')} answers")
            if survey.get("source_file_name"):
                secondary_bits.append(str(survey.get("source_file_name")))

            source_href = str(survey.get("source_href") or "").strip()
            if not source_href and survey.get("context_id") not in (None, ""):
                source_href = f"/historical/context?context_id={survey.get('context_id')}"

            source_action_html = ""
            if source_href:
                source_action_html = f"""
                    <a href="{e(source_href)}" style="
                        color:#0f766e;
                        font-size:12px;
                        font-weight:750;
                        text-decoration:none;
                        white-space:nowrap;
                    ">Source report</a>
                """

            source_rows += f"""
                <div style="
                    display:grid;
                    grid-template-columns:1fr auto auto;
                    gap:12px;
                    align-items:center;
                    padding:10px 0;
                    border-bottom:1px solid #eef2f6;
                    font-size:14px;
                ">
                    <div>
                        <strong>{e(survey_name)}</strong><br>
                        <span style="color:#667085; font-size:13px;">{e(' · '.join(secondary_bits) or 'Source survey')}</span>
                    </div>
                    <div style="font-weight:700; color:#344054; white-space:nowrap;">
                        {e(survey.get("response_count") or 0)} responses
                    </div>
                    <div>{source_action_html}</div>
                </div>
            """

    generated_meta = metadata.get("updated_at") or metadata.get("created_at") or ""

    return f"""
        <details style="
            margin-top:18px;
            border:1px solid #e5e7eb;
            border-radius:12px;
            background:#ffffff;
            overflow:hidden;
        ">
            <summary style="
                padding:12px 14px;
                background:#f9fafb;
                cursor:pointer;
                color:#475467;
                font-size:13px;
                font-weight:750;
            ">
                {e(title)}
                <span style="font-weight:500; color:#667085; margin-left:8px;">
                    {e(summary.get("section_count") or 0)} sections · {e(summary.get("response_count") or 0)} responses · {e(summary.get("answer_count") or 0)} answers
                </span>
            </summary>
            <div style="padding:12px 14px;">
                {source_rows}
                <div style="margin-top:10px; padding-top:10px; border-top:1px solid #eef2f6; color:#667085; font-size:12px;">
                    Generated: {e(generated_meta or "—")}
                </div>
            </div>
        </details>
    """


def _render_participant_profile(report: dict) -> str:
    participant_profile = report.get("participant_profile") or {}
    questions = participant_profile.get("questions") if isinstance(participant_profile, dict) else []

    if not questions:
        return ""

    cards_html = ""
    visible_card_count = 0
    for question in questions[:12]:
        if not isinstance(question, dict):
            continue

        options = question.get("options") or []
        if not options:
            continue

        total_count = int(question.get("total_count") or 0)
        max_count = max([int(option.get("count") or 0) for option in options] or [1])
        option_rows = ""

        for option in options[:8]:
            label = option.get("label") or "-"
            count = int(option.get("count") or 0)
            width = int((count / max_count) * 100) if max_count else 0
            option_rows += f"""
                <div style="margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; font-size:13px; color:#344054; margin-bottom:3px; gap:8px;">
                        <div>{e(label)}</div>
                        <div style="font-variant-numeric:tabular-nums;">{e(count)}</div>
                    </div>
                    <div style="background:#eef2f6; height:7px; border-radius:999px; overflow:hidden;">
                        <div style="width:{width}%; background:#7bd7c5; height:100%;"></div>
                    </div>
                </div>
            """

        if len(options) > 8:
            option_rows += f"""
                <div style="font-size:12px; color:#667085; margin-top:6px;">
                    + {len(options) - 8} more response option(s)
                </div>
            """

        visible_card_count += 1
        cards_html += f"""
            <div style="
                border:1px solid #e5e7eb;
                border-radius:12px;
                padding:14px;
                background:#ffffff;
                min-width:0;
            ">
                <div style="font-size:14px; font-weight:750; color:#344054; line-height:1.35; margin-bottom:10px;">
                    {e(question.get('question') or 'Profile question')}
                </div>
                {option_rows}
                <div style="font-size:12px; color:#667085; margin-top:10px;">
                    {e(total_count)} response value(s)
                </div>
            </div>
        """

    if not cards_html:
        return ""

    title = participant_profile.get("title") or "Participant Profile / User Context"

    return f"""
        <details style="
            margin-top:18px;
            border:1px solid #d9f3ee;
            border-radius:12px;
            background:#ffffff;
            overflow:hidden;
        " open>
            <summary style="
                padding:12px 14px;
                background:#f4fffc;
                cursor:pointer;
                color:#344054;
                font-size:13px;
                font-weight:750;
            ">
                {e(title)}
                <span style="font-weight:500; color:#667085; margin-left:8px;">
                    {e(len(questions))} profile question(s)
                </span>
            </summary>
            <div style="padding:14px;">
                <div style="font-size:13px; color:#667085; line-height:1.5; margin-bottom:12px;">
                    Profile and screener answers are shown here as report context instead of being mixed into Section Results.
                </div>
                <div style="{_balanced_grid_style(visible_card_count, max_columns=4, gap=12)}">
                    {cards_html}
                </div>
            </div>
        </details>
    """


def _render_sections(report: dict, *, section_actions_html: str = "", section_prefix: str = "canonical") -> str:
    is_project_report = _is_project_report(report)
    sections = _sort_sections(report.get("sections") or [])

    if is_project_report:
        sections = [
            section for section in sections
            if _section_report_group(section) != "KPI Summary and Progression"
        ]

    if not sections:
        empty_message = (
            "No project report detail sections are stored yet."
            if is_project_report
            else "No report sections are stored yet."
        )
        return f"""
            <div class="card" style="margin-top:20px; color:#667085; font-size:14px;">
                {e(empty_message)}
            </div>
        """

    section_heading = "Project Report Details" if is_project_report else "Section Results"

    html = f"""
        <div style="display:flex; align-items:center; justify-content:space-between; margin-top:24px; margin-bottom:10px; gap:12px;">
            <div style="display:flex; align-items:center; gap:12px;">
                <h3 style="margin:0;">{e(section_heading)}</h3>
                <div style="font-size:12px; color:#667085; display:flex; gap:8px; margin-left:8px;">
                    <a href="#" onclick="expandCanonicalReportSections('{e(section_prefix)}'); return false;" style="color:#667085;">Expand all</a>
                    <span>|</span>
                    <a href="#" onclick="collapseCanonicalReportSections('{e(section_prefix)}'); return false;" style="color:#667085;">Collapse all</a>
                </div>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                {section_actions_html}
            </div>
        </div>
    """

    last_group = None

    for index, section in enumerate(sections, start=1):
        report_group = _section_report_group(section)

        if report_group != last_group:
            if last_group is not None:
                html += "</div></details>"

            html += f"""
                <details class="canonical-report-phase-group" data-canonical-report-group="{e(section_prefix)}" open style="
                    margin-top:18px;
                    border:1px solid #d9f3ee;
                    border-radius:12px;
                    background:#ffffff;
                    overflow:hidden;
                ">
                    <summary style="
                        padding:11px 14px;
                        border-left:4px solid #7bd7c5;
                        background:#f4fffc;
                        color:#1f2937;
                        font-size:13px;
                        font-weight:750;
                        letter-spacing:0.03em;
                        text-transform:uppercase;
                        cursor:pointer;
                    ">{e(report_group)}</summary>
                    <div style="padding:12px 14px 16px 14px;">
            """
            last_group = report_group

        section_name = section.get("section_name") or f"Section {index}"
        survey_label = section.get("survey_name") or section.get("dataset_type") or "Survey"
        report_kpis = report.get("kpis") if isinstance(report.get("kpis"), dict) else {}
        if _is_ready_for_sales_section(section) and report_kpis.get("ready_for_sales") not in (None, ""):
            section_preview_html, section_border_color = _ready_for_sales_section_preview_html(report_kpis)
        else:
            section_preview_html, section_border_color = _section_preview_html(section)

        quant_questions = [
            question for question in section.get("quant_questions") or []
            if isinstance(question, dict)
        ]
        question_grid_style = _balanced_grid_style(
            len(quant_questions),
            max_columns=4,
            gap=12,
        )

        html += f"""
            <div class="rail-group historical-section-result collapsed" data-canonical-report-section="{e(section_prefix)}" style="
                margin-top:12px;
                margin-bottom:12px;
                border:1px solid #e5e7eb;
                border-left:4px solid {section_border_color};
                border-radius:12px;
                background:#fafafa;
            ">
                <div class="rail-toggle" style="
                    display:flex;
                    align-items:center;
                    padding:14px 16px;
                    border-bottom:1px solid #eef2f6;
                    cursor:pointer;
                    gap:12px;
                ">
                    <div style="min-width:0;">
                        <div style="font-size:15px; font-weight:700; color:#344054;">{e(section_name)}</div>
                    </div>
                    <div style="display:flex; align-items:center; gap:12px; margin-left:auto; font-size:12px; color:#667085;">
                        {section_preview_html}
                        <div style="white-space:nowrap;">{e(survey_label)}</div>
                    </div>
                </div>
                <div class="rail-content" style="padding:14px 16px;">
                    <div style="{question_grid_style} margin-bottom:10px;">
        """

        rfs_section_html = ""
        if _is_ready_for_sales_section(section) and report_kpis.get("ready_for_sales") not in (None, ""):
            rfs_section_html = _render_ready_for_sales_section_result(report_kpis)

        if rfs_section_html:
            html += rfs_section_html
        else:
            for question in quant_questions:
                html += _render_question_card(question)

        html += "</div>"
        html += _render_comment_buckets(section)
        html += _render_swot_grid(section)
        html += "</div></div>"

    if last_group is not None:
        html += "</div></details>"

    return html


def _render_insights(report: dict, *, insights_action_html: str = "") -> str:
    insights = [
        insight for insight in report.get("insights") or []
        if isinstance(insight, dict)
    ]

    if not insights and not str(insights_action_html or "").strip():
        return ""

    open_attr = " open" if insights else ""
    action_html = ""
    if str(insights_action_html or "").strip():
        action_html = f"""
            <div style="display:flex; justify-content:flex-end; gap:8px; flex-wrap:wrap;">
                {insights_action_html}
            </div>
        """

    html = f"""
        <details class="card" style="margin-top:20px;"{open_attr}>
            <summary style="
                cursor:pointer;
                display:flex;
                align-items:center;
                justify-content:space-between;
                gap:12px;
                list-style:none;
            ">
                <h3 style="margin:0;">Insights</h3>
                <span style="color:#667085; font-size:13px; font-weight:600;">
                    {e(len(insights))} insight(s)
                </span>
            </summary>
            <div style="margin-top:12px;">
                {action_html}
    """

    if not insights:
        html += """
            <div style="color:#667085; font-size:14px; margin-top:10px;">
                No insights generated yet.
            </div>
        """
    else:
        insight_grid_style = _balanced_grid_style(
            len(insights),
            max_columns=3,
            gap=16,
            align="start",
        )
        html += f"""
            <div style="{insight_grid_style} margin-top:10px;">
        """

        for insight in insights:
            title = e(insight.get("title") or insight.get("insight_type") or "Untitled Insight")
            section_name = e(insight.get("section_name") or insight.get("survey_name") or "General")
            explanation = e(insight.get("explanation") or insight.get("insight_summary") or "")
            impact = (insight.get("impact") or "medium").lower()
            sentiment = (insight.get("sentiment") or "neutral").lower()
            evidence = insight.get("evidence") or []

            border_color = "#98a2b3"
            if sentiment == "positive":
                border_color = "#12b76a" if impact == "high" else "#7bd7c5"
            elif sentiment == "negative":
                border_color = "#f04438" if impact == "high" else "#f79009"
            elif sentiment == "mixed":
                border_color = "#7a5af8"

            evidence_html = ""
            for item in evidence[:4]:
                evidence_html += f"<li>{e(item)}</li>"
            if not evidence_html:
                evidence_html = "<li>No supporting evidence stored.</li>"

            html += f"""
                <div style="padding:14px; border:1px solid #e5e7eb; border-left:4px solid {border_color}; border-radius:10px; background:white; min-width:0;">
                    <div style="font-size:11px; color:#667085; margin-bottom:6px; text-transform:uppercase; font-weight:700; letter-spacing:0.04em;">
                        {section_name}
                    </div>
                    <div style="font-size:12px; color:#667085; margin-bottom:6px; text-transform:uppercase; font-weight:700;">
                        {e(impact.upper())} • {e(sentiment.upper())}
                    </div>
                    <div style="font-weight:700; margin-bottom:8px; color:#344054;">{title}</div>
                    <div style="font-size:14px; color:#475467; line-height:1.5; margin-bottom:10px;">{explanation}</div>
                    <ul style="margin:0; padding-left:18px; font-size:13px; color:#667085; line-height:1.5;">
                        {evidence_html}
                    </ul>
                </div>
            """

        html += "</div>"

    html += "</div></details>"
    return html


def _render_executive_summary(report: dict) -> str:
    if _is_project_report(report):
        return ""

    summary = report.get("summary") or {}
    executive_summary = _clean_text(summary.get("executive_summary"))

    if not executive_summary:
        return ""

    return f"""
        <section style="
            margin-top:16px;
            border:1px solid #bdeee7;
            border-left:5px solid #7bd7c5;
            border-radius:14px;
            background:linear-gradient(90deg, #f4fffc 0%, #ffffff 72%);
            padding:16px 18px;
            box-shadow:0 1px 2px rgba(16, 24, 40, 0.04);
        ">
            <h3 style="margin:0 0 8px 0; color:#101828;">Executive Summary</h3>
            <div style="font-size:15px; line-height:1.7; color:#344054; max-width:1120px;">
                {e(executive_summary)}
            </div>
        </section>
    """


def render_canonical_report_panel(
    *,
    report: dict,
    panel_id: str,
    panel_title: str,
    panel_status: str,
    notice_html: str = "",
    primary_action_html: str = "",
    primary_action_placement: str = "body",
    section_actions_html: str = "",
    insights_action_html: str = "",
    source_title: str = "Report Source Details",
) -> str:
    """
    Render the shared report presentation used by report-producing workflows.

    This renderer is intentionally read-only. Report generation and persistence stay
    in POST-only handlers/services; GET paths pass already-saved report JSON here.
    """

    if not isinstance(report, dict):
        report = {}

    safe_prefix = panel_id.replace(" ", "-")
    clean_primary_action_html = str(primary_action_html or "").strip()
    use_summary_actions = clean_primary_action_html and primary_action_placement == "summary"

    summary_action_html = ""
    body_action_html = ""
    if clean_primary_action_html and use_summary_actions:
        summary_action_html = f"""
            <div class="canonical-report-summary-actions" style="
                display:flex;
                align-items:center;
                justify-content:flex-end;
                gap:8px;
                flex-wrap:wrap;
                margin-left:auto;
                line-height:1;
            ">
                {primary_action_html}
            </div>
        """
    elif clean_primary_action_html:
        body_action_html = f"""
            <div style="display:flex; justify-content:flex-end; margin-top:8px; gap:8px; flex-wrap:wrap;">
                {primary_action_html}
            </div>
        """

    return f"""
    <style>
        #{e(panel_id)} .canonical-report-summary-actions form {{
            align-items: center;
            display: flex;
            line-height: 1;
            margin: 0;
        }}

        #{e(panel_id)} .canonical-report-summary-actions .historical-action-pill {{
            align-items: center;
            box-sizing: border-box;
            display: inline-flex;
            font-family: inherit;
            font-size: 12px;
            font-weight: 700;
            justify-content: center;
            line-height: 1;
            min-height: 30px;
            padding-bottom: 0;
            padding-top: 0;
            text-decoration: none;
            vertical-align: middle;
            white-space: nowrap;
        }}
    </style>

    <details id="{e(panel_id)}" class="ut-lead-section product-trial-report-section canonical-report-section" open>
        <summary class="ut-lead-section-summary" style="display:flex; align-items:center; gap:12px;">
            <span style="display:flex; align-items:baseline; gap:4px; min-width:0;">
                <strong>{e(panel_title)}</strong>
                <span class="muted small">— {e(panel_status)}</span>
            </span>
            {summary_action_html}
        </summary>
        <div class="ut-lead-section-body">
            {notice_html}
            {body_action_html}
            {_render_executive_summary(report)}
            {_render_kpi_summary(report)}
            {_render_source_surveys(report, title=source_title)}
            {_render_participant_profile(report)}
            {_render_sections(report, section_actions_html=section_actions_html, section_prefix=safe_prefix)}
            {_render_insights(report, insights_action_html=insights_action_html)}
        </div>
    </details>

    <script>
    function expandCanonicalReportSections(prefix) {{
        document.querySelectorAll('[data-canonical-report-section="' + prefix + '"]').forEach((section) => {{
            section.classList.remove('collapsed');
        }});
        document.querySelectorAll('[data-canonical-report-group="' + prefix + '"]').forEach((group) => {{
            group.open = true;
        }});
    }}

    function collapseCanonicalReportSections(prefix) {{
        document.querySelectorAll('[data-canonical-report-section="' + prefix + '"]').forEach((section) => {{
            section.classList.add('collapsed');
        }});
        document.querySelectorAll('[data-canonical-report-group="' + prefix + '"]').forEach((group) => {{
            group.open = false;
        }});
    }}
    </script>
    """