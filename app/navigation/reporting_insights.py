# app/navigation/reporting_insights.py
REPORTING_INSIGHTS_NAV_LEVELS = {50, 60, 70, 100}  # Product Team, Management, UT Lead, Admin


def get_navigation(*, permission_level: int) -> str:
    if permission_level not in REPORTING_INSIGHTS_NAV_LEVELS:
        return ""

    return """
    <div class="dropdown">
        <a class="dropdown-trigger" href="#">
            Reporting & Insights ▾
        </a>
        <div class="dropdown-menu">
            <a href="/reporting/insights">Published Reports</a>
        </div>
    </div>
    """
