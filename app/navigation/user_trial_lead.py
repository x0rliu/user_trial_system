# app/navigation/user_trial_lead.py

def get_navigation(*, permission_level: int) -> str:
    # UT Lead: 70, Admin: 100
    if permission_level not in (70, 100):
        return ""

    return """
    <div class="dropdown">
        <a class="dropdown-trigger" href="#">
            User Trial Lead ▾
        </a>
        <div class="dropdown-menu">
            <a href="/ut-lead/trials">All Trials</a>
        </div>
    </div>
    """
