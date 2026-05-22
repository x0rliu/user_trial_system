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


_KPI_DEFINITIONS = [
    {
        "key": "star_rating",
        "label": "Star Rating",
        "count_key": "star_rating_count",
        "suffix": " / 5",
        "target": 4.0,
        "direction": "higher",
    },
    {
        "key": "software_rating",
        "label": "Software Rating",
        "count_key": "software_rating_count",
        "suffix": " / 5",
        "target": 4.0,
        "direction": "higher",
    },
    {
        "key": "nps",
        "label": "NPS",
        "count_key": "nps_count",
        "suffix": "",
        "target": 0,
        "direction": "higher",
    },
    {
        "key": "ready_for_sales",
        "label": "Ready for Sales",
        "count_key": "ready_for_sales_count",
        "suffix": "%",
        "target": 80,
        "direction": "higher",
    },
]


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


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


def _to_float_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
        return "No score", "#98a2b3"

    if score >= 4.0:
        return "Positive", "#12b76a"

    if score >= 3.3:
        return "Mixed", "#f79009"

    return "Needs attention", "#f04438"


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


def _section_preview_html(section: dict) -> tuple[str, str]:
    score = _section_score(section)
    sentiment_label, border_color = _section_sentiment(score)

    preview_bits = []
    if score is not None:
        preview_bits.append(f"Avg {_metric_display(score, suffix=' / 5')}")
    preview_bits.append(sentiment_label)

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
        width = _bar_width(average, max_value=5.0)
        return f"""
            <div style="
                min-height:92px;
                padding:12px 14px;
                border:1px solid #e5e7eb;
                border-radius:10px;
                display:flex;
                align-items:center;
                justify-content:space-between;
                gap:14px;
                box-sizing:border-box;
                background:white;
            ">
                <div style="font-size:14px; flex:1; line-height:1.4; color:#344054;">
                    {question_text}
                </div>
                <div style="display:flex; align-items:center; gap:8px; min-width:150px; justify-content:flex-end;">
                    <div style="background:#eef2f6; height:7px; width:96px; border-radius:999px; overflow:hidden;">
                        <div style="width:{width}%; background:#7bd7c5; height:100%;"></div>
                    </div>
                    <div style="font-size:13px; color:#475467; width:40px; text-align:right; font-variant-numeric:tabular-nums;">
                        {average:.2f}
                    </div>
                </div>
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
                        <div style="width:{width}%; background:#7bd7c5; height:100%;"></div>
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


def _render_ready_for_sales_diagnostic(kpis: dict) -> str:
    diagnostic = kpis.get("ready_for_sales_diagnostic")
    if not isinstance(diagnostic, dict):
        return ""

    raw_yes = diagnostic.get("raw_yes")
    raw_no = diagnostic.get("raw_no")
    blocking_no = diagnostic.get("blocking_no")
    non_blocking_no = diagnostic.get("non_blocking_no")
    adjusted_ready_count = diagnostic.get("adjusted_ready_count")
    total_count = diagnostic.get("total_count")

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
    status_label, status_class = _status_for_kpi(
        value,
        target=80,
        direction="higher",
    )
    border_color = _rfs_status_color(status_class)
    diagnostic = kpis.get("ready_for_sales_diagnostic") if isinstance(kpis.get("ready_for_sales_diagnostic"), dict) else {}
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

    diagnostic = kpis.get("ready_for_sales_diagnostic") if isinstance(kpis.get("ready_for_sales_diagnostic"), dict) else {}
    raw_yes = int(diagnostic.get("raw_yes") or 0)
    raw_no = int(diagnostic.get("raw_no") or 0)
    blocking_no = int(diagnostic.get("blocking_no") or 0)
    non_blocking_no = int(diagnostic.get("non_blocking_no") or 0)
    adjusted_ready = int(diagnostic.get("adjusted_ready_count") or 0)
    total_count = int(diagnostic.get("total_count") or 0)
    raw_total = raw_yes + raw_no

    status_label, status_class = _status_for_kpi(
        value,
        target=80,
        direction="higher",
    )
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
                    <div>Target: 80%</div>
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


def _render_kpi_summary(kpis: dict) -> str:
    if not isinstance(kpis, dict) or not kpis:
        return ""

    cards_html = ""
    visible_card_count = 0
    for definition in _KPI_DEFINITIONS:
        value = kpis.get(definition["key"])
        count = kpis.get(definition["count_key"])
        if value in (None, ""):
            continue

        status_label, status_class = _status_for_kpi(
            value,
            target=definition.get("target"),
            direction=definition.get("direction") or "higher",
        )
        width = _bar_width(
            value,
            max_value=100.0 if definition["key"] == "ready_for_sales" else (10.0 if definition["key"] == "nps" else 5.0),
        )

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
                    <div style="width:{width}%; background:#7bd7c5; height:100%;"></div>
                </div>
                <div style="margin-top:10px; display:flex; justify-content:space-between; gap:8px; font-size:12px; color:#667085;">
                    <span class="canonical-report-kpi-status {e(status_class)}">{e(status_label)}</span>
                    <span>Target: {_metric_display(definition.get("target"), suffix=definition.get("suffix") or "")}</span>
                </div>
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
    sections = _sort_sections(report.get("sections") or [])
    if not sections:
        return """
            <div class="card" style="margin-top:20px; color:#667085; font-size:14px;">
                No report sections are stored yet.
            </div>
        """

    html = f"""
        <div style="display:flex; align-items:center; justify-content:space-between; margin-top:24px; margin-bottom:10px; gap:12px;">
            <div style="display:flex; align-items:center; gap:12px;">
                <h3 style="margin:0;">Section Results</h3>
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
            {_render_kpi_summary(report.get("kpis") or {})}
            {_render_source_surveys(report, title=source_title)}
            {_render_participant_profile(report)}
            {_render_sections(report, section_actions_html=section_actions_html, section_prefix=safe_prefix)}
            {_render_insights(report, insights_action_html=insights_action_html)}
        </div>
    </details>

    <script>
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