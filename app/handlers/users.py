# app/handlers/users.py

# NOTE:
# Search / filtering / pagination intentionally deferred.
# Admin user count is currently small; UI will evolve with role complexity.


from app.db.admin_users import get_all_users_with_permissions
from app.constants.permission_levels import PERMISSION_LEVELS
from app.utils.html_escape import escape_html as e
from app.utils.csrf import generate_csrf_token

def render_admin_users_get(*, actor_uid: str, base_template: str, inject_nav):
    from app.db.user_roles import get_effective_permission_level

    actor_level = get_effective_permission_level(actor_uid)
    csrf_token = generate_csrf_token(actor_uid)

    users = get_all_users_with_permissions()

    rows = ""

    for u in users:
        can_edit = (
            actor_level > u["PermissionLevel"]
            and actor_uid != u["user_id"]
        )

        actions_html = (
            '<button class="admin-action-button admin-action-button-primary edit-btn">Edit</button>'
            if can_edit
            else '<span class="admin-action-muted">—</span>'
        )

        rows += f"""
        <tr data-user-id="{e(u['user_id'])}">
            <td class="mono">{e(u["user_id"])}</td>
            <td class="admin-user-name">{e(u["FullName"])}</td>
            <td>{e(u["Email"])}</td>

            <td class="center">
                <span class="perm-display permission-pill">{e(u["PermissionLevel"])}</span>
                <select class="perm-editor hidden" aria-label="Permission level for {e(u['FullName'])}">
                    {''.join(
                        f'<option value="{e(lvl)}" {"selected" if lvl == u["PermissionLevel"] else ""}>{e(lvl)}</option>'
                        for lvl in PERMISSION_LEVELS
                    )}
                </select>
            </td>

            <td class="center actions-cell">
                {actions_html}
                <button class="admin-action-button admin-action-button-primary save-btn hidden">Save</button>
                <button class="admin-action-button admin-action-button-secondary cancel-btn hidden">Cancel</button>
            </td>
        </tr>
        """

    user_count_label = f"{len(users)} user" if len(users) == 1 else f"{len(users)} users"

    body_html = f"""
    <section class="admin-users-page admin-page-shell">
        <div class="page-header admin-page-header admin-users-header">
            <div class="admin-page-title-row">
                <div>
                    <h1 class="page-title">User Controls</h1>
                    <p class="page-description">
                        Manage permission levels and administrative access.
                    </p>
                </div>
                <div class="admin-page-toolbar" aria-label="User administration summary">
                    <span class="admin-summary-pill">{e(user_count_label)}</span>
                    <span class="admin-summary-note">Permission-gated access</span>
                </div>
            </div>
        </div>

        <div class="admin-table-card">
            <div class="admin-table-scroll">
                <table class="admin-table">
                    <thead>
                        <tr>
                            <th>User ID</th>
                            <th>Name</th>
                            <th>Email</th>
                            <th>Permission Level</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            </div>
        </div>
    </section>

    <div id="toast" class="toast hidden"></div>

    <script>
    function showToast(message) {{
        const toast = document.getElementById("toast");
        toast.textContent = message;
        toast.classList.remove("hidden");
        toast.classList.add("show");

        clearTimeout(toast._timer);
        toast._timer = setTimeout(() => {{
            toast.classList.add("hidden");
            toast.classList.remove("show");
        }}, 3000);
    }}

    document.addEventListener("click", async (e) => {{
        const row = e.target.closest("tr[data-user-id]");
        if (!row) return;

        const editBtnClicked   = e.target.closest(".edit-btn");
        const saveBtnClicked   = e.target.closest(".save-btn");
        const cancelBtnClicked = e.target.closest(".cancel-btn");

        const display = row.querySelector(".perm-display");
        const editor  = row.querySelector(".perm-editor");

        const editBtn   = row.querySelector(".edit-btn");
        const saveBtn   = row.querySelector(".save-btn");
        const cancelBtn = row.querySelector(".cancel-btn");

        // ---- ENTER EDIT MODE
        if (editBtnClicked) {{
            row.dataset.originalValue = display.textContent.trim();

            display.classList.add("hidden");
            editor.classList.remove("hidden");

            editBtn.classList.add("hidden");
            saveBtn.classList.remove("hidden");
            cancelBtn.classList.remove("hidden");
            return;
        }}

        // ---- CANCEL
        if (cancelBtnClicked) {{
            const original = row.dataset.originalValue || display.textContent.trim();
            editor.value = original;

            editor.classList.add("hidden");
            display.classList.remove("hidden");

            saveBtn.classList.add("hidden");
            cancelBtn.classList.add("hidden");
            editBtn.classList.remove("hidden");

            // restore button state if it was mid-save
            saveBtn.disabled = false;
            cancelBtn.disabled = false;
            saveBtn.textContent = "Save";
            return;
        }}

        // ---- SAVE
        if (saveBtnClicked) {{
            const user_id = row.dataset.userId;

            if (!user_id) {{
                console.error("Missing user_id on row:", row);
                showToast("Internal error: missing user id");
                return;
            }}
            const newLevel = Number(editor.value);

            // Button enters saving state
            saveBtn.disabled = true;
            cancelBtn.disabled = true;
            saveBtn.textContent = "Saving...";

            const resp = await fetch("/admin/users/update-permission", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{
                    csrf_token: "{e(csrf_token)}",
                    user_id: user_id,
                    permission_level: newLevel,
                }}),
            }});

            const responseBody = await resp.json().catch(() => ({{}}));

            if (!resp.ok || !responseBody.ok) {{
                const msg = responseBody.error || "You are not allowed to make this change.";

                // restore buttons
                saveBtn.disabled = false;
                cancelBtn.disabled = false;
                saveBtn.textContent = "Save";

                showToast(msg);
                return;
            }}


            // Success → update display + exit edit mode
            display.textContent = String(newLevel);

            editor.classList.add("hidden");
            display.classList.remove("hidden");

            saveBtn.classList.add("hidden");
            cancelBtn.classList.add("hidden");
            editBtn.classList.remove("hidden");

            // reset for next time
            saveBtn.disabled = false;
            cancelBtn.disabled = false;
            saveBtn.textContent = "Save";
        }}
    }});
    </script>

    """

    html = inject_nav(base_template)
    html = html.replace("__BODY_CLASS__", "admin-page admin-users-body")
    html = html.replace("{{ title }}", "User Administration")
    html = html.replace("__BODY__", body_html)
    html = html.replace(
        "</head>",
        '<link rel="stylesheet" href="/static/admin.css">\n</head>',
    )

    return {"html": html}

def handle_update_user_permission(actor_uid: str, data: dict):
    from app.constants.permission_levels import PERMISSION_LEVELS
    from app.db.admin_users import update_user_permission_level
    from app.db.user_roles import get_effective_permission_level

    target_user_id = data.get("user_id")
    new_level = data.get("permission_level")

    if not target_user_id:
        return {
            "status_code": 400,
            "payload": {"ok": False, "error": "Missing target user."},
        }

    if new_level not in PERMISSION_LEVELS:
        return {
            "status_code": 400,
            "payload": {"ok": False, "error": "Invalid permission level."},
        }

    actor_level = get_effective_permission_level(actor_uid)
    target_level = get_effective_permission_level(target_user_id)

    # 🚫 Cannot change yourself
    if actor_uid == target_user_id:
        return {
            "status_code": 403,
            "payload": {"ok": False, "error": "You are not allowed to make this change."},
        }

    # 🚫 Cannot modify users at or above your level
    if actor_level <= target_level:
        return {
            "status_code": 403,
            "payload": {"ok": False, "error": "You are not allowed to make this change."},
        }

    # 🚫 Cannot assign a level >= your own
    if new_level >= actor_level:
        return {
            "status_code": 403,
            "payload": {"ok": False, "error": "You are not allowed to make this change."},
        }

    update_user_permission_level(
        user_id=target_user_id,
        permission_level=new_level,
    )

    return {
        "status_code": 200,
        "payload": {"ok": True, "error": None},
    }

