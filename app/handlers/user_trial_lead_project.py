# app/handlers/user_trial_lead_project.py

from app.db.user_roles import get_effective_permission_level
from app.db.user_trial_lead import (
    get_project_round_by_id,
    update_project_round_overview,
    lock_project_round_overview,
    add_round_survey,
    lock_project_round_planning,
    get_round_surveys,
    get_round_surveys_basic_stats,
    get_round_participants,
    get_round_profile_criteria,
    add_round_profile_criteria,
    delete_round_profile_criteria
)
import os
import json
import csv
from io import StringIO
from datetime import datetime, timedelta
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

# Audit-first rollout for guided UT Lead workflow visibility.
# False = show every section and mark sections that would be hidden.
# True = actually hide blocked future sections.
UT_LEAD_HIDE_BLOCKED_SECTIONS = True


_PROFILE_CATEGORY_GROUP_ORDER = [
    "Work / Role",
    "Gaming & Content",
    "Computer & Mobile",
    "Device Preferences",
    "Body / Fit",
    "Other",
]

_PROFILE_CATEGORY_GROUPS = {
    "Work / Role": {
        "Work from home",
        "Work at Office (Fixed Desk)",
        "Work at Office (Flex Desk)",
        "Work in Public Spaces",
        "Remote Meetings",
        "Job",
    },
    "Gaming & Content": {
        "PC Gamer",
        "Console Gamer",
        "Streamer",
        "Content Creator",
    },
    "Computer & Mobile": {
        "Computer Type",
        "Computer OS",
        "Phone OS",
        "Monitor",
    },
    "Device Preferences": {
        "Keyboard",
        "Speakers",
        "Headset",
        "Headset Noise Cancelling",
        "Earbuds",
        "Microphone",
        "Webcam",
        "Docking Station",
        "Mouse",
        "Touchpad",
        "Console",
    },
    "Body / Fit": {
        "Hand Dominance",
        "Hand Size",
        "Head Length",
        "Head Width",
        "Hair Type",
        "Hair Volume",
        "Glasses Frequency",
        "Ear Piercing Frequency",
        "Ear Piercing Locations",
    },
}


def _get_profile_category_group(category_name: str | None) -> str:
    name = str(category_name or "").strip()
    for group_name in _PROFILE_CATEGORY_GROUP_ORDER:
        if name in _PROFILE_CATEGORY_GROUPS.get(group_name, set()):
            return group_name

    return "Other"


def _render_profile_category_options(categories: list[dict]) -> str:
    grouped_categories = {group_name: [] for group_name in _PROFILE_CATEGORY_GROUP_ORDER}

    for category in categories or []:
        category_name = str(category.get("CategoryName") or "").strip()
        if category_name == "Trial Willingness":
            continue

        group_name = _get_profile_category_group(category_name)
        grouped_categories.setdefault(group_name, []).append(category)

    html = ""
    for group_name in _PROFILE_CATEGORY_GROUP_ORDER:
        group_rows = sorted(
            grouped_categories.get(group_name, []),
            key=lambda row: str(row.get("CategoryName") or "").lower(),
        )

        if not group_rows:
            continue

        html += f'<optgroup label="{e(group_name)}">'
        for category in group_rows:
            html += (
                f'<option value="{e(category.get("CategoryID"))}">'
                f'{e(category.get("CategoryName") or "Untitled Category")}'
                '</option>'
            )
        html += '</optgroup>'

    return html


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


_WORKFLOW_SECTION_IDS = {
    "product_identity": "product-identity",
    "project_stakeholders": "project-stakeholders",
    "round_configuration": "round-configuration",
    "profile": "wanted-user-profile",
    "recruiting_configuration": "recruiting-configuration",
    "survey_links": "survey-links",
    "recruiting": "recruiting",
    "participants": "participants",
    "shipping": "shipping",
    "survey_results": "survey-results",
    "report": "product-trial-report",
}


def _workflow_details_attrs(
    section_key: str,
    current_workflow_key: str | None,
    *,
    open_for_key: str | None = None,
) -> str:
    """
    Return stable workflow attributes for collapsible UT Lead sections.
    The database-derived current workflow key decides which section opens.
    """

    dom_id = _WORKFLOW_SECTION_IDS.get(section_key, section_key)
    active_key = open_for_key or section_key
    current_attr = " data-workflow-current=\"true\"" if current_workflow_key == active_key else ""
    open_attr = " open" if current_workflow_key == active_key else ""

    return (
        f'id="{e(dom_id)}" '
        f'data-workflow-section="{e(section_key)}"'
        f'{current_attr}'
        f'{open_attr}'
    )


def _has_participant_shipping_address(participant: dict) -> bool:
    return any(
        participant.get(key)
        for key in (
            "ShippingAddressLine1",
            "ShippingOfficeID",
            "ShippingCity",
            "ShippingCountry",
        )
    )


def _build_ut_lead_workflow_state(
    *,
    round_data: dict,
    result_surveys: list[dict],
    survey_stats: list[dict],
    participants_data: list[dict],
    product_trial_report_result: dict,
    report_status: str | None,
) -> dict:
    """
    Build a read-only, DB-derived workflow state for the UT Lead project page.
    No state is stored here; this only reflects persisted round/survey/participant/report data.
    """

    round_status = str(round_data.get("Status") or "").strip().lower()
    is_closed_round = round_status in {"closed", "completed"}

    overview_complete = bool(round_data.get("OverviewLocked"))
    profile_complete = bool(round_data.get("ProfileLocked"))
    planning_complete = bool(round_data.get("PlanningLocked"))
    recruiting_complete = bool(round_data.get("RecruitingEndDate")) or is_closed_round
    participants_complete = bool(participants_data)

    if not participants_data:
        shipping_complete = False
    else:
        shipping_complete = all(
            _has_participant_shipping_address(participant)
            and bool(participant.get("ShippingAddressConfirmedAt"))
            and bool(participant.get("ShippedAt") or participant.get("DeliveredAt"))
            for participant in participants_data
        )

    survey_results_complete = bool(product_trial_report_result.get("success")) or any(
        int((row or {}).get("completed_count") or 0) > 0
        for row in (survey_stats or [])
    )

    report_complete = bool(product_trial_report_result.get("success"))

    current_key = None
    if report_status:
        current_key = "report"
    elif not overview_complete:
        current_key = "project_details"
    elif not profile_complete:
        current_key = "profile"
    elif not planning_complete:
        current_key = "survey_links"
    elif not recruiting_complete:
        current_key = "recruiting"
    elif is_closed_round and not report_complete:
        current_key = "report"
    elif not participants_complete:
        current_key = "participants"
    elif not shipping_complete and not is_closed_round:
        current_key = "shipping"
    elif result_surveys and not survey_results_complete:
        current_key = "survey_results"
    elif not report_complete:
        current_key = "report"

    shipping_status_override = None
    if is_closed_round and not shipping_complete:
        shipping_status_override = {
            "status": "not_captured",
            "status_label": "Not captured",
        }

    steps = [
        {"key": "project_details", "label": "Details", "target": "round-configuration", "complete": overview_complete},
        {"key": "profile", "label": "Profile", "target": "wanted-user-profile", "complete": profile_complete},
        {"key": "survey_links", "label": "Links", "target": "survey-links", "complete": planning_complete},
        {"key": "recruiting", "label": "Recruiting", "target": "recruiting", "complete": recruiting_complete},
        {"key": "participants", "label": "Users", "target": "participants", "complete": participants_complete},
        {"key": "shipping", "label": "Shipping", "target": "shipping", "complete": shipping_complete, "status_override": shipping_status_override},
        {"key": "survey_results", "label": "Results", "target": "survey-results", "complete": survey_results_complete},
        {"key": "report", "label": "Report", "target": "product-trial-report", "complete": report_complete},
    ]

    current_index = None
    if current_key:
        for index, step in enumerate(steps):
            if step["key"] == current_key:
                current_index = index
                break

    for index, step in enumerate(steps):
        status_override = step.pop("status_override", None)
        if status_override:
            step["status"] = status_override["status"]
            step["status_label"] = status_override["status_label"]
        elif current_key and step["key"] == current_key:
            step["status"] = "current"
            step["status_label"] = "Current"
        elif step["complete"]:
            step["status"] = "complete"
            step["status_label"] = "Complete"
        elif current_index is not None and index < current_index:
            step["status"] = "needs_attention"
            step["status_label"] = "Needs attention"
        else:
            step["status"] = "upcoming"
            step["status_label"] = "Upcoming"

    return {
        "current_key": current_key,
        "steps": steps,
    }


def _has_survey_result_data(survey_stats: list[dict] | None) -> bool:
    for row in survey_stats or []:
        for key in ("completed_count", "response_count", "answer_count"):
            try:
                if int((row or {}).get(key) or 0) > 0:
                    return True
            except (TypeError, ValueError):
                continue

    return False


def _has_product_kpi_data(product_kpis: dict | None) -> bool:
    if not product_kpis:
        return False

    for key in (
        "star_rating_count",
        "nps_count",
        "ready_for_sales_count",
        "software_rating_count",
    ):
        try:
            if int(product_kpis.get(key) or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue

    return False


def _build_ut_lead_section_visibility(
    *,
    round_data: dict,
    result_surveys: list[dict],
    survey_stats: list[dict],
    participants_data: list[dict],
    product_trial_report_result: dict,
    workflow_state: dict,
) -> dict:
    """
    Build body-section visibility from persisted DB state.
    This controls what is rendered in guided mode, not authorization.
    """

    round_status = str(round_data.get("Status") or "").strip().lower()
    is_closed_round = round_status in {"closed", "completed"}

    details_confirmed = bool(round_data.get("OverviewLocked"))
    profile_confirmed = bool(round_data.get("ProfileLocked"))
    survey_setup_confirmed = bool(round_data.get("PlanningLocked"))

    surveys_exist = bool(result_surveys)
    any_round_survey_exists = bool(round_data.get("PlanningLocked")) or surveys_exist
    participants_exist = bool(participants_data)
    recruiting_has_started = bool(round_data.get("RecruitingStartDate"))
    recruiting_has_ended = bool(round_data.get("RecruitingEndDate")) or is_closed_round
    results_exist = _has_survey_result_data(survey_stats)
    report_exists = bool(product_trial_report_result.get("success"))

    visibility = {
        "product_identity": True,
        "project_stakeholders": True,
        "round_configuration": True,
        "constraints": ENABLE_CONSTRAINT_CAPTURE_UI,
        "profile": details_confirmed or profile_confirmed,
        "recruiting_configuration": (
            profile_confirmed
            or survey_setup_confirmed
            or any_round_survey_exists
            or recruiting_has_started
            or participants_exist
            or report_exists
            or is_closed_round
        ),
        "survey_links": (
            profile_confirmed
            or survey_setup_confirmed
            or any_round_survey_exists
            or recruiting_has_started
            or participants_exist
            or report_exists
            or is_closed_round
        ),
        "recruiting": (
            survey_setup_confirmed
            or recruiting_has_started
            or recruiting_has_ended
            or participants_exist
            or report_exists
        ),
        "participants": (
            recruiting_has_started
            or recruiting_has_ended
            or participants_exist
            or report_exists
        ),
        "shipping": participants_exist,
        "survey_results": (
            surveys_exist
            and (participants_exist or results_exist or report_exists or is_closed_round)
        ),
        "product_readiness": False,
        "report": results_exist or report_exists or is_closed_round,
    }

    current_key = workflow_state.get("current_key")
    if current_key == "project_details":
        visibility["product_identity"] = True
        visibility["project_stakeholders"] = True
        visibility["round_configuration"] = True
    elif current_key == "profile":
        visibility["profile"] = True
    elif current_key == "survey_links":
        visibility["recruiting_configuration"] = True
        visibility["survey_links"] = True
    elif current_key == "recruiting":
        visibility["recruiting"] = True
    elif current_key == "participants":
        visibility["participants"] = True
    elif current_key == "shipping":
        visibility["shipping"] = True
    elif current_key == "survey_results":
        visibility["survey_results"] = True
    elif current_key == "report":
        visibility["report"] = True

    return visibility


_SECTION_VISIBILITY_LABELS = {
    "profile": "Wanted User Profile",
    "recruiting_configuration": "Recruiting Configuration",
    "survey_links": "Planning – Survey Links",
    "recruiting": "Recruiting",
    "participants": "Participants",
    "shipping": "Shipping",
    "survey_results": "Survey Results",
    "product_readiness": "Product Readiness Snapshot",
    "report": "Product Trial Report",
}


def _render_visibility_gated_section(
    section_key: str,
    section_html: str,
    section_visibility: dict,
) -> str:
    """
    Render a section with audit-first guided visibility.
    When UT_LEAD_HIDE_BLOCKED_SECTIONS is False, blocked sections stay visible
    and are marked so real-world trial testing can verify the gating logic.
    """

    if section_visibility.get(section_key, True):
        return section_html

    if UT_LEAD_HIDE_BLOCKED_SECTIONS:
        return ""

    label = _SECTION_VISIBILITY_LABELS.get(
        section_key,
        section_key.replace("_", " ").title(),
    )

    return f"""
        <div class="ut-visibility-preview" data-would-hide-section="{e(section_key)}">
            <strong>Visibility preview</strong>
            <span>{e(label)} would be hidden when guided visibility is enforced.</span>
        </div>
        {section_html}
    """


def _render_ut_lead_workflow_tracker(workflow_state: dict) -> str:
    steps = workflow_state.get("steps") or []

    step_html = ""
    for index, step in enumerate(steps, start=1):
        status = step.get("status") or "upcoming"
        step_html += f"""
            <a
                class="ut-workflow-step ut-workflow-step-{e(status)}"
                href="#{e(step.get('target') or '')}"
                aria-label="{e(step.get('label') or 'Workflow step')}: {e(step.get('status_label') or '')}"
            >
                <span class="ut-workflow-step-index">{e(index)}</span>
                <span class="ut-workflow-step-main">
                    <span class="ut-workflow-step-label">{e(step.get('label') or '')}</span>
                    <span class="ut-workflow-step-status">{e(step.get('status_label') or '')}</span>
                </span>
            </a>
        """

    return f"""
        <div class="ut-workflow-tracker" aria-label="Project workflow progress">
            {step_html}
        </div>
    """


def _render_ut_lead_project_autoscroll_script(workflow_state: dict) -> str:
    current_key = workflow_state.get("current_key")
    if not current_key:
        return ""

    return f"""
        <script>
        document.addEventListener("DOMContentLoaded", function () {{
            if (window.location.hash) return;

            const currentSection = document.querySelector(
                '.ut-lead-project-page [data-workflow-current="true"]'
            );

            if (!currentSection) return;

            window.requestAnimationFrame(function () {{
                currentSection.scrollIntoView({{
                    block: "start",
                    inline: "nearest",
                    behavior: "auto"
                }});
            }});
        }});
        </script>
    """


def _render_dynamic_survey_results_sections(
    *,
    round_data: dict,
    project_id: str,
    result_surveys: list[dict],
    survey_stats: list[dict],
    upload_status_for_survey,
    upload_summary_for_survey,
    attribution_summary_for_survey,
    current_workflow_key: str | None,
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
            .replace(
                "__SURVEY_RESULTS_DETAILS_ATTRS__",
                _workflow_details_attrs("survey_results", current_workflow_key),
            )
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
    elif report_status == "summaries_empty":
        metadata = (report or {}).get("metadata") or {}
        attempted = metadata.get("section_summary_sections_attempted")
        with_qual = metadata.get("section_summary_sections_with_qual")
        with_answers = metadata.get("section_summary_sections_with_qual_answers")
        generated = metadata.get("section_summary_calls_succeeded")

        diagnostic_bits = []
        if attempted is not None:
            diagnostic_bits.append(f"{e(attempted)} section(s) attempted")
        if with_qual is not None:
            diagnostic_bits.append(f"{e(with_qual)} had qualitative follow-up")
        if with_answers is not None:
            diagnostic_bits.append(f"{e(with_answers)} had qualitative answers")
        if generated is not None:
            diagnostic_bits.append(f"{e(generated)} summary response(s) saved")

        diagnostic_html = ""
        if diagnostic_bits:
            diagnostic_html = f"""
                <div style="margin-top:6px; color:#7f1d1d; font-size:12px; font-weight:500;">
                    {' · '.join(diagnostic_bits)}
                </div>
            """

        notice_html = f"""
            <div class="product-report-notice product-report-notice-error">
                No section summaries were generated. Report sections were rebuilt from DB-backed answers, but Historical's SWOT helper returned no summaries.
                {diagnostic_html}
            </div>
        """
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
        <details id="product-trial-report" class="ut-lead-section product-trial-report-section" open>
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
    <details id="product-trial-report" class="ut-lead-section product-trial-report-section" open>
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
                        <a href="#" onclick="expandProductTrialReportSections(); return false;" style="color:#888;">
                            Expand all
                        </a>
                        <span>|</span>
                        <a href="#" onclick="collapseProductTrialReportSections(); return false;" style="color:#888;">
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

    <script>
    function expandProductTrialReportSections() {
        const report = document.getElementById("product-trial-report");
        if (!report) return;

        report.querySelectorAll("details.product-report-phase-group").forEach((group) => {
            group.open = true;
        });

        report.querySelectorAll(".historical-section-result[data-historical-section]").forEach((section) => {
            section.classList.remove("collapsed");
        });
    }

    function collapseProductTrialReportSections() {
        const report = document.getElementById("product-trial-report");
        if (!report) return;

        report.querySelectorAll(".historical-section-result[data-historical-section]").forEach((section) => {
            section.classList.add("collapsed");
        });

        report.querySelectorAll("details.product-report-phase-group").forEach((group) => {
            group.open = false;
        });
    }
    </script>
    """

    return html


def _format_round_date_value(value) -> str:
    if not value:
        return ""

    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")

    text = str(value).strip()
    return text[:10] if text else ""


def _default_round_end_date_value(round_data: dict) -> str:
    existing_end = _format_round_date_value(round_data.get("EndDate"))
    if existing_end:
        return existing_end

    start_value = _format_round_date_value(round_data.get("StartDate"))
    if not start_value:
        return ""

    try:
        start_date = datetime.strptime(start_value, "%Y-%m-%d").date()
    except ValueError:
        return ""

    return (start_date + timedelta(days=30)).isoformat()


def _render_round_config_unlocked(*, round_data, country_options_html, details_attrs: str = "open"):

    return f"""
    <details class="ut-lead-section round-config-section" {details_attrs}>
        <summary class="ut-lead-section-summary">
            <strong>Round Configuration</strong>
            <span class="muted small">— Editing</span>
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
            value="{e(_default_round_end_date_value(round_data))}">
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
    <button type="submit" name="action" value="lock_overview">Confirm Details</button>
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

                const parts = start.value.split("-").map(Number);
                if (parts.length !== 3 || parts.some(Number.isNaN)) return;

                const d = new Date(parts[0], parts[1] - 1, parts[2]);
                d.setDate(d.getDate() + 30);

                const yyyy = d.getFullYear();
                const mm = String(d.getMonth() + 1).padStart(2, "0");
                const dd = String(d.getDate()).padStart(2, "0");

                end.value = yyyy + "-" + mm + "-" + dd;
            }}

            if (!end.value) {{
                autoEndDate();
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

def _render_round_config_locked(*, round_data, country_rows, user_id, details_attrs: str = "open"):

    # -----------------------------------------
    # Convert Region Codes → Names
    # -----------------------------------------
    region_codes = (round_data.get("Region") or "").split(",")
    region_names = []

    for code in region_codes:
        code = code.strip()
        if not code:
            continue

        for c in country_rows:
            if c["CountryCode"] == code:
                region_names.append(c["CountryName"])
                break
        else:
            region_names.append(code)

    region_display = ", ".join(region_names) if region_names else "—"
    min_age = round_data.get("MinAge") or "Any"
    max_age = round_data.get("MaxAge") or "Any"

    html = f"""
    <details class="ut-lead-section round-config-section" {details_attrs}>
        <summary class="ut-lead-section-summary">
            <strong>Round Configuration</strong>
            <span class="muted small">— Confirmed</span>
        </summary>

        <div class="ut-lead-section-body">
            <div class="round-config-locked-grid">
                <div class="round-config-locked-card">
                    <div class="round-config-locked-title">Schedule</div>
                    <div class="round-config-locked-row">
                        <span class="round-config-locked-label">Start</span>
                        <span class="round-config-locked-value">{e(round_data.get('StartDate') or '—')}</span>
                    </div>
                    <div class="round-config-locked-row">
                        <span class="round-config-locked-label">End</span>
                        <span class="round-config-locked-value">{e(round_data.get('EndDate') or '—')}</span>
                    </div>
                    <div class="round-config-locked-row">
                        <span class="round-config-locked-label">Ship</span>
                        <span class="round-config-locked-value">{e(round_data.get('ShipDate') or '—')}</span>
                    </div>
                </div>

                <div class="round-config-locked-card">
                    <div class="round-config-locked-title">Participants</div>
                    <div class="round-config-locked-row">
                        <span class="round-config-locked-label">Scope</span>
                        <span class="round-config-locked-value">{e(round_data.get('UserScope') or '—')}</span>
                    </div>
                    <div class="round-config-locked-row">
                        <span class="round-config-locked-label">Users</span>
                        <span class="round-config-locked-value">{e(round_data.get('TargetUsers') or '—')}</span>
                    </div>
                    <div class="round-config-locked-row">
                        <span class="round-config-locked-label">Age</span>
                        <span class="round-config-locked-value">{e(min_age)} – {e(max_age)}</span>
                    </div>
                </div>

                <div class="round-config-locked-card">
                    <div class="round-config-locked-title">Product</div>
                    <div class="round-config-locked-row">
                        <span class="round-config-locked-label">Prototype</span>
                        <span class="round-config-locked-value">{e(round_data.get('PrototypeVersion') or '—')}</span>
                    </div>
                    <div class="round-config-locked-row">
                        <span class="round-config-locked-label">FW</span>
                        <span class="round-config-locked-value">{e(round_data.get('ProductSKU') or '—')}</span>
                    </div>
                </div>

                <div class="round-config-locked-card round-config-locked-card-wide">
                    <div class="round-config-locked-title">Regions</div>
                    <div class="round-config-locked-row round-config-locked-row-wide">
                        <span class="round-config-locked-label">Countries</span>
                        <span class="round-config-locked-value">{e(region_display)}</span>
                    </div>
                </div>
            </div>
    """

    html += f"""
        <form method="post" action="/ut-lead/project" style="margin-top:12px;">
            <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
            <button type="submit" name="action" value="unlock_overview">
                Reopen Details
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
    shipping_upload_status = query_params.get("shipping_upload", [None])[0]

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


    round_surveys = get_round_surveys(int(round_data["RoundID"]))
    result_surveys = _get_result_surveys(round_surveys)
    survey_stats = get_round_surveys_basic_stats(int(round_id))

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
            "email": row.get("Email"),

            "nda_complete": bool(row.get("NDAComplete")),
            "surveys": survey_rows,
            "DeliveryType": row.get("DeliveryType"),
            "ShippingAddressConfirmedAt": row.get("ShippingAddressConfirmedAt"),
            "ResponsibilitiesAcceptedAt": row.get("ResponsibilitiesAcceptedAt"),
            "Courier": row.get("Courier"),
            "TrackingNumber": row.get("TrackingNumber"),
            "TrackingURL": row.get("TrackingURL"),
            "ShippedAt": row.get("ShippedAt"),
            "DeliveredAt": row.get("DeliveredAt"),
            "DeviceReceivedConfirmedAt": row.get("DeviceReceivedConfirmedAt"),
            "ParticipantStatus": row.get("ParticipantStatus"),
            "CompletedAt": row.get("CompletedAt"),
            "ShippingAddressLine1": row.get("ShippingAddressLine1"),
            "ShippingAddressLine2": row.get("ShippingAddressLine2"),
            "ShippingCity": row.get("ShippingCity"),
            "ShippingStateRegion": row.get("ShippingStateRegion"),
            "ShippingPostalCode": row.get("ShippingPostalCode"),
            "ShippingCountry": row.get("ShippingCountry"),
            "ShippingOfficeID": row.get("ShippingOfficeID"),
            "ShippingRecipientFirstName": row.get("ShippingRecipientFirstName"),
            "ShippingRecipientLastName": row.get("ShippingRecipientLastName"),
            "ShippingPhoneNumber": row.get("ShippingPhoneNumber"),

            "reason": "",
            "reason_notes": ""
        })

    product_trial_report_result = get_product_trial_report(
        round_id=int(round_data["RoundID"]),
    )

    workflow_state = _build_ut_lead_workflow_state(
        round_data=round_data,
        result_surveys=result_surveys,
        survey_stats=survey_stats,
        participants_data=participants_data,
        product_trial_report_result=product_trial_report_result,
        report_status=report_status,
    )
    current_workflow_key = workflow_state.get("current_key")
    workflow_tracker_html = _render_ut_lead_workflow_tracker(workflow_state)
    section_visibility = _build_ut_lead_section_visibility(
        round_data=round_data,
        result_surveys=result_surveys,
        survey_stats=survey_stats,
        participants_data=participants_data,
        product_trial_report_result=product_trial_report_result,
        workflow_state=workflow_state,
    )


    # =========================================================
    # PRODUCT IDENTITY SECTION
    # =========================================================

    product_identity_section = f"""
<details class="ut-lead-section product-identity-section" {_workflow_details_attrs("product_identity", current_workflow_key, open_for_key="project_details")}>
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
    <details class="ut-lead-section project-stakeholders-section" {_workflow_details_attrs("project_stakeholders", current_workflow_key, open_for_key="project_details")}>
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
            details_attrs=_workflow_details_attrs(
                "round_configuration",
                current_workflow_key,
                open_for_key="project_details",
            ),
        )
    else:
        round_config_section = _render_round_config_unlocked(
            round_data=round_data,
            country_options_html=country_options_html,
            details_attrs=_workflow_details_attrs(
                "round_configuration",
                current_workflow_key,
                open_for_key="project_details",
            ),
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
    <details class="ut-lead-section wanted-profile-section" {_workflow_details_attrs("profile", current_workflow_key)}>
        <summary class="ut-lead-section-summary">
            <strong>Wanted User Profile</strong>
            <span class="muted small">
                {"— Confirmed" if profile_locked else "— Editing"}
            </span>
        </summary>

        <div class="ut-lead-section-body">

            <div class="profile-rules-list">
    """

    # ---------------------------------
    # Existing Criteria Rows
    # ---------------------------------

    for c in criteria_rows:

        operator = (c.get("Operator") or "—").upper()
        operator_class = "include" if operator == "INCLUDE" else "exclude"

        wanted_profile_section += f"""
                <div class="profile-rule-row profile-rule-card">
                    <div class="profile-rule-operator profile-rule-operator-{e(operator_class)}">
                        {e(operator)}
                    </div>

                    <div class="profile-rule-main">
                        <div class="profile-rule-category">{e(c['CategoryName'])}</div>
                        <div class="profile-rule-description">{e(c['LevelDescription'])}</div>
                    </div>
        """

        if not profile_locked:
            wanted_profile_section += f"""
                    <div class="profile-rule-action">
                        <form method="post" action="/ut-lead/project">
                            <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                            <input type="hidden" name="criteria_id" value="{e(c['RoundCriteriaID'])}">
                            <button
                                class="profile-rule-remove-btn"
                                type="submit"
                                name="action"
                                value="delete_profile_criteria"
                                title="Remove this criterion"
                                aria-label="Remove {e(c['CategoryName'])} {e(c['LevelDescription'])} criterion"
                            >
                                ×
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

        wanted_profile_section += _render_profile_category_options(categories)

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
            <div class="profile-footer">
                <form method="post" action="/ut-lead/project">
                    <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                    {f'''
                    <button type="submit" name="action" value="unlock_profile">
                        Reopen Profile
                    </button>
                    ''' if profile_locked else f'''
                    <button type="submit" name="action" value="lock_profile">
                        Confirm Profile
                    </button>
                    '''}
                </form>
            </div>

        </div>
    </details>
    """

    # =========================================================
    # RECRUITING CONFIGURATION SECTION
    # =========================================================

    raw_value = round_data.get("UseExternalRecruitingSurvey")
    use_external = str(raw_value) == "1"

    recruiting_config_content_html = f"""
        <div class="survey-setup-config-card">
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
                    <span class="recruiting-toggle-copy">
                        <span class="recruiting-toggle-title">Require external recruiting survey before opening recruiting</span>
                        <span class="recruiting-toggle-help">Use this only when recruiting depends on a separate screening survey. Survey result links are configured below.</span>
                    </span>
                </label>
            </form>
        </div>
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
            <div class="ut-lead-project-hero">
                <div class="ut-lead-project-title-block">
                    <h1 class="ut-lead-project-title">{e(round_data.get("RoundName") or "Project Round")}</h1>
                </div>

                <div class="ut-lead-project-actions">
                    <a class="ut-lead-project-back-link" href="/ut-lead/trials">← Back to All Trials</a>
                </div>
            </div>

            {workflow_tracker_html}

            {_render_visibility_gated_section("product_identity", product_identity_section, section_visibility)}
            {_render_visibility_gated_section("project_stakeholders", project_stakeholders_section, section_visibility)}
            {_render_visibility_gated_section("round_configuration", round_config_section, section_visibility)}
            {constraints_section_html if ENABLE_CONSTRAINT_CAPTURE_UI else ""}
            {_render_visibility_gated_section("profile", wanted_profile_section, section_visibility)}
    """

    # Recruiting configuration is now part of the Survey & Recruiting Setup section.

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
    <details class="ut-lead-section wanted-profile-section" {_workflow_details_attrs("survey_links", current_workflow_key)}>
        <summary class="ut-lead-section-summary">
            <strong>Survey & Recruiting Setup</strong>
            <span class="muted small">
                {"— Confirmed" if planning_locked else "— Editing"}
            </span>
        </summary>
        <div class="ut-lead-section-body">
            {recruiting_config_content_html}
    """

    action_header = "" if planning_locked else "<th>Action</th>"

    links_section += f"""
        <table class="ut-lead-table">
            <thead>
                <tr>
                    <th>Survey Type</th>
                    <th>Internal Review Link</th>
                    <th>Participant Link</th>
                    <th>Audience</th>
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
                    Open review link
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
                    Open participant link
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

        <details class="survey-link-qsg">
            <summary>Need help formatting participant links?</summary>
            <div class="survey-link-qsg-body">
                <p>Participant links must include <code>user_token_here</code>. The system replaces that placeholder with each participant's unique token.</p>
                <ol>
                    <li>Open the Google Form you want participants to answer.</li>
                    <li>Use <strong>Pre-fill form</strong>.</li>
                    <li>Enter <code>user_token_here</code> in the user token field.</li>
                    <li>Click <strong>Get link</strong>.</li>
                    <li>Copy the generated URL and paste it into <strong>Participant Link</strong>.</li>
                </ol>
                <div class="survey-link-qsg-example">
                    Example ending: <code>...viewform?usp=pp_url&amp;entry.1711341715=user_token_here</code>
                </div>
            </div>
        </details>
    """

    # --------------------------------------------------
    # Lock / Locked Info
    # --------------------------------------------------

    if not planning_locked:

        links_section += f"""
            <form method="post" action="/ut-lead/project" style="margin-top:12px;">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">

                <button type="submit" name="action" value="lock_planning">
                    Confirm Survey Setup
                </button>
            </form>
        """

    else:

        links_section += f"""
            <div class="muted small" style="margin-top:10px;">
                Survey setup confirmed at {e(planning_locked_at)}
                by {e(planning_locked_display)}
            </div>
            <form method="post" action="/ut-lead/project" style="margin-top:12px;">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                <button type="submit" name="action" value="unlock_planning">
                    Reopen Survey Setup
                </button>
            </form>
        """

    links_section += """
        </div>
    </details>
    """

    # Append planning links to body
    body_html += _render_visibility_gated_section(
        "survey_links",
        links_section,
        section_visibility,
    )

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

    recruiting_section_html = f"""
        <details class="ut-lead-section wanted-profile-section" {_workflow_details_attrs("recruiting", current_workflow_key)}>
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

        recruiting_section_html += f"""
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

        recruiting_section_html += f"""
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
                                    {render_csv_dropzone(
                                        input_name="csv_file",
                                        input_id="recruiting_results_csv_file",
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

        recruiting_section_html += f"""
            <div class="overview-card recruiting-status-card">
                <div class="recruiting-date-grid">
                    <div class="recruiting-date-chip">
                        <div class="overview-label">Recruiting Started</div>
                        <div class="overview-value">{e(start_date or "—")}</div>
                    </div>

                    <div class="recruiting-date-chip">
                        <div class="overview-label">Recruiting Ended</div>
                        <div class="overview-value">{e(end_date or "—")}</div>
                    </div>
                </div>

                {controls_html}

            </div>
        """

    else:

        recruiting_section_html += """
            <div class="muted small">
                Survey setup must be confirmed before recruiting can open.
            </div>
        """

    recruiting_section_html += """
            </div>
        </details>
    """

    body_html += _render_visibility_gated_section(
        "recruiting",
        recruiting_section_html,
        section_visibility,
    )

    # Participants data was hydrated above for workflow, participants, and shipping.

    participant_survey_headers = ""

    for index, survey in enumerate(result_surveys, start=1):
        participant_label = f"Survey {index}"
        participant_survey_headers += f"""
                    <th class="participant-status-col">{e(participant_label)}</th>
                    <th class="participant-reminders-col">Reminders</th>
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
                    <td class="participant-status-cell">
                        <input type="checkbox"
                            name="survey_{e(survey.get('round_survey_id') or survey.get('survey_type_id') or 'unknown')}_{e(p['user_id'])}"
                            {checked_attr}
                            disabled>
                    </td>

                    <td class="participant-reminders-cell muted small">
                        {e(survey.get('reminders') or 0)}
                    </td>
                """

            participants_rows_html += f"""
                <tr data-nda-complete="{nda_complete}">
                    <td class="participant-name-cell">{e(p['name'])}</td>

                    <td class="participant-status-cell">{"✔" if p["nda_complete"] else "—"}</td>

                    {survey_cells_html}

                    <td class="participant-action-cell">
                        <select name="row_action_{e(p['user_id'])}">
                            <option value="">Select Action</option>
                            <option value="remove">Remove from Trial</option>
                            <option value="drop">Mark Dropped</option>
                        </select>
                    </td>

                    <td class="participant-reason-cell">
                        <select name="reason_{e(p['user_id'])}">
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
    <div class="participant-tracking-footer">
        <button type="submit" name="action" value="save_participants">
            Save Tracking Changes
        </button>
        <span class="muted small">
            Membership, NDA status, and survey completion come from the database. Actions/reasons are saved here.
        </span>
    </div>
    """

    participants_html = participants_template
    participants_html = participants_html.replace(
        "__PARTICIPANTS_DETAILS_ATTRS__",
        _workflow_details_attrs("participants", current_workflow_key),
    )
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

    survey_results_html = _render_dynamic_survey_results_sections(
        round_data=round_data,
        project_id=project_id,
        result_surveys=result_surveys,
        survey_stats=survey_stats,
        upload_status_for_survey=_survey_results_upload_status,
        upload_summary_for_survey=_survey_results_upload_summary,
        attribution_summary_for_survey=_persistent_attribution_summary,
        current_workflow_key=current_workflow_key,
    )

    # =========================================================
    # Shipping Section
    # =========================================================
    shipping_template = Path(
        "app/templates/ut_lead/ut_lead_project_shipping.html"
    ).read_text(encoding="utf-8")


    shipping_upload_status_html = ""
    if shipping_upload_status == "success":
        shipping_upload_status_html = f"""
            <div class="shipping-upload-status shipping-upload-status-success">
                <strong>Tracking upload complete.</strong>
                <span>
                    {e(_query_int("tracking_updated"))} updated /
                    {e(_query_int("tracking_rows"))} rows processed.
                    {e(_query_int("tracking_unmatched"))} unmatched,
                    {e(_query_int("tracking_missing_email"))} missing email,
                    {e(_query_int("tracking_ignored"))} ignored.
                </span>
            </div>
        """
    elif shipping_upload_status == "error":
        shipping_upload_status_html = """
            <div class="shipping-upload-status shipping-upload-status-error">
                <strong>Tracking upload failed.</strong>
                <span>Upload a CSV with at least Email and Tracking Number columns.</span>
            </div>
        """

    shipping_upload_html = f"""
        {shipping_upload_status_html}
        <form
            method="post"
            action="/ut-lead/project"
            enctype="multipart/form-data"
            class="shipping-tracking-upload-form"
        >
            <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
            <input type="hidden" name="action" value="upload_tracking_csv">
            <div class="shipping-tracking-upload-header">
                <div>
                    <div class="shipping-tracking-upload-title">Upload tracking CSV</div>
                    <div class="shipping-tracking-upload-help">Match rows by participant email. Accepted columns: Email, Courier, Tracking Number, Tracking URL, Shipped At, Delivered At.</div>
                </div>
            </div>
            {render_csv_dropzone(
                input_name="tracking_csv",
                input_id=f"tracking_csv_{int(round_data['RoundID'])}",
                label="Drop tracking CSV here or click to choose",
                help_text="CSV files only. Existing tracking values are preserved when matching CSV cells are blank.",
            )}
        </form>
    """

    shipping_table_html = """
    <table class="data-table shipping-table">
        <thead>
            <tr>
                <th>Participant</th>
                <th>Address</th>
                <th>Contact / Recipient</th>
                <th class="shipping-status-col">Confirmed</th>
                <th class="shipping-status-col">Shipped</th>
                <th class="shipping-status-col">Delivered</th>
            </tr>
        </thead>
        <tbody>
    """

    if participants_data:
        for p in participants_data:

            confirmed = bool(p.get("ShippingAddressConfirmedAt"))
            delivered = bool(p.get("DeliveredAt"))

            address_parts = [
                p.get("ShippingAddressLine1"),
                p.get("ShippingAddressLine2"),
                p.get("ShippingCity"),
                p.get("ShippingStateRegion"),
                p.get("ShippingPostalCode"),
                p.get("ShippingCountry"),
            ]
            address_display = ", ".join(
                str(part).strip()
                for part in address_parts
                if str(part or "").strip()
            ) or "—"

            participant_name = str(p.get("name") or "").strip()
            participant_email = str(p.get("email") or "").strip()
            recipient_name = " ".join(
                part
                for part in (
                    str(p.get("ShippingRecipientFirstName") or "").strip(),
                    str(p.get("ShippingRecipientLastName") or "").strip(),
                )
                if part
            )
            recipient_is_participant = (
                not recipient_name
                or recipient_name.lower() == participant_name.lower()
            )

            recipient_display = (
                "Participant recipient"
                if recipient_is_participant
                else f"Recipient: {e(recipient_name)}"
            )
            phone_display = e(p.get("ShippingPhoneNumber") or "—")

            tracking_number = str(p.get("TrackingNumber") or "").strip()
            courier = str(p.get("Courier") or "").strip()
            tracking_url = str(p.get("TrackingURL") or "").strip()
            shipped_display = "—"
            if tracking_number:
                tracking_label = e(f"{courier} {tracking_number}".strip())
                if tracking_url:
                    shipped_display = f'<a href="{e(tracking_url)}" target="_blank" rel="noopener noreferrer">{tracking_label}</a>'
                else:
                    shipped_display = tracking_label
            elif p.get("ShippedAt"):
                shipped_display = "✔"

            shipping_table_html += f"""
            <tr>
                <td>
                    <div class="shipping-participant-name">{e(participant_name)}</div>
                    <div class="shipping-participant-email">{e(participant_email) if participant_email else "—"}</div>
                </td>
                <td>{e(address_display)}</td>
                <td>
                    <div class="shipping-recipient-meta">{recipient_display}</div>
                    <div class="shipping-phone-meta">{phone_display}</div>
                </td>
                <td class="shipping-status-cell">{"✔" if confirmed else "—"}</td>
                <td class="shipping-status-cell shipping-tracking-cell">{shipped_display}</td>
                <td class="shipping-status-cell">{"✔" if delivered else "—"}</td>
            </tr>
            """
    else:
        shipping_table_html += """
            <tr>
                <td colspan="6" class="muted small">
                    No participants.
                </td>
            </tr>
        """

    shipping_table_html += """
        </tbody>
    </table>
    """


    shipping_html = shipping_template.replace(
        "__SHIPPING_DETAILS_ATTRS__",
        _workflow_details_attrs("shipping", current_workflow_key),
    )
    shipping_html = shipping_html.replace(
        "__SHIPPING_UPLOAD__",
        shipping_upload_html,
    )
    shipping_html = shipping_html.replace(
        "__SHIPPING_TABLE__",
        shipping_table_html
    )

    # =========================================================
    # TEMPLATE INJECTION (MISSING PIECE)
    # =========================================================

    sections_html = sections_template
    sections_html = sections_html.replace(
        "__PARTICIPANTS__",
        _render_visibility_gated_section(
            "participants",
            participants_html,
            section_visibility,
        ),
    )
    sections_html = sections_html.replace(
        "__SHIPPING__",
        _render_visibility_gated_section(
            "shipping",
            shipping_html,
            section_visibility,
        ),
    )
    sections_html = sections_html.replace(
        "__SURVEY_RESULTS__",
        _render_visibility_gated_section(
            "survey_results",
            survey_results_html,
            section_visibility,
        ),
    )

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

    section_visibility["product_readiness"] = (
        section_visibility["report"]
        or _has_product_kpi_data(product_kpis)
    )

    product_readiness_html = f"""
        <details class="ut-lead-section product-readiness-section">
            <summary class="ut-lead-section-summary">
                <strong>Product Readiness Snapshot</strong>
                <span class="muted small">— DB-derived Product KPI</span>
            </summary>

            <div class="ut-lead-section-body">
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
        </details>
    """

    body_html += _render_visibility_gated_section(
        "product_readiness",
        product_readiness_html,
        section_visibility,
    )

    body_html += _render_visibility_gated_section(
        "report",
        _render_product_trial_report_section(
            round_id=int(round_data["RoundID"]),
            report_status=report_status,
        ),
        section_visibility,
    )

    body_html += _render_ut_lead_project_autoscroll_script(workflow_state)

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


def _normalize_tracking_csv_header(value: str | None) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("#", " number ")
    text = " ".join(text.replace("_", " ").replace("-", " ").split())

    aliases = {
        "email": "email",
        "participant email": "email",
        "user email": "email",
        "recipient email": "email",
        "courier": "courier",
        "carrier": "courier",
        "shipping carrier": "courier",
        "tracking": "tracking_number",
        "tracking number": "tracking_number",
        "tracking no": "tracking_number",
        "tracking code": "tracking_number",
        "tracking id": "tracking_number",
        "tracking url": "tracking_url",
        "tracking link": "tracking_url",
        "shipping url": "tracking_url",
        "shipped": "shipped_at",
        "shipped at": "shipped_at",
        "shipped date": "shipped_at",
        "ship date": "shipped_at",
        "delivered": "delivered_at",
        "delivered at": "delivered_at",
        "delivered date": "delivered_at",
        "delivery date": "delivered_at",
    }

    return aliases.get(text, text.replace(" ", "_"))


def _parse_optional_tracking_datetime(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None

    normalized = text.replace("/", "-")
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m-%d-%Y",
        "%m-%d-%y",
    ):
        try:
            parsed = datetime.strptime(normalized, fmt)
            if fmt == "%Y-%m-%d":
                return parsed.strftime("%Y-%m-%d 00:00:00")
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    return None


def _parse_tracking_csv_rows(csv_bytes: bytes) -> list[dict]:
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(StringIO(text))

    if not reader.fieldnames:
        return []

    normalized_headers = {
        field_name: _normalize_tracking_csv_header(field_name)
        for field_name in reader.fieldnames
    }

    rows = []
    for raw_row in reader:
        normalized_row = {}
        for original_key, value in (raw_row or {}).items():
            normalized_key = normalized_headers.get(original_key)
            if not normalized_key:
                continue
            normalized_row[normalized_key] = str(value or "").strip()

        rows.append({
            "email": normalized_row.get("email", ""),
            "courier": normalized_row.get("courier", ""),
            "tracking_number": normalized_row.get("tracking_number", ""),
            "tracking_url": normalized_row.get("tracking_url", ""),
            "shipped_at": _parse_optional_tracking_datetime(normalized_row.get("shipped_at")),
            "delivered_at": _parse_optional_tracking_datetime(normalized_row.get("delivered_at")),
        })

    return rows


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
    # REOPEN OVERVIEW
    # --------------------------------------------------

    if action == "unlock_overview":

        from app.db.user_trial_lead import unlock_project_round_overview

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
    # CONFIRM PROFILE
    # --------------------------------------------------

    if action == "lock_profile":
        from app.db.user_trial_lead import lock_project_round_profile

        lock_project_round_profile(
            round_id=int(round_id),
            locked_by=user_id,
        )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # REOPEN PROFILE
    # --------------------------------------------------

    if action == "unlock_profile":
        if not round_data.get("ProfileLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        from app.db.user_trial_lead import unlock_project_round_profile

        unlock_project_round_profile(
            round_id=int(round_id),
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
    # CONFIRM Planning
    # --------------------------------------------------

    if action == "lock_planning":

        if round_data.get("PlanningLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        from app.db.user_trial_lead import lock_project_round_planning

        from app.db.project_rounds import set_project_round_status

        round_surveys = get_round_surveys(round_id)

        # --------------------------------------------------
        # MVP: No survey link enforcement
        # Planning can be confirmed regardless of survey setup
        # --------------------------------------------------

        # (intentionally no validation here)

        # --------------------------------------------------
        # Confirm planning
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
    # REOPEN Planning
    # --------------------------------------------------

    if action == "unlock_planning":

        if not round_data.get("PlanningLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        from app.db.user_trial_lead import unlock_project_round_planning

        unlock_project_round_planning(
            round_id=round_id,
        )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}


    # --------------------------------------------------
    # Upload Tracking CSV
    # --------------------------------------------------

    if action == "upload_tracking_csv":

        files = data.get("files") or {}
        tracking_csv = files.get("tracking_csv")
        shipping_anchor = "#shipping"

        if not tracking_csv:
            return {"redirect": f"/ut-lead/project?round_id={round_id}&shipping_upload=error{shipping_anchor}"}

        try:
            csv_bytes = tracking_csv.read()
            require_csv_upload(
                filename=getattr(tracking_csv, "filename", None) or "tracking.csv",
                file_bytes=csv_bytes,
            )
            tracking_rows = _parse_tracking_csv_rows(csv_bytes)
        except Exception:
            return {"redirect": f"/ut-lead/project?round_id={round_id}&shipping_upload=error{shipping_anchor}"}

        if not tracking_rows:
            return {"redirect": f"/ut-lead/project?round_id={round_id}&shipping_upload=error{shipping_anchor}"}

        from app.db.user_trial_lead import update_round_participant_tracking_from_rows

        try:
            tracking_summary = update_round_participant_tracking_from_rows(
                round_id=round_id,
                tracking_rows=tracking_rows,
            )
        except Exception:
            return {"redirect": f"/ut-lead/project?round_id={round_id}&shipping_upload=error{shipping_anchor}"}

        from urllib.parse import urlencode

        redirect_params = {
            "round_id": round_id,
            "shipping_upload": "success",
            "tracking_rows": tracking_summary.get("total_rows", 0),
            "tracking_updated": tracking_summary.get("updated_rows", 0),
            "tracking_unmatched": tracking_summary.get("unmatched_rows", 0),
            "tracking_missing_email": tracking_summary.get("missing_email_rows", 0),
            "tracking_ignored": tracking_summary.get("ignored_rows", 0),
        }

        return {
            "redirect": f"/ut-lead/project?{urlencode(redirect_params)}{shipping_anchor}"
        }


    # --------------------------------------------------
    # Upload Survey Results
    # --------------------------------------------------

    if action == "upload_survey_results":

        files = data.get("files") or {}
        csv_file = files.get("csv_file")

        project_id = round_data.get("ProjectID")
        survey_type_id = data.get("survey_type_id")
        round_survey_id = data.get("round_survey_id")
        report_anchor = "#product-trial-report"

        if not project_id or not survey_type_id or not csv_file:
            return {"redirect": f"/ut-lead/project?round_id={round_id}&upload=error{report_anchor}"}

        if round_survey_id:
            matched_configured_survey = None

            for survey in get_round_surveys(int(round_id)):
                current_round_survey_id = survey.get("RoundSurveyID") or survey.get("SurveyID")
                if str(current_round_survey_id or "") == str(round_survey_id):
                    matched_configured_survey = survey
                    break

            if not matched_configured_survey:
                return {"redirect": f"/ut-lead/project?round_id={round_id}&upload=error{report_anchor}"}

            if str(matched_configured_survey.get("SurveyTypeID") or "") != str(survey_type_id or ""):
                return {"redirect": f"/ut-lead/project?round_id={round_id}&upload=error{report_anchor}"}

        try:
            csv_bytes = csv_file.read()
            original_filename = getattr(csv_file, "filename", None)
            safe_filename = require_csv_upload(
                filename=original_filename or "survey_results.csv",
                file_bytes=csv_bytes,
            )
        except Exception:
            return {"redirect": f"/ut-lead/project?round_id={round_id}&upload=error{report_anchor}"}

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
                "redirect": f"/ut-lead/project?round_id={round_id}&upload=error{report_anchor}"
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
            "redirect": f"/ut-lead/project?{urlencode(redirect_params)}{report_anchor}"
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

        report_anchor = "#product-trial-report"

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
            return {"redirect": f"/ut-lead/project?round_id={round_id}&report=table_missing{report_anchor}"}
        except Exception:
            return {"redirect": f"/ut-lead/project?round_id={round_id}&report=error{report_anchor}"}

        if not report_result.get("success"):
            error_key = report_result.get("error") or "error"
            if error_key == "no_result_answers":
                return {"redirect": f"/ut-lead/project?round_id={round_id}&report=no_data{report_anchor}"}
            if error_key in {"not_found", "report_not_found"}:
                return {"redirect": f"/ut-lead/project?round_id={round_id}&report=not_generated{report_anchor}"}
            if error_key == "no_summaries_generated":
                return {"redirect": f"/ut-lead/project?round_id={round_id}&report=summaries_empty{report_anchor}"}
            return {"redirect": f"/ut-lead/project?round_id={round_id}&report=error{report_anchor}"}

        report_status = product_trial_report_actions[action]
        return {"redirect": f"/ut-lead/project?round_id={round_id}&report={report_status}{report_anchor}"}

    # --------------------------------------------------
    # Default Fallback (Critical)
    # --------------------------------------------------

    # If execution reaches here, no action matched.
    # Never fall through silently.
    return {"redirect": f"/ut-lead/project?round_id={round_id}"}