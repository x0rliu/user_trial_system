# app/handlers/user_trial_lead_project_survey_results.py

from app.utils.html_escape import escape_html as e
from app.services.upload_controls import render_csv_dropzone


def _render_upload_status_banner(*, upload_status, upload_summary=None) -> str:
    if upload_status == "error":
        return """
        <div style="margin-bottom:10px;padding:10px;background:#fff2f0;border:1px solid #ffccc7;">
            Upload failed.
        </div>
        """

    if upload_status != "success":
        return ""

    summary = upload_summary or {}

    def _count(name: str) -> int:
        try:
            return max(0, int(summary.get(name) or 0))
        except (TypeError, ValueError):
            return 0

    total_rows = _count("total_rows")
    token_rows = _count("token_rows")
    email_rows = _count("email_rows")
    anonymous_rows = _count("anonymous_rows")
    unmatched_rows = _count("unmatched_rows")
    review_rows = _count("review_rows")
    ignored_rows = _count("ignored_rows")
    inserted_answers = _count("inserted_answers")

    if not summary:
        return """
        <div style="margin-bottom:10px;padding:10px;background:#e6ffed;border:1px solid #b7eb8f;">
            Successfully uploaded file.
        </div>
        """

    return f"""
    <div style="margin-bottom:10px;padding:12px;background:#e6ffed;border:1px solid #b7eb8f;border-radius:8px;">
        <div style="font-weight:700;margin-bottom:6px;">
            Survey results upload processed.
        </div>

        <div class="muted" style="margin-bottom:10px;">
            Feedback-first ingestion completed for result surveys. Identity attribution is tracked separately
            from whether feedback is included in analysis.
        </div>

        <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 16px;font-size:13px;">
            <div><strong>Responses analyzed:</strong> {total_rows}</div>
            <div><strong>Answers inserted:</strong> {inserted_answers}</div>
            <div><strong>Matched by token:</strong> {token_rows}</div>
            <div><strong>Matched by email:</strong> {email_rows}</div>
            <div><strong>Anonymous:</strong> {anonymous_rows}</div>
            <div><strong>Unmatched:</strong> {unmatched_rows}</div>
            <div><strong>Needs review:</strong> {review_rows}</div>
            <div><strong>Ignored rows:</strong> {ignored_rows}</div>
        </div>
    </div>
    """


def _render_persistent_attribution_summary(*, attribution_summary=None) -> str:
    summary = attribution_summary or {}

    def _count(name: str) -> int:
        try:
            return max(0, int(summary.get(name) or 0))
        except (TypeError, ValueError):
            return 0

    responses_analyzed = _count("responses_analyzed")
    if responses_analyzed <= 0:
        return ""

    matched_by_token = _count("matched_by_token")
    matched_by_email = _count("matched_by_email")
    anonymous = _count("anonymous")
    unmatched = _count("unmatched")
    needs_review = _count("needs_review")
    total_answers = _count("total_answers")

    return f"""
    <div style="margin-bottom:10px;padding:12px;background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;">
        <div style="font-weight:700;margin-bottom:6px;">
            Response Attribution
        </div>

        <div class="muted" style="margin-bottom:10px;">
            Persistent attribution summary for stored result responses.
        </div>

        <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 16px;font-size:13px;">
            <div><strong>Responses analyzed:</strong> {responses_analyzed}</div>
            <div><strong>Answers stored:</strong> {total_answers}</div>
            <div><strong>Matched by token:</strong> {matched_by_token}</div>
            <div><strong>Matched by email:</strong> {matched_by_email}</div>
            <div><strong>Anonymous:</strong> {anonymous}</div>
            <div><strong>Unmatched:</strong> {unmatched}</div>
            <div><strong>Needs review:</strong> {needs_review}</div>
        </div>
    </div>
    """


def render_survey_results_section(
    *,
    round_data,
    survey_stats,
    upload_status,
    project_id,
    section_title,
    section_subtitle,
    survey_type_id,
    upload_summary=None,
    attribution_summary=None,
):
    upload_banner_html = _render_upload_status_banner(
        upload_status=upload_status,
        upload_summary=upload_summary,
    )
    attribution_summary_html = _render_persistent_attribution_summary(
        attribution_summary=attribution_summary,
    )

    body_html = f"""
    <div class="ut-lead-section-body">

        {upload_banner_html}
        {attribution_summary_html}

        <div class="survey-upload-bar">
            <form method="post"
                action="/ut-lead/project"
                enctype="multipart/form-data">

                <input type="hidden" name="action" value="upload_survey_results">
                <input type="hidden" name="project_id" value="{e(project_id)}">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                <input type="hidden" name="survey_type_id" value="{e(survey_type_id or '')}">

                {render_csv_dropzone(
                    input_name="csv_file",
                    input_id="ut_lead_survey_results_csv_file",
                    label="Drop survey results CSV here or click to choose",
                )}
            </form>
        </div>
    </div>
    """

    return body_html