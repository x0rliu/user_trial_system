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

    key_findings = section_analysis.get("key_findings") or []
    qualitative_insights = section_analysis.get("qualitative_insights") or []
    notable_quotes = section_analysis.get("notable_quotes") or []

    if not key_findings and not qualitative_insights and not notable_quotes:
        return ""

    return f"""
        <div style="
            display:grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap:12px;
            margin-top:12px;
        ">
            {_render_section_analysis_card("Key Findings", key_findings)}
            {_render_section_analysis_card("Qualitative Insights", qualitative_insights)}
            {_render_section_analysis_card("Notable Quotes", notable_quotes)}
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

    return f"""
        <section class="card" style="margin-top:16px;">
            <h3 style="margin-bottom:10px;">KPI Summary</h3>
            <div style="{_balanced_grid_style(visible_card_count, max_columns=4, gap=12)}">
                {cards_html}
            </div>
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
                border-radius:12px;
                background:#fafafa;
            ">
                <div class="rail-toggle" style="
                    display:flex;
                    align-items:center;
                    padding:14px 16px;
                    border-bottom:1px solid #eef2f6;
                    cursor:pointer;
                ">
                    <div style="font-size:15px; font-weight:700; color:#344054;">{e(section_name)}</div>
                    <div style="display:flex; align-items:center; gap:12px; margin-left:auto; font-size:12px; color:#667085;">
                        {e(survey_label)}
                    </div>
                </div>
                <div class="rail-content" style="padding:14px 16px;">
                    <div style="{question_grid_style} margin-bottom:10px;">
        """

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
        return """
            <section class="card" style="margin-top:16px;">
                <h3 style="margin-bottom:8px;">Executive Summary</h3>
                <div style="font-size:14px; color:#667085; line-height:1.6;">
                    No executive summary has been generated yet. The section results below remain available for review.
                </div>
            </section>
        """

    return f"""
        <section class="card" style="margin-top:16px;">
            <h3 style="margin-bottom:8px;">Executive Summary</h3>
            <div style="font-size:14px; line-height:1.6; color:#344054;">
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
    action_row_html = ""
    if str(primary_action_html or "").strip():
        action_row_html = f"""
            <div style="display:flex; justify-content:flex-end; margin-top:8px; gap:8px; flex-wrap:wrap;">
                {primary_action_html}
            </div>
        """

    return f"""
    <details id="{e(panel_id)}" class="ut-lead-section product-trial-report-section canonical-report-section" open>
        <summary class="ut-lead-section-summary">
            <strong>{e(panel_title)}</strong>
            <span class="muted small">— {e(panel_status)}</span>
        </summary>
        <div class="ut-lead-section-body">
            {notice_html}
            {action_row_html}
            {_render_executive_summary(report)}
            {_render_kpi_summary(report.get("kpis") or {})}
            {_render_source_surveys(report, title=source_title)}
            {_render_participant_profile(report)}
            {_render_sections(report, section_actions_html=section_actions_html, section_prefix=safe_prefix)}
            {_render_insights(report, insights_action_html=insights_action_html)}
        </div>
    </details>

    <script>
    function expandCanonicalReportSections(prefix) {{
        document.querySelectorAll('[data-canonical-report-group="' + prefix + '"]').forEach((group) => {{
            group.open = true;
        }});
        document.querySelectorAll('[data-canonical-report-section="' + prefix + '"]').forEach((section) => {{
            section.classList.remove('collapsed');
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