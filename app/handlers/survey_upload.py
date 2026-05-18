# app/handlers/survey_upload.py

from app.services.survey_ingest import ingest_google_form_csv
from app.utils.csrf import generate_csrf_token
from app.utils.html_escape import escape_html as e
from app.utils.upload_security import require_csv_upload
from app.services.upload_controls import render_csv_dropzone

# -------------------------
# GET
# -------------------------
def render_survey_upload_get(*, user_id, base_template, inject_nav):

    csrf_token = generate_csrf_token(user_id)

    body = f"""
    <h2>Survey Upload</h2>

    <form method="POST" enctype="multipart/form-data">
        <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
        <p>Upload legacy survey CSV.</p>
        <p>Survey type will be inferred from filename.</p>

        {render_csv_dropzone(
            input_name="file",
            input_id="legacy_survey_csv_file",
            label="Drop legacy survey CSV here or click to choose",
        )}
    </form>
    """

    html = base_template
    html = inject_nav(html)
    html = html.replace("{{ title }}", "Survey Upload")
    html = html.replace("__BODY__", body)

    return {"html": html}


# -------------------------
# POST
# -------------------------
def handle_survey_upload_post(*, user_id, data):

    files = data.get("files", {})
    file_obj = files.get("file")

    if not file_obj:
        return {"error": "No file uploaded"}

    # -------------------------
    # Extract file + validate upload
    # -------------------------
    filename = getattr(file_obj, "filename", "unknown.csv")
    file_bytes = file_obj.read()

    try:
        filename = require_csv_upload(
            filename=filename,
            file_bytes=file_bytes,
        )
    except ValueError:
        return {"redirect": "/survey/upload?error=invalid_file"}

    # Example:
    # "g502_round1_survey1.csv"
    # "MX Master 3S - Survey 2.csv"

    def infer_survey_type(name: str) -> str:
        name = name.lower()

        if "recruit" in name:
            return "recruiting"
        if "oobe" in name or "first" in name:
            return "survey_1"
        if "experience" in name or "kpi" in name:
            return "survey_2"

        return "unknown"

    survey_type = infer_survey_type(filename)

    project_id = None
    round_id = None

    # -------------------------
    # Save temp file
    # -------------------------
    import os
    import uuid

    upload_dir = "app/dev_data/uploads"
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, f"{uuid.uuid4()}.csv")

    with open(filepath, "wb") as f:
        f.write(file_bytes)

    # -------------------------
    # Call ingestion service
    # -------------------------
    try:
        ingest_google_form_csv(
            filepath=filepath,
            survey_type=survey_type,
            source_filename=filename,
        )
    except Exception:
        return {"redirect": "/survey/upload?error=ingest_failed"}

    return {"redirect": "/survey/upload?success=1"}