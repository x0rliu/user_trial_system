# app/navigation/product_team.py

def get_navigation(*, permission_level: int) -> str:
    # Product Team: 50, UT Lead: 70, Admin: 100
    if permission_level not in (50, 70, 100):
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
