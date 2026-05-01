# app/handlers/user_trial_lead_project.py

from app.db.user_roles import get_effective_permission_level
from app.db.user_trial_lead import (
    get_project_round_by_id,
    update_project_round_overview,
    lock_project_round_overview,
    add_round_survey,
    lock_project_round_planning,
    get_round_surveys,
    get_round_profile_criteria,
    add_round_profile_criteria,
    delete_round_profile_criteria
)
import os
import json
from datetime import datetime
from pathlib import Path
from app.db.user_pool import get_display_name_by_user_id
from app.db.user_pool_country_codes import get_country_codes
from app.db.user_trial_lead import update_recruiting_config
from app.handlers.user_trial_lead_project_survey_results import render_survey_results_section
from app.db.survey_recruiting_kpis import get_recruiting_kpis  # add near imports
from app.utils.html_escape import escape_html as e

def _render_round_config_unlocked(*, round_data, country_options_html):

    return f"""
    <details class="ut-lead-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Round Configuration</strong>
            <span class="muted small">— Unlocked</span>
        </summary>
        <div class="ut-lead-section-body">

    <form method="post" action="/ut-lead/project" class="round-config-form">
    <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">

    <div class="section-header">Dates</div>
    <div class="form-grid">

    <div class="form-field full">
    <label>Description</label>
    <textarea name="description" rows="2">{e(round_data.get("Description") or "")}</textarea>
    </div>

    </div>  <!-- CLOSE form-grid BEFORE dates -->

    <div class="inline-row">

        <div class="inline-field">
            <span class="inline-label">Start</span>
            <input type="date" id="start_date" name="start_date"
            value="{e(round_data.get("StartDate") or "")}">
        </div>

        <div class="inline-field">
            <span class="inline-label">End</span>
            <input type="date" id="end_date" name="end_date"
            value="{e(round_data.get("EndDate") or "")}">
        </div>

        <div class="inline-field">
            <span class="inline-label">Ship</span>
            <input type="date" name="ship_date"
            value="{e(round_data.get("ShipDate") or "")}">
        </div>

    </div>

    <div class="form-grid">  <!-- REOPEN grid for next section -->

    </div>

    <div class="form-grid">

    <div class="form-field">
    <label>User Scope</label>
    <select name="user_scope">
    <option value="Internal" {"selected" if round_data.get("UserScope") == "Internal" else ""}>Internal</option>
    <option value="External" {"selected" if round_data.get("UserScope") == "External" else ""}>External</option>
    <option value="Hybrid" {"selected" if round_data.get("UserScope") == "Hybrid" else ""}>Hybrid</option>
    </select>
    </div>

    <div class="form-field">
    <label>Target Users</label>
    <input type="number" name="target_users"
    value="{e(round_data.get("TargetUsers") or 30)}">
    </div>

    <div class="form-field">
    <label>Min Age</label>
    <select name="min_age">
    <option value="">Any</option>
    <option value="0">Minors</option>
    <option value="19">19+</option>
    <option value="30">30+</option>
    <option value="40">40+</option>
    <option value="50">50+</option>
    <option value="60">60+</option>
    </select>
    </div>

    <div class="form-field">
    <label>Max Age</label>
    <select name="max_age">
    <option value="">Any</option>
    <option value="30">Up to 30</option>
    <option value="40">Up to 40</option>
    <option value="50">Up to 50</option>
    <option value="60">Up to 60</option>
    <option value="61">61+</option>
    </select>
    </div>

    </div>    

    <div class="form-grid">

    <div class="form-field">
    <label>Prototype Version</label>
    <input type="text" name="prototype_version"
    value="{e(round_data.get("PrototypeVersion") or "pb1")}">
    </div>

    <div class="form-field">
    <label>FW Version</label>
    <input type="text" name="product_sku"
    value="{e(round_data.get("ProductSKU") or "")}">
    </div>

    </div>

    <div class="section-header">Countries</div>
    <div class="form-grid">

    <div class="form-field full">

    <div id="country-chip-container" class="country-chip-container"></div>

    <div class="country-add-row">

    <select id="country_select">
        <option value="">Select Country</option>
        {country_options_html}
    </select>

    </div>

    <input type="hidden" id="region_input" name="region"
    value="{e(round_data.get("Region") or "")}">

    </div>

    </div>

    <div class="form-actions">
    <button type="submit" name="action" value="save_overview">Save</button>
    <button type="submit" name="action" value="lock_overview">Lock Overview</button>
    </div>

    </form>

    <script>
    document.addEventListener("DOMContentLoaded", function () {{

        // =========================
        // DATE AUTO-FILL
        // =========================
        const start = document.getElementById("start_date");
        const end = document.getElementById("end_date");

        if (start && end) {{
            function autoEndDate() {{
                if (!start.value) return;

                let d = new Date(start.value);
                d.setDate(d.getDate() + 30);

                const yyyy = d.getFullYear();
                const mm = String(d.getMonth() + 1).padStart(2, "0");
                const dd = String(d.getDate()).padStart(2, "0");

                end.value = yyyy + "-" + mm + "-" + dd;
            }}

            start.addEventListener("change", autoEndDate);
        }}

        // =========================
        // COUNTRY SELECT → CHIP SYSTEM
        // =========================
        const container = document.getElementById("country-chip-container");
        const select = document.getElementById("country_select");
        const hidden = document.getElementById("region_input");

        if (!container || !select || !hidden) return;

        let countries = [];

        if (hidden.value) {{
            hidden.value.split(",").forEach(code => {{
                const option = select.querySelector(`option[value="${{code}}"]`);
                if (option) {{
                    countries.push({{
                        code: code,
                        name: option.text
                    }});
                }}
            }});
        }}

        function renderCountries() {{
            container.innerHTML = "";

            countries.forEach(country => {{
                const chip = document.createElement("div");
                chip.className = "country-chip";

                const span = document.createElement("span");
                span.textContent = country.name;

                const btn = document.createElement("button");
                btn.type = "button";
                btn.dataset.code = country.code;
                btn.textContent = "✕";

                chip.appendChild(span);
                chip.appendChild(btn);

                container.appendChild(chip);
            }});

            hidden.value = countries.map(c => c.code).join(",");
        }}

        select.addEventListener("change", function () {{
            const code = select.value;
            const name = select.options[select.selectedIndex].text;

            if (!code) return;

            if (!countries.some(c => c.code === code)) {{
                countries.push({{ code: code, name: name }});
            }}

            renderCountries();
            select.value = "";
        }});

        container.addEventListener("click", function (e) {{
            if (e.target.tagName !== "BUTTON") return;

            const code = e.target.dataset.code;
            countries = countries.filter(c => c.code !== code);

            renderCountries();
        }});

        renderCountries();
    }});
    </script>

    </div>
    </details>
    """

def _render_round_config_locked(*, round_data, country_rows, user_id):

    # -----------------------------------------
    # Convert Region Codes → Names
    # -----------------------------------------
    region_codes = (round_data.get("Region") or "").split(",")
    region_names = []

    for code in region_codes:
        for c in country_rows:
            if c["CountryCode"] == code:
                region_names.append(c["CountryName"])
                break
        else:
            region_names.append(code)

    region_display = ", ".join(region_names) if region_names else "—"

    html = f"""
    <details class="ut-lead-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Round Configuration</strong>
            <span class="muted small">— Locked</span>
        </summary>

        <div class="ut-lead-section-body">

            <div class="locked-section">

                <div class="locked-group">
                    <div class="locked-title">Schedule</div>

                    <div class="locked-row">
                        <div class="locked-item">
                            <span class="locked-label">Start</span>
                            <span class="locked-value">{e(round_data.get('StartDate') or '—')}</span>
                        </div>

                        <div class="locked-item">
                            <span class="locked-label">End</span>
                            <span class="locked-value">{e(round_data.get('EndDate') or '—')}</span>
                        </div>
                    </div>
                </div>

                <div class="locked-group">
                    <div class="locked-title">Participants</div>

                    <div class="locked-row">
                        <div class="locked-item">
                            <span class="locked-label">Scope</span>
                            <span class="locked-value">{e(round_data.get('UserScope') or '—')}</span>
                        </div>

                        <div class="locked-item">
                            <span class="locked-label">Users</span>
                            <span class="locked-value">{e(round_data.get('TargetUsers') or '—')}</span>
                        </div>
                    </div>

                    <div class="locked-row">
                        <div class="locked-item">
                            <span class="locked-label">Age</span>
                            <span class="locked-value">
                                {e(round_data.get('MinAge') or 'Any')} - {e(round_data.get('MaxAge') or 'Any')}
                            </span>
                        </div>

                        <div class="locked-item">
                            <span class="locked-label">Region</span>
                            <span class="locked-value">{e(region_display)}</span>
                        </div>
                    </div>
                </div>

                <div class="locked-group">
                    <div class="locked-title">Product</div>

                    <div class="locked-row">
                        <div class="locked-item">
                            <span class="locked-label">Prototype</span>
                            <span class="locked-value">{e(round_data.get('PrototypeVersion') or '—')}</span>
                        </div>

                        <div class="locked-item">
                            <span class="locked-label">FW</span>
                            <span class="locked-value">{e(round_data.get('ProductSKU') or '—')}</span>
                        </div>
                    </div>
                </div>

            </div>
    """

    if get_effective_permission_level(user_id) >= 90:
        html += f"""
            <form method="post" action="/ut-lead/project" style="margin-top:10px;">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                <button type="submit" name="action" value="unlock_overview">
                    Unlock Overview
                </button>
            </form>
        """

    html += """
        </div>
    </details>
    """

    return html

def render_ut_lead_project_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict,
):
    """
    UT Lead – Project / Round details page (read-only v1)
    """

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    permission_level = get_effective_permission_level(user_id)
    if permission_level < 70:
        return {"redirect": "/dashboard"}

    # --------------------------------------------------
    # Validate input
    # --------------------------------------------------
    round_id = query_params.get("round_id", [None])[0]
    upload_status = query_params.get("upload")
    if not round_id:
        return {"redirect": "/ut-lead/trials"}
    
    # --------------------------------------------------
    # Load project round (authoritative)
    # --------------------------------------------------
    round_data = get_project_round_by_id(round_id=int(round_id))
    if not round_data:
        return {"redirect": "/ut-lead/trials"}

    project_id = round_data.get("ProjectID")

    # --------------------------------------------------
    # Country list for dropdown
    # --------------------------------------------------

    country_rows = get_country_codes()

    country_options_html = ""

    for c in country_rows:
        country_options_html += f'<option value="{e(c["CountryCode"])}">{e(c["CountryName"])}</option>'

    # --------------------------------------------------
    # Static links (v1)
    # --------------------------------------------------
    recruiting_link = (
        "https://docs.google.com/forms/d/e/1FAIpQLSfs2e_FWkcYXCfXcq1hpCfg6MmV5qRnJ7COlQIhDPK1fHVRdQ/"
        "viewform?usp=pp_url&entry.648734718=user_token_here"
    )

    s1_link = (
        "https://docs.google.com/forms/d/e/1FAIpQLSe95KHUhSD7_UFVrIOiyfbsIxCU9IhkWPLbcUp_7Ii71qmypQ/"
        "viewform?usp=pp_url&entry.1286199023=user_token_here"
    )

    s2_link = (
        "https://docs.google.com/forms/d/e/1FAIpQLSeWeKL8DIfq_9BFJjvYU9wf9pbkGfGz9ySb04DCeSb5bPmrrg/"
        "viewform?usp=pp_url&entry.200157476=user_token_here"
    )

    report_issue_link = (
        "https://docs.google.com/forms/d/e/1FAIpQLScfRWEXIfhOhoq9wzI22Rmv57Ua0pwqk0MNv5lSQyKhaS7Zyg/"
        "viewform?usp=pp_url&entry.637802913=user_token_here"
    )

    consolidated_link = (
        "https://docs.google.com/forms/d/e/1FAIpQLSdrpyGgBCPXQlQzVTXst2s2Uqoyto8CDP7nX9FnBM7wHAkvrw/"
        "viewform?usp=header"
    )

    # after_trial_link intentionally not present yet (anonymous, no token)
    overview_locked = bool(round_data.get("OverviewLocked"))
    profile_locked = bool(round_data.get("ProfileLocked"))

    # =========================================================
    # PRODUCT IDENTITY SECTION
    # =========================================================

    product_identity_section = f"""
    <details class="ut-lead-section product-identity-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Product Identity</strong>
        </summary>

        <div class="ut-lead-section-body">

            <div class="locked-grid">

                <div class="locked-item">
                    <span class="locked-label">Project Name</span>
                    <span class="locked-value">{e(round_data.get("ProjectName") or "—")}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Business Group</span>
                    <span class="locked-value">{e(round_data.get("BusinessGroup") or "—")}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Market Name</span>
                    <span class="locked-value">{e(round_data.get("MarketName") or "—")}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Sub Group</span>
                    <span class="locked-value">{e(round_data.get("BusinessSubGroup") or "—")}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Product Type</span>
                    <span class="locked-value">{e(round_data.get("ProductType") or "—")}</span>
                </div>

                <div class="locked-item">
                    <span class="locked-label">Product SKU</span>
                    <span class="locked-value">{e(round_data.get("ProductSKU") or "—")}</span>
                </div>

            </div>

            <div class="locked-description">
                <span class="locked-label">Project Description</span>
                <div class="locked-value">
                    {e(round_data.get("ProjectDescription") or "—")}
                </div>
            </div>

        </div>

    </details>
    """

    # =========================================================
    # ROUND CONFIGURATION SECTION
    # =========================================================

    overview_locked = bool(round_data.get("OverviewLocked"))

    if overview_locked:
        round_config_section = _render_round_config_locked(
            round_data=round_data,
            country_rows=country_rows,
            user_id=user_id,
        )
    else:
        round_config_section = _render_round_config_unlocked(
            round_data=round_data,
            country_options_html=country_options_html,
        )

    # =========================================================
    # WANTED USER PROFILE SECTION
    # =========================================================

    criteria_rows = get_round_profile_criteria(int(round_data['RoundID']))

    wanted_profile_section = f"""
    <details class="ut-lead-section wanted-profile-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Wanted User Profile</strong>
            <span class="muted small">
                {"— Locked" if profile_locked else "— Editable"}
            </span>
        </summary>

        <div class="ut-lead-section-body">

            <div class="profile-rules-list">
    """

    # ---------------------------------
    # Existing Criteria Rows
    # ---------------------------------

    for c in criteria_rows:

        wanted_profile_section += f"""
                <div class="profile-rule-row">

                    <span class="profile-rule-label">Operator</span>
                    <span class="profile-rule-value">{e(c['Operator'])}</span>

                    <span class="profile-rule-label">Category</span>
                    <span class="profile-rule-value">{e(c['CategoryName'])}</span>

                    <span class="profile-rule-label">Value</span>
                    <span class="profile-rule-value">{e(c['LevelDescription'])}</span>
        """

        if not profile_locked:
            wanted_profile_section += f"""
                    <div class="profile-rule-action">
                        <form method="post" action="/ut-lead/project">
                            <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                            <input type="hidden" name="criteria_id" value="{e(c['RoundCriteriaID'])}">
                            <button type="submit" name="action" value="delete_profile_criteria">
                                Remove
                            </button>
                        </form>
                    </div>
            """
        else:
            wanted_profile_section += """
                    <div class="profile-rule-action"></div>
            """

        wanted_profile_section += """
                </div>
        """

    # ---------------------------------
    # Add Criteria Row
    # ---------------------------------

    if not profile_locked:

        from app.db.user_profiles import get_profile_categories
        categories = get_profile_categories()

        wanted_profile_section += f"""
            </div>

            <div class="profile-add-block">
                <div class="profile-add-label">Add Criteria</div>

                <form method="post" action="/ut-lead/project" class="profile-add-form">
                    <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">

                    <select name="operator" required>
                        <option value="INCLUDE">Include</option>
                        <option value="EXCLUDE">Exclude</option>
                    </select>

                    <select name="category_id" id="profile_category" required>
                        <option value="">Select Category</option>
        """

        for cat in categories:
            wanted_profile_section += f"""
                        <option value="{e(cat['CategoryID'])}">
                            {e(cat['CategoryName'])}
                        </option>
            """

        wanted_profile_section += """
                    </select>

                    <select name="profile_uid" id="profile_level" required>
                        <option value="">Select Level</option>
                    </select>

                    <button type="submit" name="action" value="add_profile_criteria">
                        Add
                    </button>
                </form>
            </div>
        """

    else:

        wanted_profile_section += """
            </div>
        """

    wanted_profile_section += f"""
            {"" if profile_locked else f'''
            <div class="profile-footer">
                <form method="post" action="/ut-lead/project">
                    <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                    <button type="submit" name="action" value="lock_profile">
                        Lock Profile
                    </button>
                </form>
            </div>
            '''}

        </div>
    </details>
    """

    # =========================================================
    # RECRUITING CONFIGURATION SECTION
    # =========================================================

    raw_value = round_data.get("UseExternalRecruitingSurvey")
    use_external = str(raw_value) == "1"

    print("USE EXTERNAL RAW:", raw_value)
    print("USE EXTERNAL PARSED:", use_external)

    recruiting_config_section = f"""
    <details class="ut-lead-section recruiting-config-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Recruiting Configuration</strong>
        </summary>

        <div class="ut-lead-section-body">

            <form method="post" action="/ut-lead/project" class="recruiting-toggle-form">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                <input type="hidden" name="action" value="update_recruiting_config">

                <label class="recruiting-toggle">
                    <input
                        type="checkbox"
                        name="use_external_recruiting_survey"
                        value="1"
                        {"checked" if use_external else ""}
                        onchange="this.form.submit()"
                    >
                    <span>Use External Recruiting Survey</span>
                </label>

                <div class="muted small" style="margin-top:6px;">
                    If enabled, a recruiting survey must be configured before opening recruiting.
                </div>

            </form>

        </div>
    </details>
    """

    # ---------------------------------
    # Level Loader Script
    # ---------------------------------

    wanted_profile_section += """
    <script>

    document.addEventListener("DOMContentLoaded", function(){

        const categorySelect = document.getElementById("profile_category");
        const levelSelect = document.getElementById("profile_level");

        if (!categorySelect || !levelSelect) return;

        categorySelect.addEventListener("change", function(){

            const categoryId = this.value;

            if (!categoryId){
                levelSelect.innerHTML = "<option value=''>Select Level</option>";
                return;
            }

            fetch("/api/profile-levels?category_id=" + categoryId)
            .then(res => res.json())
            .then(rows => {

                levelSelect.innerHTML = "<option value=''>Select Level</option>";

                rows.forEach(row => {

                    const opt = document.createElement("option");

                    opt.value = row.ProfileUID;
                    opt.textContent = row.LevelDescription;

                    levelSelect.appendChild(opt);

                });

            });

        });

    });

    </script>
    """

    # --------------------------------------------------
    # Render (read-only placeholders)
    # --------------------------------------------------
    body_html = f"""
        <div class="breadcrumb">
            <a href="/ut-lead/trials">← Back to All Trials</a>
        </div>

        <h2>{e(round_data['RoundName'])}</h2>

        {product_identity_section}
        {round_config_section}
        {wanted_profile_section}
    """

    body_html += recruiting_config_section

    # --------------------------------------------------
    # Planning Links (Survey Links per Round)
    # --------------------------------------------------
    planning_locked_by = round_data.get("PlanningLockedBy")
    planning_locked_display = (
        get_display_name_by_user_id(planning_locked_by)
        if planning_locked_by else "—"
    )

    planning_locked_at = round_data.get("PlanningLockedAt") or "—"

    round_surveys = get_round_surveys(int(round_data["RoundID"]))
    planning_locked = bool(round_data.get("PlanningLocked"))

    links_section = f"""
    <details class="ut-lead-section wanted-profile-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Planning – Survey Links</strong>
            <span class="muted small">
                {"— Locked" if planning_locked else "— Unlocked"}
            </span>
        </summary>
        <div class="ut-lead-section-body">
    """

    action_header = "" if planning_locked else "<th>Action</th>"

    links_section += f"""
        <table class="ut-lead-table">
            <thead>
                <tr>
                    <th>Type</th>
                    <th>Edit Link</th>
                    <th>Distribution</th>
                    <th>Target</th>
                    <th>Added By</th>
                    <th>Date Added</th>
                    {action_header}
                </tr>
            </thead>
            <tbody>
    """

    # --------------------------------------------------
    # Existing Survey Rows
    # --------------------------------------------------
    for s in round_surveys:

        survey_type = s.get("SurveyTypeName") or "—"

        survey_link = (s.get("SurveyLink") or "").strip()
        distribution_link = (s.get("DistributionLink") or "").strip()

        added_by = s.get("CreatedBy") or "—"
        created_at = s.get("CreatedAt")

        if created_at:
            try:
                created_at_str = created_at.strftime("%Y-%m-%d")
            except Exception:
                created_at_str = str(created_at)
        else:
            created_at_str = "—"

        target = "Participant"

        # -------------------------
        # Edit Link (Product Team Link)
        # -------------------------
        if survey_link:
            edit_link_html = f'''
                <a href="{e(survey_link)}" target="_blank" rel="noopener noreferrer">
                    Product Team Link
                </a>
            '''
        else:
            edit_link_html = ""

        # -------------------------
        # Distribution Link
        # -------------------------
        if distribution_link:
            distribution_html = f'''
                <a href="{e(distribution_link)}" target="_blank" rel="noopener noreferrer">
                    Participant Facing Link
                </a>
            '''
        else:
            distribution_html = ""

        delete_column_html = ""

        if not planning_locked:
            delete_column_html = f"""
                <td>
                    <form method="post" action="/ut-lead/project" style="display:inline;">
                        <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                        <input type="hidden" name="survey_id" value="{e(s.get('SurveyID'))}">
                        <button type="submit" name="action" value="delete_survey_link">
                            Delete
                        </button>
                    </form>
                </td>
            """

        links_section += f"""
            <tr>
                <td>{e(survey_type)}</td>
                <td>{edit_link_html}</td>
                <td>{distribution_html}</td>
                <td>{e(target)}</td>
                <td>{e(added_by)}</td>
                <td>{e(created_at_str)}</td>
                {delete_column_html}
            </tr>
        """

    # --------------------------------------------------
    # Empty State Row
    # --------------------------------------------------
    if not round_surveys:
        colspan = "7" if not planning_locked else "6"
        links_section += f"""
            <tr>
                <td colspan="{colspan}" class="muted small">
                    No surveys configured yet.
                </td>
            </tr>
        """

    # --------------------------------------------------
    # Add Survey Row
    # --------------------------------------------------
    if not planning_locked:

        from app.db.user_trial_lead import get_survey_types
        survey_types = get_survey_types()

        links_section += f"""
            <tr>
                <form method="post" action="/ut-lead/project">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">

                <td>
                    <select name="survey_type_id" required>
                        <option value="">Select Type</option>
        """

        for st in survey_types:
            links_section += f"""
                        <option value="{e(st['SurveyTypeID'])}">{e(st['SurveyTypeName'])}</option>
            """

        links_section += """
                    </select>
                </td>

                <td>
                    <input type="url" name="survey_edit_link" placeholder="Internal Review Link">
                </td>

                <td>
                    <input type="url" name="survey_distribution_link" placeholder="Participant Link">
                </td>

                <td class="muted small">
                    Participant
                </td>

                <td>—</td>
                <td>—</td>

                <td>
                    <button type="submit" name="action" value="add_survey_link">
                        Add
                    </button>
                </td>

                </form>
            </tr>
        """

    links_section += """
            </tbody>
        </table>
    """

    # --------------------------------------------------
    # Lock / Locked Info
    # --------------------------------------------------

    if not planning_locked:

        links_section += f"""
            <form method="post" action="/ut-lead/project" style="margin-top:12px;">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">

                <button type="submit" name="action" value="lock_planning">
                    Lock Planning
                </button>
            </form>
        """

    else:

        links_section += f"""
            <div class="muted small" style="margin-top:10px;">
                Planning locked at {e(planning_locked_at)}
                by {e(planning_locked_display)}
            </div>
        """

    links_section += """
        </div>
    </details>
    """

    # Append planning links to body
    body_html += links_section

    # =========================================================
    # Recruiting Control
    # =========================================================

    from datetime import date

    recruiting_start_date = round_data.get("RecruitingStartDate")

    if recruiting_start_date:
        recruiting_started = recruiting_start_date <= date.today()
    else:
        recruiting_started = False
        
    planning_locked = bool(round_data.get("PlanningLocked"))

    recruiting_kpis = get_recruiting_kpis(round_id=int(round_id))

    body_html += f"""
        <details class="ut-lead-section wanted-profile-section" open>
            <summary class="ut-lead-section-summary">
                <strong>Recruiting</strong>
                <span class="muted small">
                    {"— Live" if recruiting_started else "— Not Open"}
                </span>
            </summary>

            <div class="ut-lead-section-body">

                {"<div style='margin-bottom:10px;padding:10px;background:#e6ffed;border:1px solid #b7eb8f;'>Successfully uploaded recruiting CSV.</div>" if upload_status == "success" else ""}

                {"<div style='margin-bottom:10px;padding:10px;background:#fff2f0;border:1px solid #ffccc7;'>Upload failed.</div>" if upload_status == "error" else ""}
    """

    if recruiting_started and recruiting_kpis:
        total = recruiting_kpis.get("total_applicants", 0)
        completed = recruiting_kpis.get("completed_count", 0)

        completion_rate = 0
        if total > 0:
            completion_rate = round((completed / total) * 100, 1)

        body_html += f"""
            <div class="overview-card">

                <div class="overview-label" style="margin-bottom:6px;">
                    Recruiting Snapshot
                </div>

                <div class="snapshot-grid">

                    <div class="snapshot-item">
                        <div class="snapshot-value">{total}</div>
                        <div class="snapshot-label">Applicants</div>
                    </div>

                    <div class="snapshot-item">
                        <div class="snapshot-value">{completed}</div>
                        <div class="snapshot-label">Completed</div>
                    </div>

                    <div class="snapshot-item">
                        <div class="snapshot-value">{recruiting_kpis.get("quitter_count", 0)}</div>
                        <div class="snapshot-label">Quitters</div>
                    </div>

                    <div class="snapshot-item">
                        <div class="snapshot-value">{completion_rate}%</div>
                        <div class="snapshot-label">Completion Rate</div>
                    </div>

                    <div class="snapshot-item">
                        <div class="snapshot-value">{recruiting_kpis.get("total_answer_rows", 0)}</div>
                        <div class="snapshot-label">Answer Rows</div>
                    </div>

                </div>

            </div>
        """

    if not recruiting_started:

        body_html += f"""
            <form method="post" action="/ut-lead/project">
                <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">

                <button type="submit" name="action" value="open_recruiting">
                    Open Recruiting
                </button>
            </form>
        """

    elif recruiting_started:

        status = (round_data.get("Status") or "").lower()

        start_date = round_data.get("RecruitingStartDate")
        end_date = round_data.get("RecruitingEndDate")

        controls_html = ""

        if status == "recruiting":
            controls_html = f"""
                <div class="recruiting-actions">
                    <form method="POST" action="/trials/end-recruiting">
                        <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                        <button type="submit" class="btn-danger">
                            End Recruiting
                        </button>
                    </form>
                </div>
            """

        from app.db.survey_answers import has_responses_for_round

        has_external = bool(round_data.get("UseExternalRecruitingSurvey"))
        has_uploaded = has_responses_for_round(round_data["RoundID"])

        if status == "closed":

            if has_external and not has_uploaded:

                controls_html = f"""
                    <div class="recruiting-controls">

                        <form method="post"
                            action="/ut-lead/project"
                            enctype="multipart/form-data"
                            class="recruiting-upload-form">

                            <input type="hidden" name="action" value="upload_survey_results">
                            <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                            <input type="hidden" name="project_id" value="{e(round_data.get('ProjectID'))}">
                            <input type="hidden" name="survey_type_id" value="UTSurveyType0001">

                            <div class="recruiting-upload-row">
                                <div class="recruiting-upload-label">
                                    Upload Recruiting CSV{" (Required)" if has_external and not has_uploaded else ""}
                                </div>

                                <div class="recruiting-upload-input">
                                    <input type="file" name="csv_file" accept=".csv" {"required" if has_external and not has_uploaded else ""}>
                                    <button type="submit" class="btn-primary">Upload</button>
                                </div>
                            </div>

                        </form>

                        {f'''
                        <div class="recruiting-warning">
                            You must upload survey results before proceeding to selection.
                        </div>
                        ''' if has_external and not has_uploaded else ""}

                        {f'''
                        <div class="recruiting-actions">
                            <a href="/trials/selection?round_id={e(round_data['RoundID'])}">
                                <button class="btn-primary">
                                    Continue to Selection →
                                </button>
                            </a>
                        </div>
                        ''' if not (has_external and not has_uploaded) else ""}

                    </div>
                """

            else:

                # Either:``
                # - no external survey
                # - OR CSV already uploaded

                controls_html = f"""
                    <div class="recruiting-controls">

                        <form method="post"
                            action="/ut-lead/project"
                            enctype="multipart/form-data"
                            class="recruiting-upload-form">

                            <input type="hidden" name="action" value="upload_survey_results">
                            <input type="hidden" name="round_id" value="{e(round_data['RoundID'])}">
                            <input type="hidden" name="project_id" value="{e(round_data.get('ProjectID'))}">
                            <input type="hidden" name="survey_type_id" value="UTSurveyType0001">

                            <div class="recruiting-upload-row">
                                <div class="recruiting-upload-label">
                                    Upload Recruiting CSV{" (Required)" if has_external and not has_uploaded else ""}
                                </div>

                                <div class="recruiting-upload-input">
                                    <input type="file" name="csv_file" accept=".csv" {"required" if has_external and not has_uploaded else ""}>
                                    <button type="submit" class="btn-primary">Upload</button>
                                </div>
                            </div>

                        </form>

                        {f'''
                        <div class="recruiting-warning">
                            You must upload survey results before proceeding to selection.
                        </div>
                        ''' if has_external and not has_uploaded else ""}

                        {f'''
                        <div class="recruiting-actions">
                            <a href="/trials/selection?round_id={e(round_data['RoundID'])}">
                                <button class="btn-primary">
                                    Continue to Selection →
                                </button>
                            </a>
                        </div>
                        ''' if not (has_external and not has_uploaded) else ""}

                    </div>
                """

        body_html += f"""
            <div class="overview-card">

                <div class="overview-field">
                    <div class="overview-label">Recruiting Started</div>
                    <div class="overview-value">{e(start_date or "—")}</div>
                </div>

                <div class="overview-field">
                    <div class="overview-label">Recruiting Ended</div>
                    <div class="overview-value">{e(end_date or "—")}</div>
                </div>

                {controls_html}

            </div>
        """

    else:

        body_html += """
            <div class="muted small">
                Planning must be locked before recruiting can open.
            </div>
        """

    body_html += """
            </div>
        </details>
    """

    # =========================================================
    # Participants JSON Hydration
    # DB is authoritative for membership + live completion fields
    # JSON only preserves local tracking fields like notes
    # =========================================================

    from app.db.user_trial_lead import get_round_participants

    db_rows = get_round_participants(int(round_id))

    participants_data = []

    for row in db_rows:

        participants_data.append({
            "user_id": row["user_id"],
            "name": f"{row.get('FirstName', '')} {row.get('LastName', '')}".strip() or row["user_id"],

            # DB is authoritative
            "nda_complete": bool(row.get("NDAComplete")),
            "survey_1_complete": bool(row.get("Survey1Complete")),
            "survey_2_complete": bool(row.get("Survey2Complete")),
            "survey_1_reminders": int(row.get("Survey1Reminders") or 0),
            "survey_2_reminders": int(row.get("Survey2Reminders") or 0),

            # TEMP: no annotation persistence
            "reason": "",
            "reason_notes": ""
        })

    # --------------------------------------------------
    # Lower Project Sections Template
    # --------------------------------------------------

    sections_template = Path(
        "app/templates/ut_lead/ut_lead_project_sections.html"
    ).read_text(encoding="utf-8")

    # =========================================================
    # Participants Section
    # =========================================================

    participants_template = Path(
        "app/templates/ut_lead/ut_lead_project_participants.html"
    ).read_text(encoding="utf-8")

    participants_rows_html = ""

    if participants_data:
        for p in participants_data:

            nda_complete = "true" if p["nda_complete"] else "false"
            s1_complete = "true" if p["survey_1_complete"] else "false"
            s2_complete = "true" if p["survey_2_complete"] else "false"

            participants_rows_html += f"""
                <tr
                    data-nda-complete="{nda_complete}"
                    data-s1-complete="{s1_complete}"
                    data-s2-complete="{s2_complete}"
                >
                    <td>{e(p['name'])}</td>

                    <td>{"✔" if p["nda_complete"] else "—"}</td>

                    <td>
                        <input type="checkbox"
                            name="survey1_{e(p['user_id'])}"
                            {"checked" if p["survey_1_complete"] else ""}>
                    </td>

                    <td class="muted small">
                        {e(p["survey_1_reminders"])}
                    </td>

                    <td>
                        <input type="checkbox"
                            name="survey2_{e(p['user_id'])}"
                            {"checked" if p["survey_2_complete"] else ""}>
                    </td>

                    <td class="muted small">
                        {e(p["survey_2_reminders"])}
                    </td>

                    <td>
                        <select name="row_action_{e(p['user_id'])}">
                            <option value="">Select Action</option>
                            <option value="remove">Remove from Trial</option>
                            <option value="drop">Mark Dropped</option>
                        </select>
                    </td>

                    <td>
                        <select name="reason_{e(p['user_id'])}" style="width:100%;">
                            <option value="">Select Reason</option>

                            <optgroup label="No Penalty">
                                <option value="health" {"selected" if p.get("reason") == "health" else ""}>Health Issue</option>
                                <option value="family" {"selected" if p.get("reason") == "family" else ""}>Family Emergency</option>
                                <option value="regional" {"selected" if p.get("reason") == "regional" else ""}>Regional Issue</option>
                                <option value="system" {"selected" if p.get("reason") == "system" else ""}>System / Logitech Issue</option>
                            </optgroup>

                            <optgroup label="Soft Penalty">
                                <option value="forgot_nda" {"selected" if p.get("reason") == "forgot_nda" else ""}>Forgot NDA</option>
                                <option value="slow_response" {"selected" if p.get("reason") == "slow_response" else ""}>Slow Response</option>
                                <option value="partial" {"selected" if p.get("reason") == "partial" else ""}>Partial Participation</option>
                            </optgroup>

                            <optgroup label="Hard Penalty">
                                <option value="refused_nda" {"selected" if p.get("reason") == "refused_nda" else ""}>Refused NDA</option>
                                <option value="low_effort" {"selected" if p.get("reason") == "low_effort" else ""}>Low Effort</option>
                                <option value="off_topic" {"selected" if p.get("reason") == "off_topic" else ""}>Off-topic Feedback</option>
                                <option value="ghosted" {"selected" if p.get("reason") == "ghosted" else ""}>Dropped Without Notice</option>
                            </optgroup>
                        </select>

                        <textarea 
                            name="reason_notes_{e(p['user_id'])}"
                            rows="1" 
                            placeholder="Optional details"
                            style="width:100%; margin-top:4px;"
                        >{e(p.get("reason_notes", ""))}</textarea>
                    </td>

                </tr>
            """

    else:
        participants_rows_html += """
                        <tr>
                            <td colspan="8" class="muted small">
                                No participants assigned yet.
                            </td>
                        </tr>
        """

    participants_footer_html = """
    <div style="margin-top:15px;">
        <button type="submit" name="action" value="save_participants">
            Save Participant Tracking
        </button>
    </div>

    <p class="muted small" style="margin-top: 10px;">
        Participant membership and NDA status come from the database. Execution tracking fields are stored separately.
    </p>
    """

    participants_html = participants_template
    participants_html = participants_html.replace(
        "__PARTICIPANTS_ROWS__",
        participants_rows_html
    )
    participants_html = participants_html.replace(
        "__PARTICIPANTS_FOOTER__",
        participants_footer_html
    )

    # =========================================================
    # Survey 1 / Survey 2 type binding
    # NOTE:
    # These must come from the configured round surveys.
    # Do not hardcode survey type IDs here.
    # =========================================================

    from app.db.user_trial_lead import get_round_surveys_basic_stats

    survey_stats = get_round_surveys_basic_stats(round_id)

    survey_1_type_id = None
    survey_2_type_id = None

    # TODO:
    # Bind these from the configured round surveys once the
    # survey mapping rule is finalized.
    #
    # Example intent:
    # - survey_1_type_id = configured survey type for Survey 1
    # - survey_2_type_id = configured survey type for Survey 2
    #
    # For now, fall back only if a default exists.
    survey_1_type_id = round_data.get("DefaultSurveyTypeID")
    survey_2_type_id = round_data.get("DefaultSurveyTypeID")

    # =========================================================
    # Survey 1 Results
    # =========================================================
    survey_1_template = Path(
        "app/templates/ut_lead/ut_lead_project_survey_1.html"
    ).read_text(encoding="utf-8")

    survey_1_content_html = render_survey_results_section(
        round_data=round_data,
        survey_stats=survey_stats,
        upload_status=upload_status,
        project_id=project_id,
        section_title="Survey 1 Results",
        section_subtitle="Basic Metrics",
        survey_type_id=survey_1_type_id,
    )

    survey_1_html = survey_1_template.replace(
        "__SURVEY_1_CONTENT__",
        survey_1_content_html
    )

    # =========================================================
    # Survey 2 Section
    # =========================================================

    survey_2_template = Path(
        "app/templates/ut_lead/ut_lead_project_survey_2.html"
    ).read_text(encoding="utf-8")

    survey_2_content_html = render_survey_results_section(
        round_data=round_data,
        survey_stats=survey_stats,
        upload_status=upload_status,
        project_id=project_id,
        section_title="Survey 2 Results",
        section_subtitle="Basic Metrics",
        survey_type_id=survey_2_type_id,
    )

    survey_2_html = survey_2_template.replace(
        "__SURVEY_2_CONTENT__",
        survey_2_content_html
    )

    # =========================================================
    # Shipping Section
    # =========================================================
    shipping_template = Path(
        "app/templates/ut_lead/ut_lead_project_shipping.html"
    ).read_text(encoding="utf-8")


    shipping_table_html = """
    <table class="data-table">
        <thead>
            <tr>
                <th>Participant</th>
                <th>Address</th>
                <th>Confirmed</th>
                <th>Shipped</th>
                <th>Delivered</th>
            </tr>
        </thead>
        <tbody>
    """

    if participants_data:
        for p in participants_data:

            has_address = bool(p.get("ShippingAddressLine1"))
            confirmed = bool(p.get("ShippingAddressConfirmedAt"))
            shipped = bool(p.get("ShippedAt"))
            delivered = bool(p.get("DeliveredAt"))

            address_display = (
                f"{e(p.get('ShippingAddressLine1', ''))}, {e(p.get('ShippingCity', ''))}"
                if has_address else "—"
            )

            shipping_table_html += f"""
            <tr>
                <td>{e(p.get("name", ""))}</td>
                <td>{address_display}</td>
                <td>{"✔" if confirmed else "—"}</td>
                <td>{"✔" if shipped else "—"}</td>
                <td>{"✔" if delivered else "—"}</td>
            </tr>
            """
    else:
        shipping_table_html += """
            <tr>
                <td colspan="5" class="muted small">
                    No participants.
                </td>
            </tr>
        """

    shipping_table_html += """
        </tbody>
    </table>
    """


    shipping_html = shipping_template.replace(
        "__SHIPPING_TABLE__",
        shipping_table_html
    )

    # =========================================================
    # TEMPLATE INJECTION (MISSING PIECE)
    # =========================================================

    sections_html = sections_template
    sections_html = sections_html.replace("__PARTICIPANTS__", participants_html)
    sections_html = sections_html.replace("__SHIPPING__", shipping_html)
    sections_html = sections_html.replace("__SURVEY_1__", survey_1_html)
    sections_html = sections_html.replace("__SURVEY_2__", survey_2_html)

    body_html += sections_html

    # --------------------------------------------------
    # PRODUCT KPI (Executive Snapshot)
    # --------------------------------------------------

    # NOTE:
    # Replace these with real DB-derived values once wired.
    # For now using placeholders or deterministic aggregates.

    product_kpis = {
        "star_rating": 4.3,
        "nps": 32,
        "ready_for_sales": 84,
        "software_readiness": 78,
    }

    body_html += f"""
        <div class="survey-metric-card">

            <div class="survey-card-header">
                <div class="survey-title">
                    Product Readiness Snapshot
                </div>
                <div class="survey-meta muted small">
                    Executive KPI
                </div>
            </div>

            <div class="survey-metrics-grid">

                <div class="metric-block">
                    <div class="metric-value">
                        {e(product_kpis["star_rating"])}★
                    </div>
                    <div class="metric-label">
                        Avg Star Rating
                    </div>
                </div>

                <div class="metric-block">
                    <div class="metric-value">
                        {e(product_kpis["nps"])}
                    </div>
                    <div class="metric-label">
                        Net Promoter Score
                    </div>
                </div>

                <div class="metric-block">
                    <div class="metric-value">
                        {e(product_kpis["ready_for_sales"])}%
                    </div>
                    <div class="metric-label">
                        Ready for Sales
                    </div>
                </div>

                <div class="metric-block">
                    <div class="metric-value">
                        {e(product_kpis["software_readiness"])}%
                    </div>
                    <div class="metric-label">
                        Software Readiness
                    </div>
                </div>

            </div>
        </div>
    """

    html = base_template
    html = inject_nav(html)
    html = html.replace("{{ title }}", "UT Lead – Project Details")
    html = html.replace("__BODY__", body_html)

    return {"html": html}

def handle_ut_lead_project_post(
    *,
    user_id: str,
    data: dict,
):
    """
    UT Lead – Project Round POST handler
    Handles overview save + lock.
    """

    from app.db.user_roles import get_effective_permission_level
    from app.db.user_trial_lead import (
        get_project_round_by_id,
        update_project_round_overview,
        lock_project_round_overview,
    )

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    permission_level = get_effective_permission_level(user_id)

    # --------------------------------------------------
    # Role Derivation
    # --------------------------------------------------

    is_admin = permission_level >= 90   # adjust threshold if needed
    is_ut_lead = permission_level >= 70

    if not is_ut_lead:
        return {"redirect": "/dashboard"}

    # --------------------------------------------------
    # Validate round
    # --------------------------------------------------
    round_id_raw = data.get("round_id")
    if isinstance(round_id_raw, list):
        round_id_raw = round_id_raw[0]

    if not round_id_raw:
        return {"redirect": "/ut-lead/trials"}

    try:
        round_id = int(round_id_raw)
    except ValueError:
        return {"redirect": "/ut-lead/trials"}

    round_data = get_project_round_by_id(round_id=int(round_id))
    if not round_data:
        return {"redirect": "/ut-lead/trials"}

    print("DEBUG UTLead_UserID:", round_data.get("UTLead_UserID"))
    print("DEBUG session user_id:", user_id)

    # Only assigned UT Lead can edit
    if round_data.get("UTLead_UserID") != user_id:
        print("❌ UTLead mismatch — redirecting to trials")
        return {"redirect": "/ut-lead/trials"}

    action = data.get("action")
    print("ACTION:", action)
    # --------------------------------------------------
    # Overview Lock Enforcement
    # --------------------------------------------------
    if action in ("save_overview", "lock_overview") and round_data.get("OverviewLocked"):
        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # Planning Lock Enforcement
    # --------------------------------------------------
    if action in ("add_survey_link", "lock_planning") and round_data.get("PlanningLocked"):
        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # SAVE OVERVIEW
    # --------------------------------------------------
    if action == "save_overview":

        if round_data.get("OverviewLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        description = (data.get("description") or "").strip()
        start_date = data.get("start_date") or None
        end_date = data.get("end_date") or None
        ship_date = data.get("ship_date") or None
        region = (data.get("region") or "").strip()

        user_scope = (data.get("user_scope") or "").strip()
        if user_scope not in ("Internal", "External", "Hybrid"):
            user_scope = None

        prototype_version = (data.get("prototype_version") or "").strip()
        product_sku = (data.get("product_sku") or "").strip()

        try:
            target_users = int(data.get("target_users") or 0)
        except ValueError:
            target_users = 0

        def _parse_int_or_none(v):
            v = (v or "").strip()
            if v == "":
                return None
            try:
                return int(v)
            except ValueError:
                return None

        min_age = _parse_int_or_none(data.get("min_age"))
        max_age = _parse_int_or_none(data.get("max_age"))

        # Basic sanity: if both present and inverted, swap or null them
        if min_age is not None and max_age is not None and min_age > max_age:
            min_age, max_age = max_age, min_age

        ok = update_project_round_overview(
            round_id=round_id,
            description=description,
            start_date=start_date,
            end_date=end_date,
            ship_date=ship_date,
            region=region,
            user_scope=user_scope,
            target_users=target_users,
            min_age=min_age,
            max_age=max_age,
            prototype_version=prototype_version,
            product_sku=product_sku,
        )

        # If DB refused the update (locked or missing), just bounce back
        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # LOCK OVERVIEW
    # --------------------------------------------------
    if action == "lock_overview":

        if round_data.get("OverviewLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        # --------------------------------------------------
        # Save current form state before locking
        # --------------------------------------------------

        description = (data.get("description") or "").strip()
        start_date = data.get("start_date") or None
        end_date = data.get("end_date") or None
        ship_date = data.get("ship_date") or None
        region = (data.get("region") or "").strip()

        user_scope = (data.get("user_scope") or "").strip()
        if user_scope not in ("Internal", "External", "Hybrid"):
            user_scope = None

        prototype_version = (data.get("prototype_version") or "").strip()
        product_sku = (data.get("product_sku") or "").strip()

        try:
            target_users = int(data.get("target_users") or 0)
        except ValueError:
            target_users = 0

        def _parse_int_or_none(v):
            v = (v or "").strip()
            if v == "":
                return None
            try:
                return int(v)
            except ValueError:
                return None

        min_age = _parse_int_or_none(data.get("min_age"))
        max_age = _parse_int_or_none(data.get("max_age"))

        if min_age is not None and max_age is not None and min_age > max_age:
            min_age, max_age = max_age, min_age

        update_project_round_overview(
            round_id=round_id,
            description=description,
            start_date=start_date,
            end_date=end_date,
            ship_date=ship_date,
            region=region,
            user_scope=user_scope,
            target_users=target_users,
            min_age=min_age,
            max_age=max_age,
            prototype_version=prototype_version,
            product_sku=product_sku,
        )

        # --------------------------------------------------
        # Now lock
        # --------------------------------------------------

        lock_project_round_overview(
            round_id=round_id,
            locked_by_user_id=user_id,
        )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}
    
    # --------------------------------------------------
    # UNLOCK OVERVIEW
    # --------------------------------------------------

    if action == "unlock_overview":

        from app.db.user_trial_lead import unlock_project_round_overview

        # Only admin should unlock (recommended)
        if not is_admin:
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        unlock_project_round_overview(
            round_id=round_id,
        )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # ADD PROFILE CRITERIA
    # --------------------------------------------------

    if action == "add_profile_criteria":

        # Prevent edits if overview locked
        if round_data.get("ProfileLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        operator = data.get("operator")
        profile_uid = data.get("profile_uid")

        if operator in ("INCLUDE", "EXCLUDE") and profile_uid:

            add_round_profile_criteria(
                round_id=round_id,
                profile_uid=profile_uid,
                operator=operator,
            )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}


    # --------------------------------------------------
    # DELETE PROFILE CRITERIA
    # --------------------------------------------------

    if action == "delete_profile_criteria":

        # Prevent edits if overview locked
        if round_data.get("ProfileLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        criteria_id = data.get("criteria_id")

        if criteria_id:
            try:
                delete_round_profile_criteria(
                    round_criteria_id=int(criteria_id)
                )
            except ValueError:
                pass

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}
    
    # --------------------------------------------------
    # ADD SURVEY LINK
    # --------------------------------------------------
    if action == "add_survey_link":

        if round_data.get("PlanningLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        survey_type_id = data.get("survey_type_id")
        survey_edit_link = (data.get("survey_edit_link") or "").strip()
        survey_distribution_link = (data.get("survey_distribution_link") or "").strip()

        if survey_type_id:

            # --------------------------------------------------
            # Prefill format validation (only if provided)
            # --------------------------------------------------
            if survey_distribution_link:

                if "user_token_here" not in survey_distribution_link:
                    return {"redirect": f"/ut-lead/project?round_id={round_id}"}

                if not survey_distribution_link.startswith(
                    "https://docs.google.com/forms/"
                ):
                    return {"redirect": f"/ut-lead/project?round_id={round_id}"}

            print("ADD SURVEY INPUT:", {
                "round_id": round_id,
                "survey_type_id": survey_type_id,
                "edit_link": survey_edit_link,
                "distribution_link": survey_distribution_link
            })

            add_round_survey(
                round_id=round_id,
                survey_type_id=survey_type_id,
                survey_link=survey_edit_link or "",   # 👈 FIX HERE
                distribution_link=survey_distribution_link or None,
                created_by_user_id=user_id,
            )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # DELETE SURVEY LINK
    # --------------------------------------------------

    if action == "delete_survey_link":

        if round_data.get("PlanningLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        survey_id = data.get("survey_id")

        if survey_id:
            from app.db.user_trial_lead import delete_round_survey
            delete_round_survey(
                round_id=round_id,
                survey_id=int(survey_id),
            )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # LOCK PROFILE
    # --------------------------------------------------

    if action == "lock_profile":
        from app.db.user_trial_lead import lock_project_round_profile

        lock_project_round_profile(
            round_id=int(round_id),
            locked_by=user_id,
        )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}


    # --------------------------------------------------
    # UPDATE RECRUITING CONFIG
    # --------------------------------------------------

    if action == "update_recruiting_config":

        from app.db.user_trial_lead import update_recruiting_config

        use_external = data.get("use_external_recruiting_survey") == "1"

        print("UPDATE RECRUITING CONFIG:", {
            "round_id": round_id,
            "use_external": use_external
        })

        update_recruiting_config(
            round_id=int(round_id),
            use_external=use_external,
        )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # OPEN RECRUITING
    # --------------------------------------------------

    if action == "open_recruiting":

        # ------------------------------------------
        # Remove planning lock dependency (your decision)
        # ------------------------------------------

        # ------------------------------------------
        # Enforce External Recruiting Survey Requirement
        # ------------------------------------------

        use_external = round_data.get("UseExternalRecruitingSurvey") in (1, "1", True)

        if use_external:

            from app.db.user_trial_lead import get_round_surveys

            surveys = get_round_surveys(round_id=int(round_id))

            has_recruiting_survey = False

            for s in surveys:
                survey_name = (s.get("SurveyTypeName") or "").lower()

                if "recruit" in survey_name:
                    has_recruiting_survey = True
                    break

            if not has_recruiting_survey:

                print("🚫 BLOCKED: External recruiting survey required but missing")

                return {
                    "redirect": f"/ut-lead/project?round_id={round_id}&error=missing_recruiting_survey"
                }

        # ------------------------------------------
        # OPEN RECRUITING
        # ------------------------------------------

        from app.db.project_rounds import set_project_round_status
        from app.db.project_rounds import get_project_round_by_id

        current = get_project_round_by_id(round_id=round_id)

        from datetime import datetime

        if current:

            # Case 1: Not yet recruiting → full transition
            if current.get("Status") != "Recruiting":
                set_project_round_status(
                    round_id=round_id,
                    status="recruiting",
                    ut_lead_id=user_id,
                )

            # Case 2: Already recruiting BUT start date missing → fix partial state
            elif not current.get("RecruitingStartDate"):

                import mysql.connector
                from app.config.config import DB_CONFIG
                from datetime import datetime

                conn = mysql.connector.connect(**DB_CONFIG)
                try:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        UPDATE project_rounds
                        SET RecruitingStartDate = %s
                        WHERE RoundID = %s
                        """,
                        (datetime.utcnow(), round_id)
                    )
                    conn.commit()
                finally:
                    conn.close()

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}
    
    # --------------------------------------------------
    # SAVE / SYNC PARTICIPANTS (JSON tracking layer)
    # --------------------------------------------------

    if action == "save_participants":

        import json
        from app.db.user_trial_lead import get_round_participants

        base = Path(__file__).resolve().parents[1] / "dev_data" / "trial_projects"
        round_dir = base / f"round_{round_id}"
        round_dir.mkdir(parents=True, exist_ok=True)
        json_path = round_dir / "participants.json"

        db_rows = get_round_participants(int(round_id))
        db_lookup = {row["user_id"]: row for row in db_rows}
        db_user_ids = set(db_lookup.keys())

        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        else:
            json_data = []

        json_lookup = {
            row.get("user_id"): row
            for row in json_data
            if row.get("user_id")
        }

        updated = []

        removed_ids = []

        for uid in db_user_ids:
            db_row = db_lookup[uid]
            existing = json_lookup.get(uid, {})

            participant = {
                "user_id": uid,
                "name": f"{db_row.get('FirstName', '')} {db_row.get('LastName', '')}".strip() or uid,
                "nda_complete": bool(db_row.get("NDAComplete")),

                # keep live survey completion/reminder values from DB function
                "survey_1_complete": bool(db_row.get("Survey1Complete")),
                "survey_2_complete": bool(db_row.get("Survey2Complete")),
                "survey_1_reminders": int(db_row.get("Survey1Reminders") or 0),
                "survey_2_reminders": int(db_row.get("Survey2Reminders") or 0),

                # NEW: structured reason
                "reason": existing.get("reason", ""),
                "reason_notes": existing.get("reason_notes", ""),
            }
            
            reason_value = (data.get(f"reason_{uid}") or "").strip()
            reason_notes_value = (data.get(f"reason_notes_{uid}") or "").strip()

            if reason_value:
                participant["reason"] = reason_value
                participant["reason_notes"] = reason_notes_value

            row_action = data.get(f"row_action_{uid}")

            # ---------------------------------
            # TRACK REMOVALS (DO NOT REDIRECT YET)
            # ---------------------------------
            if row_action == "remove":
                removed_ids.append(uid)

            updated.append(participant)

        # ---------------------------------
        # SAVE JSON FIRST (ALWAYS)
        # ---------------------------------
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(updated, f, indent=4)

        # ---------------------------------
        # THEN HANDLE REPLACEMENT REDIRECT
        # ---------------------------------
        if removed_ids:
            removed_param = ",".join(removed_ids)

            return {
                "redirect": f"/trials/selection?round_id={round_id}&mode=edit&removed_user_ids={removed_param}"
            }

        # ---------------------------------
        # NORMAL SAVE
        # ---------------------------------
        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # LOCK Planning
    # --------------------------------------------------

    if action == "lock_planning":

        if round_data.get("PlanningLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        from app.db.user_trial_lead import (
            get_round_surveys,
            lock_project_round_planning
        )

        from app.db.project_rounds import set_project_round_status

        round_surveys = get_round_surveys(round_id)

        # --------------------------------------------------
        # MVP: No survey link enforcement
        # Planning can be locked regardless of survey setup
        # --------------------------------------------------

        # (intentionally no validation here)

        # --------------------------------------------------
        # Lock planning
        # --------------------------------------------------

        lock_project_round_planning(
            round_id=round_id,
            locked_by_user_id=user_id,
        )

        # --------------------------------------------------
        # Transition lifecycle → approved
        # This makes the trial appear in Upcoming Trials
        # --------------------------------------------------

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # Upload Survey Results
    # --------------------------------------------------

    if action == "upload_survey_results":

        files = data.get("files") or {}
        csv_file = files.get("csv_file")

        project_id = round_data.get("ProjectID")
        survey_type_id = data.get("survey_type_id")

        if not project_id or not survey_type_id or not csv_file:
            return {"redirect": f"/ut-lead/project?round_id={round_id}&upload=error"}

        try:
            csv_bytes = csv_file.read()
            original_filename = getattr(csv_file, "filename", None)
        except Exception:
            return {"redirect": f"/ut-lead/project?round_id={round_id}&upload=error"}

        # --------------------------------------------------
        # Derive survey title from filename
        # Example:
        # Remo - Final Usage - Survey 2 (Responses).csv
        # --------------------------------------------------

        if original_filename:
            survey_title = Path(original_filename).stem.strip()
        else:
            survey_title = "Uploaded Survey"

        from app.services.survey_results_upload import (
            UploadContext,
            UploadError,
            ingest_google_forms_csv,
        )

        try:

            ingest_google_forms_csv(
                ctx=UploadContext(
                    project_id=project_id,
                    round_id=round_id,
                    survey_type_id=survey_type_id,
                    survey_title=survey_title,
                    uploaded_by_user_id=user_id,
                ),
                csv_bytes=csv_bytes,
                original_filename=original_filename,
            )

        except UploadError as e:

            print("UPLOAD ERROR:", str(e))

            return {
                "redirect": f"/ut-lead/project?round_id={round_id}&upload=error"
            }

        return {
            "redirect": f"/ut-lead/project?round_id={round_id}&upload=success"
        }
    
    # --------------------------------------------------
    # Default Fallback (Critical)
    # --------------------------------------------------

    # If execution reaches here, no action matched.
    # Never fall through silently.
    return {"redirect": f"/ut-lead/project?round_id={round_id}"}