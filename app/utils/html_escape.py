def escape_html(value):
    """
    Minimal, explicit HTML escaping.
    Always call this before inserting dynamic values into HTML.
    """
    if value is None:
        return ""

    value = str(value)

    return (
        value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )