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


def _status_slug(label: str) -> str:
    normalized = str(label or "").strip().lower()

    if normalized == "ongoing":
        return "ongoing"
    if normalized == "under planning":
        return "planning"
    if normalized == "upcoming":
        return "upcoming"
    if normalized == "completed":
        return "completed"
    if normalized == "withdrawn":
        return "withdrawn"

    return "draft"


def _status_class(label: str) -> str:
    return f"ut-lead-status-pill-{_status_slug(label)}"


def _selected(option_value: str, current_value: str) -> str:
    return "selected" if option_value == current_value else ""


def _round_label(row: dict) -> str:
    round_name = _fmt(row.get("RoundName"))
    round_number = _fmt(row.get("RoundNumber"))

    if round_number == "—":
        return round_name

    return f"{round_name} · Round {round_number}"


def render_ut_lead_trials_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict,
):
    # -------------------------
    # Filters (explicit GET state)
    # -------------------------
    ut_lead_filter = str(query_params.get("ut_lead", ["me"])[0] or "me").strip().lower()
    if ut_lead_filter not in {"me", "all"}:
        ut_lead_filter = "me"

    status_filter = str(query_params.get("status", [""])[0] or "").strip().lower()
    if status_filter not in {"", "draft", "planning", "ongoing", "upcoming", "completed", "withdrawn"}:
        status_filter = ""

    include_terminal_statuses = status_filter in {"completed", "withdrawn"}
    all_rounds = get_all_project_rounds_for_ut_lead(
        status="all" if include_terminal_statuses else None
    )

    scoped_rounds = []
    for row in all_rounds:
        if ut_lead_filter != "all" and str(row.get("UTLead_UserID")) != str(user_id):
            continue
        scoped_rounds.append(row)

    filtered_rounds = []
    lifecycle_counts = {
        "draft": 0,
        "planning": 0,
        "ongoing": 0,
        "upcoming": 0,
        "completed": 0,
        "withdrawn": 0,
    }

    for row in scoped_rounds:
        lifecycle_status = derive_lifecycle_status(row)
        lifecycle_slug = _status_slug(lifecycle_status)
        lifecycle_counts[lifecycle_slug] = lifecycle_counts.get(lifecycle_slug, 0) + 1

        if status_filter and lifecycle_slug != status_filter:
            continue

        display_row = dict(row)
        display_row["LifecycleStatus"] = lifecycle_status
        display_row["LifecycleSlug"] = lifecycle_slug
        filtered_rounds.append(display_row)

    rows_html = []

    for row in filtered_rounds:
        lifecycle_status = row.get("LifecycleStatus") or derive_lifecycle_status(row)
        status_class = _status_class(lifecycle_status)

        rows_html.append(f"""
            <tr>
                <td class="ut-lead-trial-primary-cell">
                    <a class="ut-lead-trial-link" href="/ut-lead/project?round_id={e(row['RoundID'])}">
                        {e(_fmt(row.get('RoundName')))}
                    </a>
                    <div class="ut-lead-trial-meta">
                        {_round_label(row)}
                    </div>
                </td>
                <td>
                    <span class="ut-lead-status-pill {e(status_class)}">
                        {e(lifecycle_status)}
                    </span>
                </td>
                <td>{e(_fmt_name(row.get('UTLead_FirstName'), row.get('UTLead_LastName')))}</td>
                <td>{e(_fmt(row.get('ShipDate')))}</td>
                <td>{e(_fmt(row.get('StartDate')))}</td>
                <td>{e(_fmt(row.get('EndDate')))}</td>
                <td>{e(_fmt(row.get('Region')))}</td>
            </tr>
        """)

    visible_count = len(filtered_rounds)
    scoped_count = len(scoped_rounds)
    total_count = len(all_rounds)
    scope_label = "My trials" if ut_lead_filter != "all" else "All UT trials"

    if rows_html:
        results_html = f"""
            <div class="ut-lead-table-shell">
                <table class="ut-lead-table ut-lead-trials-table">
                    <thead>
                        <tr>
                            <th>Project / Round</th>
                            <th>Status</th>
                            <th>UT Lead</th>
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
            </div>
        """
    else:
        results_html = f"""
            <section class="ut-lead-empty-state">
                <h2>No trials found</h2>
                <p>No trials match the current view and lifecycle filters.</p>
            </section>
        """

    body_html = f"""
        <section class="ut-lead-trials-page">
            <header class="ut-lead-page-header">
                <div>
                    <h1>User Trial Lead – Trials</h1>
                    <p class="ut-lead-page-subtitle">
                        Track assigned trials, team planning work, and lifecycle timing from one operational view.
                    </p>
                </div>
            </header>

            <section class="ut-lead-summary-strip" aria-label="Trial summary">
                <div class="ut-lead-summary-item">
                    <span class="ut-lead-summary-value">{e(str(visible_count))}</span>
                    <span class="ut-lead-summary-label">shown</span>
                </div>
                <div class="ut-lead-summary-item">
                    <span class="ut-lead-summary-value">{e(str(scoped_count))}</span>
                    <span class="ut-lead-summary-label">in view</span>
                </div>
                <div class="ut-lead-summary-item">
                    <span class="ut-lead-summary-value">{e(str(lifecycle_counts.get('ongoing', 0)))}</span>
                    <span class="ut-lead-summary-label">ongoing</span>
                </div>
                <div class="ut-lead-summary-item">
                    <span class="ut-lead-summary-value">{e(str(lifecycle_counts.get('planning', 0)))}</span>
                    <span class="ut-lead-summary-label">planning</span>
                </div>
                <div class="ut-lead-summary-item">
                    <span class="ut-lead-summary-value">{e(str(total_count))}</span>
                    <span class="ut-lead-summary-label">team total</span>
                </div>
            </section>

            <form method="get" action="/ut-lead/trials" class="ut-lead-filter-bar">
                <div class="ut-lead-filter-group">
                    <label for="ut-lead-view-filter">View</label>
                    <select id="ut-lead-view-filter" name="ut_lead">
                        <option value="me" {_selected('me', ut_lead_filter)}>My trials</option>
                        <option value="all" {_selected('all', ut_lead_filter)}>All UT trials</option>
                    </select>
                </div>

                <div class="ut-lead-filter-group">
                    <label for="ut-lead-status-filter">Lifecycle</label>
                    <select id="ut-lead-status-filter" name="status">
                        <option value="" {_selected('', status_filter)}>All lifecycles</option>
                        <option value="draft" {_selected('draft', status_filter)}>Draft / unscheduled</option>
                        <option value="planning" {_selected('planning', status_filter)}>Under planning</option>
                        <option value="ongoing" {_selected('ongoing', status_filter)}>Ongoing</option>
                        <option value="upcoming" {_selected('upcoming', status_filter)}>Upcoming</option>
                        <option value="completed" {_selected('completed', status_filter)}>Completed</option>
                        <option value="withdrawn" {_selected('withdrawn', status_filter)}>Withdrawn</option>
                    </select>
                </div>

                <div class="ut-lead-filter-actions">
                    <button type="submit" class="ut-lead-filter-apply">Apply</button>
                    <a href="/ut-lead/trials" class="ut-lead-filter-reset">Reset</a>
                </div>
            </form>

            <div class="ut-lead-results-header">
                <div>
                    <h2>{e(scope_label)}</h2>
                    <p>{e(str(visible_count))} of {e(str(scoped_count))} trials shown.</p>
                </div>
            </div>

            {results_html}
        </section>
    """

    html = base_template
    html = inject_nav(html)
    html = html.replace("{{ title }}", "UT Lead – Trials")
    html = html.replace("__BODY_CLASS__", "ut-lead-trials-body")
    html = html.replace("__BODY__", body_html)

    return {"html": html}