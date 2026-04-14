# app/handlers/admin_approval_blocks.py

from app.db.user_roles import get_users_with_permission_levels
from app.utils.html_escape import escape_html as e


UT_LEADS = get_users_with_permission_levels([70, 100])

# --------------------------------------------------
# UT Lead options (permission 70)
# --------------------------------------------------

def _render_ut_lead_options(users):
    return "".join(
        f"<option value='{u['user_id']}'>{u['FirstName']} {u['LastName']}</option>"
        for u in users
    )

UT_LEAD_OPTIONS_HTML = _render_ut_lead_options(UT_LEADS)


# --------------------------------------------------
# Product Trial Approval Block
# --------------------------------------------------

from app.utils.html_escape import escape_html as e


def render_product_trial_approval_block(items: list[dict]) -> str:
    rows = []

    for a in items:
        p = a["payload"]
        round_id = p.get("RoundID")
        if not round_id:
            raise RuntimeError("Product trial approval missing RoundID")

        approval_id = str(round_id)

        project_id = e(p.get("ProjectID"))
        project_name = e(p.get("ProjectName"))
        requested_by_name = e(p.get("requested_by_name") or "—")
        product_type = e(p.get("ProductType"))
        submitted_at = e(p.get("submitted_at") or "—")
        requested_by_user_id = e(p.get("requested_by_user_id"))

        rows.append(f"""
        <!-- Primary row -->
        <tr class="approval-row" data-approval-id="{e(approval_id)}">
            <td>
                <a href="/admin/approvals/project?project_id={project_id}">
                    {project_name}
                </a>
            </td>
            <td>{requested_by_name}</td>
            <td>{product_type}</td>
            <td>{submitted_at}</td>
            <td>
                <select class="approval-action">
                    <option value="">Choose an Action</option>
                    <option value="approve">Approve</option>
                    <option value="info_requested">Request Info</option>
                    <option value="request_change">Request Changes</option>
                    <option value="decline">Decline</option>
                </select>
            </td>
        </tr>

        <!-- Expand-down detail row -->
        <tr class="approval-detail hidden" data-approval-id="{e(approval_id)}">
            <td colspan="5">
                <div class="approval-form-wrapper">
                    <form method="post" action="/admin/approvals/submit">
                        <input type="hidden" name="approval_type" value="product_trial">
                        <input type="hidden" name="approval_id" value="{e(approval_id)}">
                        <input type="hidden" name="requested_by" value="{requested_by_user_id}">
                        <input type="hidden" name="action" value="">

                        <div class="approve-only hidden">
                            <label>Assign UT Lead</label>
                            <select name="assigned_ut_lead" required>
                                <option value="">Select UT Lead…</option>
                                {UT_LEAD_OPTIONS_HTML}
                            </select>
                        </div>

                        <div class="non-approve-only hidden">
                            <label>Reason Category</label>
                            <select name="reason_category" required>
                                <option value="">— Select a reason —</option>
                                <option value="clarification">Needs clarification</option>
                                <option value="scope_mismatch">Scope mismatch</option>
                                <option value="resource_constraint">Resource constraint</option>
                                <option value="timeline_conflict">Timeline conflict</option>
                                <option value="eligibility_issue">Eligibility issue</option>
                                <option value="other">Other</option>
                            </select>

                            <label style="margin-top:6px;">Details</label>
                            <textarea
                                name="detail_text"
                                rows="3"
                                placeholder="Explain the decision…"
                                required
                            ></textarea>
                        </div>

                        <div style="margin-top:8px;">
                            <button type="submit">Save</button>
                        </div>
                    </form>
                </div>
            </td>
        </tr>
        """)

    return f"""
    <h3>Product Trial Approvals</h3>
    <table class="data-table approval-table">
        <thead>
            <tr>
                <th>Project</th>
                <th>Requested By</th>
                <th>Product Type</th>
                <th>Est Start</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
    """


# --------------------------------------------------
# Bonus Survey Approval Block
# --------------------------------------------------

def render_bonus_survey_approval_block(items: list[dict]) -> str:
    rows = []

    for a in items:
        p = a["payload"]
        approval_id = str(a["approval_id"])  # tracker_id

        survey_title = e(p.get("survey_title"))
        requested_by_name = e(p.get("requested_by_name") or "—")
        bonus_survey_id = e(p.get("bonus_survey_id"))
        submitted_at = e(p.get("submitted_at") or "—")
        requested_by_user_id = e(p.get("requested_by_user_id"))

        rows.append(f"""
        <tr class="approval-row" data-approval-id="{e(approval_id)}">
            <td>
                <a href="/admin/approvals/view?tracker_id={e(approval_id)}">
                    {survey_title}
                </a>
            </td>
            <td>{requested_by_name}</td>
            <td>
                <a href="/surveys/bonus/edit?survey_id={bonus_survey_id}">
                    Open
                </a>
            </td>
            <td>{submitted_at}</td>
            <td>
                <select class="approval-action">
                    <option value="">Choose an Action</option>
                    <option value="approve">Approve</option>
                    <option value="info_requested">Request Info</option>
                    <option value="request_change">Request Changes</option>
                    <option value="decline">Decline</option>
                </select>
            </td>
        </tr>

        <tr class="approval-detail hidden" data-approval-id="{e(approval_id)}">
            <td colspan="5">
                <div class="approval-form-wrapper">
                    <form method="post" action="/admin/approvals/submit">
                        <input type="hidden" name="approval_type" value="bonus_survey">
                        <input type="hidden" name="approval_id" value="{e(approval_id)}">
                        <input type="hidden" name="requested_by" value="{requested_by_user_id}">
                        <input type="hidden" name="action" value="">

                        <div class="approve-only hidden">
                            <label>Assign UT Lead</label>
                            <select name="assigned_ut_lead" required>
                                <option value="">Select UT Lead…</option>
                                {UT_LEAD_OPTIONS_HTML}
                            </select>
                        </div>

                        <div class="non-approve-only hidden">
                            <label>Reason Category</label>
                            <select name="reason_category" required>
                                <option value="">— Select a reason —</option>
                                <option value="clarification">Needs clarification</option>
                                <option value="scope_mismatch">Scope mismatch</option>
                                <option value="resource_constraint">Resource constraint</option>
                                <option value="timeline_conflict">Timeline conflict</option>
                                <option value="eligibility_issue">Eligibility issue</option>
                                <option value="other">Other</option>
                            </select>

                            <label style="margin-top:6px;">Details</label>
                            <textarea
                                name="detail_text"
                                rows="3"
                                placeholder="Explain the decision…"
                                required
                            ></textarea>
                        </div>

                        <div style="margin-top:8px;">
                            <button type="submit">Save</button>
                        </div>
                    </form>
                </div>
            </td>
        </tr>
        """)

    return f"""
    <h3>Bonus Survey Approvals</h3>
    <table class="data-table approval-table">
        <thead>
            <tr>
                <th>Survey</th>
                <th>Requested By</th>
                <th>Link</th>
                <th>Submitted</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
    """


# --------------------------------------------------
# Renderer Registry
# --------------------------------------------------

APPROVAL_BLOCK_RENDERERS = {
    "bonus_survey": render_bonus_survey_approval_block,
    "product_trial": render_product_trial_approval_block,
}


from html import escape
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