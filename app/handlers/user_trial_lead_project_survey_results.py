# app/handlers/user_trial_lead_project_survey_results.py

from app.utils.html_escape import escape_html as e


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
):
    upload_banner_html = _render_upload_status_banner(
        upload_status=upload_status,
        upload_summary=upload_summary,
    )

    body_html = f"""
    <div class="ut-lead-section-body">

        {upload_banner_html}

        <div class="survey-upload-bar">
            <form method="post"
                action="/ut-lead/project"
                enctype="multipart/form-data">

                <input type="hidden" name="action" value="upload_survey_results">
                <input type="hidden" name="project_id" value="{e(project_id)}">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                <input type="hidden" name="survey_type_id" value="{e(survey_type_id or '')}">

                <input type="file" name="csv_file" accept=".csv" required>
                <button type="submit">Upload</button>
            </form>
        </div>
    </div>
    """

    return body_html