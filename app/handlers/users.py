# app/handlers/users.py

# NOTE:
# Search / filtering / pagination intentionally deferred.
# Admin user count is currently small; UI will evolve with role complexity.


from app.db.admin_users import get_all_users_with_permissions
from app.constants.permission_levels import PERMISSION_LEVELS
from app.utils.html_escape import escape_html as e

def render_admin_users_get(*, actor_uid: str, base_template: str, inject_nav):
    from app.db.user_roles import get_effective_permission_level

    actor_level = get_effective_permission_level(actor_uid)

    users = get_all_users_with_permissions()

    rows = ""

    for u in users:
        can_edit = (
            actor_level > u["PermissionLevel"]
            and actor_uid != u["user_id"]
        )

        actions_html = (
            '<button class="btn btn-small edit-btn">Edit</button>'
            if can_edit
            else ''
        )

        rows += f"""
        <tr data-user-id="{e(u['user_id'])}">
            <td class="mono">{e(u["user_id"])}</td>
            <td>{e(u["FullName"])}</td>
            <td>{e(u["Email"])}</td>

            <td class="center">
                <span class="perm-display">{e(u["PermissionLevel"])}</span>
                <select class="perm-editor hidden">
                    {''.join(
                        f'<option value="{e(lvl)}" {"selected" if lvl == u["PermissionLevel"] else ""}>{e(lvl)}</option>'
                        for lvl in PERMISSION_LEVELS
                    )}
                </select>
            </td>

            <td class="center actions-cell">
                {actions_html}
                <button class="btn btn-small save-btn hidden">Save</button>
                <button class="btn btn-small cancel-btn hidden">Cancel</button>
            </td>
        </tr>
        """

    body_html = f"""
    <link rel="stylesheet" href="/static/admin.css">

    <h1>User Control Table</h1>
    <p class="muted">
        Manage user permission levels and access.
    </p>

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
    <div id="toast" class="toast hidden"></div>

    <script>
    function showToast(message) {{
        const toast = document.getElementById("toast");
        toast.textContent = message;
        toast.classList.remove("hidden");

        clearTimeout(toast._timer);
        toast._timer = setTimeout(() => {{
            toast.classList.add("hidden");
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
                    user_id: user_id,
                    permission_level: newLevel,
                }}),
            }});

            if (!resp.ok) {{
                const msg = await resp.text();

                // restore buttons
                saveBtn.disabled = false;
                cancelBtn.disabled = false;
                saveBtn.textContent = "Save";

                showToast(msg || "You are not allowed to make this change.");
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
    html = html.replace("__BODY__", body_html)

    return {"html": html}

def handle_update_user_permission(actor_uid: str, data: dict):
    from app.constants.permission_levels import PERMISSION_LEVELS
    from app.db.admin_users import update_user_permission_level
    from app.db.user_roles import get_effective_permission_level

    target_user_id = data.get("user_id")
    new_level = data.get("permission_level")

    if not target_user_id:
        return (400, {}, "")

    if new_level not in PERMISSION_LEVELS:
        return (400, {}, "")

    actor_level  = get_effective_permission_level(actor_uid)
    target_level = get_effective_permission_level(target_user_id)

    # 🚫 Cannot change yourself
    if actor_uid == target_user_id:
        return (403, {}, "You are not allowed to make this change.")

    # 🚫 Cannot modify users at or above your level
    if actor_level <= target_level:
        return (403, {}, "You are not allowed to make this change.")

    # 🚫 Cannot assign a level >= your own
    if new_level >= actor_level:
        return (403, {}, "You are not allowed to make this change.")

    update_user_permission_level(
        user_id=target_user_id,
        permission_level=new_level,
    )

    return (200, {}, "")


