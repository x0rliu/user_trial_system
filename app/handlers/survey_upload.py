from app.services.survey_ingest import ingest_google_form_csv


# -------------------------
# GET
# -------------------------
def render_survey_upload_get(*, user_id, base_template, inject_nav):

    body = """
    <h2>Survey Upload</h2>

    <form method="POST" enctype="multipart/form-data">
        <p>Upload legacy survey CSV.</p>
        <p>Survey type will be inferred from filename.</p>

        <input type="file" name="file" accept=".csv" required><br><br>

        <button type="submit">Upload & Ingest</button>
    </form>
    """

    html = base_template
    html = inject_nav(html)
    html = html.replace("{{ title }}", "Survey Upload")
    html = html.replace("{{ body }}", body)

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
    # Extract file + infer metadata
    # -------------------------
    filename = getattr(file_obj, "filename", "unknown.csv")

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
        f.write(file_obj.read())

    # -------------------------
    # Call ingestion service
    # -------------------------
    ingest_google_form_csv(
        filepath=filepath,
        survey_type=survey_type,
        source_filename=filename,
    )

    return {"redirect": "/survey/upload?success=1"}