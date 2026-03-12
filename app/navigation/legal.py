# app/navigation/legal.py

LEGAL_NAV_LEVELS = {30, 70, 100}  # Legal, UT Lead, Admin

def get_navigation(permission_level: int) -> str:
    if permission_level not in LEGAL_NAV_LEVELS:
        return ""

    return """
    <div class="dropdown role-menu">
        <a href="#" class="dropdown-trigger role-anchor">
            Legal ▾
        </a>

        <div class="dropdown-menu role-dropdown">
            <a href="/legal/documents">Documents Editor</a>
        </div>
    </div>
    """
