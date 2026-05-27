# app/navigation/user_trial_lead.py

UT_LEAD_NAV_LEVELS = {70, 100}  # UT Lead, Admin


def get_navigation(*, permission_level: int) -> str:
    if permission_level not in UT_LEAD_NAV_LEVELS:
        return ""

    return """
    <div class="dropdown">
        <a class="dropdown-trigger" href="#">
            User Trial Lead ▾
        </a>
        <div class="dropdown-menu">
            <a href="/ut-lead/trials">All Trials</a>
            <a href="#" class="nav-disabled" title="Coming soon">Trial History (Coming Soon)</a>

            <hr class="dropdown-divider">

            <a href="/historical">Legacy Trials</a>
        </div>
    </div>
    """