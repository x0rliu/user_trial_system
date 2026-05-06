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
            <section>
                <h1>Project Review</h1>
                <p>Project not found.</p>
                <p><a href="/admin/approvals">← Back</a></p>
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

        users = get_users_with_permission_levels([0,20,30,40,50,60,70,80,100])

        match = next((u for u in users if u["user_id"] == created_by), None)

        if match:
            name = f"{match.get('FirstName','')} {match.get('LastName','')}".strip()
            if name:
                creator_display = name

    project["__CreatedByDisplay"] = creator_display

    # -------------------------
    # Section Renderer
    # -------------------------
    def render_section(title, fields, data):
        rows = []

        for label, key in fields:
            v = data.get(key)

            val = "—" if v in (None, "") else e(v)

            rows.append(f"""
            <tr>
                <th style="text-align:left;padding:8px 12px;width:220px;background:#f7f7f7;">
                    {e(label)}
                </th>
                <td style="padding:8px 12px;">
                    {val}
                </td>
            </tr>
            """)

        return f"""
        <section style="margin-bottom:24px;">
            <h2 style="margin-bottom:8px;">{e(title)}</h2>
            <table style="width:100%;border-collapse:collapse;">
                {''.join(rows)}
            </table>
        </section>
        """

    # -------------------------
    # Project Sections
    # -------------------------
    project_sections = []

    project_sections.append(render_section(
        "Product Identity",
        [
            ("Project Name", "ProjectName"),
            ("Market Name", "MarketName"),
            ("Product Type", "ProductType"),
            ("Description", "Description"),
        ],
        project
    ))

    project_sections.append(render_section(
        "Business",
        [
            ("Business Group", "BusinessGroup"),
            ("Business Sub Group", "BusinessSubGroup"),
        ],
        project
    ))

    project_sections.append(render_section(
        "Participant Requirements",
        [
            ("Min Age", "MinAge"),
            ("Max Age", "MaxAge"),
            ("Guardian Required", "GuardianRequired"),
        ],
        project
    ))

    project_sections.append(render_section(
        "Documentation",
        [
            ("PRD Document", "PRD_Document"),
            ("G1 Document", "G1_Document"),
            ("G0 Document", "G0_Document"),
            ("Additional Docs", "AdditionalDocs"),
        ],
        project
    ))

    project_sections.append(render_section(
        "System",
        [
            ("Project ID", "ProjectID"),
            ("Created By", "__CreatedByDisplay"),
            ("Created At", "CreatedAt"),
            ("Updated At", "UpdatedAt"),
        ],
        project
    ))

    # -------------------------
    # Round Sections
    # -------------------------
    round_blocks = []

    if rounds:
        for i, r in enumerate(rounds, start=1):
            round_blocks.append(render_section(
                f"Round {i}",
                [
                    ("Round Name", "RoundName"),
                    ("Region", "Region"),
                    ("User Scope", "UserScope"),
                    ("Target Users", "TargetUsers"),
                    ("Start Date", "StartDate"),
                    ("End Date", "EndDate"),
                    ("Ship Date", "ShipDate"),
                    ("Min Age", "MinAge"),
                    ("Max Age", "MaxAge"),
                    ("Prototype Version", "PrototypeVersion"),
                    ("Product SKU", "ProductSKU"),
                    ("UT Lead", "UTLead_UserID"),
                    ("Status", "Status"),
                ],
                r
            ))
    else:
        round_blocks.append("""
        <section>
            <h2>Rounds</h2>
            <p>No rounds found.</p>
        </section>
        """)

    # -------------------------
    # Final Content
    # -------------------------
    # SECURITY NOTE:
    # project_sections and round_blocks must contain ONLY pre-escaped / safe HTML

    content = f"""
    <section>
        <h1>Project Review</h1>
        <p><a href="/admin/approvals">← Back</a></p>
    </section>

    {''.join(project_sections)}

    {''.join(round_blocks)}
    """

    return {"html": content}