# app/handlers/admin_approvals.py

from app.utils.html_escape import escape_html as e
from app.db.project_projects import get_project_for_review
from app.db.project_rounds import get_rounds_for_project_review


def render_admin_approval_project_get(
    *,
    user_id: str,
    project_id: str,
    query_params,
):
    project = get_project_for_review(project_id=project_id)
    rounds = get_rounds_for_project_review(project_id=project_id)

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
            ("Business Sub Group", "BusinessSubGroup"),
        ],
        project,
    ))

    project_cards.append(render_card(
        "Participant Requirements",
        [
            ("Min Age", "MinAge"),
            ("Max Age", "MaxAge"),
            ("Guardian Required", "GuardianRequired"),
        ],
        project,
    ))

    project_cards.append(render_card(
        "Documentation",
        [
            ("PRD Document", "PRD_Document"),
            ("G1 Document", "G1_Document"),
            ("G0 Document", "G0_Document"),
            ("Additional Docs", "AdditionalDocs"),
        ],
        project,
    ))

    project_cards.append(render_card(
        "System",
        [
            ("Project ID", "ProjectID"),
            ("Created By", "__CreatedByDisplay"),
            ("Created At", "CreatedAt"),
            ("Updated At", "UpdatedAt"),
        ],
        project,
    ))

    # -------------------------
    # Round cards
    # -------------------------
    round_cards = []

    if rounds:
        for i, r in enumerate(rounds, start=1):
            round_cards.append(render_card(
                f"Round {i}",
                [
                    ("Round Name", "RoundName"),
                    ("Region", "Region"),
                    ("User Scope", "UserScope"),
                    ("Target Users", "TargetUsers"),
                    ("Start Date", "StartDate"),
                    ("End Date", "EndDate"),
                    ("Ship Date", "ShipDate"),
                    ("Gate X", "GateX_Date"),
                    ("Min Age", "MinAge"),
                    ("Max Age", "MaxAge"),
                    ("Prototype Version", "PrototypeVersion"),
                    ("Product SKU", "ProductSKU"),
                    ("UT Lead", "UTLead_UserID"),
                    ("Status", "Status"),
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
            <h2 class="page-title">Project Review</h2>
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