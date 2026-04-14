# app/handlers/settings.py

from pathlib import Path
from app.db.user_pool import get_user_by_userid
# from app.services.demographics import update_demographics
from app.utils.response import json_response

# --------------------------------------------------
# SETTINGS ROUTE DISPATCHER
# --------------------------------------------------
# This file only defines handlers.
# main.py is responsible for routing to these functions.
# --------------------------------------------------


# --------------------------------------------------
# SETTINGS DEMOGRAPHICS EDITOR
# --------------------------------------------------

# app/handlers/settings.py

DEMOGRAPHICS_TEMPLATE = Path("app/templates/settings/edit_demographics.html")
SETTINGS_TEMPLATE = Path("app/templates/settings.html")

def render_settings_get(*, user_id: str, base_template: str, inject_nav):
    """
    Full Settings page shell.
    Fragment panels are loaded client-side via JS.
    """

    body_html = SETTINGS_TEMPLATE.read_text(encoding="utf-8")

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Settings")
    html = html.replace("{{ body }}", body_html)

    return {"html": html}