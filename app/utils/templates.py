# app/utils/templates.py

from pathlib import Path

TEMPLATE_ROOT = Path("app/templates")

def render_template(template_name: str, context: dict | None = None) -> str:
    """
    Loads a template file and performs simple {{ key }} replacement.
    Returns rendered HTML string.
    """
    if context is None:
        context = {}

    template_path = TEMPLATE_ROOT / template_name
    html = template_path.read_text(encoding="utf-8")

    for key, value in context.items():
        html = html.replace(f"{{{{ {key} }}}}", str(value or ""))

    return html
