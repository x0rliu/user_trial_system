from typing import Dict, List, Set, Any


def build_section_summary(
    selected_uids: Set[str],
    definitions: List[Dict[str, Any]],
    section_config: Dict[str, Any],
    uid_field: str,
    label_field: str,
) -> Dict[str, Any]:

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
            [s.get(label_field) for s in selected if s.get(label_field)],
            key=lambda x: x or ""
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
    # demographics: Dict[str, Any],
    user_interest_uids: Set[str],
    interest_definitions: List[Dict[str, Any]],
    interest_sections: List[Dict[str, Any]],
    user_profile_uids: Set[str],
    profile_definitions: List[Dict[str, Any]],
    basic_sections: List[Dict[str, Any]],
    advanced_sections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Returns the complete profile summary structure in this order:

    1. Demographics
    2. Interests
    3. Basic Profile
    4. Advanced Profile
    """

    # --- Demographics ---
    # demographics_summary = build_demographics_summary(demographics)

    # --- Interests ---
    PRODUCT_TYPE_IDS = {
        "keyboard_details",
        "mouse_details",
        "headset_details",
        "earbuds_details",
        "speakers_details",
        "microphone_details",
        "webcam_details",
        "creator_gear",
    }

    summaries_by_id = {}

    # 1. Build ALL interest summaries normally (DB-truthful)
    for section in interest_sections:
        summaries_by_id[section["id"]] = build_section_summary(
            selected_uids=user_interest_uids,
            definitions=interest_definitions,
            section_config=section,
            uid_field="InterestUID",
            label_field="LevelName",
        )

    # 2. Collect product-type child sections
    product_type_children = [
        summaries_by_id[sid]
        for sid in PRODUCT_TYPE_IDS
        if sid in summaries_by_id and summaries_by_id[sid]["completed"] > 0
    ]

    # 3. Attach children to the real product_types section
    product_types_summary = summaries_by_id.get("product_types")
    if product_types_summary:
        product_types_summary["children"] = product_type_children

    # 4. Build final ordered list
    final_interest_summaries = []

    for section in interest_sections:
        sid = section["id"]

        if sid in PRODUCT_TYPE_IDS:
            continue  # nested

        if sid == "product_types":
            continue  # inserted manually

        final_interest_summaries.append(summaries_by_id[sid])

        if sid == "brands" and product_types_summary:
            final_interest_summaries.append(product_types_summary)

    # --- Basic Profile ---
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

    # --- Advanced Profile ---
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
        # "demographics": demographics_summary,
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
    Returns a single section summary using the unified engine.
    """

    return build_section_summary(
        selected_uids=user_profile_uids,
        definitions=profile_definitions,
        section_config=section_config,
        uid_field="ProfileUID",
        label_field="OptionLabel",
    )

def render_profile_summary_html(full_summary: dict) -> str:
    """
    Render the full profile summary (excluding demographics) as HTML.
    """

    html = []

    # -------------------------
    # Interests
    # -------------------------
    html.append("""
    <div class="profile-section-header-row">
        <h2 class="profile-section-header">Interests</h2>
    </div>
    """)

    for section in full_summary.get("interests", []):
        html.append(_render_summary_section(section))

    # -------------------------
    # Basic Profile
    # -------------------------
    html.append("""
    <div class="profile-section-header-row">
        <h2 class="profile-section-header">Basic Profile</h2>
    </div>
    """)

    for section in full_summary.get("basic_profile", []):
        html.append(_render_summary_section(section))

    # -------------------------
    # Advanced Profile
    # -------------------------
    html.append("""
    <div class="profile-section-header-row">
        <h2 class="profile-section-header">Advanced Profile</h2>
    </div>
    """)

    for section in full_summary.get("advanced_profile", []):
        html.append(_render_summary_section(section))

    return "\n".join(html)

def _render_summary_section(section: dict) -> str:
    """
    Render a single collapsible summary section.
    Supports child sections (e.g. Product Types).
    """

    html = []

    html.append(f"""
    <details class="profile-summary-collapsible">
        <summary>
            <span class="summary-title">
                {section["title"]} ({section["completed"]} / {section["total"]})
            </span>
        </summary>
    """)

    # Child sections (Product Types)
    if section.get("children"):
        for child in section["children"]:
            html.append(f"""
            <div class="summary-child-section">
                <div class="summary-child-title">
                    {child["title"]} ({child["completed"]} / {child["total"]})
                </div>
            """)

            for cat in child.get("categories", []):
                html.append(_render_summary_category(cat))

            html.append("</div>")

    # Normal sections
    else:
        for cat in section.get("categories", []):
            html.append(_render_summary_category(cat))

    if section.get("missing", 0) > 0:
        html.append(
            f"<p class='summary-missing'>{section['missing']} areas not specified</p>"
        )

    html.append("</details>")

    return "\n".join(html)

from typing import Dict, List, Set, Any


def build_section_summary(
    selected_uids: Set[str],
    definitions: List[Dict[str, Any]],
    section_config: Dict[str, Any],
    uid_field: str,
    label_field: str,
) -> Dict[str, Any]:

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
            [s.get(label_field) for s in selected if s.get(label_field)],
            key=lambda x: x or ""
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
    # demographics: Dict[str, Any],
    user_interest_uids: Set[str],
    interest_definitions: List[Dict[str, Any]],
    interest_sections: List[Dict[str, Any]],
    user_profile_uids: Set[str],
    profile_definitions: List[Dict[str, Any]],
    basic_sections: List[Dict[str, Any]],
    advanced_sections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Returns the complete profile summary structure in this order:

    1. Demographics
    2. Interests
    3. Basic Profile
    4. Advanced Profile
    """

    # --- Demographics ---
    # demographics_summary = build_demographics_summary(demographics)

    # --- Interests ---
    PRODUCT_TYPE_IDS = {
        "keyboard_details",
        "mouse_details",
        "headset_details",
        "earbuds_details",
        "speakers_details",
        "microphone_details",
        "webcam_details",
        "creator_gear",
    }

    summaries_by_id = {}

    # 1. Build ALL interest summaries normally (DB-truthful)
    for section in interest_sections:
        summaries_by_id[section["id"]] = build_section_summary(
            selected_uids=user_interest_uids,
            definitions=interest_definitions,
            section_config=section,
            uid_field="InterestUID",
            label_field="LevelName",
        )

    # 2. Collect product-type child sections
    product_type_children = [
        summaries_by_id[sid]
        for sid in PRODUCT_TYPE_IDS
        if sid in summaries_by_id and summaries_by_id[sid]["completed"] > 0
    ]

    # 3. Attach children to the real product_types section
    product_types_summary = summaries_by_id.get("product_types")
    if product_types_summary:
        product_types_summary["children"] = product_type_children

    # 4. Build final ordered list
    final_interest_summaries = []

    for section in interest_sections:
        sid = section["id"]

        if sid in PRODUCT_TYPE_IDS:
            continue  # nested

        if sid == "product_types":
            continue  # inserted manually

        final_interest_summaries.append(summaries_by_id[sid])

        if sid == "brands" and product_types_summary:
            final_interest_summaries.append(product_types_summary)

    # --- Basic Profile ---
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

    # --- Advanced Profile ---
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
        # "demographics": demographics_summary,
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
    Returns a single section summary using the unified engine.
    """

    return build_section_summary(
        selected_uids=user_profile_uids,
        definitions=profile_definitions,
        section_config=section_config,
        uid_field="ProfileUID",
        label_field="OptionLabel",
    )

def render_profile_summary_html(full_summary: dict) -> str:
    """
    Render the full profile summary (excluding demographics) as HTML.
    """

    html = []

    # -------------------------
    # Interests
    # -------------------------

    for section in full_summary.get("interests", []):
        html.append(_render_summary_section(section))

    # -------------------------
    # Basic Profile
    # -------------------------
    html.append("""
    <div class="profile-section-header-row">
        <h2 class="profile-section-header">Basic Profile</h2>
    </div>
    """)

    for section in full_summary.get("basic_profile", []):
        html.append(_render_summary_section(section))

    # -------------------------
    # Advanced Profile
    # -------------------------
    html.append("""
    <div class="profile-section-header-row">
        <h2 class="profile-section-header">Advanced Profile</h2>
    </div>
    """)

    for section in full_summary.get("advanced_profile", []):
        html.append(_render_summary_section(section))

    return "\n".join(html)

def _render_summary_section(section: dict) -> str:
    """
    Render a single collapsible summary section.
    Supports child sections (e.g. Product Types).
    """

    html = []

    html.append(f"""
    <details class="profile-summary-collapsible">
        <summary>
            <span class="summary-title">
                {section["title"]} ({section["completed"]} / {section["total"]})
            </span>
        </summary>
    """)

    # Child sections (Product Types)
    if section.get("children"):
        for child in section["children"]:
            html.append(f"""
            <div class="summary-child-section">
                <div class="summary-child-title">
                    {child["title"]} ({child["completed"]} / {child["total"]})
                </div>
            """)

            for cat in child.get("categories", []):
                html.append(_render_summary_category(cat))

            html.append("</div>")

    # Normal sections
    else:
        for cat in section.get("categories", []):
            html.append(_render_summary_category(cat))

    if section.get("missing", 0) > 0:
        html.append(
            f"<p class='summary-missing'>{section['missing']} areas not specified</p>"
        )

    html.append("</details>")

    return "\n".join(html)

def _render_summary_category(category):
    html = []

    html.append("<div class='summary-row'>")

    html.append(f"""
    <div class="summary-label">
        {category["category_name"]}
    </div>
    """)

    html.append("<div class='summary-chip-group'>")

    for value in category.get("values", []):
        html.append(f"<span class='summary-chip'>{value}</span>")

    html.append("</div>")
    html.append("</div>")

    return "\n".join(html)
