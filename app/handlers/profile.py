# app/handlers/profile.py

from urllib.parse import parse_qs
from pathlib import Path
from app.db.user_pool import get_user_by_userid
from app.services.user_context import build_user_context
from app.db.user_legal_acceptance import get_user_signed_document
from app.utils.html_escape import escape_html as e

def render_identity_header(user: dict) -> str:
    """
    Render the identity card block for the profile page.
    """

    from app.db.user_roles import get_effective_permission_level
    from app.db.user_profile_stats import (
        get_trial_application_count,
        get_trial_completion_count,
    )

    user_id = user.get("user_id")

    first = user.get("FirstName") or ""
    last = user.get("LastName") or ""
    name = f"{first} {last}".strip() or "Unnamed Participant"

    country = user.get("CountryCode") or "Not specified"
    city = user.get("City") or ""
    location = f"{city}, {country}" if city else country

    joined = user.get("CreatedAt")
    joined_str = joined.strftime("%Y-%m-%d") if joined else "Unknown"

    email_verified = "Verified ✓" if user.get("EmailVerified") else "Not Verified"

    nda_status = "Not Signed"
    nda_signed_str = "—"
    nda_version = None
    nda_document_id = None

    nda = get_user_signed_document(
        user_id=user_id,
        document_type="nda",
    )

    if nda:
        nda_status = "Signed"

        nda_signed = nda.get("accepted_at")
        if nda_signed:
            nda_signed_str = nda_signed.strftime("%Y-%m-%d")

        nda_version = nda.get("document_version")
        nda_document_id = nda.get("document_id")

    birth_year = user.get("BirthYear")
    age_range = "—"
    if birth_year:
        from datetime import datetime
        age = datetime.now().year - int(birth_year)

        if age < 30:
            age_range = "18-30"
        elif age < 40:
            age_range = "31-40"
        elif age < 50:
            age_range = "41-50"
        elif age < 60:
            age_range = "51-60"
        else:
            age_range = "60+"

    # --------------------------------------------------
    # ROLE
    # --------------------------------------------------

    level = get_effective_permission_level(user_id)

    ROLE_MAP = {
        0: "Participant",
        1: "Product Team",
        2: "User Trial Lead",
        9: "Admin",
    }

    role = ROLE_MAP.get(level, "Participant")

    # --------------------------------------------------
    # TRIAL ACTIVITY
    # --------------------------------------------------

    applied = get_trial_application_count(user_id)
    completed = get_trial_completion_count(user_id)

    # --------------------------------
    # ESCAPE ALL DISPLAY VALUES
    # --------------------------------
    name = e(name)
    location = e(location)
    joined_str = e(joined_str)
    email_verified = e(email_verified)
    nda_status = e(nda_status)
    nda_signed_str = e(nda_signed_str)
    age_range = e(age_range)
    role = e(role)

    applied = e(str(applied))
    completed = e(str(completed))

    nda_version = e(str(nda_version)) if nda_version else None
    nda_document_id = e(str(nda_document_id)) if nda_document_id else None

    return f"""
    <div class="profile-identity-card">

        <div class="profile-avatar-wrap">
            <div class="profile-avatar-placeholder">👤</div>
        </div>

        <div class="profile-identity-main">

            <div class="profile-name">{name}</div>

            <div class="profile-meta">
                <div><strong>Location:</strong> {location}</div>
                <div><strong>Joined:</strong> {joined_str}</div>
                <div><strong>Age Range:</strong> {age_range}</div>
                <div><strong>Role:</strong> {role}</div>
            </div>

            <hr class="profile-divider">

            <div class="profile-meta">
                <div><strong>Email:</strong> {email_verified}</div>
                <div><strong>NDA:</strong> {nda_status}</div>
                <div><strong>Signed:</strong> {nda_signed_str}</div>

                {f"<div><strong>Version:</strong> {nda_version}</div>" if nda_version else ""}

                {
                f"<div><a class='profile-download-link' href='/legal/download/{nda_document_id}'>Download Signed Copy</a></div>"
                if nda_document_id else
                "<div><a class='profile-sign-link' href='/legal/nda'>Sign NDA</a></div>"
                }
            </div>

            <hr class="profile-divider">

            <div class="profile-meta">
                <div><strong>Trials Applied:</strong> {applied}</div>
                <div><strong>Trials Completed:</strong> {completed}</div>
            </div>

        </div>

        <div class="profile-identity-actions">
            <a class="profile-edit-button" href="/profile/basic">
                Edit Identity
            </a>
        </div>

    </div>
    """

def _safe_debug(*args):
    """
    Keep behavior similar to your existing debug() calls without hard dependency.
    """
    try:
        from app.utils.debug import debug  # type: ignore
        debug(*args)
    except Exception:
        # fallback: don't break request flow if debug helper isn't available
        print("[DEBUG]", *args)


def _parse_post_form(raw_body: str) -> dict:
    """
    Wrapper so main.py stays clean and all wizard parsing lives here.
    """
    return parse_qs(raw_body)


def handle_profile_interests_post(user_id: str, raw_body: str) -> dict:
    """
    Returns:
      { "redirect": "/profile/basic" }
    """
    form = _parse_post_form(raw_body)

    # Single supported action: advance
    action = form.get("action", ["advance"])[0]

    # --- collect InterestUIDs (explicit submissions)
    interest_uids: list[str] = []
    for key, values in form.items():
        if key.startswith("cat_"):
            interest_uids.extend(values)

    # --------------------------------------------------
    # INFER PRODUCT TYPES (CategoryID = 102)
    # --------------------------------------------------
    from app.db.user_interests import get_interests_by_category_ids
    from app.config.profile_layout import INTEREST_PROFILE_SECTIONS

    PRODUCT_TYPE_CATEGORY_ID = 102

    # map InterestCode -> InterestUID for PT102*
    product_type_rows = get_interests_by_category_ids([PRODUCT_TYPE_CATEGORY_ID])
    product_type_code_to_uid = {
        row["InterestCode"]: row["InterestUID"]
        for row in product_type_rows
        if row.get("InterestCode")
    }

    submitted_category_ids = {
        int(k.replace("cat_", ""))
        for k, v in form.items()
        if k.startswith("cat_") and v
    }

    inferred_product_type_codes = set()
    for section_def in INTEREST_PROFILE_SECTIONS:
        parent_pt = section_def.get("parent_product_type")
        if not parent_pt:
            continue

        section_category_ids = set(section_def.get("categories", []))
        if section_category_ids & submitted_category_ids:
            inferred_product_type_codes.add(parent_pt)

    for pt_code in sorted(inferred_product_type_codes):
        uid_to_add = product_type_code_to_uid.get(pt_code)
        if uid_to_add and uid_to_add not in interest_uids:
            interest_uids.append(uid_to_add)

    # --- save interests (replace semantics)
    from app.db.user_interest_map import save_user_interests
    save_user_interests(user_id, interest_uids)

    # --- mark interests step acknowledged (even if empty)
    from app.db.user_pool import advance_profile_wizard_step
    advance_profile_wizard_step(user_id, 1)

    # --- redirect to next wizard step (Basic Profile)
    # "advance" goes to Basic (NOT advanced)
    if action == "advance":
        return {"redirect": "/profile/basic"}

    # if something weird comes in, default safe
    return {"redirect": "/profile/basic"}


def handle_profile_basic_post(user_id: str, raw_body: str) -> dict:
    """
    Returns:
      { "redirect": "/profile/advanced" }
    """
    form = _parse_post_form(raw_body)

    # --- extract country dropdown
    country = form.get("country", [None])[0]
    if country:
        country = country.strip().upper()

    # --- persist country if provided
    if country:
        from app.db.user_pool import get_connection

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE user_pool
                SET CountryCode = %s,
                    UpdatedAt = NOW()
                WHERE user_id = %s
                """,
                (country, user_id),
            )
            conn.commit()
        finally:
            conn.close()

    selected_codes: list[str] = []
    for key, values in form.items():
        if not key.startswith("cat_"):
            continue
        selected_codes.extend(values)

    from app.db.user_profile_map import save_user_profiles_for_categories
    from app.config.profile_layout import BASIC_PROFILE_SECTIONS

    basic_category_ids = [
        cat_id
        for section in BASIC_PROFILE_SECTIONS
        for cat_id in section.get("categories", [])
    ]

    save_user_profiles_for_categories(
        user_id=user_id,
        profile_uids=selected_codes,
        category_ids=basic_category_ids,
    )

    from app.db.user_pool import advance_profile_wizard_step
    advance_profile_wizard_step(user_id, 2)

    _safe_debug("BASIC PROFILE ACKNOWLEDGED:", user_id, selected_codes)

    return {"redirect": "/profile/advanced"}


def handle_profile_advanced_post(user_id: str, raw_body: str) -> dict:
    """
    Returns:
      { "redirect": "/profile" }
    """
    form = _parse_post_form(raw_body)

    selected_codes: list[str] = []
    for key, values in form.items():
        if not key.startswith("cat_"):
            continue
        selected_codes.extend(values)

    from app.db.user_profile_map import save_user_profiles_for_categories
    from app.config.profile_layout import ADVANCED_PROFILE_SECTIONS

    advanced_category_ids = [
        cat_id
        for section in ADVANCED_PROFILE_SECTIONS
        for cat_id in section.get("categories", [])
    ]

    save_user_profiles_for_categories(
        user_id=user_id,
        profile_uids=selected_codes,
        category_ids=advanced_category_ids,
    )

    from app.db.user_pool import advance_profile_wizard_step
    advance_profile_wizard_step(user_id, 3)

    _safe_debug("ADVANCED PROFILE ACKNOWLEDGED:", user_id, selected_codes)

    return {"redirect": "/profile"}

from pathlib import Path
from app.db.user_pool import get_user_by_userid
from app.services.user_context import build_user_context


def render_profile_wizard_get(user_id: str, base_template: str, inject_nav):
    user = get_user_by_userid(user_id)
    if not user:
        return {"redirect": "/logout"}

    ctx = build_user_context(user)

    # ACCESS GUARD (authoritative)
    if not ctx["access"]["is_path_allowed"]("profile/wizard"):
        return {
            "redirect": ctx["access"]["deny_redirect"]("profile/wizard")
        }

    # Completed users should not see wizard intro
    if ctx["states"]["profile"] == "complete":
        return {"redirect": "/settings"}

    body_html = Path("app/templates/wizard.html").read_text(encoding="utf-8")

    html = base_template
    html = inject_nav(html)
    html = html.replace("__BODY__", body_html)

    return {"html": html}

from pathlib import Path
from app.db.user_pool import get_user_by_userid
from app.services.user_context import build_user_context


def render_profile_interests_get(user_id: str, base_template: str) -> dict:
    user = get_user_by_userid(user_id)
    if not user:
        return {"redirect": "/logout"}

    ctx = build_user_context(user)

    # --------------------------------------------------
    # ACCESS GUARD (authoritative)
    # --------------------------------------------------
    if not ctx["access"]["is_path_allowed"]("profile/interests"):
        return {
            "redirect": ctx["access"]["deny_redirect"]("profile/interests")
        }

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

        # --- group interests by category
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

    # --------------------------------------------------
    # TEMPLATE LOAD
    # --------------------------------------------------
    body_html = Path(
        "app/templates/profile_interests.html"
    ).read_text(encoding="utf-8")

    # --------------------------------------------------
    # BUILD INTEREST BLOCK HTML
    # --------------------------------------------------
    interest_block_html = []

    for section in sections:
        parent_pt = section.get("parent_product_type")
        is_child_section = bool(parent_pt)

        section_classes = [
            "interest-section",
            "interest-child-section" if is_child_section else "interest-parent-section",
        ]

        section_title = e(section["title"])

        section_attrs = [
            f'class="{" ".join(section_classes)}"',
            "data-overlay-section",
            f'data-section-title="{section_title}"',
        ]

        if parent_pt:
            section_attrs.append(
                f'data-parent-product-type="{e(parent_pt)}"'
            )
            section_attrs.append("hidden")
            section_attrs.append('style="display:none"')

        child_has_saved_selection = any(
            interest["checked"]
            for category in section["categories"]
            for interest in category["interests"]
        )

        disable_child_inputs = (
            "disabled"
            if is_child_section and not child_has_saved_selection
            else ""
        )

        interest_block_html.append(
            f"<section {' '.join(section_attrs)}>"
        )

        interest_block_html.append(
            f"""
            <div class="interest-section-header">
                <div>
                    <h2 class="interest-section-title">{section_title}</h2>
                    {
                        f'<p class="interest-section-description">{e(section["description"])}</p>'
                        if section.get("description")
                        else ''
                    }
                </div>
            </div>
            """
        )

        for category in section["categories"]:
            is_product_type = (
                category["category_id"] == 102
                and not is_child_section
            )

            input_type = (
                "radio"
                if category["selection_mode"] == "single"
                else "checkbox"
            )

            interest_block_html.append(
                f"""
                <div class="interest-category" data-category-id="{category['category_id']}">
                    <div class="interest-category-title">{e(category['category_name'])}</div>
                    <div class="interest-options">
                """
            )

            if is_product_type:
                # Parent Product Types → overlay triggers only.
                # Child selections are enabled only after the user opens the relevant overlay.
                for interest in category["interests"]:
                    selected_class = (
                        "selected"
                        if interest["checked"]
                        else ""
                    )

                    interest_block_html.append(
                        f"""
                        <button
                            type="button"
                            class="interest-product-type-trigger {selected_class}"
                            data-product-type="{e(interest['interest_code'])}"
                        >
                            <span class="interest-product-type-label">{e(interest['label'])}</span>
                            <span class="interest-product-type-arrow">›</span>
                        </button>
                        """
                    )
            else:
                has_any_checked = any(
                    i["checked"] for i in category["interests"]
                )

                for interest in category["interests"]:
                    checked = (
                        "checked"
                        if interest["checked"] or not has_any_checked
                        else ""
                    )

                    interest_block_html.append(
                        f"""
                        <label class="interest-choice">
                            <input
                                type="{input_type}"
                                name="cat_{category['category_id']}"
                                value="{e(interest['interest_uid'])}"
                                {checked}
                                {disable_child_inputs}
                            >
                            <span>{e(interest['label'])}</span>
                        </label>
                        """
                    )

            interest_block_html.append(
                """
                    </div>
                </div>
                """
            )

        interest_block_html.append("</section>")

    # --------------------------------------------------
    # INJECT INTEREST BLOCK
    # --------------------------------------------------
    body_html = body_html.replace(
        "__INTEREST_BLOCK__",
        "\n".join(interest_block_html)
    )

    html = base_template.replace("__BODY__", body_html)

    return {"html": html}

def render_profile_basic_get(user_id: str, base_template: str, inject_nav):
    user = get_user_by_userid(user_id)
    if not user:
        return {"redirect": "/logout"}

    from app.db.user_pool import get_connection
    from app.db.user_pool_country_codes import get_country_codes

    conn = get_connection()
    countries = get_country_codes()
    conn.close()

    ctx = build_user_context(user)

    # ACCESS GUARD (authoritative)
    if not ctx["access"]["is_path_allowed"]("profile/basic"):
        return {
            "redirect": ctx["access"]["deny_redirect"]("profile/basic")
        }

    from app.config.profile_layout import BASIC_PROFILE_SECTIONS
    from app.db.user_profiles import get_profiles_by_category_ids
    from app.db.user_profile_map import get_user_profile_uids

    user_profile_uids = {
        row["ProfileUID"]
        for row in get_user_profile_uids(user_id)
    }

    sections = []

    for section_def in BASIC_PROFILE_SECTIONS:
        section = {
            "section_id": section_def["id"],
            "title": section_def["title"],
            "description": section_def.get("description"),
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

    country_options = []

    for c in countries:
        selected = "selected" if c["CountryCode"] == user.get("CountryCode") else ""
        country_options.append(
            f'<option value="{e(c["CountryCode"])}" {selected}>{e(c["CountryName"])}</option>'
        )

    country_html = "\n".join(country_options)

    body_html = Path(
        "app/templates/profile_basic.html"
    ).read_text(encoding="utf-8")

    body_html = body_html.replace(
        "__COUNTRY_OPTIONS__",
        country_html
    )

    profile_block_html = []

    for section in sections:
        section_title = e(section["title"])
        section_description = section.get("description")

        profile_block_html.append(
            f"""
            <section class="profile-basic-section" data-profile-section="{e(section["section_id"])}">
                <div class="profile-basic-section-header">
                    <h2 class="profile-basic-section-title">{section_title}</h2>
                    {
                        f'<p class="profile-basic-section-description">{e(section_description)}</p>'
                        if section_description
                        else ''
                    }
                </div>
            """
        )

        for category in section["categories"]:
            input_type = (
                "radio"
                if category["selection_mode"] == "single"
                else "checkbox"
            )

            input_name = f"cat_{category['category_id']}"

            profile_block_html.append(
                f"""
                <div class="profile-basic-category" data-category-id="{e(str(category["category_id"]))}">
                    <div class="profile-basic-category-title">{e(category["category_name"])}</div>
                    <div class="profile-basic-options">
                """
            )

            for profile in category["profiles"]:
                checked = "checked" if profile["checked"] else ""

                profile_block_html.append(
                    f"""
                    <label class="profile-basic-choice">
                        <input
                            type="{input_type}"
                            name="{input_name}"
                            value="{e(profile["profile_uid"])}"
                            {checked}
                        >
                        <span>{e(profile["label"])}</span>
                    </label>
                    """
                )

            profile_block_html.append(
                """
                    </div>
                </div>
                """
            )

        profile_block_html.append("</section>")

    body_html = body_html.replace(
        "__BASIC_PROFILE_BLOCK__",
        "\n".join(profile_block_html)
    )

    html = base_template
    html = inject_nav(html)
    html = html.replace("__BODY__", body_html)

    return {"html": html}

def render_profile_advanced_get(user_id: str, base_template: str, inject_nav):
    user = get_user_by_userid(user_id)
    if not user:
        return {"redirect": "/logout"}

    ctx = build_user_context(user)

    # ACCESS GUARD (authoritative)
    if not ctx["access"]["is_path_allowed"]("profile/advanced"):
        return {
            "redirect": ctx["access"]["deny_redirect"]("profile/advanced")
        }

    from app.config.profile_layout import ADVANCED_PROFILE_SECTIONS
    from app.db.user_profiles import get_profiles_by_category_ids
    from app.db.user_profile_map import get_user_profile_uids

    user_profile_uids = {
        row["ProfileUID"]
        for row in get_user_profile_uids(user_id)
    }

    sections = []

    for section_def in ADVANCED_PROFILE_SECTIONS:
        section = {
            "section_id": section_def["id"],
            "title": section_def["title"],
            "description": section_def.get("description"),
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

    body_html = Path(
        "app/templates/profile_advanced.html"
    ).read_text(encoding="utf-8")

    profile_block_html = []

    for section in sections:
        section_id = e(str(section["section_id"]))
        section_title = e(section["title"])
        section_description = section.get("description")

        profile_block_html.append(
            f"""
            <section class="profile-advanced-section" data-profile-section="{section_id}">
                <div class="profile-advanced-section-header">
                    <h2 class="profile-advanced-section-title">{section_title}</h2>
                    {
                        f'<p class="profile-advanced-section-description">{e(section_description)}</p>'
                        if section_description
                        else ''
                    }
                </div>
            """
        )

        for category in section["categories"]:
            category_id = e(str(category["category_id"]))
            category_name = e(category["category_name"])

            input_type = (
                "radio"
                if category["selection_mode"] == "single"
                else "checkbox"
            )

            input_name = f"cat_{category['category_id']}"

            profile_block_html.append(
                f"""
                <div class="profile-advanced-category" data-category-id="{category_id}">
                    <div class="profile-advanced-category-title">{category_name}</div>
                    <div class="profile-advanced-options">
                """
            )

            for profile in category["profiles"]:
                checked = "checked" if profile["checked"] else ""
                profile_uid = e(profile["profile_uid"])
                profile_label = e(profile["label"])

                profile_block_html.append(
                    f"""
                    <label class="profile-advanced-choice">
                        <input
                            type="{input_type}"
                            name="{input_name}"
                            value="{profile_uid}"
                            {checked}
                        >
                        <span>{profile_label}</span>
                    </label>
                    """
                )

            profile_block_html.append(
                """
                    </div>
                </div>
                """
            )

        profile_block_html.append("</section>")

    body_html = body_html.replace(
        "__ADVANCED_PROFILE_BLOCK__",
        "\n".join(profile_block_html)
    )

    html = base_template
    html = inject_nav(html)
    html = html.replace("__BODY__", body_html)

    return {"html": html}

def render_profile_summary_get(user_id: str, base_template: str, inject_nav):
    user = get_user_by_userid(user_id)
    if not user:
        return {"redirect": "/logout"}

    ctx = build_user_context(user)

    # --------------------------------------------------
    # ACCESS GUARD (authoritative)
    # --------------------------------------------------
    if not ctx["access"]["is_path_allowed"]("profile"):
        return {
            "redirect": ctx["access"]["deny_redirect"]("profile")
        }

    # --------------------------------------------------
    # SUMMARY ONLY BELOW THIS POINT
    # --------------------------------------------------

    from app.services.profile_summary import (
        build_full_profile_summary,
        render_profile_summary_html,
    )
    from app.config.profile_layout import (
        INTEREST_PROFILE_SECTIONS,
        BASIC_PROFILE_SECTIONS,
        ADVANCED_PROFILE_SECTIONS,
    )
    from app.db.user_interests import get_interests_by_category_ids
    from app.db.user_profiles import get_profiles_by_category_ids
    from app.db.user_profile_map import get_user_profile_uids
    from app.db.user_interest_map import get_user_interest_uids

    # --- demographics source of truth
    demographics = {
        "first_name": user.get("FirstName"),
        "last_name": user.get("LastName"),
        "gender": user.get("Gender"),
        "birth_year": user.get("BirthYear"),
        "country": user.get("CountryCode"),
        "city": user.get("City"),
    }

    identity_html = render_identity_header(user)

    # --- selected interests / profiles
    user_interest_uids = {
        row["InterestUID"]
        for row in get_user_interest_uids(user_id)
    }

    user_profile_uids = {
        row["ProfileUID"]
        for row in get_user_profile_uids(user_id)
    }

    # --- build interest definitions
    interest_category_ids = []

    for section in INTEREST_PROFILE_SECTIONS:
        interest_category_ids.extend(section.get("categories", []))

    interest_rows = get_interests_by_category_ids(interest_category_ids)

    interest_definitions = [
        {
            "InterestUID": r["InterestUID"],
            "CategoryID": r["CategoryID"],
            "CategoryName": r["CategoryName"],
            "LevelName": r["LevelName"],
        }
        for r in interest_rows
    ]

    # --- build profile definitions basic + advanced
    def _flatten(section_list):
        ids = []

        for section in section_list:
            ids.extend(section.get("categories", []))

        return sorted(set(ids))

    profile_rows = get_profiles_by_category_ids(
        _flatten(BASIC_PROFILE_SECTIONS)
        + _flatten(ADVANCED_PROFILE_SECTIONS)
    )

    profile_definitions = [
        {
            "ProfileUID": r["ProfileUID"],
            "CategoryID": r["CategoryID"],
            "CategoryName": r["CategoryName"],
            "OptionLabel": r["LevelDescription"],
        }
        for r in profile_rows
    ]

    # --- build full summary object
    full_summary = build_full_profile_summary(
        user_interest_uids=user_interest_uids,
        interest_definitions=interest_definitions,
        interest_sections=INTEREST_PROFILE_SECTIONS,
        user_profile_uids=user_profile_uids,
        profile_definitions=profile_definitions,
        basic_sections=BASIC_PROFILE_SECTIONS,
        advanced_sections=ADVANCED_PROFILE_SECTIONS,
    )

    # --- render summary template
    body_html = Path(
        "app/templates/profile_summary.html"
    ).read_text(encoding="utf-8")

    # --------------------------------------------------
    # Demographics injection
    # --------------------------------------------------
    body_html = body_html.replace("__FIRST_NAME__", demographics["first_name"] or "")
    body_html = body_html.replace("__LAST_NAME__", demographics["last_name"] or "")
    body_html = body_html.replace("__CITY__", demographics["city"] or "")
    body_html = body_html.replace("__COUNTRY__", demographics["country"] or "")
    body_html = body_html.replace(
        "__BIRTH_YEAR__",
        str(demographics["birth_year"] or "")
    )

    gender_display_map = {
        "male": "Male",
        "female": "Female",
        "non_binary": "Non-Binary",
        "prefer_not_to_say": "Prefer not to say",
    }

    body_html = body_html.replace(
        "__GENDER__",
        gender_display_map.get(
            demographics["gender"],
            demographics["gender"] or ""
        )
    )

    profile_content_html = render_profile_summary_html(full_summary)

    body_html = body_html.replace(
        "__IDENTITY_HEADER__",
        identity_html,
    )

    body_html = body_html.replace(
        "__PROFILE_CONTENT__",
        profile_content_html,
    )

    html = base_template
    html = inject_nav(html)
    html = html.replace("__BODY__", body_html)

    return {"html": html}


def _flatten_interest_summary_sections(sections: list[dict]) -> list[dict]:
    """
    Keep Interests as the top-level group, but do not show Product Types as
    one giant second-level section.

    Instead:
    - Brand Interests remains second-level
    - Product type children become second-level sections
    - Product Tiers remains second-level
    - Mobility / Education remains second-level
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

        if section_id == "product_types" and section.get("children"):
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
    sections: list[dict],
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
    section: dict,
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


def _render_summary_category(category: dict) -> str:
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


def _summary_group_counts(sections: list[dict]) -> tuple[int, int]:
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