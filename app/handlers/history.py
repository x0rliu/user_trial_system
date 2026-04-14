from app.db.history_db import get_trial_history
from app.utils.html_escape import escape_html as e


def render_history_get(*, user_id: str, base_template: str, inject_nav):

    events = get_trial_history(user_id)

    if not events:
        timeline = "<p class='muted'>No activity recorded yet.</p>"
    else:
        rows = ""

        for entry in events:
            ts = entry["EventTime"].strftime("%Y.%m.%d.%H.%M.%S")
            event_text = e(entry["EventText"])

            rows += f"<li>[{ts}] {event_text}</li>"

        timeline = f"<ul class='trial-history'>{rows}</ul>"

    body = f"""
        <h2>Trial History</h2>

        <p>
            This page shows a timeline of your interactions with trials.
        </p>

        {timeline}
    """

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Trial History")
    html = html.replace("{{ body }}", body)

    return {"html": html}