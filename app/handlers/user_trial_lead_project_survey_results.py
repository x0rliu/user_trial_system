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


def _mask_source_value(value, *, visible_tail: int = 6) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "—"

    if len(raw) <= visible_tail:
        return raw

    return f"…{raw[-visible_tail:]}"


def render_survey_attribution_review_panel(
    *,
    review_rows=None,
    title: str = "Attribution Review",
) -> str:
    rows = review_rows or []
    if not rows:
        return ""

    row_html = ""

    for row in rows:
        source_email = row.get("SourceEmail") or "—"
        source_token = _mask_source_value(row.get("SourceToken"))
        match_method = row.get("MatchMethod") or "—"
        match_confidence = row.get("MatchConfidence") or "—"
        user_id = row.get("user_id") or "Unlinked"
        match_notes = row.get("MatchNotes") or "Needs review"

        row_html += f"""
        <tr>
            <td>{e(source_email)}</td>
            <td>{e(source_token)}</td>
            <td>{e(match_method)}</td>
            <td>{e(match_confidence)}</td>
            <td>{e(user_id)}</td>
            <td>{e(match_notes)}</td>
        </tr>
        """

    return f"""
    <div style="margin-bottom:10px;padding:12px;background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;">
        <div style="font-weight:700;margin-bottom:6px;">
            {e(title)}
        </div>

        <div class="muted" style="margin-bottom:10px;">
            These uploaded responses were stored, but identity attribution needs review before they should be trusted for workflow decisions.
        </div>

        <div style="overflow-x:auto;">
            <table class="mini-table" style="width:100%;font-size:13px;">
                <thead>
                    <tr>
                        <th>Source Email</th>
                        <th>Token</th>
                        <th>Match</th>
                        <th>Confidence</th>
                        <th>User</th>
                        <th>Notes</th>
                    </tr>
                </thead>
                <tbody>
                    {row_html}
                </tbody>
            </table>
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
    round_survey_id=None,
    upload_summary=None,
    attribution_summary=None,
    review_rows=None,
):
    upload_banner_html = _render_upload_status_banner(
        upload_status=upload_status,
        upload_summary=upload_summary,
    )
    attribution_summary_html = _render_persistent_attribution_summary(
        attribution_summary=attribution_summary,
    )
    review_panel_html = render_survey_attribution_review_panel(
        review_rows=review_rows,
        title="Survey Attribution Review",
    )

    body_html = f"""
    <div class="ut-lead-section-body">

        {upload_banner_html}
        {attribution_summary_html}
        {review_panel_html}

        <div class="survey-upload-bar">
            <form method="post"
                action="/ut-lead/project"
                enctype="multipart/form-data">

                <input type="hidden" name="action" value="upload_survey_results">
                <input type="hidden" name="project_id" value="{e(project_id)}">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                <input type="hidden" name="survey_type_id" value="{e(survey_type_id or '')}">
                <input type="hidden" name="round_survey_id" value="{e(round_survey_id or '')}">

                {render_csv_dropzone(
                    input_name="csv_file",
                    input_id=f"ut_lead_survey_results_csv_file_{round_survey_id or survey_type_id or 'unknown'}",
                    label="Drop survey results CSV here or click to choose",
                )}
            </form>
        </div>
    </div>
    """

    return body_html