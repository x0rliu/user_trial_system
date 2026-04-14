# handler/user_trial_lead.py

from app.db.user_trial_lead import get_all_project_rounds_for_ut_lead
from app.services.user_trial_lead_status import derive_lifecycle_status
from app.utils.html_escape import escape_html as e

def _fmt_name(first, last):
    if first or last:
        return f"{first or ''} {last or ''}".strip()
    return "—"

def _fmt(val):
    return val if val not in (None, "", "0000-00-00") else "—"




def render_ut_lead_trials_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict,
):
    project_rounds = get_all_project_rounds_for_ut_lead()

    # -------------------------
    # Filters (explicit state)
    # -------------------------
    ut_lead_filter = query_params.get("ut_lead", ["me"])[0]
    status_filter = query_params.get("status", [""])[0]

    filtered_rounds = []

    for r in project_rounds:

        # -------------------------
        # UT Lead filter
        # -------------------------
        if ut_lead_filter != "all":
            if str(r.get("UTLead_UserID")) != str(user_id):
                continue

        # -------------------------
        # Status filter (raw DB field)
        # -------------------------
        if status_filter:
            if (r.get("Status") or "").lower() != status_filter.lower():
                continue

        filtered_rounds.append(r)

    project_rounds = filtered_rounds

    rows_html = []

    for r in project_rounds:
        rows_html.append(f"""
            <tr>
                <td>
                    <a href="/ut-lead/project?round_id={e(r['RoundID'])}">
                        {e(_fmt(r['RoundName']))}
                    </a>
                </td>
                <td>{e(_fmt(r['RoundNumber']))}</td>
                <td>{e(_fmt_name(r.get('UTLead_FirstName'), r.get('UTLead_LastName')))}</td>
                <td>
                    {derive_lifecycle_status(r)}
                </td>
                <td>{e(_fmt(r['ShipDate']))}</td>
                <td>{e(_fmt(r['StartDate']))}</td>
                <td>{e(_fmt(r['EndDate']))}</td>
                <td>{e(_fmt(r['Region']))}</td>
            </tr>
        """)

    body_html = f"""
        <h2>User Trial Lead – Trials</h2>

        <table class="ut-lead-table">
            <thead>
                <tr>
                    <th>Project / Round</th>
                    <th>Round</th>

                    <th>
                        UT Lead
                        <form method="get" style="display:inline;">
                            <select name="ut_lead" onchange="this.form.submit()">
                                <option value="me" {"selected" if ut_lead_filter != "all" else ""}>My</option>
                                <option value="all" {"selected" if ut_lead_filter == "all" else ""}>All</option>
                            </select>

                            <input type="hidden" name="status" value="{e(status_filter)}">
                        </form>
                    </th>

                    <th>
                        Status
                        <form method="get" style="display:inline;">
                            <select name="status" onchange="this.form.submit()">
                                <option value="">All</option>
                                <option value="Draft" {"selected" if status_filter == "Draft" else ""}>Draft</option>
                                <option value="Under Planning" {"selected" if status_filter == "Under Planning" else ""}>Planning</option>
                                <option value="Ongoing" {"selected" if status_filter == "Ongoing" else ""}>Ongoing</option>
                                <option value="Closed" {"selected" if status_filter == "Closed" else ""}>Closed</option>
                            </select>

                            <input type="hidden" name="ut_lead" value="{e(ut_lead_filter)}">
                        </form>
                    </th>

                    <th>Ship Date</th>
                    <th>Start</th>
                    <th>End</th>
                    <th>Region</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows_html)}
            </tbody>
        </table>
    """

    html = base_template
    html = inject_nav(html)
    html = html.replace("{{ title }}", "UT Lead – Trials")
    html = html.replace("{{ body }}", body_html)

    return {"html": html}
