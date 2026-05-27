# app/navigation/administration.py

from html import escape as e

# -------------------------
# Administration Navigation
# -------------------------

ADMINISTRATION_NAV_LEVELS = {70, 100}  # UT Lead, Admin
USER_CONTROL_TABLE_NAV_LEVELS = {70, 100}  # UT Lead, Admin
APPROVALS_NAV_LEVELS = {100}  # Admin
DEBUG_SETTINGS_NAV_LEVELS = {100}  # Admin


def _build_view_mode_submenu(*, permission_context: dict | None, csrf_token: str) -> str:
    if not permission_context or not permission_context.get("can_use_admin_view_mode"):
        return ""

    selected_level = permission_context.get("view_as_permission_level")
    forms = []

    for row in permission_context.get("admin_view_mode_levels", []):
        level = row.get("permission_level")
        label = row.get("label") or f"Level {level}"
        active_class = " is-active" if selected_level == level else ""
        active_note = " ✓" if selected_level == level else ""

        forms.append(f"""
        <form method="POST" action="/admin/view-mode/set" class="admin-view-mode-submenu-form">
            <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
            <input type="hidden" name="view_as_permission_level" value="{e(str(level))}">
            <button type="submit" class="admin-view-mode-submenu-button{active_class}">
                {e(str(level))} — {e(label)}{active_note}
            </button>
        </form>
        """)

    clear_html = ""
    if permission_context.get("is_viewing_as"):
        clear_html = f"""
        <form method="POST" action="/admin/view-mode/clear" class="admin-view-mode-submenu-form">
            <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
            <button type="submit" class="admin-view-mode-submenu-button admin-view-mode-submenu-exit">
                Exit view mode
            </button>
        </form>
        """

    return f"""
    <div class="admin-view-mode-flyout">
        <button
            type="button"
            class="admin-view-mode-flyout-trigger"
            aria-expanded="false"
        >
            <span>View as...</span>
            <span aria-hidden="true">›</span>
        </button>
        <div class="admin-view-mode-submenu">
            {''.join(forms)}
            {clear_html}
        </div>
    </div>
    """


def get_navigation(
    *,
    permission_level: int,
    permission_context: dict | None = None,
    admin_view_mode_csrf_token: str = "",
) -> str:
    show_admin_menu = permission_level in ADMINISTRATION_NAV_LEVELS
    show_view_mode = bool(
        permission_context and permission_context.get("can_use_admin_view_mode")
    )

    if not show_admin_menu and not show_view_mode:
        return ""

    items = []

    if permission_level in USER_CONTROL_TABLE_NAV_LEVELS:
        items.append(
            '<a href="/admin/users">User Control Table</a>'
        )

    if permission_level in APPROVALS_NAV_LEVELS:
        items.append(
            '<a href="/admin/approvals">Approvals</a>'
        )

    if permission_level in DEBUG_SETTINGS_NAV_LEVELS:
        items.append(
            '<a href="/admin/debug-settings">Debug Settings</a>'
        )

    view_mode_html = _build_view_mode_submenu(
        permission_context=permission_context,
        csrf_token=admin_view_mode_csrf_token,
    )

    if view_mode_html:
        if items:
            items.append('<hr>')
        items.append(view_mode_html)

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