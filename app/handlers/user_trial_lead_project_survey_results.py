# app/handlers/user_trial_lead_project_survey_results.py

def render_survey_results_section(
    *,
    round_data,
    survey_stats,
    upload_status,
    project_id,
    section_title,
    section_subtitle,
    survey_type_id,
):
    body_html = f"""
    <details class="ut-lead-section" open>
        <summary class="ut-lead-section-summary">
            <strong>{section_title}</strong>
            <span class="muted small"> — {section_subtitle}</span>
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
                    <input type="hidden" name="survey_type_id" value="{survey_type_id or ''}">

                    <input type="file" name="csv_file" accept=".csv" required>
                    <button type="submit">Upload</button>
                </form>
            </div>
        </div>
    </details>
    """

    return body_html