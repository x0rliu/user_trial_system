# app/navigation/trials.py

def get_navigation(permission_level: int) -> str:
    """
    Trials navigation.
    Visible to Participant (20) and above.
    """
    if permission_level < 20:
        return ""

    return """
    <div class="dropdown role-menu">
        <a href="#" class="dropdown-trigger role-anchor">
            Trials ▾
        </a>

        <div class="dropdown-menu role-dropdown">
            <a href="/trials/active">Active Trials</a>
            <a href="/trials/past">Past Trials</a>

            <hr>

            <a href="/trials/recruiting">Currently Recruiting</a>
            <a href="/trials/upcoming">Upcoming Trials</a>
        </div>
    </div>
    """
