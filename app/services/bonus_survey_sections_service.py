# app/services/bonus_survey_sections_service.py

from typing import List, Dict
import re

from app.db.bonus_survey_sections import (
    get_bonus_survey_sections,
    create_bonus_survey_section,
    update_bonus_survey_section_name,
    delete_bonus_survey_section,
)
from app.db.bonus_survey_question_structure import (
    get_bonus_survey_structure_rows,
    update_bonus_survey_question_placement_batch,
)


# -------------------------
# helpers
# -------------------------
def _slugify(name: str) -> str:
    """
    Convert display name to section_key (snake_case).
    """
    name = (name or "").strip().lower()
    # replace non-alnum with space, then collapse to underscores
    name = re.sub(r"[^a-z0-9]+", " ", name)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name or "section"


def _ensure_unique_key(existing_keys: set, base_key: str) -> str:
    """
    Ensure section_key uniqueness within a survey.
    """
    if base_key not in existing_keys:
        return base_key

    i = 2
    while f"{base_key}_{i}" in existing_keys:
        i += 1
    return f"{base_key}_{i}"


# -------------------------
# GET (pass-through)
# -------------------------
def list_sections(*, bonus_survey_id: int) -> List[Dict]:
    return get_bonus_survey_sections(bonus_survey_id=bonus_survey_id)


# -------------------------
# CREATE
# -------------------------
def add_section(*, bonus_survey_id: int, display_name: str) -> None:
    """
    Create a new section with unique section_key.
    """
    display_name = (display_name or "").strip()
    if not display_name:
        return

    existing = get_bonus_survey_sections(bonus_survey_id=bonus_survey_id)
    existing_keys = {s["section_key"] for s in existing}

    base_key = _slugify(display_name)
    section_key = _ensure_unique_key(existing_keys, base_key)

    create_bonus_survey_section(
        bonus_survey_id=bonus_survey_id,
        section_key=section_key,
        display_name=display_name,
    )


# -------------------------
# RENAME
# -------------------------
def rename_section(*, section_id: int, display_name: str) -> None:
    """
    Rename display only (keep section_key stable).
    """
    display_name = (display_name or "").strip()
    if not display_name:
        return

    update_bonus_survey_section_name(
        section_id=section_id,
        display_name=display_name,
    )


# -------------------------
# DELETE (safe)
# -------------------------
def remove_section(*, bonus_survey_id: int, section_id: int) -> None:
    """
    Delete section and move its questions → unassigned.
    """

    # 1) find the section_key
    sections = get_bonus_survey_sections(bonus_survey_id=bonus_survey_id)
    target = next((s for s in sections if s["section_id"] == section_id), None)
    if not target:
        return

    section_key = target["section_key"]

    # 2) load all rows
    rows = get_bonus_survey_structure_rows(
        bonus_survey_id=bonus_survey_id
    )

    # 3) collect affected questions
    updates = []
    for r in rows:
        if r["placement_type"] == "section" and (r.get("section_key") == section_key):
            updates.append({
                "structure_id": r["structure_id"],
                "placement_type": "unassigned",
                "section_key": None,
                "section_order": 0,
                "question_order": 0,
            })

    # 4) persist question updates first
    if updates:
        update_bonus_survey_question_placement_batch(
            bonus_survey_id=bonus_survey_id,
            updates=updates,
        )

    # 5) delete section
    delete_bonus_survey_section(section_id=section_id)