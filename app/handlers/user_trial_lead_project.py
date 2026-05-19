# app/handlers/user_trial_lead_project.py

from app.db.user_roles import get_effective_permission_level
from app.db.user_trial_lead import (
    get_project_round_by_id,
    update_project_round_overview,
    lock_project_round_overview,
    add_round_survey,
    lock_project_round_planning,
    get_round_surveys,
    get_round_profile_criteria,
    add_round_profile_criteria,
    delete_round_profile_criteria
)
import os
import json
from datetime import datetime
from pathlib import Path
from app.db.user_pool import get_display_name_by_user_id
from app.db.user_pool_country_codes import get_country_codes
from app.db.user_trial_lead import update_recruiting_config
from app.handlers.user_trial_lead_project_survey_results import render_survey_results_section
from app.db.survey_answers import get_survey_response_attribution_summary
from app.db.survey_recruiting_kpis import get_recruiting_kpis  # add near imports
from app.db.survey_kpis import get_round_product_kpis
from app.db.product_trial_reports import get_product_trial_report
from app.db.project_rounds import get_round_stakeholders
from app.services.constraint_capture_service import (
    build_constraint_capture_packet,
    deactivate_explicit_constraint,
    save_explicit_constraint,
)
from app.utils.html_escape import escape_html as e
from app.utils.csrf import generate_csrf_token
from app.utils.upload_security import require_csv_upload
from app.services.upload_controls import render_csv_dropzone


# Constraint capture plumbing exists, but the UI is deferred until post-MVP.
# Reason: constraints need clearer product/UT definition before stakeholders use them.
ENABLE_CONSTRAINT_CAPTURE_UI = False


_RESULT_SURVEY_EXCLUDED_TYPE_IDS = {
    "UTSurveyType0001",  # Recruiting
    "UTSurveyType0027",  # Consolidated/internal results
    "UTSurveyType0028",  # Report issue; rendered separately
}


def _clean_survey_display_name(value: str | None) -> str:
    label = str(value or "").replace("_", " ").strip()
    return label or "Survey"


def _is_participant_result_survey(survey: dict | None) -> bool:
    if not survey:
        return False

    survey_type_id = survey.get("SurveyTypeID")
    survey_type_name = (survey.get("SurveyTypeName") or "").strip().lower()

    if survey_type_id in _RESULT_SURVEY_EXCLUDED_TYPE_IDS:
        return False

    if survey_type_name in ("recruiting", "consolidated", "report_issue"):
        return False

    return True


def _get_result_surveys(round_surveys: list[dict] | None) -> list[dict]:
    return [
        survey
        for survey in (round_surveys or [])
        if _is_participant_result_survey(survey)
    ]


def _render_dynamic_survey_results_sections(
    *,
    round_data: dict,
    project_id: str,
    result_surveys: list[dict],
    survey_stats: list[dict],
    upload_status_for_survey,
    upload_summary_for_survey,
    attribution_summary_for_survey,
) -> str:
    template = Path(
        "app/templates/ut_lead/ut_lead_project_survey_results.html"
    ).read_text(encoding="utf-8")

    if not result_surveys:
        return """
        <details class="ut-lead-section" open>
            <summary class="ut-lead-section-summary">
                <strong>Survey Results</strong>
                <span class="muted small"> — Not Configured</span>
            </summary>

            <div class="ut-lead-section-body">
                <div class="muted small">
                    No participant result surveys are configured for this round yet.
                </div>
            </div>
        </details>
        """

    sections = []

    for index, survey in enumerate(result_surveys, start=1):
        round_survey_id = survey.get("RoundSurveyID") or survey.get("SurveyID")
        survey_type_id = survey.get("SurveyTypeID")
        survey_title = _clean_survey_display_name(
            survey.get("SurveyTypeName") or f"Survey {index}"
        )

        content_html = render_survey_results_section(
            round_data=round_data,
            survey_stats=survey_stats,
            upload_status=upload_status_for_survey(
                round_survey_id=round_survey_id,
                survey_type_id=survey_type_id,
            ),
            upload_summary=upload_summary_for_survey(
                round_survey_id=round_survey_id,
                survey_type_id=survey_type_id,
            ),
            attribution_summary=attribution_summary_for_survey(
                survey_type_id=survey_type_id,
            ),
            project_id=project_id,
            section_title=survey_title,
            section_subtitle="Basic Metrics",
            survey_type_id=survey_type_id,
            round_survey_id=round_survey_id,
        )

        sections.append(
            template
            .replace("__SURVEY_RESULTS_TITLE__", e(survey_title))
            .replace("__SURVEY_RESULTS_SUBTITLE__", "Basic Metrics")
            .replace("__SURVEY_RESULTS_CONTENT__", content_html)
        )

    return "\n".join(sections)


def _can_access_ut_lead_round(*, user_id: str, round_data: dict | None) -> bool:
    if not user_id or not round_data:
        return False

    permission_level = get_effective_permission_level(user_id)
    if permission_level >= 100:
        return True

    return str(round_data.get("UTLead_UserID") or "") == str(user_id)


def _inject_ut_lead_project_csrf_inputs(*, html: str, csrf_token: str) -> str:
    """
    Add the same page-scoped CSRF token to every POST form that submits
    to /ut-lead/project. This page renders many independently-built
    sections, including upload forms, so the final assembled page is the
    safest single insertion point.
    """

    import re

    csrf_input_html = (
        f'<input type="hidden" name="csrf_token" value="{e(csrf_token)}">'
    )

    pattern = re.compile(
        r"(<form\b(?=[^>]*\bmethod=[\"']post[\"'])(?=[^>]*\baction=[\"']/ut-lead/project[\"'])[^>]*>)",
        flags=re.IGNORECASE | re.DOTALL,
    )

    return pattern.sub(r"\1\n" + csrf_input_html, html)


def _render_product_trial_report_section(
    *,
    round_id: int,
    report_status: str | None,
) -> str:
    """
    Render the saved Product Trial report section on the UT Lead project page.

    GET renders never generate reports. This renderer intentionally mirrors the
    Historical report presentation instead of maintaining a separate Product
    Trial report UI language.
    """

    report_result = get_product_trial_report(round_id=int(round_id))
    report = report_result.get("report") if report_result.get("success") else None
    report_error = report_result.get("error")

    def _success_toast(message: str) -> str:
        return f"""
            <div data-product-report-toast="true" style="
                position:fixed;
                right:24px;
                bottom:24px;
                z-index:9999;
                max-width:360px;
                padding:10px 12px;
                border:1px solid #b7efd5;
                border-radius:10px;
                background:#ecfff5;
                color:#166534;
                font-size:13px;
                font-weight:650;
                box-shadow:0 10px 24px rgba(15,23,42,0.16);
                opacity:1;
                transition:opacity 0.35s ease;
            ">
                {e(message)}
            </div>
            <script>
                setTimeout(function () {{
                    const toast = document.querySelector('[data-product-report-toast="true"]');
                    if (toast) {{
                        toast.style.opacity = '0';
                        setTimeout(function () {{ toast.remove(); }}, 400);
                    }}
                }}, 2800);
            </script>
        """

    notice_html = ""
    if report_status == "generated":
        notice_html = _success_toast("Product Trial report generated.")
    elif report_status == "names_generated":
        notice_html = _success_toast("Product Trial section names generated.")
    elif report_status == "summaries_generated":
        notice_html = _success_toast("Product Trial section summaries generated.")
    elif report_status == "insights_generated":
        notice_html = _success_toast("Product Trial insights generated.")
    elif report_status == "not_generated":
        notice_html = """
            <div class="product-report-notice product-report-notice-error">
                Generate the Product Trial report before generating names, summaries, or insights.
            </div>
        """
    elif report_status == "no_data":
        notice_html = """
            <div class="product-report-notice product-report-notice-error">
                Report could not be generated because no participant result answers are stored for this round yet.
            </div>
        """
    elif report_status == "table_missing":
        notice_html = """
            <div class="product-report-notice product-report-notice-error">
                Report storage table is missing. Run the product_trial_reports migration before generating reports.
            </div>
        """
    elif report_status == "error":
        notice_html = """
            <div class="product-report-notice product-report-notice-error">
                Report generation failed. Stored survey answers were not changed.
            </div>
        """

    generate_label = "Regenerate Report" if report else "Generate Report"

    form_html = f"""
        <form method="post" action="/ut-lead/project" style="margin:0;" data-analysis-loading="true">
            <input type="hidden" name="round_id" value="{e(round_id)}">
            <input type="hidden" name="action" value="generate_product_trial_report">
            <button type="submit" style="font-size:12px; padding:6px 10px;">
                {e(generate_label)}
            </button>
        </form>
    """

    if not report:
        table_missing_note = ""
        if report_error == "table_missing":
            table_missing_note = """
                <div style="font-size:13px; color:#991b1b; margin-top:8px;">
                    Report storage is not available yet. Apply the DB migration before using this section.
                </div>
            """

        return f"""
        <details class="ut-lead-section product-trial-report-section" open>
            <summary class="ut-lead-section-summary">
                <strong>Product Trial Report</strong>
                <span class="muted small">— Not Generated</span>
            </summary>
            <div class="ut-lead-section-body">
                {notice_html}
                <div class="card" style="margin-top:16px; display:flex; justify-content:space-between; gap:16px; align-items:flex-start;">
                    <div>
                        <h3 style="margin-bottom:8px;">Product Trial Report</h3>
                        <div style="font-size:14px; line-height:1.6; color:#333;">
                            Generate the report using the same section naming and SWOT summary pattern as Historical reports.
                        </div>
                        {table_missing_note}
                    </div>
                    {form_html}
                </div>
            </div>
        </details>
        """

    metadata = report.get("metadata") or {}
    summary = report.get("summary") or {}
    kpis = report.get("kpis") or {}
    source_surveys = report.get("source_surveys") or []
    sections = report.get("sections") or []
    insights = report.get("insights") or []

    def _metric_display(value, *, suffix="", decimals=1):
        if value in (None, ""):
            return "—"
        try:
            text = f"{float(value):.{decimals}f}"
        except (TypeError, ValueError):
            text = str(value)
        if text.endswith(".0"):
            text = text[:-2]
        return f"{text}{suffix}"

    def _metric_count_display(value):
        try:
            count = int(value or 0)
        except (TypeError, ValueError):
            count = 0
        return f"n={count}" if count else "No KPI data"

    def _source_survey_rows():
        if not source_surveys:
            return """
                <div style="font-size:14px; color:#666;">
                    No source surveys stored for this report.
                </div>
            """

        rows_html = ""
        for survey in source_surveys:
            rows_html += f"""
                <div style="
                    display:grid;
                    grid-template-columns: 1fr auto;
                    gap:12px;
                    padding:8px 0;
                    border-bottom:1px solid #eee;
                    font-size:14px;
                ">
                    <div>
                        <strong>{e(survey.get("survey_name") or "Survey")}</strong><br>
                        <span style="color:#666; font-size:13px;">
                            {e(survey.get("question_count") or 0)} questions · {e(survey.get("answer_count") or 0)} answers
                        </span>
                    </div>
                    <div style="font-weight:600;">
                        {e(survey.get("response_count") or 0)} responses
                    </div>
                </div>
            """
        return rows_html

    def _parse_swot(section):
        raw_json = section.get("swot_json")
        parsed = section.get("swot") if isinstance(section.get("swot"), dict) else None

        if not parsed and raw_json:
            try:
                parsed = json.loads(raw_json)
            except Exception:
                parsed = {}

        return parsed or {}

    def _build_items(items):
        html_items = ""
        for i, item in enumerate(items or []):
            if i == 0:
                html_items += f"<li style='font-weight:500;'>{e(item)}</li>"
            else:
                html_items += f"<li style='color:#777;'>{e(item)}</li>"
        return html_items

    def _swot_card(title, icon, items):
        return f"""
            <div style="
                border:1px solid #e5e5e5;
                border-radius:6px;
                padding:10px 12px;
                width:calc(50% - 6px);
                box-sizing:border-box;
            ">
                <div style="
                    font-size:13px;
                    color:#888;
                    text-transform:uppercase;
                    margin-bottom:6px;
                ">
                    {icon} {title}
                </div>

                <ul style="
                    margin:0;
                    padding-left:16px;
                    font-size:14px;
                ">
                    {_build_items(items)}
                </ul>
            </div>
        """

    def _section_report_group(section):
        group = (section.get("report_group") or "").strip()
        if group:
            return group

        section_name = (section.get("section_name") or "").strip().lower()
        survey_name = (section.get("survey_name") or "").strip().lower()
        question_text = " ".join(
            str(question.get("question") or "")
            for question in section.get("quant_questions") or []
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

    group_display_order = {
        "KPIs": 10,
        "OOBE": 20,
        "First Impressions": 30,
        "Usage": 40,
        "Other": 90,
    }
    sections = [
        section for _source_index, section in sorted(
            enumerate(sections, start=1),
            key=lambda item: (
                group_display_order.get(_section_report_group(item[1]), 90),
                item[0],
            ),
        )
    ]

    generated_meta = metadata.get("updated_at") or metadata.get("created_at") or ""
    executive_summary = (summary.get("executive_summary") or "").strip()
    show_executive_summary = bool(insights) and bool(executive_summary)

    html = f"""
    <details class="ut-lead-section product-trial-report-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Product Trial Report</strong>
            <span class="muted small">— Generated</span>
        </summary>
        <div class="ut-lead-section-body">
            {notice_html}
    """

    if show_executive_summary:
        html += f"""
            <div class="card" style="margin-top:12px;">
                <h3 style="margin-bottom:8px;">
                    Executive Summary
                </h3>
                <div style="
                    font-size:14px;
                    line-height:1.6;
                    color:#333;
                ">
                    {e(executive_summary)}
                </div>
            </div>
        """

    if sections:
        html += f"""
            <div style="
                display:flex;
                align-items:center;
                justify-content:space-between;
                margin-top:24px;
                margin-bottom:10px;
            ">
                <div style="display:flex; align-items:center; gap:12px;">
                    <h3 style="margin:0;">
                        Section Results
                    </h3>

                    <div style="
                        font-size:12px;
                        color:#888;
                        display:flex;
                        gap:8px;
                        margin-left:8px;
                    ">
                        <a href="#" onclick="expandAllSections(); return false;" style="color:#888;">
                            Expand all
                        </a>
                        <span>|</span>
                        <a href="#" onclick="collapseAllSections(); return false;" style="color:#888;">
                            Collapse all
                        </a>
                    </div>
                </div>

                <div style="
                    display:flex;
                    gap:8px;
                    flex-wrap:wrap;
                    justify-content:flex-end;
                ">
                    {form_html}

                    <form method="post" action="/ut-lead/project" style="margin:0;" data-analysis-loading="true">
                        <input type="hidden" name="round_id" value="{e(round_id)}">
                        <input type="hidden" name="action" value="generate_product_trial_section_names">
                        <button type="submit" style="font-size:12px; padding:6px 10px;">
                            Generate Names
                        </button>
                    </form>

                    <form method="post" action="/ut-lead/project" style="margin:0;" data-analysis-loading="true">
                        <input type="hidden" name="round_id" value="{e(round_id)}">
                        <input type="hidden" name="action" value="generate_product_trial_section_summaries">
                        <button type="submit" style="font-size:12px; padding:6px 10px;">
                            Generate Summaries
                        </button>
                    </form>
                </div>
            </div>
        """

        last_report_group = None
        group_index = 0

        for idx, section in enumerate(sections, start=1):
            section_name = section.get("section_name") or f"Section {idx}"
            survey_label = section.get("survey_name") or "Survey"
            report_group = _section_report_group(section)

            if report_group != last_report_group:
                if last_report_group is not None:
                    html += "</div></details>"

                group_index += 1
                html += f"""
                    <details class="product-report-phase-group" data-product-report-group="{e(report_group)}" open style="
                        margin-top:18px;
                        border:1px solid #d9f3ee;
                        border-radius:8px;
                        background:#ffffff;
                        overflow:hidden;
                    ">
                        <summary style="
                            padding:10px 12px;
                            border-left:4px solid #7bd7c5;
                            background:#f4fffc;
                            color:#1f2937;
                            font-size:13px;
                            font-weight:700;
                            letter-spacing:0.03em;
                            text-transform:uppercase;
                            cursor:pointer;
                        ">
                            {e(report_group)}
                        </summary>
                        <div style="padding:12px 14px 16px 14px;">
                """
                last_report_group = report_group

            html += f"""
            <div class="rail-group historical-section-result collapsed" data-historical-section="product-trial-{idx}" style="
                margin-top:12px;
                margin-bottom:12px;
                border:1px solid #e5e5e5;
                border-radius:8px;
                background:#fafafa;
            ">

                <div class="rail-toggle" style="
                    display:flex;
                    align-items:center;
                    padding:14px 16px;
                    border-bottom:1px solid #eee;
                    cursor:pointer;
                ">
                    <div style="
                        font-size:15px;
                        font-weight:600;
                    ">
                        {e(section_name)}
                    </div>

                    <div style="
                        display:flex;
                        align-items:center;
                        gap:12px;
                        margin-left:auto;
                        font-size:12px;
                        color:#888;
                    ">
                        {e(survey_label)}
                    </div>
                </div>

                <div class="rail-content" style="
                    padding:14px 16px;
                ">
            """

            html += """
                <div style="
                    display:grid;
                    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
                    gap:12px;
                    align-items:stretch;
                    margin-bottom:10px;
                ">
            """

            for q in section.get("quant_questions") or []:
                question = e(q.get("question") or "")
                values = q.get("values") or []

                numeric_vals = []
                counts = {}

                for v in values:
                    if v is None:
                        continue

                    v_str = str(v).strip()

                    if v_str.replace(".", "", 1).isdigit():
                        numeric_vals.append(float(v_str))
                    else:
                        counts[v_str] = counts.get(v_str, 0) + 1

                if numeric_vals:
                    avg = sum(numeric_vals) / len(numeric_vals)
                    bar_width = int((avg / 5) * 100)
                    if bar_width > 100:
                        bar_width = 100

                    html += f"""
                        <div style="
                            min-height:86px;
                            padding:10px 12px;
                            border:1px solid #e5e5e5;
                            border-radius:6px;
                            display:flex;
                            align-items:center;
                            justify-content:space-between;
                            gap:12px;
                            box-sizing:border-box;
                            background:white;
                        ">

                            <div style="
                                font-size:14px;
                                flex:1;
                                line-height:1.35;
                            ">
                                {question}
                            </div>

                            <div style="
                                display:flex;
                                align-items:center;
                                gap:8px;
                                min-width:150px;
                                justify-content:flex-end;
                            ">
                                <div style="
                                    background:#eee;
                                    height:6px;
                                    width:96px;
                                    border-radius:4px;
                                    overflow:hidden;
                                ">
                                    <div style="
                                        width:{bar_width}%;
                                        background:#2c7be5;
                                        height:100%;
                                    "></div>
                                </div>

                                <div style="
                                    font-size:13px;
                                    color:#666;
                                    width:38px;
                                    text-align:right;
                                    font-variant-numeric: tabular-nums;
                                ">
                                    {avg:.2f}
                                </div>
                            </div>
                        </div>
                    """

                elif counts:
                    split_counts = {}

                    for opt, cnt in counts.items():
                        parts = [p.strip() for p in opt.split(",")]

                        for part in parts:
                            if not part:
                                continue

                            if part not in split_counts:
                                split_counts[part] = 0

                            split_counts[part] += cnt

                    sorted_items = sorted(split_counts.items(), key=lambda x: x[1], reverse=True)
                    max_val = max(split_counts.values()) if split_counts else 1

                    options_html = ""
                    for opt, cnt in sorted_items:
                        bar_width = int((cnt / max_val) * 100)

                        options_html += f"""
                            <div style="margin-bottom:8px;">
                                <div style="
                                    display:flex;
                                    justify-content:space-between;
                                    font-size:13px;
                                    color:#444;
                                    margin-bottom:2px;
                                    gap:8px;
                                ">
                                    <div>{e(opt)}</div>
                                    <div style="font-variant-numeric: tabular-nums;">
                                        {cnt}
                                    </div>
                                </div>

                                <div style="
                                    background:#eee;
                                    height:6px;
                                    border-radius:4px;
                                    overflow:hidden;
                                ">
                                    <div style="
                                        width:{bar_width}%;
                                        background:#2c7be5;
                                        height:100%;
                                    "></div>
                                </div>
                            </div>
                        """

                    html += f"""
                        <div style="
                            min-height:86px;
                            padding:10px 12px;
                            border:1px solid #e5e5e5;
                            border-radius:6px;
                            box-sizing:border-box;
                            background:white;
                        ">
                            <div style="
                                font-size:14px;
                                margin-bottom:8px;
                                line-height:1.35;
                            ">
                                {question}
                            </div>
                            <div>
                                {options_html}
                            </div>
                        </div>
                    """

            html += "</div>"

            parsed = _parse_swot(section)
            if parsed:
                strengths = parsed.get("strengths", [])
                weaknesses = parsed.get("weaknesses", [])
                opportunities = parsed.get("opportunities", [])
                threats = parsed.get("threats", [])

                html += """
                    <div style="
                        display:flex;
                        gap:12px;
                        flex-wrap:wrap;
                        margin-left:0;
                        margin-top:10px;
                    ">
                """

                html += _swot_card("Strengths", "💪", strengths)
                html += _swot_card("Weaknesses", "⚠️", weaknesses)
                html += _swot_card("Opportunities", "🚀", opportunities)
                html += _swot_card("Threats", "🔥", threats)
                html += "</div>"

            html += "</div></div>"

        if last_report_group is not None:
            html += "</div></details>"

    else:
        html += """
            <div class="card" style="margin-top:20px; color:#666; font-size:14px;">
                No Historical-style report sections are stored yet. Regenerate the report after survey results are uploaded.
            </div>
        """

    html += f"""
        <details style="
            margin-top:18px;
            border:1px solid #e5e5e5;
            border-radius:8px;
            background:#ffffff;
            overflow:hidden;
        ">
            <summary style="
                padding:10px 12px;
                background:#fafafa;
                cursor:pointer;
                color:#475467;
                font-size:13px;
                font-weight:700;
            ">
                Report Source Details
                <span style="font-weight:500; color:#888; margin-left:8px;">
                    {e(summary.get("section_count") or len(sections))} sections · {e(summary.get("response_count") or 0)} responses · {e(summary.get("answer_count") or 0)} answers
                </span>
            </summary>
            <div style="padding:12px 14px;">
                {_source_survey_rows()}
                <div style="
                    margin-top:10px;
                    padding-top:10px;
                    border-top:1px solid #eee;
                    color:#888;
                    font-size:12px;
                ">
                    Generated: {e(generated_meta or "—")}
                </div>
            </div>
        </details>
    """

    html += f"""
        <div class="card" style="margin-top:20px;">
            <div style="
                display:flex;
                justify-content:space-between;
                align-items:center;
                margin-bottom:12px;
            ">
                <h3 style="margin:0;">Insights</h3>

                <form method="post" action="/ut-lead/project" style="margin:0;" data-analysis-loading="true">
                    <input type="hidden" name="round_id" value="{e(round_id)}">
                    <input type="hidden" name="action" value="generate_product_trial_insights">
                    <button type="submit" style="font-size:12px; padding:6px 10px;">
                        Generate Insights
                    </button>
                </form>
            </div>
    """

    if not insights:
        html += """
            <div style="color:#666; font-size:14px;">
                No insights generated yet.
            </div>
        """
    else:
        grouped = {}
        for insight in insights:
            if not isinstance(insight, dict):
                continue
            section_name = insight.get("section_name") or "General"
            grouped.setdefault(section_name, []).append(insight)

        for section_name, items in grouped.items():
            html += f"""
            <div style="
                margin-bottom:16px;
                padding:12px;
                border:1px solid #e5e5e5;
                border-radius:6px;
                background:#fafafa;
            ">
                <div style="
                    font-size:13px;
                    text-transform:uppercase;
                    color:#888;
                    margin-bottom:8px;
                ">
                    {e(section_name)}
                </div>

                <div style="
                    display:grid;
                    grid-template-columns: 1fr 1fr;
                    gap:12px;
                ">
            """

            for insight in items:
                title = e(insight.get("title") or "Untitled Insight")
                explanation = e(insight.get("explanation") or "")
                impact = (insight.get("impact") or "medium").lower()
                sentiment = (insight.get("sentiment") or "neutral").lower()
                evidence = insight.get("evidence") or []

                border_color = "#999"
                if sentiment == "positive":
                    border_color = "#2fbf71" if impact == "high" else "#3b82f6"
                elif sentiment == "negative":
                    border_color = "#e5533d" if impact == "high" else "#f59e0b"
                elif sentiment == "mixed":
                    border_color = "#7b61ff"

                evidence_html = ""
                for item in evidence[:4]:
                    evidence_html += f"<li>{e(item)}</li>"

                if not evidence_html:
                    evidence_html = "<li>No supporting evidence stored.</li>"

                html += f"""
                    <div style="
                        padding:14px;
                        border:1px solid #e5e5e5;
                        border-left:4px solid {border_color};
                        border-radius:8px;
                        background:white;
                    ">
                        <div style="font-size:12px; color:#888; margin-bottom:6px; text-transform:uppercase;">
                            {e(impact.upper())} • {e(sentiment.upper())}
                        </div>
                        <div style="font-weight:600; margin-bottom:8px;">
                            {title}
                        </div>
                        <div style="font-size:14px; color:#444; line-height:1.5; margin-bottom:10px;">
                            {explanation}
                        </div>
                        <ul style="margin:0; padding-left:18px; font-size:13px; color:#666; line-height:1.5;">
                            {evidence_html}
                        </ul>
                    </div>
                """

            html += "</div></div>"

    html += """
        </div>
        </div>
    </details>
    """

    return html


def _render_round_config_unlocked(*, round_data, country_options_html):

    return f"""
    <details class="ut-lead-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Round Configuration</strong>
            <span class="muted small">— Unlocked</span>
        </summary>
        <div class="ut-lead-section-body">

    <form method="post" action="/ut-lead/project" class="round-config-form">
    <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">

    <div class="section-header">Dates</div>
    <div class="form-grid">

    <div class="form-field full">
    <label>Description</label>
    <textarea name="description" rows="2">{e(round_data.get("Description") or "")}</textarea>
    </div>

    </div>  <!-- CLOSE form-grid BEFORE dates -->

    <div class="inline-row">

        <div class="inline-field">
            <span class="inline-label">Start</span>
            <input type="date" id="start_date" name="start_date"
            value="{e(round_data.get("StartDate") or "")}">
        </div>

        <div class="inline-field">
            <span class="inline-label">End</span>
            <input type="date" id="end_date" name="end_date"
            value="{e(round_data.get("EndDate") or "")}">
        </div>

        <div class="inline-field">
            <span class="inline-label">Ship</span>
            <input type="date" name="ship_date"
            value="{e(round_data.get("ShipDate") or "")}">
        </div>

    </div>

    <div class="form-grid">  <!-- REOPEN grid for next section -->

    </div>

    <div class="form-grid">

    <div class="form-field">
    <label>User Scope</label>
    <select name="user_scope">
    <option value="Internal" {"selected" if round_data.get("UserScope") == "Internal" else ""}>Internal</option>
    <option value="External" {"selected" if round_data.get("UserScope") == "External" else ""}>External</option>
    <option value="Hybrid" {"selected" if round_data.get("UserScope") == "Hybrid" else ""}>Hybrid</option>
    </select>
    </div>

    <div class="form-field">
    <label>Target Users</label>
    <input type="number" name="target_users"
    value="{e(round_data.get("TargetUsers") or 30)}">
    </div>

    <div class="form-field">
    <label>Min Age</label>
    <select name="min_age">
    <option value="">Any</option>
    <option value="0">Minors</option>
    <option value="19">19+</option>
    <option value="30">30+</option>
    <option value="40">40+</option>
    <option value="50">50+</option>
    <option value="60">60+</option>
    </select>
    </div>

    <div class="form-field">
    <label>Max Age</label>
    <select name="max_age">
    <option value="">Any</option>
    <option value="30">Up to 30</option>
    <option value="40">Up to 40</option>
    <option value="50">Up to 50</option>
    <option value="60">Up to 60</option>
    <option value="61">61+</option>
    </select>
    </div>

    </div>    

    <div class="form-grid">

    <div class="form-field">
    <label>Prototype Version</label>
    <input type="text" name="prototype_version"
    value="{e(round_data.get("PrototypeVersion") or "pb1")}">
    </div>

    <div class="form-field">
    <label>FW Version</label>
    <input type="text" name="product_sku"
    value="{e(round_data.get("ProductSKU") or "")}">
    </div>

    </div>

    <div class="section-header">Countries</div>
    <div class="form-grid">

    <div class="form-field full">

    <div id="country-chip-container" class="country-chip-container"></div>

    <div class="country-add-row">

    <select id="country_select">
        <option value="">Select Country</option>
        {country_options_html}
    </select>

    </div>

    <input type="hidden" id="region_input" name="region"
    value="{e(round_data.get("Region") or "")}">

    </div>

    </div>

    <div class="form-actions">
    <button type="submit" name="action" value="save_overview">Save</button>
    <button type="submit" name="action" value="lock_overview">Lock Overview</button>
    </div>

    </form>

    <script>
    document.addEventListener("DOMContentLoaded", function () {{

        // =========================
        // DATE AUTO-FILL
        // =========================
        const start = document.getElementById("start_date");
        const end = document.getElementById("end_date");

        if (start && end) {{
            function autoEndDate() {{
                if (!start.value) return;

                let d = new Date(start.value);
                d.setDate(d.getDate() + 30);

                const yyyy = d.getFullYear();
                const mm = String(d.getMonth() + 1).padStart(2, "0");
                const dd = String(d.getDate()).padStart(2, "0");

                end.value = yyyy + "-" + mm + "-" + dd;
            }}

            start.addEventListener("change", autoEndDate);
        }}

        // =========================
        // COUNTRY SELECT → CHIP SYSTEM
        // =========================
        const container = document.getElementById("country-chip-container");
        const select = document.getElementById("country_select");
        const hidden = document.getElementById("region_input");

        if (!container || !select || !hidden) return;

        let countries = [];

        if (hidden.value) {{
            hidden.value.split(",").forEach(code => {{
                const option = select.querySelector(`option[value="${{code}}"]`);
                if (option) {{
                    countries.push({{
                        code: code,
                        name: option.text
                    }});
                }}
            }});
        }}

        function renderCountries() {{
            container.innerHTML = "";

            countries.forEach(country => {{
                const chip = document.createElement("div");
                chip.className = "country-chip";

                const span = document.createElement("span");
                span.textContent = country.name;

                const btn = document.createElement("button");
                btn.type = "button";
                btn.dataset.code = country.code;
                btn.textContent = "✕";

                chip.appendChild(span);
                chip.appendChild(btn);

                container.appendChild(chip);
            }});

            hidden.value = countries.map(c => c.code).join(",");
        }}

        select.addEventListener("change", function () {{
            const code = select.value;
            const name = select.options[select.selectedIndex].text;

            if (!code) return;

            if (!countries.some(c => c.code === code)) {{
                countries.push({{ code: code, name: name }});
            }}

            renderCountries();
            select.value = "";
        }});

        container.addEventListener("click", function (e) {{
            if (e.target.tagName !== "BUTTON") return;

            const code = e.target.dataset.code;
            countries = countries.filter(c => c.code !== code);

            renderCountries();
        }});

        renderCountries();
    }});
    </script>

    </div>
    </details>
    """

def _render_round_config_locked(*, round_data, country_rows, user_id):

    # -----------------------------------------
    # Convert Region Codes → Names
    # -----------------------------------------
    region_codes = (round_data.get("Region") or "").split(",")
    region_names = []

    for code in region_codes:
        for c in country_rows:
            if c["CountryCode"] == code:
                region_names.append(c["CountryName"])
                break
        else:
            region_names.append(code)

    region_display = ", ".join(region_names) if region_names else "—"

    html = f"""
    <details class="ut-lead-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Round Configuration</strong>
            <span class="muted small">— Locked</span>
        </summary>

        <div class="ut-lead-section-body">

            <div class="locked-section">

                <div class="locked-group">
                    <div class="locked-title">Schedule</div>

                    <div class="locked-row">
                        <div class="locked-item">
                            <span class="locked-label">Start</span>
                            <span class="locked-value">{e(round_data.get('StartDate') or '—')}</span>
                        </div>

                        <div class="locked-item">
                            <span class="locked-label">End</span>
                            <span class="locked-value">{e(round_data.get('EndDate') or '—')}</span>
                        </div>
                    </div>
                </div>

                <div class="locked-group">
                    <div class="locked-title">Participants</div>

                    <div class="locked-row">
                        <div class="locked-item">
                            <span class="locked-label">Scope</span>
                            <span class="locked-value">{e(round_data.get('UserScope') or '—')}</span>
                        </div>

                        <div class="locked-item">
                            <span class="locked-label">Users</span>
                            <span class="locked-value">{e(round_data.get('TargetUsers') or '—')}</span>
                        </div>
                    </div>

                    <div class="locked-row">
                        <div class="locked-item">
                            <span class="locked-label">Age</span>
                            <span class="locked-value">
                                {e(round_data.get('MinAge') or 'Any')} - {e(round_data.get('MaxAge') or 'Any')}
                            </span>
                        </div>

                        <div class="locked-item">
                            <span class="locked-label">Region</span>
                            <span class="locked-value">{e(region_display)}</span>
                        </div>
                    </div>
                </div>

                <div class="locked-group">
                    <div class="locked-title">Product</div>

                    <div class="locked-row">
                        <div class="locked-item">
                            <span class="locked-label">Prototype</span>
                            <span class="locked-value">{e(round_data.get('PrototypeVersion') or '—')}</span>
                        </div>

                        <div class="locked-item">
                            <span class="locked-label">FW</span>
                            <span class="locked-value">{e(round_data.get('ProductSKU') or '—')}</span>
                        </div>
                    </div>
                </div>

            </div>
    """

    if get_effective_permission_level(user_id) >= 90:
        html += f"""
            <form method="post" action="/ut-lead/project" style="margin-top:10px;">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                <button type="submit" name="action" value="unlock_overview">
                    Unlock Overview
                </button>
            </form>
        """

    html += """
        </div>
    </details>
    """

    return html

def render_ut_lead_project_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict,
):
    """
    UT Lead – Project / Round details page (read-only v1)
    """

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    permission_level = get_effective_permission_level(user_id)
    if permission_level < 70:
        return {"redirect": "/dashboard"}

    csrf_token = generate_csrf_token(user_id)

    # --------------------------------------------------
    # Validate input
    # --------------------------------------------------
    round_id = query_params.get("round_id", [None])[0]
    upload_status = query_params.get("upload", [None])[0]
    upload_survey_type_id = query_params.get("upload_survey_type_id", [None])[0]
    upload_round_survey_id = query_params.get("upload_round_survey_id", [None])[0]
    constraint_status = query_params.get("constraint", [None])[0]
    constraint_error = query_params.get("constraint_error", [None])[0]
    report_status = query_params.get("report", [None])[0]

    def _query_int(name: str) -> int:
        raw_value = query_params.get(name, ["0"])[0]
        try:
            return max(0, int(raw_value or 0))
        except (TypeError, ValueError):
            return 0

    upload_summary = None
    if upload_status == "success" and upload_survey_type_id:
        upload_summary = {
            "total_rows": _query_int("total_rows"),
            "matched_users": _query_int("matched_users"),
            "ignored_rows": _query_int("ignored_rows"),
            "token_rows": _query_int("token_rows"),
            "email_rows": _query_int("email_rows"),
            "anonymous_rows": _query_int("anonymous_rows"),
            "unmatched_rows": _query_int("unmatched_rows"),
            "review_rows": _query_int("review_rows"),
            "inserted_answers": _query_int("inserted_answers"),
        }

    def _survey_results_upload_status(*, round_survey_id=None, survey_type_id=None) -> str | None:
        if upload_status == "error":
            return "error"

        if upload_status != "success":
            return None

        # Recruiting upload success belongs to the Recruiting section, not the
        # participant result cards.
        if upload_survey_type_id == "UTSurveyType0001":
            return None

        if upload_round_survey_id:
            if str(round_survey_id or "") == str(upload_round_survey_id):
                return "success"
            return None

        if not upload_survey_type_id:
            return "success"

        if str(survey_type_id or "") == str(upload_survey_type_id):
            return "success"

        return None

    def _survey_results_upload_summary(*, round_survey_id=None, survey_type_id=None) -> dict | None:
        if _survey_results_upload_status(
            round_survey_id=round_survey_id,
            survey_type_id=survey_type_id,
        ) != "success":
            return None

        return upload_summary

    def _persistent_attribution_summary(*, survey_type_id) -> dict | None:
        if not survey_type_id:
            return None

        try:
            return get_survey_response_attribution_summary(
                round_id=int(round_id),
                survey_type_id=survey_type_id,
            )
        except Exception:
            # Report page rendering should not fail if attribution summary
            # lookup has an issue. Upload audit and distribution rows remain
            # the DB source of truth.
            return None

    if not round_id:
        return {"redirect": "/ut-lead/trials"}
    
    # --------------------------------------------------
    # Load project round (authoritative)
    # --------------------------------------------------
    round_data = get_project_round_by_id(round_id=int(round_id))
    if not round_data:
        return {"redirect": "/ut-lead/trials"}

    if not _can_access_ut_lead_round(
        user_id=user_id,
        round_data=round_data,
    ):
        return {"redirect": "/ut-lead/trials"}

    project_id = round_data.get("ProjectID")

    constraint_packet = {
        "constraint_count": 0,
        "project_scope_count": 0,
        "round_scope_count": 0,
        "must_have_count": 0,
        "should_have_count": 0,
        "nice_to_have_count": 0,
        "unknown_priority_count": 0,
        "limitations": [],
        "constraints": [],
        "allowed_categories": [],
        "allowed_priorities": [],
    }

    if ENABLE_CONSTRAINT_CAPTURE_UI:
        constraint_packet = build_constraint_capture_packet(
            project_id=project_id,
            round_id=int(round_data["RoundID"]),
        )

    # --------------------------------------------------
    # Country list for dropdown
    # --------------------------------------------------

    country_rows = get_country_codes()

    country_options_html = ""

    for c in country_rows:
        country_options_html += f'<option value="{e(c["CountryCode"])}">{e(c["CountryName"])}</option>'

    # --------------------------------------------------
    # Static links (v1)
    # --------------------------------------------------
    recruiting_link = (
        "https://docs.google.com/forms/d/e/1FAIpQLSfs2e_FWkcYXCfXcq1hpCfg6MmV5qRnJ7COlQIhDPK1fHVRdQ/"
        "viewform?usp=pp_url&entry.648734718=user_token_here"
    )

    s1_link = (
        "https://docs.google.com/forms/d/e/1FAIpQLSe95KHUhSD7_UFVrIOiyfbsIxCU9IhkWPLbcUp_7Ii71qmypQ/"
        "viewform?usp=pp_url&entry.1286199023=user_token_here"
    )

    s2_link = (
        "https://docs.google.com/forms/d/e/1FAIpQLSeWeKL8DIfq_9BFJjvYU9wf9pbkGfGz9ySb04DCeSb5bPmrrg/"
        "viewform?usp=pp_url&entry.200157476=user_token_here"
    )

    report_issue_link = (
        "https://docs.google.com/forms/d/e/1FAIpQLScfRWEXIfhOhoq9wzI22Rmv57Ua0pwqk0MNv5lSQyKhaS7Zyg/"
        "viewform?usp=pp_url&entry.637802913=user_token_here"
    )

    consolidated_link = (
        "https://docs.google.com/forms/d/e/1FAIpQLSdrpyGgBCPXQlQzVTXst2s2Uqoyto8CDP7nX9FnBM7wHAkvrw/"
        "viewform?usp=header"
    )

    # after_trial_link intentionally not present yet (anonymous, no token)
    overview_locked = bool(round_data.get("OverviewLocked"))
    profile_locked = bool(round_data.get("ProfileLocked"))
    project_stakeholders = get_round_stakeholders(
        round_id=int(round_data["RoundID"]),
    )

    # =========================================================
    # PRODUCT IDENTITY SECTION
    # =========================================================

    product_identity_section = f"""
    <details class="ut-lead-section product-identity-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Product Identity</strong>
        </summary>

        <div class="ut-lead-section-body">

            <div class="locked-grid">

                <div class="locked-item">
                    <span class="locked-label">Project Name</span>
                    <span class="locked-value">{e(round_data.get("ProjectName") or "—")}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Business Group</span>
                    <span class="locked-value">{e(round_data.get("BusinessGroup") or "—")}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Market Name</span>
                    <span class="locked-value">{e(round_data.get("MarketName") or "—")}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Sub Group</span>
                    <span class="locked-value">{e(round_data.get("BusinessSubGroup") or "—")}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Product Type</span>
                    <span class="locked-value">{e(round_data.get("ProductType") or "—")}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Product SKU</span>
                    <span class="locked-value">{e(round_data.get("ProductSKU") or "—")}</span>
                </div>

            </div>

            <div class="locked-description">
                <span class="locked-label">Project Description</span>
                <div class="locked-value">
                    {e(round_data.get("ProjectDescription") or "—")}
                </div>
            </div>

        </div>

    </details>
    """

    # =========================================================
    # PROJECT STAKEHOLDERS SECTION
    # =========================================================

    stakeholder_rows_html = ""

    for stakeholder in project_stakeholders:
        display_name = stakeholder.get("DisplayName") or "—"
        email = stakeholder.get("Email") or ""
        role_name = stakeholder.get("StakeholderRole") or "—"
        linked_user_id = stakeholder.get("user_id")

        if linked_user_id:
            access_label = "Registered"
        elif email:
            access_label = "Pending registration / SSO link"
        else:
            access_label = "Legacy name-only stakeholder"

        email_html = ""
        if email:
            email_html = f"""
                <div class="project-stakeholder-email">{e(email)}</div>
            """

        stakeholder_rows_html += f"""
            <div class="project-stakeholder-card">
                <div class="project-stakeholder-main">
                    <div class="project-stakeholder-name">{e(display_name)}</div>
                    {email_html}
                </div>
                <div class="project-stakeholder-meta">
                    <span class="project-stakeholder-role">{e(role_name)}</span>
                    <span class="project-stakeholder-access">{e(access_label)}</span>
                </div>
            </div>
        """

    if not stakeholder_rows_html:
        stakeholder_rows_html = """
            <p class="muted small" style="margin:0;">
                No project stakeholders were submitted with this request.
            </p>
        """

    project_stakeholders_section = f"""
    <details class="ut-lead-section project-stakeholders-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Project Stakeholders</strong>
            <span class="muted small">— Submitted by Product Team</span>
        </summary>

        <div class="ut-lead-section-body">
            <p class="muted small" style="margin-top:0;">
                Product Team contacts attached to this trial request. Email is the stable identity key for future SSO linking.
            </p>

            <div class="project-stakeholder-list">
                {stakeholder_rows_html}
            </div>
        </div>
    </details>
    """

    # =========================================================
    # ROUND CONFIGURATION SECTION
    # =========================================================

    overview_locked = bool(round_data.get("OverviewLocked"))

    if overview_locked:
        round_config_section = _render_round_config_locked(
            round_data=round_data,
            country_rows=country_rows,
            user_id=user_id,
        )
    else:
        round_config_section = _render_round_config_unlocked(
            round_data=round_data,
            country_options_html=country_options_html,
        )

    # =========================================================
    # EXPLICIT CONSTRAINTS SECTION
    # =========================================================

    constraint_count = constraint_packet.get("constraint_count") or 0
    project_scope_count = constraint_packet.get("project_scope_count") or 0
    round_scope_count = constraint_packet.get("round_scope_count") or 0
    must_have_count = constraint_packet.get("must_have_count") or 0
    should_have_count = constraint_packet.get("should_have_count") or 0
    nice_to_have_count = constraint_packet.get("nice_to_have_count") or 0
    unknown_priority_count = constraint_packet.get("unknown_priority_count") or 0

    constraint_limitations = constraint_packet.get("limitations") or []
    constraint_rows = constraint_packet.get("constraints") or []
    allowed_categories = constraint_packet.get("allowed_categories") or []
    allowed_priorities = constraint_packet.get("allowed_priorities") or []

    def _constraint_option_html(values, selected_value=None):
        option_html = ""

        for value in values:
            selected = "selected" if selected_value and value == selected_value else ""
            label = str(value or "").replace("_", " ").title()
            option_html += f"""
                <option value="{e(value)}" {selected}>{e(label)}</option>
            """

        return option_html

    category_options_html = _constraint_option_html(allowed_categories)
    priority_options_html = _constraint_option_html(allowed_priorities, "unknown")

    constraint_notice_html = ""

    if constraint_status == "added":
        constraint_notice_html = """
            <div style="
                margin:12px 0;
                padding:10px 12px;
                border-left:4px solid #16a34a;
                background:#f0fdf4;
                border-radius:8px;
            ">
                Constraint added.
            </div>
        """
    elif constraint_status == "removed":
        constraint_notice_html = """
            <div style="
                margin:12px 0;
                padding:10px 12px;
                border-left:4px solid #16a34a;
                background:#f0fdf4;
                border-radius:8px;
            ">
                Constraint removed.
            </div>
        """
    elif constraint_error:
        constraint_error_messages = {
            "missing_project_id": "Constraint could not be saved because the project ID was missing.",
            "missing_constraint_key": "Constraint key is required.",
            "missing_constraint_value": "Constraint value is required.",
            "missing_created_by_user_id": "Constraint could not be saved because the user ID was missing.",
            "constraint_key_too_long": "Constraint key must be 100 characters or fewer.",
            "constraint_value_too_long": "Constraint value must be 1,000 characters or fewer.",
            "duplicate_constraint": "That active constraint already exists for this scope.",
            "save_failed": "Constraint could not be saved.",
            "invalid_constraint_id": "Constraint could not be removed because the constraint ID was invalid.",
            "constraint_not_found": "Constraint could not be removed because it was not found for this project.",
            "deactivate_failed": "Constraint could not be removed.",
        }

        constraint_notice_html = f"""
            <div style="
                margin:12px 0;
                padding:10px 12px;
                border-left:4px solid #dc2626;
                background:#fef2f2;
                border-radius:8px;
            ">
                {e(constraint_error_messages.get(
                    constraint_error,
                    "Constraint action failed."
                ))}
            </div>
        """

    constraints_section = f"""
    <details id="constraints" class="ut-lead-section constraints-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Explicit Constraints</strong>
            <span class="muted small">— Editable</span>
        </summary>

        <div class="ut-lead-section-body">

            <p class="muted" style="margin-top:0;">
                Constraint capture plumbing for future planning and recommendation layers.
                These are explicit DB-backed constraints only; nothing here is inferred from survey text or AI output.
            </p>

            {constraint_notice_html}

            <div class="locked-grid">
                <div class="locked-item">
                    <span class="locked-label">Total Constraints</span>
                    <span class="locked-value">{e(constraint_count)}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Project Scope</span>
                    <span class="locked-value">{e(project_scope_count)}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Round Scope</span>
                    <span class="locked-value">{e(round_scope_count)}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Must Have</span>
                    <span class="locked-value">{e(must_have_count)}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Should Have</span>
                    <span class="locked-value">{e(should_have_count)}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Nice to Have</span>
                    <span class="locked-value">{e(nice_to_have_count)}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Unknown Priority</span>
                    <span class="locked-value">{e(unknown_priority_count)}</span>
                </div>
            </div>
    """

    if constraint_limitations:
        constraints_section += """
            <div style="margin-top:12px;">
        """

        for limitation in constraint_limitations:
            constraints_section += f"""
                <div class="muted" style="margin-bottom:6px;">
                    • {e(limitation)}
                </div>
            """

        constraints_section += """
            </div>
        """

    if constraint_rows:
        constraints_section += """
            <div class="table-scroll" style="margin-top:14px;">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Scope</th>
                            <th>Category</th>
                            <th>Priority</th>
                            <th>Key</th>
                            <th>Value</th>
                            <th>Source</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
        """

        for constraint in constraint_rows:
            scope_label = "Project"
            if constraint.get("round_id"):
                scope_label = f"Round {constraint.get('round_id')}"

            category_label = str(
                constraint.get("constraint_category") or ""
            ).replace("_", " ").title()

            priority_label = str(
                constraint.get("constraint_priority") or ""
            ).replace("_", " ").title()

            source_label = str(
                constraint.get("constraint_source") or ""
            ).replace("_", " ").title()

            constraints_section += f"""
                        <tr>
                            <td>{e(scope_label)}</td>
                            <td>{e(category_label)}</td>
                            <td>{e(priority_label)}</td>
                            <td>{e(constraint.get("constraint_key") or "")}</td>
                            <td>{e(constraint.get("constraint_value") or "")}</td>
                            <td>{e(source_label)}</td>
                            <td>
                                <form method="post" action="/ut-lead/project" style="margin:0;">
                                    <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                                    <input type="hidden" name="constraint_id" value="{e(constraint.get("constraint_id"))}">
                                    <button type="submit" name="action" value="deactivate_constraint">
                                        Remove
                                    </button>
                                </form>
                            </td>
                        </tr>
            """

        constraints_section += """
                    </tbody>
                </table>
            </div>
        """

    constraints_section += f"""
            <div style="margin-top:16px; border-top:1px solid #e5e7eb; padding-top:12px;">
                <form method="post" action="/ut-lead/project" class="profile-add-form">
                    <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">

                    <select name="constraint_scope">
                        <option value="round">Round Constraint</option>
                        <option value="project">Project Constraint</option>
                    </select>

                    <select name="constraint_category" required>
                        <option value="">Select Category</option>
                        {category_options_html}
                    </select>

                    <select name="constraint_priority">
                        {priority_options_html}
                    </select>

                    <input
                        type="text"
                        name="constraint_key"
                        placeholder="Key, e.g. target_region"
                        maxlength="100"
                        required
                    >

                    <input
                        type="text"
                        name="constraint_value"
                        placeholder="Value, e.g. Taiwan only"
                        maxlength="1000"
                        required
                    >

                    <button type="submit" name="action" value="add_constraint">
                        Add Constraint
                    </button>
                </form>
            </div>

        </div>
    </details>
    """

    # =========================================================
    # WANTED USER PROFILE SECTION
    # =========================================================

    criteria_rows = get_round_profile_criteria(int(round_data['RoundID']))

    wanted_profile_section = f"""
    <details class="ut-lead-section wanted-profile-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Wanted User Profile</strong>
            <span class="muted small">
                {"— Locked" if profile_locked else "— Editable"}
            </span>
        </summary>

        <div class="ut-lead-section-body">

            <div class="profile-rules-list">
    """

    # ---------------------------------
    # Existing Criteria Rows
    # ---------------------------------

    for c in criteria_rows:

        wanted_profile_section += f"""
                <div class="profile-rule-row">

                    <span class="profile-rule-label">Operator</span>
                    <span class="profile-rule-value">{e(c['Operator'])}</span>

                    <span class="profile-rule-label">Category</span>
                    <span class="profile-rule-value">{e(c['CategoryName'])}</span>

                    <span class="profile-rule-label">Value</span>
                    <span class="profile-rule-value">{e(c['LevelDescription'])}</span>
        """

        if not profile_locked:
            wanted_profile_section += f"""
                    <div class="profile-rule-action">
                        <form method="post" action="/ut-lead/project">
                            <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                            <input type="hidden" name="criteria_id" value="{e(c['RoundCriteriaID'])}">
                            <button type="submit" name="action" value="delete_profile_criteria">
                                Remove
                            </button>
                        </form>
                    </div>
            """
        else:
            wanted_profile_section += """
                    <div class="profile-rule-action"></div>
            """

        wanted_profile_section += """
                </div>
        """

    # ---------------------------------
    # Add Criteria Row
    # ---------------------------------

    if not profile_locked:

        from app.db.user_profiles import get_profile_categories
        categories = get_profile_categories()

        wanted_profile_section += f"""
            </div>

            <div class="profile-add-block">
                <div class="profile-add-label">Add Criteria</div>

                <form method="post" action="/ut-lead/project" class="profile-add-form">
                    <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">

                    <select name="operator" required>
                        <option value="INCLUDE">Include</option>
                        <option value="EXCLUDE">Exclude</option>
                    </select>

                    <select name="category_id" id="profile_category" required>
                        <option value="">Select Category</option>
        """

        for cat in categories:
            wanted_profile_section += f"""
                        <option value="{e(cat['CategoryID'])}">
                            {e(cat['CategoryName'])}
                        </option>
            """

        wanted_profile_section += """
                    </select>

                    <select name="profile_uid" id="profile_level" required>
                        <option value="">Select Level</option>
                    </select>

                    <button type="submit" name="action" value="add_profile_criteria">
                        Add
                    </button>
                </form>
            </div>
        """

    else:

        wanted_profile_section += """
            </div>
        """

    wanted_profile_section += f"""
            {"" if profile_locked else f'''
            <div class="profile-footer">
                <form method="post" action="/ut-lead/project">
                    <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                    <button type="submit" name="action" value="lock_profile">
                        Lock Profile
                    </button>
                </form>
            </div>
            '''}

        </div>
    </details>
    """

    # =========================================================
    # RECRUITING CONFIGURATION SECTION
    # =========================================================

    raw_value = round_data.get("UseExternalRecruitingSurvey")
    use_external = str(raw_value) == "1"

    recruiting_config_section = f"""
    <details class="ut-lead-section recruiting-config-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Recruiting Configuration</strong>
        </summary>

        <div class="ut-lead-section-body">

            <form method="post" action="/ut-lead/project" class="recruiting-toggle-form">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                <input type="hidden" name="action" value="update_recruiting_config">

                <label class="recruiting-toggle">
                    <input
                        type="checkbox"
                        name="use_external_recruiting_survey"
                        value="1"
                        {"checked" if use_external else ""}
                        onchange="this.form.submit()"
                    >
                    <span>Use External Recruiting Survey</span>
                </label>

                <div class="muted small" style="margin-top:6px;">
                    If enabled, a recruiting survey must be configured before opening recruiting.
                </div>

            </form>

        </div>
    </details>
    """

    # ---------------------------------
    # Level Loader Script
    # ---------------------------------

    wanted_profile_section += """
    <script>

    document.addEventListener("DOMContentLoaded", function(){

        const categorySelect = document.getElementById("profile_category");
        const levelSelect = document.getElementById("profile_level");

        if (!categorySelect || !levelSelect) return;

        categorySelect.addEventListener("change", function(){

            const categoryId = this.value;

            if (!categoryId){
                levelSelect.innerHTML = "<option value=''>Select Level</option>";
                return;
            }

            fetch("/api/profile-levels?category_id=" + categoryId)
            .then(res => res.json())
            .then(rows => {

                levelSelect.innerHTML = "<option value=''>Select Level</option>";

                rows.forEach(row => {

                    const opt = document.createElement("option");

                    opt.value = row.ProfileUID;
                    opt.textContent = row.LevelDescription;

                    levelSelect.appendChild(opt);

                });

            });

        });

    });

    </script>
    """

    constraints_section_html = constraints_section if ENABLE_CONSTRAINT_CAPTURE_UI else ""

    # --------------------------------------------------
    # Render (read-only placeholders)
    # --------------------------------------------------
    body_html = f"""
        <div class="ut-lead-project-page">
            <div class="breadcrumb ut-lead-project-breadcrumb">
                <a href="/ut-lead/trials">← Back to All Trials</a>
            </div>

            <div class="ut-lead-project-hero">
                <div class="ut-lead-project-title-block">
                    <div class="ut-lead-project-eyebrow">UT Lead Project</div>
                    <h1 class="ut-lead-project-title">{e(round_data.get("RoundName") or "Project Round")}</h1>
                    <div class="ut-lead-project-subtitle">
                        {e(round_data.get("ProjectName") or "Project")}
                    </div>
                </div>

                <div class="ut-lead-project-meta">
                    <span class="ut-lead-project-status">
                        {e(round_data.get("Status") or "Draft")}
                    </span>
                    <span class="ut-lead-project-id">
                        Round {e(round_data.get("RoundID") or "—")}
                    </span>
                </div>
            </div>

            {product_identity_section}
            {project_stakeholders_section}
            {round_config_section}
            {constraints_section_html}
            {wanted_profile_section}
    """

    body_html += recruiting_config_section

    # --------------------------------------------------
    # Planning Links (Survey Links per Round)
    # --------------------------------------------------
    planning_locked_by = round_data.get("PlanningLockedBy")
    planning_locked_display = (
        get_display_name_by_user_id(planning_locked_by)
        if planning_locked_by else "—"
    )

    planning_locked_at = round_data.get("PlanningLockedAt") or "—"

    round_surveys = get_round_surveys(int(round_data["RoundID"]))
    result_surveys = _get_result_surveys(round_surveys)
    planning_locked = bool(round_data.get("PlanningLocked"))

    links_section = f"""
    <details class="ut-lead-section wanted-profile-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Planning – Survey Links</strong>
            <span class="muted small">
                {"— Locked" if planning_locked else "— Unlocked"}
            </span>
        </summary>
        <div class="ut-lead-section-body">
    """

    action_header = "" if planning_locked else "<th>Action</th>"

    links_section += f"""
        <table class="ut-lead-table">
            <thead>
                <tr>
                    <th>Type</th>
                    <th>Edit Link</th>
                    <th>Distribution</th>
                    <th>Target</th>
                    <th>Added By</th>
                    <th>Date Added</th>
                    {action_header}
                </tr>
            </thead>
            <tbody>
    """

    # --------------------------------------------------
    # Existing Survey Rows
    # --------------------------------------------------
    for s in round_surveys:

        survey_type = s.get("SurveyTypeName") or "—"

        survey_link = (s.get("SurveyLink") or "").strip()
        distribution_link = (s.get("DistributionLink") or "").strip()

        added_by = s.get("CreatedBy") or "—"
        created_at = s.get("CreatedAt")

        if created_at:
            try:
                created_at_str = created_at.strftime("%Y-%m-%d")
            except Exception:
                created_at_str = str(created_at)
        else:
            created_at_str = "—"

        target = "Participant"

        # -------------------------
        # Edit Link (Product Team Link)
        # -------------------------
        if survey_link:
            edit_link_html = f'''
                <a href="{e(survey_link)}" target="_blank" rel="noopener noreferrer">
                    Product Team Link
                </a>
            '''
        else:
            edit_link_html = ""

        # -------------------------
        # Distribution Link
        # -------------------------
        if distribution_link:
            distribution_html = f'''
                <a href="{e(distribution_link)}" target="_blank" rel="noopener noreferrer">
                    Participant Facing Link
                </a>
            '''
        else:
            distribution_html = ""

        delete_column_html = ""

        if not planning_locked:
            delete_column_html = f"""
                <td>
                    <form method="post" action="/ut-lead/project" style="display:inline;">
                        <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                        <input type="hidden" name="survey_id" value="{e(s.get('SurveyID'))}">
                        <button type="submit" name="action" value="delete_survey_link">
                            Delete
                        </button>
                    </form>
                </td>
            """

        links_section += f"""
            <tr>
                <td>{e(survey_type)}</td>
                <td>{edit_link_html}</td>
                <td>{distribution_html}</td>
                <td>{e(target)}</td>
                <td>{e(added_by)}</td>
                <td>{e(created_at_str)}</td>
                {delete_column_html}
            </tr>
        """

    # --------------------------------------------------
    # Empty State Row
    # --------------------------------------------------
    if not round_surveys:
        colspan = "7" if not planning_locked else "6"
        links_section += f"""
            <tr>
                <td colspan="{colspan}" class="muted small">
                    No surveys configured yet.
                </td>
            </tr>
        """

    # --------------------------------------------------
    # Add Survey Row
    # --------------------------------------------------
    if not planning_locked:

        from app.db.user_trial_lead import get_survey_types
        survey_types = get_survey_types()

        links_section += f"""
            <tr>
                <form method="post" action="/ut-lead/project">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">

                <td>
                    <select name="survey_type_id" required>
                        <option value="">Select Type</option>
        """

        for st in survey_types:
            links_section += f"""
                        <option value="{e(st['SurveyTypeID'])}">{e(st['SurveyTypeName'])}</option>
            """

        links_section += """
                    </select>
                </td>

                <td>
                    <input type="url" name="survey_edit_link" placeholder="Internal Review Link">
                </td>

                <td>
                    <input type="url" name="survey_distribution_link" placeholder="Participant Link">
                </td>

                <td class="muted small">
                    Participant
                </td>

                <td>—</td>
                <td>—</td>

                <td>
                    <button type="submit" name="action" value="add_survey_link">
                        Add
                    </button>
                </td>

                </form>
            </tr>
        """

    links_section += """
            </tbody>
        </table>
    """

    # --------------------------------------------------
    # Lock / Locked Info
    # --------------------------------------------------

    if not planning_locked:

        links_section += f"""
            <form method="post" action="/ut-lead/project" style="margin-top:12px;">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">

                <button type="submit" name="action" value="lock_planning">
                    Lock Planning
                </button>
            </form>
        """

    else:

        links_section += f"""
            <div class="muted small" style="margin-top:10px;">
                Planning locked at {e(planning_locked_at)}
                by {e(planning_locked_display)}
            </div>
        """

    links_section += """
        </div>
    </details>
    """

    # Append planning links to body
    body_html += links_section

    # =========================================================
    # Recruiting Control
    # =========================================================

    from datetime import date

    recruiting_start_date = round_data.get("RecruitingStartDate")

    if recruiting_start_date:
        recruiting_started = recruiting_start_date <= date.today()
    else:
        recruiting_started = False
        
    planning_locked = bool(round_data.get("PlanningLocked"))

    recruiting_kpis = get_recruiting_kpis(round_id=int(round_id))

    body_html += f"""
        <details class="ut-lead-section wanted-profile-section" open>
            <summary class="ut-lead-section-summary">
                <strong>Recruiting</strong>
                <span class="muted small">
                    {"— Live" if recruiting_started else "— Not Open"}
                </span>
            </summary>

            <div class="ut-lead-section-body">

                {"<div style='margin-bottom:10px;padding:10px;background:#e6ffed;border:1px solid #b7eb8f;'>Successfully uploaded recruiting CSV.</div>" if upload_status == "success" and upload_survey_type_id == "UTSurveyType0001" else ""}

                {"<div style='margin-bottom:10px;padding:10px;background:#fff2f0;border:1px solid #ffccc7;'>Upload failed.</div>" if upload_status == "error" else ""}
    """

    if recruiting_started and recruiting_kpis:
        total = recruiting_kpis.get("total_applicants", 0)
        completed = recruiting_kpis.get("completed_count", 0)

        completion_rate = 0
        if total > 0:
            completion_rate = round((completed / total) * 100, 1)

        body_html += f"""
            <div class="overview-card">

                <div class="overview-label" style="margin-bottom:6px;">
                    Recruiting Snapshot
                </div>

                <div class="snapshot-grid">

                    <div class="snapshot-item">
                        <div class="snapshot-value">{total}</div>
                        <div class="snapshot-label">Applicants</div>
                    </div>

                    <div class="snapshot-item">
                        <div class="snapshot-value">{completed}</div>
                        <div class="snapshot-label">Completed</div>
                    </div>

                    <div class="snapshot-item">
                        <div class="snapshot-value">{recruiting_kpis.get("quitter_count", 0)}</div>
                        <div class="snapshot-label">Quitters</div>
                    </div>

                    <div class="snapshot-item">
                        <div class="snapshot-value">{completion_rate}%</div>
                        <div class="snapshot-label">Completion Rate</div>
                    </div>

                    <div class="snapshot-item">
                        <div class="snapshot-value">{recruiting_kpis.get("total_answer_rows", 0)}</div>
                        <div class="snapshot-label">Answer Rows</div>
                    </div>

                </div>

            </div>
        """

    if not recruiting_started:

        body_html += f"""
            <form method="post" action="/ut-lead/project">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">

                <button type="submit" name="action" value="open_recruiting">
                    Open Recruiting
                </button>
            </form>
        """

    elif recruiting_started:

        status = (round_data.get("Status") or "").lower()

        start_date = round_data.get("RecruitingStartDate")
        end_date = round_data.get("RecruitingEndDate")

        controls_html = ""

        if status == "recruiting":
            controls_html = f"""
                <div class="recruiting-actions">
                    <form method="POST" action="/trials/end-recruiting">
                        <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
                        <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                        <button type="submit" class="btn-danger">
                            End Recruiting
                        </button>
                    </form>
                </div>
            """

        from app.db.survey_answers import has_responses_for_round

        has_external = bool(round_data.get("UseExternalRecruitingSurvey"))
        has_uploaded = has_responses_for_round(round_data["RoundID"])

        if status == "closed":

            if has_external and not has_uploaded:

                controls_html = f"""
                    <div class="recruiting-controls">

                        <form method="post"
                            action="/ut-lead/project"
                            enctype="multipart/form-data"
                            class="recruiting-upload-form">

                            <input type="hidden" name="action" value="upload_survey_results">
                            <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                            <input type="hidden" name="project_id" value="{e(round_data.get('ProjectID'))}">
                            <input type="hidden" name="survey_type_id" value="UTSurveyType0001">

                            <div class="recruiting-upload-row">
                                <div class="recruiting-upload-label">
                                    Upload Recruiting CSV{" (Required)" if has_external and not has_uploaded else ""}
                                </div>

                                <div class="recruiting-upload-input">
                                    {render_csv_dropzone(
                                        input_name="csv_file",
                                        input_id="ut_lead_recruiting_csv_file",
                                        label="Drop recruiting CSV here or click to choose",
                                        required=has_external and not has_uploaded,
                                    )}
                                </div>
                            </div>

                        </form>

                        {f'''
                        <div class="recruiting-warning">
                            You must upload survey results before proceeding to selection.
                        </div>
                        ''' if has_external and not has_uploaded else ""}

                        {f'''
                        <div class="recruiting-actions">
                            <a href="/trials/selection?round_id={e(round_data['RoundID'])}">
                                <button class="btn-primary">
                                    Continue to Selection →
                                </button>
                            </a>
                        </div>
                        ''' if not (has_external and not has_uploaded) else ""}

                    </div>
                """

            else:

                # Either:``
                # - no external survey
                # - OR CSV already uploaded

                controls_html = f"""
                    <div class="recruiting-controls">

                        <form method="post"
                            action="/ut-lead/project"
                            enctype="multipart/form-data"
                            class="recruiting-upload-form">

                            <input type="hidden" name="action" value="upload_survey_results">
                            <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                            <input type="hidden" name="project_id" value="{e(round_data.get('ProjectID'))}">
                            <input type="hidden" name="survey_type_id" value="UTSurveyType0001">

                            <div class="recruiting-upload-row">
                                <div class="recruiting-upload-label">
                                    Upload Recruiting CSV{" (Required)" if has_external and not has_uploaded else ""}
                                </div>

                                <div class="recruiting-upload-input">
                                    <input type="file" name="csv_file" accept=".csv" {"required" if has_external and not has_uploaded else ""}>
                                    <button type="submit" class="btn-primary">Upload</button>
                                </div>
                            </div>

                        </form>

                        {f'''
                        <div class="recruiting-warning">
                            You must upload survey results before proceeding to selection.
                        </div>
                        ''' if has_external and not has_uploaded else ""}

                        {f'''
                        <div class="recruiting-actions">
                            <a href="/trials/selection?round_id={e(round_data['RoundID'])}">
                                <button class="btn-primary">
                                    Continue to Selection →
                                </button>
                            </a>
                        </div>
                        ''' if not (has_external and not has_uploaded) else ""}

                    </div>
                """

        body_html += f"""
            <div class="overview-card">

                <div class="overview-field">
                    <div class="overview-label">Recruiting Started</div>
                    <div class="overview-value">{e(start_date or "—")}</div>
                </div>

                <div class="overview-field">
                    <div class="overview-label">Recruiting Ended</div>
                    <div class="overview-value">{e(end_date or "—")}</div>
                </div>

                {controls_html}

            </div>
        """

    else:

        body_html += """
            <div class="muted small">
                Planning must be locked before recruiting can open.
            </div>
        """

    body_html += """
            </div>
        </details>
    """

    # =========================================================
    # Participants JSON Hydration
    # DB is authoritative for membership + live completion fields
    # JSON only preserves local tracking fields like notes
    # =========================================================

    from app.db.user_trial_lead import get_round_participants

    db_rows = get_round_participants(int(round_id))

    participants_data = []

    for row in db_rows:
        survey_rows = []
        for survey in row.get("Surveys") or []:
            survey_rows.append({
                "round_survey_id": survey.get("RoundSurveyID"),
                "survey_type_id": survey.get("SurveyTypeID"),
                "label": _clean_survey_display_name(survey.get("SurveyTypeName")),
                "complete": bool(survey.get("Complete")),
                "reminders": int(survey.get("ReminderCount") or 0),
            })

        participants_data.append({
            "user_id": row["user_id"],
            "name": f"{row.get('FirstName', '')} {row.get('LastName', '')}".strip() or row["user_id"],

            # DB is authoritative
            "nda_complete": bool(row.get("NDAComplete")),
            "surveys": survey_rows,

            # TEMP: no annotation persistence
            "reason": "",
            "reason_notes": ""
        })

    participant_survey_headers = ""

    for survey in result_surveys:
        participant_survey_headers += f"""
                    <th>{e(_clean_survey_display_name(survey.get('SurveyTypeName')))}</th>
                    <th>Reminders</th>
        """

    participant_colspan = 4 + (len(result_surveys) * 2)

    # --------------------------------------------------
    # Lower Project Sections Template
    # --------------------------------------------------

    sections_template = Path(
        "app/templates/ut_lead/ut_lead_project_sections.html"
    ).read_text(encoding="utf-8")

    # =========================================================
    # Participants Section
    # =========================================================

    participants_template = Path(
        "app/templates/ut_lead/ut_lead_project_participants.html"
    ).read_text(encoding="utf-8")

    participants_rows_html = ""

    if participants_data:
        for p in participants_data:

            nda_complete = "true" if p["nda_complete"] else "false"

            survey_cells_html = ""
            for survey in p.get("surveys") or []:
                checked_attr = "checked" if survey.get("complete") else ""
                survey_cells_html += f"""
                    <td>
                        <input type="checkbox"
                            name="survey_{e(survey.get('round_survey_id') or survey.get('survey_type_id') or 'unknown')}_{e(p['user_id'])}"
                            {checked_attr}
                            disabled>
                    </td>

                    <td class="muted small">
                        {e(survey.get('reminders') or 0)}
                    </td>
                """

            participants_rows_html += f"""
                <tr data-nda-complete="{nda_complete}">
                    <td>{e(p['name'])}</td>

                    <td>{"✔" if p["nda_complete"] else "—"}</td>

                    {survey_cells_html}

                    <td>
                        <select name="row_action_{e(p['user_id'])}">
                            <option value="">Select Action</option>
                            <option value="remove">Remove from Trial</option>
                            <option value="drop">Mark Dropped</option>
                        </select>
                    </td>

                    <td>
                        <select name="reason_{e(p['user_id'])}" style="width:100%;">
                            <option value="">Select Reason</option>

                            <optgroup label="No Penalty">
                                <option value="health" {"selected" if p.get("reason") == "health" else ""}>Health Issue</option>
                                <option value="family" {"selected" if p.get("reason") == "family" else ""}>Family Emergency</option>
                                <option value="regional" {"selected" if p.get("reason") == "regional" else ""}>Regional Issue</option>
                                <option value="system" {"selected" if p.get("reason") == "system" else ""}>System / Logitech Issue</option>
                            </optgroup>

                            <optgroup label="Soft Penalty">
                                <option value="forgot_nda" {"selected" if p.get("reason") == "forgot_nda" else ""}>Forgot NDA</option>
                                <option value="slow_response" {"selected" if p.get("reason") == "slow_response" else ""}>Slow Response</option>
                                <option value="partial" {"selected" if p.get("reason") == "partial" else ""}>Partial Participation</option>
                            </optgroup>

                            <optgroup label="Hard Penalty">
                                <option value="refused_nda" {"selected" if p.get("reason") == "refused_nda" else ""}>Refused NDA</option>
                                <option value="low_effort" {"selected" if p.get("reason") == "low_effort" else ""}>Low Effort</option>
                                <option value="off_topic" {"selected" if p.get("reason") == "off_topic" else ""}>Off-topic Feedback</option>
                                <option value="ghosted" {"selected" if p.get("reason") == "ghosted" else ""}>Dropped Without Notice</option>
                            </optgroup>
                        </select>

                        <textarea 
                            name="reason_notes_{e(p['user_id'])}"
                            rows="1" 
                            placeholder="Optional details"
                            style="width:100%; margin-top:4px;"
                        >{e(p.get("reason_notes", ""))}</textarea>
                    </td>

                </tr>
            """

    else:
        participants_rows_html += f"""
                        <tr>
                            <td colspan="{participant_colspan}" class="muted small">
                                No participants assigned yet.
                            </td>
                        </tr>
        """

    participants_footer_html = """
    <div style="margin-top:15px;">
        <button type="submit" name="action" value="save_participants">
            Save Participant Tracking
        </button>
    </div>

    <p class="muted small" style="margin-top: 10px;">
        Participant membership, NDA status, and survey completion come from the database. Execution tracking fields are stored separately.
    </p>
    """

    participants_html = participants_template
    participants_html = participants_html.replace(
        "__PARTICIPANTS_SURVEY_HEADERS__",
        participant_survey_headers,
    )
    participants_html = participants_html.replace(
        "__PARTICIPANTS_ROWS__",
        participants_rows_html
    )
    participants_html = participants_html.replace(
        "__PARTICIPANTS_FOOTER__",
        participants_footer_html
    )

    # =========================================================
    # Dynamic Survey Results Sections
    # =========================================================

    from app.db.user_trial_lead import get_round_surveys_basic_stats

    survey_stats = get_round_surveys_basic_stats(round_id)

    survey_results_html = _render_dynamic_survey_results_sections(
        round_data=round_data,
        project_id=project_id,
        result_surveys=result_surveys,
        survey_stats=survey_stats,
        upload_status_for_survey=_survey_results_upload_status,
        upload_summary_for_survey=_survey_results_upload_summary,
        attribution_summary_for_survey=_persistent_attribution_summary,
    )

    # =========================================================
    # Shipping Section
    # =========================================================
    shipping_template = Path(
        "app/templates/ut_lead/ut_lead_project_shipping.html"
    ).read_text(encoding="utf-8")


    shipping_table_html = """
    <table class="data-table">
        <thead>
            <tr>
                <th>Participant</th>
                <th>Address</th>
                <th>Confirmed</th>
                <th>Shipped</th>
                <th>Delivered</th>
            </tr>
        </thead>
        <tbody>
    """

    if participants_data:
        for p in participants_data:

            has_address = bool(p.get("ShippingAddressLine1"))
            confirmed = bool(p.get("ShippingAddressConfirmedAt"))
            shipped = bool(p.get("ShippedAt"))
            delivered = bool(p.get("DeliveredAt"))

            address_display = (
                f"{e(p.get('ShippingAddressLine1', ''))}, {e(p.get('ShippingCity', ''))}"
                if has_address else "—"
            )

            shipping_table_html += f"""
            <tr>
                <td>{e(p.get("name", ""))}</td>
                <td>{address_display}</td>
                <td>{"✔" if confirmed else "—"}</td>
                <td>{"✔" if shipped else "—"}</td>
                <td>{"✔" if delivered else "—"}</td>
            </tr>
            """
    else:
        shipping_table_html += """
            <tr>
                <td colspan="5" class="muted small">
                    No participants.
                </td>
            </tr>
        """

    shipping_table_html += """
        </tbody>
    </table>
    """


    shipping_html = shipping_template.replace(
        "__SHIPPING_TABLE__",
        shipping_table_html
    )

    # =========================================================
    # TEMPLATE INJECTION (MISSING PIECE)
    # =========================================================

    sections_html = sections_template
    sections_html = sections_html.replace("__PARTICIPANTS__", participants_html)
    sections_html = sections_html.replace("__SHIPPING__", shipping_html)
    sections_html = sections_html.replace("__SURVEY_RESULTS__", survey_results_html)

    body_html += sections_html

    # --------------------------------------------------
    # PRODUCT KPI (Executive Snapshot)
    # --------------------------------------------------

    product_kpis = get_round_product_kpis(round_id=int(round_data["RoundID"]))

    def _metric_display(value, *, suffix="", decimals=None):
        if value is None:
            return "—"

        if decimals is not None:
            try:
                formatted = f"{float(value):.{decimals}f}"
            except (TypeError, ValueError):
                formatted = str(value)
        else:
            formatted = str(value)

        if formatted.endswith(".0"):
            formatted = formatted[:-2]

        return f"{formatted}{suffix}"

    def _metric_count_display(value):
        try:
            count = int(value or 0)
        except (TypeError, ValueError):
            count = 0

        return f"n={count}" if count > 0 else "No KPI data"

    body_html += f"""
        <div class="survey-metric-card">

            <div class="survey-card-header">
                <div class="survey-title">
                    Product Readiness Snapshot
                </div>
                <div class="survey-meta muted small">
                    DB-derived Product KPI
                </div>
            </div>

            <div class="survey-metrics-grid">

                <div class="metric-block">
                    <div class="metric-value">
                        {e(_metric_display(product_kpis.get("star_rating"), suffix="★", decimals=2))}
                    </div>
                    <div class="metric-label">
                        Star Rating
                    </div>
                    <div class="muted small">
                        {e(_metric_count_display(product_kpis.get("star_rating_count")))}
                    </div>
                </div>

                <div class="metric-block">
                    <div class="metric-value">
                        {e(_metric_display(product_kpis.get("nps")))}
                    </div>
                    <div class="metric-label">
                        Net Promoter Score
                    </div>
                    <div class="muted small">
                        {e(_metric_count_display(product_kpis.get("nps_count")))}
                    </div>
                </div>

                <div class="metric-block">
                    <div class="metric-value">
                        {e(_metric_display(product_kpis.get("ready_for_sales"), suffix="%", decimals=1))}
                    </div>
                    <div class="metric-label">
                        Ready for Sales
                    </div>
                    <div class="muted small">
                        {e(_metric_count_display(product_kpis.get("ready_for_sales_count")))}
                    </div>
                </div>

                <div class="metric-block">
                    <div class="metric-value">
                        {e(_metric_display(product_kpis.get("software_rating"), suffix="★", decimals=2))}
                    </div>
                    <div class="metric-label">
                        Software Rating
                    </div>
                    <div class="muted small">
                        {e(_metric_count_display(product_kpis.get("software_rating_count")))}
                    </div>
                </div>

            </div>
        </div>
    """

    body_html += _render_product_trial_report_section(
        round_id=int(round_data["RoundID"]),
        report_status=report_status,
    )

    body_html += """
        </div>
    """

    body_html = _inject_ut_lead_project_csrf_inputs(
        html=body_html,
        csrf_token=csrf_token,
    )

    html = base_template
    html = inject_nav(html)
    html = html.replace("{{ title }}", "UT Lead – Project Details")
    html = html.replace(
        "</head>",
        '    <link rel="stylesheet" href="/static/user_trial_lead_project.css">\n</head>'
    )
    html = html.replace("__BODY__", body_html)

    return {"html": html}

def handle_ut_lead_project_post(
    *,
    user_id: str,
    data: dict,
):
    """
    UT Lead – Project Round POST handler
    Handles overview save + lock.
    """

    from app.db.user_roles import get_effective_permission_level
    from app.db.user_trial_lead import (
        get_project_round_by_id,
        update_project_round_overview,
        lock_project_round_overview,
        get_round_surveys,
    )

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    permission_level = get_effective_permission_level(user_id)

    # --------------------------------------------------
    # Role Derivation
    # --------------------------------------------------

    is_admin = permission_level >= 90   # adjust threshold if needed
    is_ut_lead = permission_level >= 70

    if not is_ut_lead:
        return {"redirect": "/dashboard"}

    # --------------------------------------------------
    # Validate round
    # --------------------------------------------------
    round_id_raw = data.get("round_id")
    if isinstance(round_id_raw, list):
        round_id_raw = round_id_raw[0]

    if not round_id_raw:
        return {"redirect": "/ut-lead/trials"}

    try:
        round_id = int(round_id_raw)
    except ValueError:
        return {"redirect": "/ut-lead/trials"}

    round_data = get_project_round_by_id(round_id=int(round_id))
    if not round_data:
        return {"redirect": "/ut-lead/trials"}

    if not _can_access_ut_lead_round(
        user_id=user_id,
        round_data=round_data,
    ):
        return {"redirect": "/ut-lead/trials"}

    action = data.get("action")
    # --------------------------------------------------
    # Overview Lock Enforcement
    # --------------------------------------------------
    if action in ("save_overview", "lock_overview") and round_data.get("OverviewLocked"):
        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # Planning Lock Enforcement
    # --------------------------------------------------
    if action in ("add_survey_link", "lock_planning") and round_data.get("PlanningLocked"):
        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # SAVE OVERVIEW
    # --------------------------------------------------
    if action == "save_overview":

        if round_data.get("OverviewLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        description = (data.get("description") or "").strip()
        start_date = data.get("start_date") or None
        end_date = data.get("end_date") or None
        ship_date = data.get("ship_date") or None
        region = (data.get("region") or "").strip()

        user_scope = (data.get("user_scope") or "").strip()
        if user_scope not in ("Internal", "External", "Hybrid"):
            user_scope = None

        prototype_version = (data.get("prototype_version") or "").strip()
        product_sku = (data.get("product_sku") or "").strip()

        try:
            target_users = int(data.get("target_users") or 0)
        except ValueError:
            target_users = 0

        def _parse_int_or_none(v):
            v = (v or "").strip()
            if v == "":
                return None
            try:
                return int(v)
            except ValueError:
                return None

        min_age = _parse_int_or_none(data.get("min_age"))
        max_age = _parse_int_or_none(data.get("max_age"))

        # Basic sanity: if both present and inverted, swap or null them
        if min_age is not None and max_age is not None and min_age > max_age:
            min_age, max_age = max_age, min_age

        ok = update_project_round_overview(
            round_id=round_id,
            description=description,
            start_date=start_date,
            end_date=end_date,
            ship_date=ship_date,
            region=region,
            user_scope=user_scope,
            target_users=target_users,
            min_age=min_age,
            max_age=max_age,
            prototype_version=prototype_version,
            product_sku=product_sku,
        )

        # If DB refused the update (locked or missing), just bounce back
        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # LOCK OVERVIEW
    # --------------------------------------------------
    if action == "lock_overview":

        if round_data.get("OverviewLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        # --------------------------------------------------
        # Save current form state before locking
        # --------------------------------------------------

        description = (data.get("description") or "").strip()
        start_date = data.get("start_date") or None
        end_date = data.get("end_date") or None
        ship_date = data.get("ship_date") or None
        region = (data.get("region") or "").strip()

        user_scope = (data.get("user_scope") or "").strip()
        if user_scope not in ("Internal", "External", "Hybrid"):
            user_scope = None

        prototype_version = (data.get("prototype_version") or "").strip()
        product_sku = (data.get("product_sku") or "").strip()

        try:
            target_users = int(data.get("target_users") or 0)
        except ValueError:
            target_users = 0

        def _parse_int_or_none(v):
            v = (v or "").strip()
            if v == "":
                return None
            try:
                return int(v)
            except ValueError:
                return None

        min_age = _parse_int_or_none(data.get("min_age"))
        max_age = _parse_int_or_none(data.get("max_age"))

        if min_age is not None and max_age is not None and min_age > max_age:
            min_age, max_age = max_age, min_age

        update_project_round_overview(
            round_id=round_id,
            description=description,
            start_date=start_date,
            end_date=end_date,
            ship_date=ship_date,
            region=region,
            user_scope=user_scope,
            target_users=target_users,
            min_age=min_age,
            max_age=max_age,
            prototype_version=prototype_version,
            product_sku=product_sku,
        )

        # --------------------------------------------------
        # Now lock
        # --------------------------------------------------

        lock_project_round_overview(
            round_id=round_id,
            locked_by_user_id=user_id,
        )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}
    
    # --------------------------------------------------
    # UNLOCK OVERVIEW
    # --------------------------------------------------

    if action == "unlock_overview":

        from app.db.user_trial_lead import unlock_project_round_overview

        # Only admin should unlock (recommended)
        if not is_admin:
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        unlock_project_round_overview(
            round_id=round_id,
        )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # ADD PROFILE CRITERIA
    # --------------------------------------------------

    if action == "add_profile_criteria":

        # Prevent edits if overview locked
        if round_data.get("ProfileLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        operator = data.get("operator")
        profile_uid = data.get("profile_uid")

        if operator in ("INCLUDE", "EXCLUDE") and profile_uid:

            add_round_profile_criteria(
                round_id=round_id,
                profile_uid=profile_uid,
                operator=operator,
            )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}


    # --------------------------------------------------
    # DELETE PROFILE CRITERIA
    # --------------------------------------------------

    if action == "delete_profile_criteria":

        # Prevent edits if overview locked
        if round_data.get("ProfileLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        criteria_id = data.get("criteria_id")

        if criteria_id:
            try:
                delete_round_profile_criteria(
                    round_criteria_id=int(criteria_id)
                )
            except ValueError:
                pass

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}
    
    # --------------------------------------------------
    # ADD EXPLICIT CONSTRAINT
    # --------------------------------------------------

    if action == "add_constraint":

        if not ENABLE_CONSTRAINT_CAPTURE_UI:
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        constraint_scope = (data.get("constraint_scope") or "round").strip()
        constraint_category = data.get("constraint_category")
        constraint_priority = data.get("constraint_priority") or "unknown"
        constraint_key = data.get("constraint_key")
        constraint_value = data.get("constraint_value")

        constraint_round_id = round_id
        if constraint_scope == "project":
            constraint_round_id = None

        result = save_explicit_constraint(
            project_id=round_data.get("ProjectID"),
            round_id=constraint_round_id,
            constraint_category=constraint_category,
            constraint_key=constraint_key,
            constraint_value=constraint_value,
            created_by_user_id=user_id,
            constraint_priority=constraint_priority,
            constraint_source="ut_lead",
        )

        if result.get("success"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}&constraint=added#constraints"}

        return {
            "redirect": f"/ut-lead/project?round_id={round_id}&constraint_error={result.get('error') or 'save_failed'}#constraints"
        }

    # --------------------------------------------------
    # DEACTIVATE EXPLICIT CONSTRAINT
    # --------------------------------------------------

    if action == "deactivate_constraint":

        if not ENABLE_CONSTRAINT_CAPTURE_UI:
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        result = deactivate_explicit_constraint(
            project_id=round_data.get("ProjectID"),
            constraint_id=data.get("constraint_id"),
        )

        if result.get("success"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}&constraint=removed#constraints"}

        return {
            "redirect": f"/ut-lead/project?round_id={round_id}&constraint_error={result.get('error') or 'deactivate_failed'}#constraints"
        }

    # --------------------------------------------------
    # ADD SURVEY LINK
    # --------------------------------------------------
    if action == "add_survey_link":

        if round_data.get("PlanningLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        survey_type_id = data.get("survey_type_id")
        survey_edit_link = (data.get("survey_edit_link") or "").strip()
        survey_distribution_link = (data.get("survey_distribution_link") or "").strip()

        if survey_type_id:

            # --------------------------------------------------
            # Prefill format validation (only if provided)
            # --------------------------------------------------
            if survey_distribution_link:

                if "user_token_here" not in survey_distribution_link:
                    return {"redirect": f"/ut-lead/project?round_id={round_id}"}

                if not survey_distribution_link.startswith(
                    "https://docs.google.com/forms/"
                ):
                    return {"redirect": f"/ut-lead/project?round_id={round_id}"}

            add_round_survey(
                round_id=round_id,
                survey_type_id=survey_type_id,
                survey_link=survey_edit_link or "",   # 👈 FIX HERE
                distribution_link=survey_distribution_link or None,
                created_by_user_id=user_id,
            )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # DELETE SURVEY LINK
    # --------------------------------------------------

    if action == "delete_survey_link":

        if round_data.get("PlanningLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        survey_id = data.get("survey_id")

        if survey_id:
            from app.db.user_trial_lead import delete_round_survey
            delete_round_survey(
                round_id=round_id,
                survey_id=int(survey_id),
            )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # LOCK PROFILE
    # --------------------------------------------------

    if action == "lock_profile":
        from app.db.user_trial_lead import lock_project_round_profile

        lock_project_round_profile(
            round_id=int(round_id),
            locked_by=user_id,
        )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}


    # --------------------------------------------------
    # UPDATE RECRUITING CONFIG
    # --------------------------------------------------

    if action == "update_recruiting_config":

        from app.db.user_trial_lead import update_recruiting_config

        use_external = data.get("use_external_recruiting_survey") == "1"

        update_recruiting_config(
            round_id=int(round_id),
            use_external=use_external,
        )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # OPEN RECRUITING
    # --------------------------------------------------

    if action == "open_recruiting":

        # ------------------------------------------
        # Remove planning lock dependency (your decision)
        # ------------------------------------------

        # ------------------------------------------
        # Enforce External Recruiting Survey Requirement
        # ------------------------------------------

        use_external = round_data.get("UseExternalRecruitingSurvey") in (1, "1", True)

        if use_external:

            surveys = get_round_surveys(round_id=int(round_id))

            has_recruiting_survey = False

            for s in surveys:
                survey_name = (s.get("SurveyTypeName") or "").lower()

                if "recruit" in survey_name:
                    has_recruiting_survey = True
                    break

            if not has_recruiting_survey:

                return {
                    "redirect": f"/ut-lead/project?round_id={round_id}&error=missing_recruiting_survey"
                }

        # ------------------------------------------
        # OPEN RECRUITING
        # ------------------------------------------

        from app.db.project_rounds import set_project_round_status
        from app.db.project_rounds import get_project_round_by_id

        current = get_project_round_by_id(round_id=round_id)

        from datetime import datetime

        if current:

            # Case 1: Not yet recruiting → full transition
            if current.get("Status") != "Recruiting":
                set_project_round_status(
                    round_id=round_id,
                    status="recruiting",
                    ut_lead_id=user_id,
                )

            # Case 2: Already recruiting BUT start date missing → fix partial state
            elif not current.get("RecruitingStartDate"):

                import mysql.connector
                from app.config.config import DB_CONFIG
                from datetime import datetime

                conn = mysql.connector.connect(**DB_CONFIG)
                try:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        UPDATE project_rounds
                        SET RecruitingStartDate = %s
                        WHERE RoundID = %s
                        """,
                        (datetime.utcnow(), round_id)
                    )
                    conn.commit()
                finally:
                    conn.close()

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}
    
    # --------------------------------------------------
    # SAVE / SYNC PARTICIPANTS (JSON tracking layer)
    # --------------------------------------------------

    if action == "save_participants":

        import json
        from app.db.user_trial_lead import get_round_participants

        base = Path(__file__).resolve().parents[1] / "dev_data" / "trial_projects"
        round_dir = base / f"round_{round_id}"
        round_dir.mkdir(parents=True, exist_ok=True)
        json_path = round_dir / "participants.json"

        db_rows = get_round_participants(int(round_id))
        db_lookup = {row["user_id"]: row for row in db_rows}
        db_user_ids = set(db_lookup.keys())

        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        else:
            json_data = []

        json_lookup = {
            row.get("user_id"): row
            for row in json_data
            if row.get("user_id")
        }

        updated = []

        removed_ids = []

        for uid in db_user_ids:
            db_row = db_lookup[uid]
            existing = json_lookup.get(uid, {})

            participant_surveys = []

            for survey in db_row.get("Surveys") or []:
                participant_surveys.append({
                    "round_survey_id": survey.get("RoundSurveyID"),
                    "survey_type_id": survey.get("SurveyTypeID"),
                    "label": _clean_survey_display_name(survey.get("SurveyTypeName")),
                    "complete": bool(survey.get("Complete")),
                    "reminders": int(survey.get("ReminderCount") or 0),
                })

            participant = {
                "user_id": uid,
                "name": f"{db_row.get('FirstName', '')} {db_row.get('LastName', '')}".strip() or uid,
                "nda_complete": bool(db_row.get("NDAComplete")),

                # keep live survey completion/reminder values from DB function
                "surveys": participant_surveys,

                # NEW: structured reason
                "reason": existing.get("reason", ""),
                "reason_notes": existing.get("reason_notes", ""),
            }
            
            reason_value = (data.get(f"reason_{uid}") or "").strip()
            reason_notes_value = (data.get(f"reason_notes_{uid}") or "").strip()

            if reason_value:
                participant["reason"] = reason_value
                participant["reason_notes"] = reason_notes_value

            row_action = data.get(f"row_action_{uid}")

            # ---------------------------------
            # TRACK REMOVALS (DO NOT REDIRECT YET)
            # ---------------------------------
            if row_action == "remove":
                removed_ids.append(uid)

            updated.append(participant)

        # ---------------------------------
        # SAVE JSON FIRST (ALWAYS)
        # ---------------------------------
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(updated, f, indent=4)

        # ---------------------------------
        # THEN HANDLE REPLACEMENT REDIRECT
        # ---------------------------------
        if removed_ids:
            removed_param = ",".join(removed_ids)

            return {
                "redirect": f"/trials/selection?round_id={round_id}&mode=edit&removed_user_ids={removed_param}"
            }

        # ---------------------------------
        # NORMAL SAVE
        # ---------------------------------
        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # LOCK Planning
    # --------------------------------------------------

    if action == "lock_planning":

        if round_data.get("PlanningLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        from app.db.user_trial_lead import lock_project_round_planning

        from app.db.project_rounds import set_project_round_status

        round_surveys = get_round_surveys(round_id)

        # --------------------------------------------------
        # MVP: No survey link enforcement
        # Planning can be locked regardless of survey setup
        # --------------------------------------------------

        # (intentionally no validation here)

        # --------------------------------------------------
        # Lock planning
        # --------------------------------------------------

        lock_project_round_planning(
            round_id=round_id,
            locked_by_user_id=user_id,
        )

        # --------------------------------------------------
        # Transition lifecycle → approved
        # This makes the trial appear in Upcoming Trials
        # --------------------------------------------------

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # Upload Survey Results
    # --------------------------------------------------

    if action == "upload_survey_results":

        files = data.get("files") or {}
        csv_file = files.get("csv_file")

        project_id = round_data.get("ProjectID")
        survey_type_id = data.get("survey_type_id")
        round_survey_id = data.get("round_survey_id")

        if not project_id or not survey_type_id or not csv_file:
            return {"redirect": f"/ut-lead/project?round_id={round_id}&upload=error"}

        if round_survey_id:
            matched_configured_survey = None

            for survey in get_round_surveys(int(round_id)):
                current_round_survey_id = survey.get("RoundSurveyID") or survey.get("SurveyID")
                if str(current_round_survey_id or "") == str(round_survey_id):
                    matched_configured_survey = survey
                    break

            if not matched_configured_survey:
                return {"redirect": f"/ut-lead/project?round_id={round_id}&upload=error"}

            if str(matched_configured_survey.get("SurveyTypeID") or "") != str(survey_type_id or ""):
                return {"redirect": f"/ut-lead/project?round_id={round_id}&upload=error"}

        try:
            csv_bytes = csv_file.read()
            original_filename = getattr(csv_file, "filename", None)
            safe_filename = require_csv_upload(
                filename=original_filename or "survey_results.csv",
                file_bytes=csv_bytes,
            )
        except Exception:
            return {"redirect": f"/ut-lead/project?round_id={round_id}&upload=error"}

        # --------------------------------------------------
        # Derive survey title from sanitized filename
        # Example:
        # Remo - Final Usage - Survey Results (Responses).csv
        # --------------------------------------------------

        survey_title = Path(safe_filename).stem.strip() or "Uploaded Survey"

        from app.services.survey_results_upload import (
            UploadContext,
            UploadError,
            ingest_google_forms_csv,
        )

        try:

            upload_summary = ingest_google_forms_csv(
                ctx=UploadContext(
                    project_id=project_id,
                    round_id=round_id,
                    survey_type_id=survey_type_id,
                    survey_title=survey_title,
                    uploaded_by_user_id=user_id,
                ),
                csv_bytes=csv_bytes,
                original_filename=safe_filename,
            )

        except UploadError:

            return {
                "redirect": f"/ut-lead/project?round_id={round_id}&upload=error"
            }

        from urllib.parse import urlencode

        redirect_params = {
            "round_id": round_id,
            "upload": "success",
            "upload_survey_type_id": survey_type_id,
            "upload_round_survey_id": round_survey_id or "",
            "total_rows": upload_summary.total_respondent_rows,
            "matched_users": upload_summary.matched_users,
            "ignored_rows": upload_summary.ignored_rows_no_user,
            "token_rows": upload_summary.matched_by_token_rows,
            "email_rows": upload_summary.matched_by_email_rows,
            "anonymous_rows": upload_summary.anonymous_rows,
            "unmatched_rows": upload_summary.unmatched_rows,
            "review_rows": upload_summary.needs_review_rows,
            "inserted_answers": upload_summary.inserted_answer_rows,
        }

        return {
            "redirect": f"/ut-lead/project?{urlencode(redirect_params)}"
        }
    
    # --------------------------------------------------
    # Product Trial Report Actions
    # --------------------------------------------------

    product_trial_report_actions = {
        "generate_product_trial_report": "generated",
        "generate_product_trial_section_names": "names_generated",
        "generate_product_trial_section_summaries": "summaries_generated",
        "generate_product_trial_insights": "insights_generated",
    }

    if action in product_trial_report_actions:

        from app.db.product_trial_reports import ProductTrialReportsTableMissing
        from app.services.product_trial_report_service import (
            generate_product_trial_insights,
            generate_product_trial_report,
            generate_product_trial_section_names,
            generate_product_trial_section_summaries,
        )

        generator_by_action = {
            "generate_product_trial_report": generate_product_trial_report,
            "generate_product_trial_section_names": generate_product_trial_section_names,
            "generate_product_trial_section_summaries": generate_product_trial_section_summaries,
            "generate_product_trial_insights": generate_product_trial_insights,
        }

        try:
            report_result = generator_by_action[action](
                round_id=int(round_id),
                generated_by_user_id=user_id,
            )
        except ProductTrialReportsTableMissing:
            return {"redirect": f"/ut-lead/project?round_id={round_id}&report=table_missing"}
        except Exception:
            return {"redirect": f"/ut-lead/project?round_id={round_id}&report=error"}

        if not report_result.get("success"):
            error_key = report_result.get("error") or "error"
            if error_key == "no_result_answers":
                return {"redirect": f"/ut-lead/project?round_id={round_id}&report=no_data"}
            if error_key in {"not_found", "report_not_found"}:
                return {"redirect": f"/ut-lead/project?round_id={round_id}&report=not_generated"}
            return {"redirect": f"/ut-lead/project?round_id={round_id}&report=error"}

        report_status = product_trial_report_actions[action]
        return {"redirect": f"/ut-lead/project?round_id={round_id}&report={report_status}"}

    # --------------------------------------------------
    # Default Fallback (Critical)
    # --------------------------------------------------

    # If execution reaches here, no action matched.
    # Never fall through silently.
    return {"redirect": f"/ut-lead/project?round_id={round_id}"}