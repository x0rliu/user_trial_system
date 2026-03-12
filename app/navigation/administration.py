# app/navigation/administration.py

# -------------------------
# Administration Navigation
# -------------------------

ADMIN_MENU_BADGES = {70, 100}
UCT_BADGES = {70, 100}
BONUS_APPROVAL_BADGES = {100}

def get_navigation(*, permission_level: int) -> str:
    if permission_level not in ADMIN_MENU_BADGES:
        return ""

    items = []

    if permission_level in UCT_BADGES:
        items.append(
            '<a href="/admin/users">User Control Table</a>'
        )

    if permission_level in BONUS_APPROVAL_BADGES:
        items.append(
            '<a href="/admin/approvals">Approvals</a>'
        )

    if not items:
        return ""

    return f"""
    <div class="dropdown role-menu">
        <a href="#" class="dropdown-trigger role-anchor">
            Administration ▾
        </a>
        <div class="dropdown-menu role-dropdown">
            {''.join(items)}
        </div>
    </div>
    """
