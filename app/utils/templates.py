# app/utils/templates.py

from pathlib import Path

TEMPLATE_ROOT = Path("app/templates")

def render_template(template_name: str, context: dict | None = None) -> str:
    """
    Loads a template file and performs simple replacement.

    Supports BOTH:
    - {{ key }}   (legacy)
    - __KEY__     (new standard)
    """
    if context is None:
        context = {}

    template_path = TEMPLATE_ROOT / template_name
    html = template_path.read_text(encoding="utf-8")

    for key, value in context.items():
        val = str(value or "")

        # Legacy support
        html = html.replace(f"{{{{ {key} }}}}", val)

        # New standard
        html = html.replace(f"__{key}__", val)

    return html