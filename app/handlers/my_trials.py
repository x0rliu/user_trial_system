# app/handlers/my_trials.py

from app.db.my_trials_db import get_my_trials
from app.db.project_participants import get_past_trials_for_user
from app.utils.html_escape import escape_html as e
from app.utils.trial_display import get_project_display_name, get_round_display_label


def render_my_trials_get(user_id, base_template, inject_nav):
    """
    My Trials page.

    GET renderer only:
    - Reads DB-backed trial state.
    - Builds presentational HTML.
    - Does not mutate state.
    """

    data = get_my_trials(user_id)

    watching = data["watching"]
    applied = data["applied"]
    joined = data["joined"]

    def render_trial_state_table(
        *,
        title,
        description,
        rows,
        empty_message,
        status_label,
        section_href,
        section_link_label,
    ):
        table_rows = ""

        if not rows:
            table_rows = f"""
            <tr>
                <td colspan="3" class="participant-trials-empty-row">
                    {e(empty_message)}
                </td>
            </tr>
            """

        else:
            for r in rows:
                project_name = e(get_project_display_name(r))
                round_label = e(get_round_display_label(r))

                table_rows += f"""
                <tr>
                    <td>
                        <a href="{section_href}" class="participant-trials-primary-link">
                            {project_name}
                        </a>
                    </td>
                    <td>{round_label}</td>
                    <td>{e(status_label)}</td>
                </tr>
                """

        return f"""
        <section class="trial-card">
            <div class="trial-card-header">
                <h2>{e(title)}</h2>
                <span class="trial-subtitle">
                    {e(description)}
                    <a href="{section_href}" class="participant-trials-primary-link" style="margin-left: 8px;">
                        {e(section_link_label)} →
                    </a>
                </span>
            </div>

            <table class="participant-trials-table participant-trials-table-compact">
                <thead>
                    <tr>
                        <th>Trial</th>
                        <th>Round</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </section>
        """

    body = f"""
    <section class="participant-trials-page participant-trials-active-page">
        <h1 class="participant-trials-title">My Trials</h1>

        <div class="participant-trials-empty-card" style="margin-bottom: 24px;">
            <p>
                Track the trials you are watching, your pending applications,
                and the trials you have joined.
            </p>
        </div>

        {render_trial_state_table(
            title="Watching",
            description="Trials you asked to be notified about when recruiting opens.",
            rows=watching,
            empty_message="You are not watching any trials right now.",
            status_label="Watching",
            section_href="/trials/upcoming",
            section_link_label="View upcoming trials",
        )}

        {render_trial_state_table(
            title="Pending Applications",
            description="Trials where your application is currently waiting for an outcome.",
            rows=applied,
            empty_message="You do not have any pending applications right now.",
            status_label="Pending",
            section_href="/trials/recruiting",
            section_link_label="View recruiting trials",
        )}

        {render_trial_state_table(
            title="Joined",
            description="Trials where you have been selected or are actively participating.",
            rows=joined,
            empty_message="You have not joined any active trials right now.",
            status_label="Joined",
            section_href="/trials/active",
            section_link_label="View active trials",
        )}
    </section>
    """

    html = inject_nav(base_template)
    html = html.replace("__BODY_CLASS__", "trials-page")
    html = html.replace("{{ title }}", "My Trials")
    html = html.replace("__BODY__", body)

    return {"html": html}


def render_past_trials_get(user_id, base_template, inject_nav):

    rows = get_past_trials_for_user(user_id)

    table_rows = ""

    if not rows:

        table_rows = """
        <tr>
            <td colspan="4" class="participant-trials-empty-row">
                No past trials yet.
            </td>
        </tr>
        """

    else:

        for r in rows:

            trial_name_raw = r["TrialNickname"] or get_project_display_name(r)
            trial_name = e(trial_name_raw)

            round_id = e(r["RoundID"])
            trial_link = f"/trials/past/view?round_id={round_id}"

            start_date = e(r["StartDate"] or "—")
            end_date = e(r["EndDate"] or "—")

            surveys_returned = e(r["surveys_returned"])
            surveys_issued = e(r["surveys_issued"])

            table_rows += f"""
            <tr>
                <td>
                    <a href="{trial_link}" class="participant-trials-primary-link">
                        {trial_name}
                    </a>
                </td>

                <td>{start_date}</td>

                <td>{end_date}</td>

                <td>
                    {surveys_returned} / {surveys_issued}
                </td>
            </tr>
            """

    body = f"""
    <section class="participant-trials-page participant-trials-list-page">
        <h1 class="participant-trials-title">Past Trials</h1>

        <table class="participant-trials-table">
            <thead>
                <tr>
                    <th>Trial</th>
                    <th>Start Date</th>
                    <th>End Date</th>
                    <th>Surveys Returned</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
    </section>
    """

    html = inject_nav(base_template)
    html = html.replace("__BODY_CLASS__", "trials-page")
    html = html.replace("{{ title }}", "Past Trials")
    html = html.replace("__BODY__", body)

    return {"html": html}