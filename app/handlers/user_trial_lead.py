from app.db.user_trial_lead import get_all_project_rounds_for_ut_lead
from app.services.user_trial_lead_status import derive_lifecycle_status


def _fmt_name(first, last):
    if first or last:
        return f"{first or ''} {last or ''}".strip()
    return "—"

def _fmt(val):
    return val if val not in (None, "", "0000-00-00") else "—"


def delete_round_survey(*, round_id: int, survey_id: int):
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM project_round_surveys
            WHERE RoundID = %s
            AND SurveyID = %s
            """,
            (round_id, survey_id),
        )

        conn.commit()

    finally:
        conn.close()

def render_ut_lead_trials_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
):
    project_rounds = get_all_project_rounds_for_ut_lead()

    rows_html = []

    for r in project_rounds:
        rows_html.append(f"""
            <tr>
                <td>
                    <a href="/ut-lead/project?round_id={r['RoundID']}">
                        {_fmt(r['RoundName'])}
                    </a>
                </td>
                <td>{_fmt(r['RoundNumber'])}</td>
                <td>{_fmt_name(r.get('UTLead_FirstName'), r.get('UTLead_LastName'))}</td>
                <td>
                    {derive_lifecycle_status(r)}
                    <span class="muted">({_fmt(r['Status'])})</span>
                </td>
                <td>{_fmt(r['ShipDate'])}</td>
                <td>{_fmt(r['StartDate'])}</td>
                <td>{_fmt(r['EndDate'])}</td>
                <td>{_fmt(r['Region'])}</td>
            </tr>
        """)

    body_html = f"""
        <h2>User Trial Lead – Trials</h2>

        <table class="ut-lead-table">
            <thead>
                <tr>
                    <th>Project / Round</th>
                    <th>Round</th>
                    <th>UT Lead</th>
                    <th>Status (raw)</th>
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
