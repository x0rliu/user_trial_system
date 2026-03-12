from app.db.my_trials_db import get_my_trials


def render_my_trials_get(user_id, base_template, inject_nav):

    data = get_my_trials(user_id)

    watching = data["watching"]
    applied = data["applied"]
    joined = data["joined"]

    def render_list(rows):
        if not rows:
            return "<p class='muted'>None</p>"

        items = ""
        for r in rows:
            items += f"<li>{r['ProjectName']} (Round {r['RoundID']})</li>"

        return f"<ul>{items}</ul>"


    body = f"""
    <h1>My Trials</h1>

    <h2>Watching</h2>
    {render_list(watching)}

    <h2>Applied</h2>
    {render_list(applied)}

    <h2>Joined</h2>
    {render_list(joined)}
    """

    html = base_template.replace("{{ body }}", body)

    html = inject_nav(html)

    return {"html": html}

from app.db.project_participants import get_past_trials_for_user


def render_past_trials_get(user_id, base_template, inject_nav):

    rows = get_past_trials_for_user(user_id)

    table_rows = ""

    if not rows:

        table_rows = """
        <tr>
            <td colspan="4" class="muted">
                No past trials yet.
            </td>
        </tr>
        """

    else:

        for r in rows:

            trial_name = r["TrialNickname"] or r["ProjectName"]
            trial_link = f"/trials/past/view?round_id={r['RoundID']}"

            table_rows += f"""
            <tr>
                <td>
                    <a href="{trial_link}">
                        {trial_name}
                    </a>
                </td>

                <td>{r['StartDate'] or '-'}</td>

                <td>{r['EndDate'] or '-'}</td>

                <td>
                    {r['surveys_returned']} / {r['surveys_issued']}
                </td>
            </tr>
            """

    body = f"""
    <h1>Past Trials</h1>

    <table class="data-table">
        <tr>
            <th>Trial</th>
            <th>Start Date</th>
            <th>End Date</th>
            <th>Surveys Returned</th>
        </tr>

        {table_rows}

    </table>
    """

    html = base_template.replace("{{ body }}", body)

    html = inject_nav(html)

    return {"html": html}