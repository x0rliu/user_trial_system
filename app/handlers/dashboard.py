def render_dashboard_get(*, user_id: str, base_template: str, inject_nav):
    body = """
        <h2>Dashboard</h2>

        <p>
            This is your dashboard.
            In future iterations, this page will adapt based on your role.
        </p>

        <ul>
            <li><a href="/profile/wizard">Complete your profile</a></li>
        </ul>

        <hr>

        <p style="color: #888;">
            🚧 Dashboard features coming soon.
        </p>
    """

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Dashboard")
    html = html.replace("{{ body }}", body)

    return {"html": html}
