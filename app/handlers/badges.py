def render_badges_get(*, user_id: str, base_template: str, inject_nav):
    body = """
        <h2>Badges</h2>

        <p>
            This page will display your earned badges,
            achievements, and contribution milestones.
        </p>

        <p style="color: #888;">
            🚧 Badge system coming soon.
        </p>
    """

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Badges")
    html = html.replace("{{ body }}", body)

    return {"html": html}
