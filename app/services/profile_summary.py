# app/services/profile_summary.py

from typing import Any, Dict, List, Set

from app.utils.html_escape import escape_html as e


# ------------------------------------------------------------
# SHARED SECTION SUMMARY BUILDER
# ------------------------------------------------------------

def build_section_summary(
    selected_uids: Set[str],
    definitions: List[Dict[str, Any]],
    section_config: Dict[str, Any],
    uid_field: str,
    label_field: str,
) -> Dict[str, Any]:
    """
    Build a read-only summary for one profile/interest section.

    No DB writes.
    No hidden state.
    """

    section_categories = section_config["categories"]
    total = len(section_categories)

    categories = []
    completed = 0

    for category_id in section_categories:
        selected = [
            d for d in definitions
            if int(d.get("CategoryID")) == category_id
            and d.get(uid_field) in selected_uids
        ]

        if not selected:
            continue

        category_name = selected[0].get("CategoryName")
        if not category_name:
            continue

        values = sorted(
            [
                s.get(label_field)
                for s in selected
                if s.get(label_field)
            ],
            key=lambda x: x or "",
        )

        categories.append({
            "category_id": category_id,
            "category_name": category_name,
            "values": values,
        })

        completed += 1

    missing = total - completed

    return {
        "id": section_config["id"],
        "title": section_config["title"],
        "completed": completed,
        "total": total,
        "categories": categories,
        "missing": missing,
    }


# ------------------------------------------------------------
# DEMOGRAPHICS SUMMARY
# ------------------------------------------------------------

def build_demographics_summary(demographics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Demographics are identity-level data and are summarized differently.

    Kept for compatibility, even though the current profile summary page
    renders identity through render_identity_header().
    """

    items = []

    if demographics.get("first_name") or demographics.get("last_name"):
        items.append({
            "label": "Name",
            "value": f"{demographics.get('first_name', '')} {demographics.get('last_name', '')}".strip(),
        })

    if demographics.get("country"):
        items.append({
            "label": "Country / Region",
            "value": demographics["country"],
        })

    if demographics.get("gender"):
        items.append({
            "label": "Gender",
            "value": demographics["gender"],
        })

    if demographics.get("birth_year"):
        items.append({
            "label": "Year of Birth",
            "value": demographics["birth_year"],
        })

    return {
        "id": "demographics",
        "title": "Demographics",
        "items": items,
        "editable": True,
    }


# ------------------------------------------------------------
# FULL PROFILE SUMMARY BUILDER
# ------------------------------------------------------------

def build_full_profile_summary(
    *,
    user_interest_uids: Set[str],
    interest_definitions: List[Dict[str, Any]],
    interest_sections: List[Dict[str, Any]],
    user_profile_uids: Set[str],
    profile_definitions: List[Dict[str, Any]],
    basic_sections: List[Dict[str, Any]],
    advanced_sections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Returns the complete profile summary structure.

    Top-level groups:
    1. Interests
    2. Basic Profile
    3. Advanced Profile

    Product-type child sections are built as real summaries, but the renderer
    controls whether they appear nested or flattened.
    """

    product_type_ids = [
        "speakers_details",
        "earbuds_details",
        "headset_details",
        "mouse_details",
        "keyboard_details",
        "microphone_details",
        "webcam_details",
        "creator_gear",
    ]

    product_type_id_set = set(product_type_ids)

    summaries_by_id = {}

    # Build all interest summaries from DB-backed definitions.
    for section in interest_sections:
        summaries_by_id[section["id"]] = build_section_summary(
            selected_uids=user_interest_uids,
            definitions=interest_definitions,
            section_config=section,
            uid_field="InterestUID",
            label_field="LevelName",
        )

    product_type_children = [
        summaries_by_id[section_id]
        for section_id in product_type_ids
        if section_id in summaries_by_id
        and summaries_by_id[section_id]["completed"] > 0
    ]

    product_types_summary = summaries_by_id.get("product_types")
    if product_types_summary:
        product_types_summary["children"] = product_type_children

    final_interest_summaries = []

    for section in interest_sections:
        section_id = section["id"]

        # Product detail sections are represented through product_types.
        if section_id in product_type_id_set:
            continue

        if section_id == "product_types":
            final_interest_summaries.append(product_types_summary)
            continue

        final_interest_summaries.append(summaries_by_id[section_id])

    basic_profile_summaries = [
        build_section_summary(
            selected_uids=user_profile_uids,
            definitions=profile_definitions,
            section_config=section,
            uid_field="ProfileUID",
            label_field="OptionLabel",
        )
        for section in basic_sections
    ]

    advanced_profile_summaries = [
        build_section_summary(
            selected_uids=user_profile_uids,
            definitions=profile_definitions,
            section_config=section,
            uid_field="ProfileUID",
            label_field="OptionLabel",
        )
        for section in advanced_sections
    ]

    return {
        "interests": final_interest_summaries,
        "basic_profile": basic_profile_summaries,
        "advanced_profile": advanced_profile_summaries,
    }


def build_profile_section_summary(
    *,
    user_profile_uids: Set[str],
    profile_definitions: List[Dict[str, Any]],
    section_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Backward-compatible wrapper for legacy callers.
    """

    return build_section_summary(
        selected_uids=user_profile_uids,
        definitions=profile_definitions,
        section_config=section_config,
        uid_field="ProfileUID",
        label_field="OptionLabel",
    )


# ------------------------------------------------------------
# PROFILE SUMMARY HTML RENDERER
# ------------------------------------------------------------

def render_profile_summary_html(full_summary: dict) -> str:
    """
    Render the full profile summary as read-only HTML.

    Top level:
    - Interests
    - Basic Profile
    - Advanced Profile

    Second level:
    - Brand Interests
    - Product-specific sections such as Speakers, Earbuds, Mouse, Keyboard
    - Product Tiers
    - Mobility / Education Context
    """

    interests = _flatten_interest_summary_sections(
        full_summary.get("interests", [])
    )

    return "\n".join([
        _render_summary_group(
            group_id="profile-summary-interests",
            title="Interests",
            sections=interests,
            edit_href="/profile/interests",
        ),
        _render_summary_group(
            group_id="profile-summary-basic",
            title="Basic Profile",
            sections=full_summary.get("basic_profile", []),
            edit_href="/profile/basic",
        ),
        _render_summary_group(
            group_id="profile-summary-advanced",
            title="Advanced Profile",
            sections=full_summary.get("advanced_profile", []),
            edit_href="/profile/advanced",
        ),
    ])


def _flatten_interest_summary_sections(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Keep Interests as the top-level group.

    Do not show Product Types as one large second-level section.
    Instead, show each selected product detail section as its own second-level
    section.
    """

    product_child_order = {
        "speakers_details": 10,
        "earbuds_details": 20,
        "headset_details": 30,
        "mouse_details": 40,
        "keyboard_details": 50,
        "microphone_details": 60,
        "webcam_details": 70,
        "creator_gear": 80,
    }

    flattened = []

    for section in sections:
        section_id = section.get("id")

        if section_id == "product_types":
            children = sorted(
                section.get("children", []),
                key=lambda child: product_child_order.get(
                    child.get("id"),
                    999,
                ),
            )

            flattened.extend(children)
            continue

        flattened.append(section)

    return flattened


def _render_summary_group(
    *,
    group_id: str,
    title: str,
    sections: List[Dict[str, Any]],
    edit_href: str,
) -> str:
    completed, total = _summary_group_counts(sections)

    html = []

    html.append(f"""
    <details class="profile-summary-group" id="{e(group_id)}" open>
        <summary class="profile-summary-group-summary">
            <span class="profile-summary-arrow" aria-hidden="true">›</span>

            <span class="profile-summary-group-title">
                {e(title)}
            </span>

            <span class="profile-summary-group-count">
                {e(str(completed))} / {e(str(total))} areas answered
            </span>

            <a class="profile-summary-edit-link" href="{e(edit_href)}">
                Edit
            </a>
        </summary>

        <div class="profile-summary-group-body">
    """)

    if not sections:
        html.append("""
            <div class="profile-summary-empty">
                No profile sections are available yet.
            </div>
        """)

    for section in sections:
        html.append(
            _render_summary_subsection(
                section=section,
                edit_href=edit_href,
            )
        )

    html.append("""
        </div>
    </details>
    """)

    return "\n".join(html)


def _render_summary_subsection(
    *,
    section: Dict[str, Any],
    edit_href: str,
) -> str:
    section_title = section.get("title") or "Untitled Section"
    completed = _safe_int(section.get("completed"))
    total = _safe_int(section.get("total"))
    missing = _safe_int(section.get("missing"))

    html = []

    html.append(f"""
    <details class="profile-summary-subsection">
        <summary class="profile-summary-subsection-summary">
            <span class="profile-summary-arrow" aria-hidden="true">›</span>

            <span class="profile-summary-subsection-title">
                {e(section_title)}
            </span>

            <span class="profile-summary-subsection-count">
                {e(str(completed))} / {e(str(total))}
            </span>

            <a class="profile-summary-edit-link secondary" href="{e(edit_href)}">
                Edit
            </a>
        </summary>

        <div class="profile-summary-subsection-body">
    """)

    categories = section.get("categories", [])

    if categories:
        for category in categories:
            html.append(_render_summary_category(category))
    else:
        html.append("""
            <div class="profile-summary-empty">
                No selections saved for this area yet.
            </div>
        """)

    if missing > 0:
        area_label = "area" if missing == 1 else "areas"
        html.append(f"""
            <div class="profile-summary-missing">
                {e(str(missing))} {area_label} not specified.
            </div>
        """)

    html.append("""
        </div>
    </details>
    """)

    return "\n".join(html)


def _render_summary_category(category: Dict[str, Any]) -> str:
    category_name = category.get("category_name") or "Category"
    values = category.get("values", [])

    html = []

    html.append(f"""
    <div class="profile-summary-item">
        <div class="profile-summary-item-label">
            {e(category_name)}
        </div>

        <div class="profile-summary-chip-list">
    """)

    if values:
        for value in values:
            html.append(f"""
                <span class="profile-summary-chip">
                    {e(value)}
                </span>
            """)
    else:
        html.append("""
            <span class="profile-summary-empty-chip">
                Not specified
            </span>
        """)

    html.append("""
        </div>
    </div>
    """)

    return "\n".join(html)


def _summary_group_counts(sections: List[Dict[str, Any]]) -> tuple[int, int]:
    completed = 0
    total = 0

    for section in sections:
        completed += _safe_int(section.get("completed"))
        total += _safe_int(section.get("total"))

    return completed, total


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0