# app/handlers/bonus_survey_structure.py

from app.services.bonus_survey_structure_service import (
    ensure_structure_initialized,
    apply_ai_section_suggestions,
    build_structure_view_model,
)
from app.db.bonus_survey_question_structure import (
    get_bonus_survey_structure_summary,
    get_bonus_survey_structure_rows,
)
from app.utils.templates import render_template


def render_bonus_survey_structure_get(
    *,
    user_id: int,
    base_template: str,
    inject_nav,
    bonus_survey_id: int,
):
    from app.services.bonus_survey_structure_service import (
        ensure_structure_initialized,
    )
    from app.services.bonus_survey_sections_service import list_sections
    from app.db.bonus_survey_question_structure import (
        get_bonus_survey_structure_summary,
        get_bonus_survey_structure_rows,
    )
    from app.utils.html_escape import escape_html as e
    from app.utils.templates import render_template

    # --- ensure structure exists ---
    ensure_structure_initialized(bonus_survey_id=bonus_survey_id)

    # --- load data ---
    summary = get_bonus_survey_structure_summary(
        bonus_survey_id=bonus_survey_id
    )

    rows = get_bonus_survey_structure_rows(
        bonus_survey_id=bonus_survey_id
    )

    sections = list_sections(
        bonus_survey_id=bonus_survey_id
    )

    # -------------------------
    # BUILD SECTIONS UI
    # -------------------------
    sections_ui = ""

    for s in sections:
        sections_ui += f"""
        <div class="section-row">

            <strong>{e(s['display_name'])}</strong>

            <form method="POST" action="/surveys/bonus/section/rename" style="display:inline;">
                <input type="hidden" name="survey_id" value="{bonus_survey_id}">
                <input type="hidden" name="section_id" value="{s['section_id']}">
                <input type="text" name="display_name" placeholder="Rename">
                <button type="submit">Rename</button>
            </form>

            <form method="POST" action="/surveys/bonus/section/delete" style="display:inline;">
                <input type="hidden" name="survey_id" value="{bonus_survey_id}">
                <input type="hidden" name="section_id" value="{s['section_id']}">
                <button type="submit">Remove</button>
            </form>

        </div>
        """

    # -------------------------
    # BUILD SECTION OPTIONS (for BOTH bulk + per-row)
    # -------------------------
    section_options_html = ""

    for s in sections:
        section_options_html += f"""
            <option value="section:{s['section_key']}">
                {e(s['display_name'])}
            </option>
        """

    # -------------------------
    # BUILD QUESTION ROWS
    # -------------------------
    question_rows = ""

    for r in rows:
        q_text = r["question_text"]
        q_order = r["question_order"]

        q = f"{e(q_text)} <span class='muted'>(Q{q_order})</span>"
        sid = r["structure_id"]

        current = r["placement_type"]
        section_key = r.get("section_key") or ""

        # dynamic section options per row
        row_section_options = ""

        for s in sections:
            selected = "selected" if section_key == s["section_key"] else ""
            row_section_options += f"""
                <option value="section:{s['section_key']}" {selected}>
                    {e(s['display_name'])}
                </option>
            """

        question_rows += f"""
        <div class="question-row" style="display:flex; gap:10px; align-items:center;">

            <input type="checkbox" class="q-checkbox" data-sid="{sid}">

            <div style="flex:1;">{q}</div>

            <select name="assign_{sid}" class="q-select">
                <option value="unassigned" {"selected" if current == "unassigned" else ""}>Unassigned</option>
                <option value="profile" {"selected" if current == "profile" else ""}>Profile</option>
                <option value="ignored" {"selected" if current == "ignored" else ""}>Ignore</option>

                {row_section_options}
            </select>

        </div>
        """

    # -------------------------
    # DEBUG BLOCK
    # -------------------------
    debug_block = f"""
    <div class="content-card" style="background:#fff3cd;">
        <strong>Structure Status</strong><br>
        Total: {summary["total_questions"]} |
        Profile: {summary["profile_count"]} |
        Sections: {summary["section_count"]} |
        Unassigned: {summary["unassigned_count"]}
    </div>
    """

    # -------------------------
    # RENDER TEMPLATE
    # -------------------------
    html_body = render_template(
        "bonus_survey_structure.html",
        {
            "SECTIONS_UI": sections_ui,
            "QUESTION_ROWS": question_rows,
            "SECTION_OPTIONS": section_options_html,
            "BONUS_SURVEY_ID": str(bonus_survey_id),
        }
    )

    html_body = debug_block + html_body

    html = base_template.replace("__BODY__", html_body)
    html = inject_nav(html, user_id)

    return {
        "html": html
    }

def handle_bonus_survey_structure_generate_post(*, user_id: int, raw_body: str):
    from urllib.parse import parse_qs

    form = parse_qs(raw_body)
    bonus_survey_id = int(form.get("survey_id", [0])[0])

    from app.services.bonus_survey_structure_service import (
        apply_ai_section_suggestions,
    )
    from app.db.bonus_survey_question_structure import (
        get_bonus_survey_structure_rows,
    )

    rows = get_bonus_survey_structure_rows(
        bonus_survey_id=bonus_survey_id
    )

    payload = {
        "responses": [
            {
                "answers": [
                    {"question_text": r["question_text"]}
                    for r in rows
                ]
            }
        ]
    }

    apply_ai_section_suggestions(
        bonus_survey_id=bonus_survey_id,
        payload=payload,
    )

    return {
        "redirect": f"/surveys/bonus/structure?survey_id={bonus_survey_id}"
    }

def handle_bonus_survey_structure_reset_post(*, user_id: int, raw_body: str):
    from urllib.parse import parse_qs

    form = parse_qs(raw_body)
    bonus_survey_id = int(form.get("survey_id", [0])[0])

    from app.db.bonus_survey_question_structure import (
        reset_bonus_survey_structure_to_unassigned
    )

    reset_bonus_survey_structure_to_unassigned(
        bonus_survey_id=bonus_survey_id
    )

    return {
        "redirect": f"/surveys/bonus/structure?survey_id={bonus_survey_id}"
    }

def handle_bonus_survey_structure_classify_profile_post(*, user_id: int, raw_body: str):
    from urllib.parse import parse_qs

    form = parse_qs(raw_body)
    bonus_survey_id = int(form.get("survey_id", [0])[0])

    from app.db.bonus_survey_question_structure import (
        classify_profile_questions
    )

    classify_profile_questions(
        bonus_survey_id=bonus_survey_id
    )

    return {
        "redirect": f"/surveys/bonus/structure?survey_id={bonus_survey_id}"
    }

def handle_bonus_survey_structure_save_post(*, user_id: int, raw_body: str):
    """
    Handle bulk section assignment save.

    Expects form data structured as:
        survey_id=29
        assign_123=section:Navigation
        assign_124=profile
        assign_125=ignored
    """

    from urllib.parse import parse_qs
    from app.services.bonus_survey_structure_service import (
        save_bonus_survey_structure_assignments
    )

    form = parse_qs(raw_body)

    bonus_survey_id = int(form.get("survey_id", [0])[0])

    assignments = []

    for key, values in form.items():
        if not key.startswith("assign_"):
            continue

        try:
            structure_id = int(key.replace("assign_", ""))
        except ValueError:
            continue

        value = values[0]

        # -------------------------
        # Parse value
        # -------------------------
        if value.startswith("section:"):
            placement_type = "section"
            section_key = value.replace("section:", "").strip() or None

        elif value == "profile":
            placement_type = "profile"
            section_key = None

        elif value == "ignored":
            placement_type = "ignored"
            section_key = None

        else:
            placement_type = "unassigned"
            section_key = None

        assignments.append({
            "structure_id": structure_id,
            "placement_type": placement_type,
            "section_key": section_key,
        })

    # -------------------------
    # Persist via service
    # -------------------------
    save_bonus_survey_structure_assignments(
        bonus_survey_id=bonus_survey_id,
        assignments=assignments,
    )

    return {
        "redirect": f"/surveys/bonus/structure?survey_id={bonus_survey_id}"
    }

def handle_bonus_survey_section_add_post(*, user_id: int, raw_body: str):
    from urllib.parse import parse_qs
    from app.services.bonus_survey_sections_service import add_section

    form = parse_qs(raw_body)

    bonus_survey_id = int(form.get("survey_id", [0])[0])
    display_name = (form.get("display_name", [""])[0] or "").strip()

    if display_name:
        add_section(
            bonus_survey_id=bonus_survey_id,
            display_name=display_name,
        )

    return {
        "redirect": f"/surveys/bonus/structure?survey_id={bonus_survey_id}"
    }

def handle_bonus_survey_section_rename_post(*, user_id: int, raw_body: str):
    from urllib.parse import parse_qs
    from app.services.bonus_survey_sections_service import rename_section

    form = parse_qs(raw_body)

    bonus_survey_id = int(form.get("survey_id", [0])[0])
    section_id = int(form.get("section_id", [0])[0])
    display_name = (form.get("display_name", [""])[0] or "").strip()

    if section_id and display_name:
        rename_section(
            section_id=section_id,
            display_name=display_name,
        )

    return {
        "redirect": f"/surveys/bonus/structure?survey_id={bonus_survey_id}"
    }

def handle_bonus_survey_section_delete_post(*, user_id: int, raw_body: str):
    from urllib.parse import parse_qs
    from app.services.bonus_survey_sections_service import remove_section

    form = parse_qs(raw_body)

    bonus_survey_id = int(form.get("survey_id", [0])[0])
    section_id = int(form.get("section_id", [0])[0])

    if section_id:
        remove_section(
            bonus_survey_id=bonus_survey_id,
            section_id=section_id,
        )

    return {
        "redirect": f"/surveys/bonus/structure?survey_id={bonus_survey_id}"
    }