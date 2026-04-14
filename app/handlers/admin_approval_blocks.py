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
        approval_id = str(a["approval_id"])

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
