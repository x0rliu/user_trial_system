# app/navigation/product_team.py

PRODUCT_TEAM_NAV_LEVELS = {50, 70, 100}  # Product Team, UT Lead, Admin


def get_navigation(*, permission_level: int) -> str:
    if permission_level not in PRODUCT_TEAM_NAV_LEVELS:
        return ""

    return """
    <div class="dropdown">
        <a class="dropdown-trigger" href="#">
            Product Team ▾
        </a>
        <div class="dropdown-menu">
            <a href="/product/request-trial">User Trial Requests</a>
            <a href="/product/current-trials">My Current Trials</a>
            <a href="/product/past-trials">My Past Trials</a>
            <div class="dropdown-divider"></div>
            <a href="/product/reports">Reports & Summaries</a>
        </div>
    </div>
    """