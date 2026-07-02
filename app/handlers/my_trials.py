# app/handlers/my_trials.py

from app.db.my_trials_db import get_my_trials
from app.db.project_participants import get_past_trials_for_user
from app.utils.html_escape import escape_html as e
from app.utils.csrf import generate_csrf_token
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
    csrf_token = generate_csrf_token(user_id)

    watching = data["watching"]
    applied = data["applied"]
    joined = data["joined"]

    def render_stop_watching_action(row):
        safe_round_id = e(row.get("RoundID") or "")

        return f"""
        <form method="POST" action="/trials/interest/stop" class="participant-trials-inline-form">
            <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
            <input type="hidden" name="round_id" value="{safe_round_id}">
            <input type="hidden" name="return_to" value="/my_trials">
            <button type="submit" class="participant-trials-link-button">
                Stop watching
            </button>
        </form>
        """

    def render_trial_state_table(
        *,
        title,
        description,
        rows,
        empty_message,
        status_label,
        section_href,
        section_link_label,
        action_builder=None,
    ):
        table_rows = ""
        has_actions = action_builder is not None
        empty_colspan = 4 if has_actions else 3
        action_header = "<th>Action</th>" if has_actions else ""

        if not rows:
            table_rows = f"""
            <tr>
                <td colspan="{empty_colspan}" class="participant-trials-empty-row">
                    {e(empty_message)}
                </td>
            </tr>
            """

        else:
            for r in rows:
                project_name = e(get_project_display_name(r))
                round_label = e(get_round_display_label(r))
                action_cell = ""

                if has_actions:
                    action_cell = f"<td>{action_builder(r)}</td>"

                table_rows += f"""
                <tr>
                    <td>
                        <a href="{section_href}" class="participant-trials-primary-link">
                            {project_name}
                        </a>
                    </td>
                    <td>{round_label}</td>
                    <td>{e(status_label)}</td>
                    {action_cell}
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
                        {action_header}
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
            action_builder=render_stop_watching_action,
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

    def safe_text(value, fallback="-"):
        if value is None or value == "":
            return e(fallback)

        return e(str(value))

    def date_text(value):
        if not value:
            return "-"

        return e(str(value).split(" ")[0])

    def int_value(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def past_status_label(row):
        state = str(row.get("PastTrialState") or "")

        if state == "completed":
            return "Completed"

        if state == "round_closed":
            return "Round closed"

        return "Past"

    def nda_status_html(row):
        status = str(row.get("NDAStatus") or "").strip()
        signed_at = row.get("NDASignedAt")

        if status == "Signed":
            return f"""
            <span class="participant-trials-pill participant-trials-pill-success">Signed</span>
            <div class="participant-trials-muted-meta">{date_text(signed_at)}</div>
            """

        if status:
            return f"""
            <span class="participant-trials-pill participant-trials-pill-neutral">{e(status)}</span>
            """

        return """
        <span class="participant-trials-pill participant-trials-pill-muted">Not recorded</span>
        """

    def participation_signal_html(*, surveys_returned, surveys_issued):
        if surveys_issued <= 0:
            return ""

        if surveys_returned >= surveys_issued:
            return ""

        missing_count = surveys_issued - surveys_returned

        if surveys_issued <= 2:
            note = (
                f"{missing_count} official survey not returned. "
                "Reputation context is interpreted with small-sample leniency."
            )
        else:
            note = (
                f"{missing_count} official surveys not returned. "
                "This is included in reputation context."
            )

        return f"""
        <div class="participant-trials-reputation-note">
            {e(note)}
        </div>
        """

    total_trials = len(rows)
    total_surveys_returned = sum(int_value(r.get("surveys_returned")) for r in rows)
    total_surveys_issued = sum(int_value(r.get("surveys_issued")) for r in rows)
    signed_nda_count = sum(1 for r in rows if str(r.get("NDAStatus") or "") == "Signed")
    incomplete_survey_trial_count = sum(
        1
        for r in rows
        if int_value(r.get("surveys_issued")) > 0
        and int_value(r.get("surveys_returned")) < int_value(r.get("surveys_issued"))
    )

    if incomplete_survey_trial_count == 1:
        reputation_summary_note = "1 trial has survey follow-through context."
    elif incomplete_survey_trial_count > 1:
        reputation_summary_note = f"{incomplete_survey_trial_count} trials have survey follow-through context."
    else:
        reputation_summary_note = "No incomplete official survey history."

    table_rows = ""

    if not rows:

        table_rows = """
        <tr>
            <td colspan="7" class="participant-trials-empty-row">
                No past trials yet.
            </td>
        </tr>
        """

    else:

        for r in rows:

            trial_name = e(get_project_display_name(r))
            round_label = e(get_round_display_label(r))
            market_name = safe_text(r.get("MarketName"))

            start_date = date_text(r.get("StartDate"))
            end_date = date_text(r.get("EndDate"))
            date_range = f"{start_date} - {end_date}"

            surveys_returned = int_value(r.get("surveys_returned"))
            surveys_issued = int_value(r.get("surveys_issued"))
            survey_text = f"{surveys_returned} / {surveys_issued}"

            status_label = e(past_status_label(r))

            table_rows += f"""
            <tr>
                <td>
                    <strong class="participant-trials-trial-name">{trial_name}</strong>
                </td>

                <td>{round_label}</td>

                <td>{market_name}</td>

                <td>{date_range}</td>

                <td>{nda_status_html(r)}</td>

                <td>
                    <span class="participant-trials-survey-count">{e(survey_text)}</span>
                    {participation_signal_html(
                        surveys_returned=surveys_returned,
                        surveys_issued=surveys_issued,
                    )}
                </td>

                <td>
                    <span class="participant-trials-pill participant-trials-pill-neutral">
                        {status_label}
                    </span>
                </td>
            </tr>
            """

    body = f"""
    <section class="participant-trials-page participant-trials-list-page participant-trials-past-page">
        <header class="participant-trials-history-header">
            <div>
                <h1 class="participant-trials-title">Past Trials</h1>
                <p class="participant-trials-subtitle">
                    Review your completed and closed User Trial participation history.
                </p>
            </div>
        </header>

        <div class="participant-trials-history-summary">
            <article>
                <span class="participant-trials-summary-label">Trials</span>
                <strong>{e(total_trials)}</strong>
            </article>
            <article>
                <span class="participant-trials-summary-label">Official surveys returned</span>
                <strong>{e(total_surveys_returned)} / {e(total_surveys_issued)}</strong>
            </article>
            <article>
                <span class="participant-trials-summary-label">NDAs signed</span>
                <strong>{e(signed_nda_count)}</strong>
            </article>
            <article>
                <span class="participant-trials-summary-label">Reputation</span>
                <a href="/dashboard/reputation">View reputation</a>
                <div class="participant-trials-summary-note">
                    {e(reputation_summary_note)}
                </div>
            </article>
        </div>

        <table class="participant-trials-table participant-trials-past-table">
            <thead>
                <tr>
                    <th>Trial</th>
                    <th>Round</th>
                    <th>Market</th>
                    <th>Dates</th>
                    <th>NDA</th>
                    <th>Surveys</th>
                    <th>Status</th>
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