# app/handlers/user_trial_lead_project_survey_results.py
from app.db.survey_recruiting_kpis import get_recruiting_kpis

def render_survey_results_section(
    *,
    round_data,
    survey_stats,
    upload_status,
    project_id,
):
    body_html = f"""
    <details class="ut-lead-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Survey Results</strong>
            <span class="muted small"> — Step 1–2 (Basic Metrics)</span>
        </summary>

        <div class="ut-lead-section-body">

            {"<div style='margin-bottom:10px;padding:10px;background:#e6ffed;border:1px solid #b7eb8f;'>Successfully uploaded file.</div>" if upload_status == "success" else ""}

            {"<div style='margin-bottom:10px;padding:10px;background:#fff2f0;border:1px solid #ffccc7;'>Upload failed.</div>" if upload_status == "error" else ""}

            <div class="survey-upload-bar">
                <form method="post"
                    action="/ut-lead/project"
                    enctype="multipart/form-data">

                    <input type="hidden" name="action" value="upload_survey_results">
                    <input type="hidden" name="project_id" value="{project_id}">
                    <input type="hidden" name="round_id" value="{round_data['RoundID']}">
                    <input type="hidden" name="survey_type_id" value="{round_data.get('DefaultSurveyTypeID') or 'UTSurveyType0001'}">

                    <input type="file" name="csv_file" accept=".csv" required>
                    <button type="submit">Upload</button>
                </form>
            </div>
    """

    body_html += """
        </div>
    </details>
    """

    return body_html