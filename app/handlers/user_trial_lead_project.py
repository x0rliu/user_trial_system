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
        country_options_html += f'<option value="{c["CountryCode"]}">{c["CountryName"]}</option>'

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
    <details class="ut-lead-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Product Identity</strong>
        </summary>
        <div class="ut-lead-section-body">

            <div class="overview-card">

                <div class="overview-grid">

                    <div class="overview-field">
                        <div class="overview-label">Project Name</div>
                        <div class="overview-value">{round_data.get("ProjectName") or "—"}</div>
                    </div>

                    <div class="overview-field">
                        <div class="overview-label">Business Group</div>
                        <div class="overview-value">{round_data.get("BusinessGroup") or "—"}</div>
                    </div>

                    <div class="overview-field">
                        <div class="overview-label">Market Name</div>
                        <div class="overview-value">{round_data.get("MarketName") or "—"}</div>
                    </div>

                    <div class="overview-field">
                        <div class="overview-label">Sub Group</div>
                        <div class="overview-value">{round_data.get("BusinessSubGroup") or "—"}</div>
                    </div>

                    <div class="overview-field">
                        <div class="overview-label">Product Type</div>
                        <div class="overview-value">{round_data.get("ProductType") or "—"}</div>
                    </div>

                    <div class="overview-field">
                        <div class="overview-label">Product SKU</div>
                        <div class="overview-value">{round_data.get("ProductSKU") or "—"}</div>
                    </div>

                </div>

                <div class="overview-full-width">
                    <div class="overview-label">Project Description</div>
                    <div class="overview-value muted small">
                        {round_data.get("ProjectDescription") or "—"}
                    </div>
                </div>

            </div>

        </div>
    </details>
    """


    # =========================================================
    # ROUND CONFIGURATION SECTION
    # =========================================================

    overview_locked = bool(round_data.get("OverviewLocked"))

    round_config_section = f"""
    <details class="ut-lead-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Round Configuration</strong>
            <span class="muted small">
                {"— Locked" if overview_locked else "— Unlocked"}
            </span>
        </summary>
        <div class="ut-lead-section-body">
    """

    if not overview_locked:

        round_config_section += f"""
    <form method="post" action="/ut-lead/project" class="round-config-form">
    <input type="hidden" name="round_id" value="{round_data['RoundID']}">

    <div class="section-header">Dates</div>
    <div class="form-grid">

    <div class="form-field full">
    <label>Description</label>
    <textarea name="description" rows="2">{round_data.get("Description") or ""}</textarea>
    </div>

    <div class="form-field">
    <label>Start Date</label>
    <input type="date" id="start_date" name="start_date"
    value="{round_data.get("StartDate") or ""}">
    </div>

    <div class="form-field">
    <label>End Date</label>
    <input type="date" id="end_date" name="end_date"
    value="{round_data.get("EndDate") or ""}">
    </div>

    <div class="form-field">
    <label>Ship Date</label>
    <input type="date" name="ship_date"
    value="{round_data.get("ShipDate") or ""}">
    </div>

    </div>

    <div class="section-header">User Scope</div>
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
    value="{round_data.get("TargetUsers") or 30}">
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

    <div class="section-header">Product Details</div>
    <div class="form-grid">

    <div class="form-field">
    <label>Prototype Version</label>
    <input type="text" name="prototype_version"
    value="{round_data.get("PrototypeVersion") or "pb1"}">
    </div>

    <div class="form-field">
    <label>FW Version</label>
    <input type="text" name="product_sku"
    value="{round_data.get("ProductSKU") or ""}">
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

    <button type="button" id="add_country_btn">
    + Add Country
    </button>

    </div>

    <input type="hidden" id="region_input" name="region"
    value="{round_data.get("Region") or ""}">

    </div>

    </div>

    <div class="form-actions">
    <button type="submit" name="action" value="save_overview">Save</button>
    <button type="submit" name="action" value="lock_overview">Lock Overview</button>
    </div>

    </form>

    <script>
    document.addEventListener("DOMContentLoaded", function () {{

    const start = document.getElementById("start_date");
    const end = document.getElementById("end_date");

    if (!start || !end) return;

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

    }});
    </script>
    <script>

    document.addEventListener("DOMContentLoaded", function() {{

    const container = document.getElementById("country-chip-container");
    const addBtn = document.getElementById("add_country_btn");
    const select = document.getElementById("country_select");
    const hidden = document.getElementById("region_input");

    if (!container || !addBtn || !select || !hidden) return;

    let countries = [];

    if (hidden.value) {{
    hidden.value.split(",").forEach(code => {{
    countries.push({{ code: code, name: code }});
    }});
    }}

    function renderCountries(){{

    container.innerHTML = "";

    countries.forEach(country => {{

    const chip = document.createElement("div");
    chip.className = "country-chip";

    chip.innerHTML = `
    <span>${{country.name}}</span>
    <button type="button" data-code="${{country.code}}">✕</button>
    `;

    container.appendChild(chip);

    }});

    hidden.value = countries.map(c => c.code).join(",");

    }}

    addBtn.addEventListener("click", function(){{

    const code = select.value;
    const name = select.options[select.selectedIndex].text;

    if (!code) return;

    if (!countries.some(c => c.code === code)){{
    countries.push({{code: code, name: name}});
    }}

    renderCountries();

    }});

    container.addEventListener("click", function(e){{

    if(e.target.tagName !== "BUTTON") return;

    const code = e.target.dataset.code;

    countries = countries.filter(c => c.code !== code);

    renderCountries();

    }});

    renderCountries();

    }});

    </script>
    """

    else:

        round_config_section += f"""
            <div class="overview-card">
                <div class="overview-grid">
                    <div class="overview-field">
                        <div class="overview-label">Start Date</div>
                        <div class="overview-value">{round_data.get('StartDate') or '—'}</div>
                    </div>

                    <div class="overview-field">
                        <div class="overview-label">End Date</div>
                        <div class="overview-value">{round_data.get('EndDate') or '—'}</div>
                    </div>

                    <div class="overview-field">
                        <div class="overview-label">Region</div>
                        <div class="overview-value">{round_data.get('Region') or '—'}</div>
                    </div>
                </div>
            </div>
        """

        # Admin Unlock Button
        if get_effective_permission_level(user_id) >= 90:
            round_config_section += f"""
                <form method="post" action="/ut-lead/project" style="margin-top:10px;">
                    <input type="hidden" name="round_id" value="{round_data['RoundID']}">
                    <button type="submit" name="action" value="unlock_overview">
                        Unlock Overview
                    </button>
                </form>
            """

    round_config_section += """
        </div>
    </details>
    """


    # =========================================================
    # WANTED USER PROFILE SECTION
    # =========================================================

    criteria_rows = get_round_profile_criteria(int(round_data['RoundID']))

    wanted_profile_section = f"""
    <details class="ut-lead-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Wanted User Profile</strong>
            <span class="muted small">
                {"— Locked" if profile_locked else "— Editable"}
            </span>
        </summary>

        <div class="ut-lead-section-body">
    """

    wanted_profile_section += "<div class='overview-card'>"

    wanted_profile_section += """
    <table class="ut-lead-table">
    <thead>
    <tr>
    <th>Operator</th>
    <th>Category</th>
    <th>Value</th>
    """ + ("" if profile_locked else "<th>Action</th>") + """
    </tr>
    </thead>
    <tbody>
    """

    # ---------------------------------
    # Existing Criteria Rows
    # ---------------------------------

    for c in criteria_rows:

        wanted_profile_section += f"""
        <tr>
            <td>{c['Operator']}</td>
            <td>{c['CategoryName']}</td>
            <td>{c['LevelDescription']}</td>
        """

        if not profile_locked:
            wanted_profile_section += f"""
            <td>
                <form method="post" action="/ut-lead/project" style="display:inline;">
                    <input type="hidden" name="round_id" value="{round_data['RoundID']}">
                    <input type="hidden" name="criteria_id" value="{c['RoundCriteriaID']}">
                    <button type="submit" name="action" value="delete_profile_criteria">
                        Delete
                    </button>
                </form>
            </td>
            """

        wanted_profile_section += "</tr>"


    # ---------------------------------
    # Add Criteria Row
    # ---------------------------------

    if not profile_locked:

        from app.db.user_profiles import get_profile_categories
        categories = get_profile_categories()

        wanted_profile_section += f"""
    <tr>
    <form method="post" action="/ut-lead/project">
    <input type="hidden" name="round_id" value="{round_data['RoundID']}">

    <td>
    <select name="operator" required>
    <option value="INCLUDE">Include</option>
    <option value="EXCLUDE">Exclude</option>
    </select>
    </td>

    <td>
    <select name="category_id" id="profile_category" required>
    <option value="">Select Category</option>
    """

        for cat in categories:
            wanted_profile_section += f"""
    <option value="{cat['CategoryID']}">{cat['CategoryName']}</option>
    """

        wanted_profile_section += """
    </select>
    </td>

    <td>
    <select name="profile_uid" id="profile_level" required>
    <option value="">Select Level</option>
    </select>
    </td>

    <td>
    <button type="submit" name="action" value="add_profile_criteria">
    Add
    </button>
    </td>

    </form>
    </tr>
    """

    wanted_profile_section += """
    </tbody>
    </table>
    """

    wanted_profile_section += "</div>"

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

    # ---------------------------------
    # Lock Button
    # ---------------------------------

    if not profile_locked:

        wanted_profile_section += f"""
    <form method="post" action="/ut-lead/project" style="margin-top:10px;">
    <input type="hidden" name="round_id" value="{round_data['RoundID']}">
    <button type="submit" name="action" value="lock_profile">
    Lock Profile
    </button>
    </form>
    """

    # --------------------------------------------------
    # Render (read-only placeholders)
    # --------------------------------------------------
    body_html = f"""
        <div class="breadcrumb">
            <a href="/ut-lead/trials">← Back to All Trials</a>
        </div>

        <h2>{round_data['RoundName']}</h2>

        {product_identity_section}
        {round_config_section}
        {wanted_profile_section}
    """

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
    <details class="ut-lead-section" open>
        <summary class="ut-lead-section-summary">
            <strong>Planning – Survey Links</strong>
            <span class="muted small">
                {"— Locked" if planning_locked else "— Unlocked"}
            </span>
        </summary>
        <div class="ut-lead-section-body">
    """

    # Existing Surveys
    if round_surveys:

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

        for s in round_surveys:

            survey_type = s.get("SurveyTypeName") or "—"
            survey_link = s.get("SurveyLink") or "#"
            added_by = s.get("CreatedBy") or "—"
            created_at = s.get("CreatedAt")

            if created_at:
                try:
                    created_at_str = created_at.strftime("%Y-%m-%d")
                except Exception:
                    created_at_str = str(created_at)
            else:
                created_at_str = "—"

            target = "Participant"  # placeholder for now

            distribution_link = s.get("DistributionLink")

            if distribution_link:
                distribution_html = f'<a href="{distribution_link}" target="_blank">Participant Facing Link</a>'
            else:
                distribution_html = '<span class="muted small">—</span>'

            delete_column_html = ""

            if not planning_locked:
                delete_column_html = f"""
                    <td>
                        <form method="post" action="/ut-lead/project" style="display:inline;">
                            <input type="hidden" name="round_id" value="{round_data['RoundID']}">
                            <input type="hidden" name="survey_id" value="{s.get('SurveyID')}">
                            <button type="submit" name="action" value="delete_survey_link">
                                Delete
                            </button>
                        </form>
                    </td>
                """

            links_section += f"""
            <tr>
                <td>{survey_type}</td>
                <td>
                    <a href="{survey_link}" target="_blank" rel="noopener noreferrer">
                        Product Team Link
                    </a>
                </td>
                <td>{distribution_html}</td>
                <td>{target}</td>
                <td>{added_by}</td>
                <td>{created_at_str}</td>
                {delete_column_html}
            </tr>
            """
        links_section += """
                </tbody>
            </table>
        """

    else:
        links_section += "<div class='muted small'>No surveys configured yet.</div>"


    # Add Form (Only if unlocked)
    if not planning_locked:

        from app.db.user_trial_lead import get_survey_types
        survey_types = get_survey_types()

        links_section += f"""
            <hr style="margin:15px 0;">

            <!-- Add Survey Form -->
            <form method="post" action="/ut-lead/project" style="margin-bottom:15px;">
                <input type="hidden" name="round_id" value="{round_data['RoundID']}">

                <label>Survey Type</label><br>
                <select name="survey_type_id" required>
                    <option value="">-- Select Survey Type --</option>
        """

        for st in survey_types:
            links_section += f"""
                    <option value="{st['SurveyTypeID']}">
                        {st['SurveyTypeName']}
                    </option>
            """

        links_section += f"""
                </select><br><br>

                <label>Survey Edit Link (Internal Review)</label><br>
                <input type="url" name="survey_edit_link" style="width:100%;" required><br><br>

                <label>Survey Distribution Link (Participants)</label><br>
                <input type="url" name="survey_distribution_link" style="width:100%;"><br>
                <div class="muted small">
                    Required for Recruiting, OOBE, and Experience/KPI surveys.
                    Must include <code>user_token_here</code>.
                </div><br>

                <button type="submit" name="action" value="add_survey_link">
                    Add Survey
                </button>
            </form>

            <!-- Lock Planning Form -->
            <form method="post" action="/ut-lead/project">
                <input type="hidden" name="round_id" value="{round_data['RoundID']}">

                <button type="submit" name="action" value="lock_planning">
                    Lock Planning
                </button>
            </form>
        """

    else:
        links_section += f"""
            <div class="muted small" style="margin-top:10px;">
                Planning locked at {planning_locked_at}
                by {planning_locked_display}
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

    body_html += f"""
        <details class="ut-lead-section" open>
            <summary class="ut-lead-section-summary">
                <strong>Recruiting</strong>
                <span class="muted small">
                    {"— Live" if recruiting_started else "— Not Open"}
                </span>
            </summary>

            <div class="ut-lead-section-body">
    """

    if planning_locked and not recruiting_started:

        body_html += f"""
            <form method="post" action="/ut-lead/project">
                <input type="hidden" name="round_id" value="{round_data['RoundID']}">

                <button type="submit" name="action" value="open_recruiting">
                    Open Recruiting
                </button>
            </form>
        """

    elif recruiting_started:

        body_html += f"""
            <div class="overview-card">
                <div class="overview-field">
                    <div class="overview-label">Recruiting Started</div>
                    <div class="overview-value">
                        {round_data.get("RecruitingStartDate")}
                    </div>
                </div>
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
    # =========================================================

    def _get_participant_json_path(round_id: int) -> Path:
        base = Path(__file__).resolve().parents[1] / "dev_data" / "trial_projects"
        round_dir = base / f"round_{round_id}"
        round_dir.mkdir(parents=True, exist_ok=True)
        return round_dir / "participants.json"

    json_path = _get_participant_json_path(round_id)

    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            participants_data = json.load(f)
    else:

        from app.db.user_trial_lead import get_round_participants

        db_rows = get_round_participants(int(round_id))

        participants_data = []

        for row in db_rows:
            nda_complete = row.get("RoundNDA_SignedAt") is not None

            participants_data.append({
                "user_id": row["user_id"],
                "name": f"{row['FirstName']} {row['LastName']}".strip(),
                "nda_complete": nda_complete,
                "survey_1_complete": False,
                "survey_2_complete": False,
                "survey_1_reminders": 0,
                "survey_2_reminders": 0,
                "notes": ""
            })

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(participants_data, f, indent=4)


    # --------------------------------------------------
    # Participants Section (Dynamic)
    # --------------------------------------------------

    body_html += f"""
        <details class="ut-lead-section" open>
            <summary class="ut-lead-section-summary">
                <strong>Participants</strong>
                <span class="muted small"> — Execution Tracking</span>
            </summary>

            <div class="ut-lead-section-body">

                <form method="post" action="/ut-lead/project">

                    <input type="hidden" name="round_id" value="{round_data['RoundID']}">

                    <table class="data-table" id="participants-table">
                        <thead>
                            <tr>
                                <th>Participant</th>

                                <th>
                                    NDA
                                    <span class="column-filter-icon" data-filter="nda" title="Toggle Hide Completed">
                                        ⛃
                                    </span>
                                </th>

                                <th>
                                    Survey 1
                                    <span class="column-filter-icon" data-filter="s1" title="Toggle Hide Completed">
                                        ⛃
                                    </span>
                                </th>

                                <th>Reminders</th>

                                <th>
                                    Survey 2
                                    <span class="column-filter-icon" data-filter="s2" title="Toggle Hide Completed">
                                        ⛃
                                    </span>
                                </th>

                                <th>Reminders</th>
                                <th>Action</th>
                                <th>Notes</th>
                            </tr>
                        </thead>
                        <tbody>
    """

    if participants_data:
        for p in participants_data:

            nda_complete = "true" if p["nda_complete"] else "false"
            s1_complete = "true" if p["survey_1_complete"] else "false"
            s2_complete = "true" if p["survey_2_complete"] else "false"

            body_html += f"""
                <tr
                    data-nda-complete="{nda_complete}"
                    data-s1-complete="{s1_complete}"
                    data-s2-complete="{s2_complete}"
                >
                    <td>{p['name']}</td>

                    <td>{"✔" if p["nda_complete"] else "—"}</td>

                    <td>
                        <input type="checkbox"
                            name="survey1_{p['user_id']}"
                            {"checked" if p["survey_1_complete"] else ""}>
                    </td>

                    <td class="muted small">
                        {p["survey_1_reminders"]}
                    </td>

                    <td>
                        <input type="checkbox"
                            name="survey2_{p['user_id']}"
                            {"checked" if p["survey_2_complete"] else ""}>
                    </td>

                    <td class="muted small">
                        {p["survey_2_reminders"]}
                    </td>

                    <td>
                        <select name="row_action_{p['user_id']}">
                            <option value="">Select Action</option>
                            <option value="remove">Remove from Trial</option>
                            <option value="drop">Mark Dropped</option>
                        </select>
                    </td>

                    <td>
                        <textarea 
                            name="notes_{p['user_id']}" 
                            rows="1" 
                            style="width:100%;"
                        >{p.get("notes") or ""}</textarea>
                    </td>

                </tr>
            """

    else:
        body_html += """
                        <tr>
                            <td colspan="8" class="muted small">
                                No participants assigned yet.
                            </td>
                        </tr>
        """

    body_html += """
                    </tbody>
                </table>

                <div style="margin-top:15px;">
                    <button type="submit" name="action" value="save_participants">
                        Save Participant Tracking
                    </button>
                </div>

                <script>
                document.addEventListener("DOMContentLoaded", function () {

                    // Toggle state per column
                    const filters = {
                        nda: false,
                        s1: false,
                        s2: false
                    };

                    function applyParticipantFilters() {

                        const rows = document.querySelectorAll("#participants-table tbody tr");

                        rows.forEach((row) => {
                            const nda = row.dataset.ndaComplete === "true";
                            const s1 = row.dataset.s1Complete === "true";
                            const s2 = row.dataset.s2Complete === "true";

                            let hide = false;

                            if (filters.nda && nda) hide = true;
                            if (filters.s1 && s1) hide = true;
                            if (filters.s2 && s2) hide = true;

                            row.style.display = hide ? "none" : "";
                        });
                    }

                    // Click handler for icons in table headers
                    document.querySelectorAll(".column-filter-icon").forEach((el) => {
                        el.addEventListener("click", function () {
                            const type = this.dataset.filter;

                            if (!type || !(type in filters)) return;

                            filters[type] = !filters[type];
                            this.classList.toggle("active", filters[type]);

                            applyParticipantFilters();
                        });
                    });

                });
                </script>


                <p class="muted small" style="margin-top: 10px;">
                    Live data bound from project_nda + survey_distribution.
                </p>
                
                </form>
            </div>
        </details>"""

    # =========================================================
    # Survey Results (Step 1 + Step 2)
    # =========================================================

    from app.db.user_trial_lead import get_round_participants
    from app.db.survey_stats import (
        get_round_surveys_basic_stats,
    )
    from app.db.survey_kpis import get_round_product_kpis

    # Total participants (SOT)
    participants = get_round_participants(int(round_data["RoundID"]))
    total_participants = len(participants)

    # Survey stats (SOT from DB)
    survey_stats = get_round_surveys_basic_stats(
        round_id=int(round_data["RoundID"]),
    )

    # Product KPIs (derived from answers)
    product_kpis = get_round_product_kpis(
        round_id=int(round_data["RoundID"]),
    )

    body_html += f"""    
        <details class="ut-lead-section" open>
            <summary class="ut-lead-section-summary">
                <strong>Survey Results</strong>
                <span class="muted small"> — Step 1–2 (Basic Metrics)</span>
            </summary>

            <div class="ut-lead-section-body">

                <!-- Upload Bar -->
                <div class="survey-upload-bar">
                    <form method="post"
                        action="/ut-lead/project"
                        enctype="multipart/form-data"
                        style="display:flex; align-items:center; gap:16px; flex-wrap:wrap;">

                        <input type="hidden" name="action" value="upload_survey_results">
                        <input type="hidden" name="project_id" value="{project_id}">
                        <input type="hidden" name="round_id" value="{round_data['RoundID']}">
                        <input type="hidden" name="survey_type_id" value="UTSurveyType0006">

                        <label style="white-space:nowrap;">
                            Upload CSV
                        </label>

                        <input type="file"
                            name="csv_file"
                            accept=".csv"
                            required>

                        <button type="submit">
                            Upload
                        </button>
                    </form>
                </div>

                <!-- Survey Name Header (above Product Readiness) -->
                {"<h2 style='margin:20px 0 20px 0;'>" + survey_stats[0]['SurveyTitle'] + "</h2>" if survey_stats else ""}
    """


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
                        {product_kpis["star_rating"]}★
                    </div>
                    <div class="metric-label">
                        Avg Star Rating
                    </div>
                </div>

                <div class="metric-block">
                    <div class="metric-value">
                        {product_kpis["nps"]}
                    </div>
                    <div class="metric-label">
                        Net Promoter Score
                    </div>
                </div>

                <div class="metric-block">
                    <div class="metric-value">
                        {product_kpis["ready_for_sales"]}%
                    </div>
                    <div class="metric-label">
                        Ready for Sales
                    </div>
                </div>

                <div class="metric-block">
                    <div class="metric-value">
                        {product_kpis["software_readiness"]}%
                    </div>
                    <div class="metric-label">
                        Software Readiness
                    </div>
                </div>

            </div>
        </div>
    """

    # --------------------------------------------------
    # Render Basic Survey Metrics
    # --------------------------------------------------

    if survey_stats:

        for s in survey_stats:

            completion_rate = 0
            if s["total_participants"] > 0:
                completion_rate = round(
                    (s["completed_count"] / s["total_participants"]) * 100,
                    1
                )

            body_html += f"""
                <div class="survey-metric-card">

                    <div class="survey-card-header">
                        <div class="survey-title">
                            Trial Execution Snapshot
                        </div>
                        <div class="survey-meta muted small">
                            SurveyID: {s['SurveyID']}
                        </div>
                    </div>

                    <div class="survey-metrics-grid">

                        <div class="metric-block">
                            <div class="metric-value">
                                {completion_rate}%
                            </div>
                            <div class="metric-label">
                                Completion Rate
                            </div>
                        </div>

                        <div class="metric-block">
                            <div class="metric-value">
                                {s['completed_count']} / {s['total_participants']}
                            </div>
                            <div class="metric-label">
                                Completed
                            </div>
                        </div>

                        <div class="metric-block">
                            <div class="metric-value">
                                {s['total_answers']}
                            </div>
                            <div class="metric-label">
                                Total Answer Rows
                            </div>
                        </div>

                    </div>
                </div>
            """

    else:
        body_html += """
            <div class="muted small">
                No surveys uploaded yet.
            </div>
        """

    body_html += """
            </div>
        </details>
    """


    html = base_template
    html = inject_nav(html)
    html = html.replace("{{ title }}", "UT Lead – Project Details")
    html = html.replace("{{ body }}", body_html)

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

        if survey_type_id and survey_edit_link:

            # --------------------------------------------------
            # Prefill format validation (if provided)
            # --------------------------------------------------
            if survey_distribution_link:

                if "user_token_here" not in survey_distribution_link:
                    # Refuse invalid format
                    return {"redirect": f"/ut-lead/project?round_id={round_id}"}

                if not survey_distribution_link.startswith(
                    "https://docs.google.com/forms/"
                ):
                    return {"redirect": f"/ut-lead/project?round_id={round_id}"}

            add_round_survey(
                round_id=round_id,
                survey_type_id=survey_type_id,
                survey_link=survey_edit_link,
                distribution_link=survey_distribution_link,
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
    # OPEN RECRUITING
    # --------------------------------------------------

    if action == "open_recruiting":

        if not round_data.get("PlanningLocked"):
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        from app.db.project_rounds import set_project_round_status

        set_project_round_status(
            round_id=round_id,
            status="recruiting",
            ut_lead_id=user_id,
        )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}
    
    # --------------------------------------------------
    # SAVE / SYNC PARTICIPANTS (JSON tracking layer)
    # --------------------------------------------------

    if action == "save_participants":

        from pathlib import Path
        import json
        from app.db.user_trial_lead import get_round_participants

        # --------------------------------------------------
        # Build JSON path
        # --------------------------------------------------

        base = Path(__file__).resolve().parents[1] / "dev_data" / "trial_projects"
        round_dir = base / f"round_{round_id}"
        round_dir.mkdir(parents=True, exist_ok=True)
        json_path = round_dir / "participants.json"
        # --------------------------------------------------
        # Pull authoritative DB membership snapshot
        # --------------------------------------------------

        db_rows = get_round_participants(int(round_id))

        db_user_ids = set([row["user_id"] for row in db_rows])

        # --------------------------------------------------
        # Load existing JSON (if exists)
        # --------------------------------------------------

        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        else:
            json_data = []

        json_user_ids = set([p["user_id"] for p in json_data])

        # --------------------------------------------------
        # If membership mismatch → rebuild JSON entirely
        # --------------------------------------------------

        if db_user_ids != json_user_ids:

            rebuilt = []

            for row in db_rows:
                nda_complete = row.get("RoundNDA_SignedAt") is not None

                rebuilt.append({
                    "user_id": row["user_id"],
                    "name": f"{row['FirstName']} {row['LastName']}".strip(),
                    "nda_complete": nda_complete,
                    "survey_1_complete": False,
                    "survey_2_complete": False,
                    "survey_1_reminders": 0,
                    "survey_2_reminders": 0,
                    "notes": ""
                })

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(rebuilt, f, indent=4)

            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        # --------------------------------------------------
        # Membership identical → persist tracking edits only
        # --------------------------------------------------

        updated = []

        # Build DB lookup for fast access
        db_lookup = {row["user_id"]: row for row in db_rows}

        for participant in json_data:

            uid = participant["user_id"]

            db_row = db_lookup.get(uid)
            if not db_row:
                continue

            # -------------------------------
            # Authoritative NDA from DB
            # -------------------------------
            participant["nda_complete"] = (
                db_row.get("RoundNDA_SignedAt") is not None
            )

            # -------------------------------
            # Checkboxes (tracking only)
            # -------------------------------
            survey1_checked = f"survey1_{uid}" in data
            survey2_checked = f"survey2_{uid}" in data

            participant["survey_1_complete"] = survey1_checked
            participant["survey_2_complete"] = survey2_checked

            # -------------------------------
            # Notes (JSON tracking only)
            # -------------------------------
            notes_value = (data.get(f"notes_{uid}") or "").strip()
            participant["notes"] = notes_value

            # -------------------------------
            # Row-level actions
            # -------------------------------
            row_action = data.get(f"row_action_{uid}")

            if row_action == "remove":
                from app.db.project_participants import remove_project_participant
                remove_project_participant(round_id=round_id, user_id=uid)
                continue  # skip adding to updated list (membership will rebuild)

            if row_action == "drop":
                participant["notes"] = (
                    participant.get("notes", "") + " [MARKED DROPPED]"
                )

            updated.append(participant)


        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(updated, f, indent=4)

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

        TOKEN_REQUIRED_TYPES = {
            "Recruiting",
            "First Impressions",
            "Experience",
        }

        for s in round_surveys:

            survey_type_name = s.get("SurveyTypeName")
            distribution_link = s.get("DistributionLink")

            if survey_type_name in TOKEN_REQUIRED_TYPES:

                if not distribution_link:
                    return {"redirect": f"/ut-lead/project?round_id={round_id}"}

                if "user_token_here" not in distribution_link:
                    return {"redirect": f"/ut-lead/project?round_id={round_id}"}

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

        set_project_round_status(
            round_id=round_id,
            status="approved",
            ut_lead_id=user_id,
        )

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}

    # --------------------------------------------------
    # Upload Survey Results
    # --------------------------------------------------

    if action == "upload_survey_results":

        from pathlib import Path

        files = data.get("files") or {}
        csv_file = files.get("csv_file")

        project_id = round_data.get("ProjectID")
        survey_type_id = data.get("survey_type_id")

        if not project_id or not survey_type_id or not csv_file:
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

        try:
            csv_bytes = csv_file.read()
            original_filename = getattr(csv_file, "filename", None)
        except Exception:
            return {"redirect": f"/ut-lead/project?round_id={round_id}"}

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

        return {"redirect": f"/ut-lead/project?round_id={round_id}"}
    # --------------------------------------------------
    # Default Fallback (Critical)
    # --------------------------------------------------

    # If execution reaches here, no action matched.
    # Never fall through silently.
    return {"redirect": f"/ut-lead/project?round_id={round_id}"}

