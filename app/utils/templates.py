# app/utils/templates.py

from pathlib import Path

TEMPLATE_ROOT = Path("app/templates")


def _template_value_to_string(value) -> str:
    """
    Converts a context value to a template-safe replacement string.

    Important:
    - None becomes ""
    - 0 stays "0"
    - False stays "False"

    Do not use `value or ""` here because falsey values can be meaningful.
    """
    if value is None:
        return ""

    return str(value)


def _build_context(
    context: dict | None = None,
    extra_context: dict | None = None,
) -> dict:
    """
    Normalizes template context into a single dictionary.

    This keeps render_template() compatible with the existing dict-based calls
    while also allowing explicit keyword-style context where needed.
    """
    merged = {}

    if context is not None:
        if not isinstance(context, dict):
            raise TypeError("render_template context must be a dict or None")

        merged.update(context)

    if extra_context:
        merged.update(extra_context)

    return merged


def render_template(
    template_name: str,
    context: dict | None = None,
    **extra_context,
) -> str:
    """
    Loads a template file and performs explicit token replacement.

    Supports BOTH:
    - {{ key }}   legacy tokens
    - __KEY__     current standard tokens

    New or modified templates should use __KEY__ anchors exclusively.

    Escaping rule:
    This renderer does not automatically escape values.

    Callers must pass already-escaped text for user/database values, or pass
    intentionally safe HTML fragments when the template slot is meant to render
    HTML.
    """
    values = _build_context(
        context=context,
        extra_context=extra_context,
    )

    template_path = TEMPLATE_ROOT / template_name
    html = template_path.read_text(encoding="utf-8")

    for key, value in values.items():
        val = _template_value_to_string(value)

        # Legacy support
        html = html.replace(f"{{{{ {key} }}}}", val)

        # Current standard
        html = html.replace(f"__{key}__", val)

    return html