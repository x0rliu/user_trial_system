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


def render_demographics_form(user_id: str) -> str:
    """
    Returns demographics form HTML populated with user data.
    No redirects. No onboarding logic.
    """
    user = get_user_by_userid(user_id)
    if not user:
        return "<p>Unable to load demographics.</p>"

    gender = (user.get("Gender") or "").strip()

    options = [
        ("", "—"),
        ("female", "Female"),
        ("male", "Male"),
        ("non_binary", "Non-binary"),
        ("prefer_not_to_say", "Prefer not to say"),
    ]

    option_html = []
    for value, label in options:
        selected = " selected" if value == gender else ""
        option_html.append(
            f'<option value="{value}"{selected}>{label}</option>'
        )

    html = DEMOGRAPHICS_TEMPLATE.read_text(encoding="utf-8")

    # Strip onboarding-only chrome if needed later
    html = html.replace("__ERROR_BLOCK__", "")

    def inject_value(html, field, value):
        return html.replace(
            f'name="{field}"',
            f'name="{field}" value="{value or ""}"'
        )

    html = inject_value(html, "first_name", user.get("FirstName"))
    html = inject_value(html, "last_name", user.get("LastName"))
    html = inject_value(html, "phone_number", user.get("PhoneNumber"))
    html = inject_value(html, "birth_year", user.get("BirthYear"))
    html = inject_value(html, "country", user.get("Country"))
    html = inject_value(html, "city", user.get("City"))
    html = html.replace("__GENDER_OPTIONS__", "\n".join(option_html))

    return html

def save_demographics_inline(user_id: str, data: dict):
    from app.db.user_pool import update_user_demographics

    birth_year = data.get("birth_year")
    birth_year = int(birth_year) if birth_year else None

    # ---- guardrail: sanity check ----
    assert birth_year is None or 1900 <= birth_year <= 2025, (
        f"Invalid birth_year: {birth_year}"
    )

    # ---- mobile number normalization ----
    mobile_country_code = data.get("mobile_country_code")
    mobile_national = data.get("mobile_national")

    mobile_e164 = None
    if mobile_country_code and mobile_national:
        mobile_national = "".join(c for c in mobile_national if c.isdigit())
        mobile_e164 = f"{mobile_country_code}{mobile_national}"

    try:
        update_user_demographics(
            user_id=user_id,
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            gender=data.get("gender"),
            birth_year=birth_year,
            country=data.get("country"),
            city=data.get("city"),
            mobile_country_code=mobile_country_code,
            mobile_national=mobile_national,
            mobile_e164=mobile_e164,
        )

    except Exception as e:
        return json_response(
            {"ok": False, "error": str(e)},
            status=400
        )

    return json_response({"ok": True})

# --------------------------------------------------
# Settings: Interests fragment renderer
# --------------------------------------------------

def render_interests_form(user_id: str) -> str:
    from pathlib import Path
    from app.config.profile_layout import INTEREST_PROFILE_SECTIONS
    from app.db.user_interests import get_interests_by_category_ids
    from app.db.user_interest_map import get_user_interest_uids

    # --- fetch existing interest selections
    user_interest_uids = {
        row["InterestUID"]
        for row in get_user_interest_uids(user_id)
    }

    sections = []

    for section_def in INTEREST_PROFILE_SECTIONS:
        section = {
            "section_id": section_def["id"],
            "title": section_def["title"],
            "description": section_def.get("description"),
            "collapsible": section_def.get("collapsible", False),
            "parent_product_type": section_def.get("parent_product_type"),
            "categories": [],
        }

        category_ids = section_def.get("categories", [])
        interest_rows = get_interests_by_category_ids(category_ids)

        # --- group by category
        interests_by_category = {}
        for row in interest_rows:
            interests_by_category.setdefault(row["CategoryID"], []).append(row)

        for category_id in category_ids:
            interests = interests_by_category.get(category_id, [])
            if not interests:
                continue

            selection_mode = section_def.get(
                "selection_mode", {}
            ).get(category_id, "multi")

            category_block = {
                "category_id": category_id,
                "category_name": interests[0]["CategoryName"],
                "selection_mode": selection_mode,
                "interests": [],
            }

            for i in interests:
                category_block["interests"].append({
                    "interest_uid": i["InterestUID"],
                    "interest_code": i["InterestCode"],
                    "label": i["LevelName"],
                    "checked": i["InterestUID"] in user_interest_uids,
                })

            section["categories"].append(category_block)

        sections.append(section)

    # --- render template
    body_html = Path("app/templates/profile_interests.html").read_text(
        encoding="utf-8"
    )

    # --- build interest block HTML
    interest_block_html = []

    for section in sections:
        parent_pt = section.get("parent_product_type")

        fieldset_attrs = [
            "class='interest-section'",
            "data-overlay-section"
        ]

        if parent_pt:
            fieldset_attrs.append(f'data-parent-product-type="{parent_pt}"')
            fieldset_attrs.append("hidden")
            fieldset_attrs.append("style='display:none'")

        interest_block_html.append(
            f"<fieldset {' '.join(fieldset_attrs)}>"
        )

        interest_block_html.append(f"<legend>{section['title']}</legend>")

        if section.get("description"):
            interest_block_html.append(
                f"<p class='section-description'>{section['description']}</p>"
            )

        is_child_section = bool(section.get("parent_product_type"))

        for category in section["categories"]:
            is_product_type = (
                category["category_id"] == 102
                and not is_child_section
            )

            input_type = (
                "radio" if category["selection_mode"] == "single" else "checkbox"
            )

            interest_block_html.append(
                f"<div class='profile-category'>"
                f"<div class='category-title'>{category['category_name']}</div>"
                f"<div class='category-options'>"
            )

            any_child_checked = any(i["checked"] for i in category["interests"])

            if is_product_type:
                for interest in category["interests"]:
                    interest_block_html.append(f"""
                    <label class="profile-option product-type-trigger"
                            data-product-type="{interest['interest_code']}">
                        <input type="checkbox" disabled
                            {'checked' if any_child_checked else ''}>
                        <span class="product-type-label">{interest['label']}</span>
                    </label>
                    """)
            else:
                for interest in category["interests"]:
                    has_any_checked = any(i["checked"] for i in category["interests"])
                    checked = "checked" if (interest["checked"] or not has_any_checked) else ""

                    interest_block_html.append(f"""
                    <label class="profile-option">
                        <input type="{input_type}"
                            name="cat_{category['category_id']}"
                            value="{interest['interest_uid']}"
                            {checked}>
                        <span>{interest['label']}</span>
                    </label>
                    """)

            interest_block_html.append("</div></div>")

        interest_block_html.append("</fieldset>")

    return body_html.replace(
        "__INTEREST_BLOCK__",
        "\n".join(interest_block_html)
    )

# --------------------------------------------------
# SETTINGS: BASIC PROFILE EDITOR
# --------------------------------------------------

BASIC_PROFILE_TEMPLATE = Path("app/templates/settings/edit_basic.html")

def render_basic_form(uid: str) -> str:
    from app.config.profile_layout import BASIC_PROFILE_SECTIONS
    from app.db.user_profiles import get_profiles_by_category_ids
    from app.db.user_profile_map import get_user_profile_uids

    # Fetch existing selections
    user_profile_uids = {
        row["ProfileUID"]
        for row in get_user_profile_uids(uid)
    }

    sections = []

    for section_def in BASIC_PROFILE_SECTIONS:
        section = {
            "title": section_def["title"],
            "categories": [],
        }

        category_ids = section_def.get("categories", [])
        profile_rows = get_profiles_by_category_ids(category_ids)

        profiles_by_category = {}
        for row in profile_rows:
            profiles_by_category.setdefault(row["CategoryID"], []).append(row)

        for category_id in category_ids:
            profiles = profiles_by_category.get(category_id, [])
            if not profiles:
                continue

            selection_mode = section_def.get(
                "selection_mode", {}
            ).get(category_id, "multi")

            section["categories"].append({
                "category_id": category_id,
                "category_name": profiles[0]["CategoryName"],
                "selection_mode": selection_mode,
                "profiles": [
                    {
                        "uid": p["ProfileUID"],
                        "label": p["LevelDescription"],
                        "checked": p["ProfileUID"] in user_profile_uids,
                    }
                    for p in profiles
                ]
            })

        sections.append(section)

    # --- render fieldsets
    blocks = []

    for section in sections:
        blocks.append("<fieldset>")
        blocks.append(f"<legend>{section['title']}</legend>")

        for category in section["categories"]:
            input_type = (
                "radio"
                if category["selection_mode"] == "single"
                else "checkbox"
            )

            blocks.append(
                f"<div class='profile-category'>"
                f"<div class='category-title'>{category['category_name']}</div>"
                f"<div class='category-options'>"
            )

            for p in category["profiles"]:
                checked = "checked" if p["checked"] else ""

                blocks.append(f"""
                <label class="profile-option">
                    <input
                        type="{input_type}"
                        name="cat_{category['category_id']}"
                        value="{p['uid']}"
                        {checked}
                    >
                    <span>{p['label']}</span>
                </label>
                """)

            blocks.append("</div></div>")

        blocks.append("</fieldset>")

    html = BASIC_PROFILE_TEMPLATE.read_text(encoding="utf-8")
    return html.replace("__BASIC_PROFILE_BLOCK__", "\n".join(blocks))

# --------------------------------------------------
# Settings: Advanced Profile fragment renderer
# --------------------------------------------------

def render_advanced_form(uid: str) -> str:
    from pathlib import Path
    from app.config.profile_layout import ADVANCED_PROFILE_SECTIONS
    from app.db.user_profiles import get_profiles_by_category_ids
    from app.db.user_profile_map import get_user_profile_uids

    # --- fetch existing selections
    user_profile_uids = {
        row["ProfileUID"]
        for row in get_user_profile_uids(uid)
    }

    sections = []

    for section_def in ADVANCED_PROFILE_SECTIONS:
        section = {
            "section_id": section_def["id"],
            "title": section_def["title"],
            "categories": [],
        }

        category_ids = section_def.get("categories", [])
        profile_rows = get_profiles_by_category_ids(category_ids)

        profiles_by_category = {}
        for row in profile_rows:
            profiles_by_category.setdefault(row["CategoryID"], []).append(row)

        for category_id in category_ids:
            profiles = profiles_by_category.get(category_id, [])
            if not profiles:
                continue

            selection_mode = section_def.get(
                "selection_mode", {}
            ).get(category_id, "multi")

            category_block = {
                "category_id": category_id,
                "category_name": profiles[0]["CategoryName"],
                "selection_mode": selection_mode,
                "profiles": [],
            }

            for p in profiles:
                category_block["profiles"].append({
                    "profile_uid": p["ProfileUID"],
                    "label": p["LevelDescription"],
                    "checked": p["ProfileUID"] in user_profile_uids,
                })

            section["categories"].append(category_block)

        sections.append(section)

    # --- load template
    body_html = Path(
        "app/templates/profile_advanced.html"
    ).read_text(encoding="utf-8")

    profile_block_html = []

    for section in sections:
        profile_block_html.append("<fieldset>")
        profile_block_html.append(f"<legend>{section['title']}</legend>")

        for category in section["categories"]:
            input_type = (
                "radio"
                if category["selection_mode"] == "single"
                else "checkbox"
            )

            profile_block_html.append(
                f"<div class='profile-category'>"
                f"<div class='category-title'>{category['category_name']}</div>"
                f"<div class='category-options'>"
            )

            for profile in category["profiles"]:
                checked = "checked" if profile["checked"] else ""
                input_name = f"cat_{category['category_id']}"

                profile_block_html.append(f"""
                <label class="profile-option">
                    <input
                        type="{input_type}"
                        name="{input_name}"
                        value="{profile['profile_uid']}"
                        {checked}
                    >
                    <span>{profile['label']}</span>
                </label>
                """)

            profile_block_html.append("</div></div>")

        profile_block_html.append("</fieldset>")

    return body_html.replace(
        "__ADVANCED_PROFILE_BLOCK__",
        "\n".join(profile_block_html)
    )
