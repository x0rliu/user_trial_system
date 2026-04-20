# app/handlers/admin.py

from app.db.user_roles import get_effective_permission_level

# approval aggregation
from app.services.approvals import get_pending_approvals

# approval block renderers
from app.handlers.admin_approval_blocks import APPROVAL_BLOCK_RENDERERS

# detail view dependencies (unchanged)
from app.db.surveys_tracker import (
    get_tracker_by_id,
    get_tracker_entries,
)
from app.db.surveys import get_bonus_survey_by_id
from app.utils.html_escape import escape_html as e



# --------------------------------------------------
# Permission Gate
# --------------------------------------------------

def _require_ut_lead(user_id: str):
    permission_level = get_effective_permission_level(user_id)
    if permission_level < 70:
        return {"redirect": "/dashboard"}
    return None


# --------------------------------------------------
# Admin Approvals Landing
# --------------------------------------------------

def render_admin_approvals_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
):
    """
    Admin approvals landing page.
    Chronological list of approval blocks.
    """

    denied = _require_ut_lead(user_id)
    if denied:
        return denied

    from app.services.approvals import get_pending_approvals
    from app.handlers.admin_approval_blocks import (
        render_product_trial_approval_block,
        render_bonus_survey_approval_block,
    )

    approvals = get_pending_approvals()

    grouped = {
        "product_trial": [],
        "bonus_survey": [],
    }

    for a in approvals:
        grouped[a["approval_type"]].append(a)

    blocks = []

    # Newest tables first
    if grouped["product_trial"]:
        blocks.append(render_product_trial_approval_block(grouped["product_trial"]))

    if grouped["bonus_survey"]:
        blocks.append(render_bonus_survey_approval_block(grouped["bonus_survey"]))

    body_html = "\n".join(blocks) or "<p>No items pending approval.</p>"

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Admin Approvals")
    html = html.replace("__BODY__", body_html)

    return {"html": html}



# --------------------------------------------------
# Admin Approval Detail View
# --------------------------------------------------

def render_admin_approval_view_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict,
):
    """
    Admin approval detail view.
    Admin-owned UI. Domain supplies data only.
    """

    denied = _require_ut_lead(user_id)
    if denied:
        return denied

    tracker_id = query_params.get("tracker_id", [None])[0]
    if not tracker_id:
        return {"redirect": "/admin/approvals"}

    tracker = get_tracker_by_id(int(tracker_id))
    if not tracker:
        return {"redirect": "/admin/approvals"}

    survey = get_bonus_survey_by_id(tracker["bonus_survey_id"])
    entries = get_tracker_entries(int(tracker_id))

    safe_tracker_id = e(tracker_id)
    survey_title = e(survey['survey_title'])
    current_state = e(tracker['current_state'])

    body = [
        f"<h2>{survey_title}</h2>",
        "<p>Type: <strong>Bonus Survey</strong></p>",
        f"<p>Status: <strong>{current_state}</strong></p>",
        "<hr>",
        "<h3>Approval History</h3>",
        "<div class='tracker-log'>",
    ]

    for entry in entries:
        actor_user_id = e(entry['actor_user_id'])
        entry_type = e(entry['entry_type'])
        detail_text = e(entry.get('detail_text') or '')
        created_at = e(entry['created_at'])

        body.append(
            f"""
            <div class="tracker-entry">
                <div><strong>{actor_user_id}</strong></div>
                <div>{entry_type}</div>
                <div class="tracker-detail">{detail_text}</div>
                <div class="tracker-time">{created_at}</div>
            </div>
            """
        )

    body.extend(
        [
            "</div>",
            "<hr>",
            f"""
            <form method="post" action="/surveys/bonus/approve">
                <input type="hidden" name="tracker_id" value="{safe_tracker_id}">
                <button type="submit">Approve</button>
            </form>

            <form method="post" action="/surveys/bonus/request-info">
                <input type="hidden" name="tracker_id" value="{safe_tracker_id}">
                <textarea name="detail_text" required></textarea>
                <button type="submit">Request More Information</button>
            </form>

            <form method="post" action="/surveys/bonus/request-changes">
                <input type="hidden" name="tracker_id" value="{safe_tracker_id}">
                <textarea name="detail_text" required></textarea>
                <button type="submit">Request Changes</button>
            </form>
            """,
        ]
    )

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Review Approval")
    html = html.replace("__BODY__", "\n".join(body))

    return {"html": html}
