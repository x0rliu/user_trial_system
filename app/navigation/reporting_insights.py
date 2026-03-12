# app/navigation/reporting_insights.py

def get_navigation(*, permission_level: int) -> str:
    if permission_level < 60:
        return ""

    return """
    <div class="dropdown">
        <a class="dropdown-trigger" href="#">
            Reporting & Insights ▾
        </a>
        <div class="dropdown-menu">
            <a href="#">Coming Soon</a>
        </div>
    </div>
    """
