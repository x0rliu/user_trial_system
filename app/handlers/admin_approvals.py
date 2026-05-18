# app/handlers/admin_approvals.py

from app.utils.html_escape import escape_html as e
from app.db.project_projects import get_project_for_review
from app.db.project_rounds import (
    get_round_stakeholders,
    get_rounds_for_project_review,
)


def render_admin_approval_project_get(
    *,
    user_id: str,
    project_id: str,
    query_params,
):
    project = get_project_for_review(project_id=project_id)
    rounds = get_rounds_for_project_review(project_id=project_id)
    first_round = rounds[0] if rounds else {}

    stakeholders = []
    if first_round.get("RoundID"):
        stakeholders = get_round_stakeholders(
            round_id=int(first_round["RoundID"]),
        )

    if not project:
        return {
            "html": """
            <section class="admin-project-review-page">
                <div class="page-header admin-project-review-header">
                    <h2 class="page-title">Project Review</h2>
                    <p class="page-description">
                        The requested project could not be found.
                    </p>
                </div>

                <p>
                    <a class="admin-back-link" href="/admin/approvals">← Back to Approvals</a>
                </p>
            </section>
            """
        }

    # -------------------------
    # Resolve CreatedBy → Display Name
    # -------------------------
    created_by = project.get("CreatedBy")
    creator_display = created_by or "—"

    if created_by:
        from app.db.user_roles import get_users_with_permission_levels

        users = get_users_with_permission_levels([0, 20, 30, 40, 50, 60, 70, 80, 100])
        match = next((u for u in users if u["user_id"] == created_by), None)

        if match:
            name = f"{match.get('FirstName', '')} {match.get('LastName', '')}".strip()
            if name:
                creator_display = name

    project["__CreatedByDisplay"] = creator_display

    # -------------------------
    # Display helpers
    # -------------------------
    def format_value(value):
        if value in (None, ""):
            return "—"

        raw = str(value)

        if raw.lower() == "none":
            return "—"

        return e(raw)

    def format_status_label(value):
        if value in (None, ""):
            return "Unknown Status"

        raw = str(value)

        status_map = {
            "draft": "Draft",
            "pending_ut_review": "Pending UT Review",
            "info_requested": "Information Requested",
            "change_requested": "Change Requested",
            "approved": "Approved",
            "declined": "Declined",
            "closed": "Closed",
            "archived": "Archived",
        }

        if raw in status_map:
            return status_map[raw]

        return raw.replace("_", " ").title().replace("Ut", "UT")

    def render_card(title, fields, data):
        rows = []

        for label, key in fields:
            rows.append(f"""
                <dt>{e(label)}</dt>
                <dd>{format_value(data.get(key))}</dd>
            """)

        return f"""
        <section class="admin-review-card">
            <h3 class="section-title">{e(title)}</h3>
            <dl class="admin-review-list">
                {''.join(rows)}
            </dl>
        </section>
        """

    def render_stakeholders_card(title, stakeholder_rows):
        if not stakeholder_rows:
            return f"""
            <section class="admin-review-card admin-stakeholders-card">
                <h3 class="section-title">{e(title)}</h3>
                <p class="admin-review-empty">No stakeholders submitted.</p>
            </section>
            """

        stakeholder_items = []

        for stakeholder in stakeholder_rows:
            display_name = format_value(stakeholder.get("DisplayName"))
            role_name = format_value(stakeholder.get("StakeholderRole"))
            email = stakeholder.get("Email") or ""
            linked_user_id = stakeholder.get("user_id")

            if linked_user_id:
                access_label = "Registered"
            elif email:
                access_label = "Pending registration / SSO link"
            else:
                access_label = "Legacy name-only stakeholder"

            email_html = ""
            if email:
                email_html = f"""
                <div class="admin-stakeholder-email">{e(email)}</div>
                """

            stakeholder_items.append(f"""
                <div class="admin-stakeholder-item">
                    <div class="admin-stakeholder-main">
                        <div class="admin-stakeholder-name">{display_name}</div>
                        {email_html}
                    </div>
                    <div class="admin-stakeholder-meta">
                        <span class="admin-stakeholder-role">{role_name}</span>
                        <span class="admin-stakeholder-access">{e(access_label)}</span>
                    </div>
                </div>
            """)

        return f"""
        <section class="admin-review-card admin-stakeholders-card">
            <h3 class="section-title">{e(title)}</h3>
            <div class="admin-stakeholder-list">
                {''.join(stakeholder_items)}
            </div>
        </section>
        """

    # -------------------------
    # Page title context
    # -------------------------
    project_name = format_value(project.get("ProjectName"))
    round_number = first_round.get("RoundNumber") or 1
    round_label = f"Round {round_number}"
    status_label = format_status_label(first_round.get("Status"))

    page_title = (
        f"Project Review - {project_name} {round_label} ({e(status_label)})"
    )

    # -------------------------
    # Project cards
    # -------------------------
    project_cards = []

    project_cards.append(render_card(
        "Product Identity",
        [
            ("Project Name", "ProjectName"),
            ("Market Name", "MarketName"),
            ("Product Type", "ProductType"),
            ("Description", "Description"),
        ],
        project,
    ))

    project_cards.append(render_card(
        "Business",
        [
            ("Business Group", "BusinessGroup"),
        ],
        project,
    ))

    project_cards.append(render_card(
        "Requester",
        [
            ("Requested By", "__CreatedByDisplay"),
            ("Submitted At", "CreatedAt"),
        ],
        project,
    ))

    project_cards.append(render_stakeholders_card(
        "Project Stakeholders",
        stakeholders,
    ))

    # -------------------------
    # Round cards
    # -------------------------
    round_cards = []

    if rounds:
        for i, r in enumerate(rounds, start=1):
            round_title = f"Round {r.get('RoundNumber') or i}"

            round_cards.append(render_card(
                round_title,
                [
                    ("Round Name", "RoundName"),
                    ("Countries", "Region"),
                    ("User Scope", "UserScope"),
                    ("Shipping Date", "ShipDate"),
                    ("Gate X", "GateX_Date"),
                ],
                r,
            ))
    else:
        round_cards.append("""
        <section class="admin-review-card">
            <h3 class="section-title">Rounds</h3>
            <p class="admin-review-empty">No rounds found.</p>
        </section>
        """)

    content = f"""
    <section class="admin-project-review-page">
        <div class="page-header admin-project-review-header">
            <a class="admin-back-link" href="/admin/approvals">← Back to Approvals</a>
            <h2 class="page-title">{page_title}</h2>
            <p class="page-description">
                Review the submitted Product Trial request before making an approval decision.
            </p>
        </div>

        <div class="admin-review-grid">
            {''.join(project_cards)}
            {''.join(round_cards)}
        </div>
    </section>
    """

    return {"html": content}