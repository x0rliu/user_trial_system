# app/navigation/trials.py

TRIALS_NAV_LEVELS = {20, 30, 40, 50, 60, 70, 80, 100}


def get_navigation(permission_level: int) -> str:
    """
    Trials navigation.

    Visible to every authenticated permission bundle that includes the
    participant-facing 020 experience. This is explicit membership, not
    numeric permission inheritance.
    """
    if permission_level not in TRIALS_NAV_LEVELS:
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