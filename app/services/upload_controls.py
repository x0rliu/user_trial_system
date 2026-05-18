# app/services/upload_controls.py

from app.utils.html_escape import escape_html as e


def render_csv_dropzone(
    *,
    input_name: str,
    input_id: str,
    label: str = "Drop CSV here or click to choose",
    required: bool = True,
    help_text: str = "CSV files only. Upload starts automatically when the form is ready.",
) -> str:
    required_attr = " required" if required else ""

    return f'''
    <label class="uts-upload-dropzone" for="{e(input_id)}">
        <input
            id="{e(input_id)}"
            class="uts-upload-dropzone-input"
            type="file"
            name="{e(input_name)}"
            accept=".csv,text/csv"
            data-upload-control="csv-dropzone"
            {required_attr}
        >
        <span class="uts-upload-dropzone-main">{e(label)}</span>
        <span class="uts-upload-dropzone-sub">{e(help_text)}</span>
        <span class="uts-upload-dropzone-file" aria-live="polite"></span>
    </label>
    '''