# app/handlers/trials.py

from app.db.project_participants import get_active_trials_for_user
from app.db.project_round_interest import record_round_interest
from app.db.project_round_interest import user_has_interest
from app.services.trial_visibility import get_visible_upcoming_rounds

def render_active_trials(user_id: str) -> str:
    """
    Active Trials view.
    Fragment only. No base.html. No redirects.
    """

    trials = get_active_trials_for_user(user_id)

    if not trials:
        return _render_no_active_trials()

    return _render_active_trials_list(trials)


def _render_no_active_trials() -> str:
    return """
    <section class="trials-section">
        <h1>Active Trials</h1>

        <p class="trials-empty">
            You are not currently in an active trial.
        </p>

        <p class="trials-hint">
            Check <strong>Currently Recruiting</strong> to apply for trials,
            or <strong>Upcoming Trials</strong> to see what’s coming next.
        </p>
    </section>
    """

def _render_logistics_section(t: dict) -> str:
    """
    Logistics section using structured service state (t["device"], t["shipping"])
    """

    device = t["device"]
    shipping = t["shipping"]

    state = device["state"]

    # Collapse if fully done
    collapsed_attr = " data-collapsed='true'" if state == "completed" else ""

    rows = []

    # -------------------------
    # DELIVERY TYPE
    # -------------------------
    delivery_type = t.get("delivery_type") or "Home"

    if delivery_type == "Home":
        label = "Home Delivery"
    else:
        label = "Office Pickup"

    rows.append(f"""
    <div class="logistics-row">
        <span class="label">Delivery</span>
        <span class="value">{label}</span>
    </div>
    """)

    # -------------------------
    # STATE-DRIVEN LOGIC
    # -------------------------
    if state == "pending":
        rows.append("""
        <div class="logistics-row status pending">
            <span class="value">Preparing shipment</span>
        </div>
        """)

    elif state == "in_transit":
        rows.append(f"""
        <div class="logistics-row status transit">
            <span class="label">Status</span>
            <span class="value">In Transit</span>
        </div>
        """)

        if device.get("tracking_url"):
            rows.append(f"""
            <div class="logistics-row">
                <span class="label">Tracking</span>
                <span class="value">
                    <a href="{device["tracking_url"]}" target="_blank" class="tracking-link">
                        Track Package
                    </a>
                </span>
            </div>
            """)

    elif state == "awaiting_confirmation":
        rows.append(f"""
        <div class="logistics-row status delivered">
            <span class="label">Status</span>
            <span class="value">Delivered</span>
        </div>
        """)

        rows.append("""
        <div class="logistics-row highlight">
            <span class="value">Please confirm you have received the device</span>
        </div>
        """)

    elif state == "completed":
        rows.append(f"""
        <div class="logistics-row status delivered">
            <span class="label">Status</span>
            <span class="value">Received</span>
        </div>
        """)

    if not rows:
        return ""

    return f"""
    <section class="trial-logistics"{collapsed_attr}>
        <h3>Logistics</h3>
        <div class="logistics-body">
            {''.join(rows)}
        </div>
    </section>
    """

def _render_action_checklist(t: dict) -> str:
    """
    Table-based deterministic checklist using structured service output.
    """

    # -------------------------
    # STATUS SYSTEM (STANDARDIZED)
    # -------------------------
    def done():
        return '<span class="status-badge status-completed">Completed</span>'

    def locked():
        return '<span class="status-badge status-locked">Locked</span>'

    def muted(text):
        return f'<span class="status-muted">{text}</span>'

    def action(url, text):
        return f'<span class="status-action"><a href="{url}">{text}</a></span>'

    def button(form_html):
        return f'<span class="status-action">{form_html}</span>'

    # -------------------------
    # ROW BUILDER
    # -------------------------
    def row(label, desc, status, deadline=None):
        deadline_html = "—"

        if deadline:
            try:
                deadline_html = deadline.strftime("%Y-%m-%d")
            except Exception:
                deadline_html = str(deadline)

        return f"""
        <tr>
            <td>{label}</td>
            <td>{desc}</td>
            <td>{status}</td>
            <td>{deadline_html}</td>
        </tr>
        """

    rows = []

    # -------------------------
    # NDA
    # -------------------------
    if t["nda"]["required"]:
        if t["nda"]["signed"]:
            status = done()
        else:
            status = action(f"/trials/nda?round_id={t['RoundID']}", "Sign")

        rows.append(row(
            "NDA",
            "Review and sign the trial NDA",
            status,
            t["deadlines"]["effective_deadline"]
        ))

    # -------------------------
    # SHIPPING ADDRESS
    # -------------------------
    if t["shipping"]["required"]:

        address_text = t.get("shipping_address_display") or "No address on file"

        expand_id = f"shipping-edit-{t['RoundID']}"

        # -------------------------
        # STATUS BUTTONS
        # -------------------------
        if t["shipping"]["confirmed"]:
            status = f"""
            <div>
                {done()}
                <button 
                    type="button" 
                    id="btn-{expand_id}" 
                    onclick="toggleShipping('{expand_id}', 'btn-{expand_id}')"
                >
                    Edit
                </button>
            </div>
            """
        else:
            status = f"""
            <div>
                <form method="POST" action="/trials/confirm-shipping" style="display:inline;">
                    <input type="hidden" name="round_id" value="{t['RoundID']}">
                    <button type="submit">Confirm</button>
                </form>

                <button 
                    type="button" 
                    id="btn-{expand_id}" 
                    onclick="toggleShipping('{expand_id}', 'btn-{expand_id}')"
                >
                    Add / Edit
                </button>
            </div>
            """

        # -------------------------
        # EXPANDABLE FORM
        # -------------------------
        expand_html = f"""
        <div style="
            margin-top:10px;
            padding:16px;
            border:1px solid #ddd;
            background:#fafafa;
        ">

            <form method="POST" action="/trials/save-shipping">

                <input type="hidden" name="round_id" value="{t['RoundID']}">

                <!-- DELIVERY METHOD -->
                <div style="margin-bottom:14px;">
                    <div style="font-size:13px; color:#555; margin-bottom:6px;">
                        Delivery Method
                    </div>

                    <select 
                        name="delivery_type" 
                        onchange="toggleDeliveryFields(this, '{expand_id}')"
                        style="width:100%; padding:6px 8px; box-sizing:border-box;"
                    >
                        <option value="Home" {"selected" if t.get("delivery_type") == "Home" else ""}>
                            Home
                        </option>

                        <option value="Office" {"selected" if t.get("delivery_type") == "Office" else ""}>
                            Office (Internal Only)
                        </option>
                    </select>
                </div>

                <!-- ADDRESS -->
                <div style="margin-bottom:14px;">
                    <div style="font-size:13px; color:#555; margin-bottom:6px;">
                        Address
                    </div>

                    <div class="home-fields">

                        <input name="line1" value="{t['prefill']['line1']}" placeholder="Address Line 1"
                            style="width:100%; margin-bottom:10px; padding:6px 8px; box-sizing:border-box;">

                        <input name="line2" value="{t['prefill']['line2']}" placeholder="Address Line 2"
                            style="width:100%; margin-bottom:10px; padding:6px 8px; box-sizing:border-box;">

                        <input name="city" value="{t['prefill']['city']}" placeholder="City"
                            style="width:100%; margin-bottom:10px; padding:6px 8px; box-sizing:border-box;">

                        <input name="state" value="{t['prefill']['state']}" placeholder="State/Region"
                            style="width:100%; margin-bottom:10px; padding:6px 8px; box-sizing:border-box;">

                        <input name="postal" value="{t['prefill']['postal']}" placeholder="Postal Code"
                            style="width:100%; margin-bottom:10px; padding:6px 8px; box-sizing:border-box;">

                        <input name="country" value="{t['prefill']['country']}" placeholder="Country"
                            style="width:100%; margin-bottom:10px; padding:6px 8px; box-sizing:border-box;">

                    </div>
                </div>

                <!-- OFFICE -->
                <div class="office-fields" style="display:none; margin-bottom:14px;">
                    <select name="office_id" style="width:100%; padding:6px 8px;">
                        <option value="">Select Office</option>
                    </select>
                </div>

                <!-- SAVE OPTION -->
                <div style="margin-top:10px; font-size:13px;">
                    <label style="display:flex; align-items:center; gap:6px;">
                        <input type="checkbox" name="save_globally" value="1">
                        Save this address for future trials
                    </label>
                </div>

                <!-- BUTTON -->
                <div style="margin-top:16px;">
                    <button type="submit" style="padding:6px 14px;">
                        Save
                    </button>
                </div>

            </form>
        </div>
        """

        # -------------------------
        # MAIN ROW (CLEAN)
        # -------------------------
        rows.append(row(
            "Shipping Address",
            f"Confirm delivery location: {address_text}",
            status,
            t["deadlines"]["effective_deadline"]
        ))

        # -------------------------
        # EXPAND ROW (FULL WIDTH)
        # -------------------------
        rows.append(f"""
        <tr id="{expand_id}" style="display:none;">
            <td colspan="4" style="padding:0; border:none;">

                <div style="
                    width:100%;
                    display:flex;
                    justify-content:center;
                    background:#fafafa;
                    border-top:1px solid #eee;
                    padding:16px 24px;
                ">

                    <div style="
                        max-width:700px;
                        width:100%;
                    ">
                        {expand_html}
                    </div>

                </div>

            </td>
        </tr>
        """)

    # -------------------------
    # RESPONSIBILITIES
    # -------------------------
    if t["responsibilities"]["accepted"]:
        status = done()
    else:
        status = action(
            f"/trials/responsibilities?round_id={t['RoundID']}",
            "Review"
        )

    rows.append(row(
        "Responsibilities",
        "Review expectations and confirm participation",
        status,
        t["deadlines"]["effective_deadline"]
    ))

    # -------------------------
    # DEVICE
    # -------------------------
    device_state = t["device"]["state"]

    if device_state == "pending":
        status = muted("Pending shipment")

    elif device_state == "in_transit":
        if t["device"].get("tracking_url"):
            status = action(t["device"]["tracking_url"], "Track")
        else:
            status = muted("In transit")

    elif device_state == "awaiting_confirmation":
        status = action(
            f"/trials/confirm-receipt?round_id={t['RoundID']}",
            "Confirm Receipt"
        )

    else:
        status = done()

    rows.append(row(
        "Device",
        "Track shipment and confirm receipt",
        status
    ))

    # -------------------------
    # SURVEY 1
    # -------------------------
    if t["survey1"]["required"]:
        if t["survey1"]["completed"]:
            status = done()
        elif t["survey1"]["available"]:
            status = action(t["survey1"]["url"], "Open")
        else:
            status = locked()

        rows.append(row(
            "Survey 1",
            "Initial impressions survey",
            status,
            t["survey1"]["deadline"]
        ))

    # -------------------------
    # SURVEY 2
    # -------------------------
    if t["survey2"]["required"]:
        if t["survey2"]["completed"]:
            status = done()
        elif t["survey2"]["available"]:
            status = action(t["survey2"]["url"], "Open")
        else:
            status = locked()

        rows.append(row(
            "Survey 2",
            "Usage and feedback survey",
            status,
            t["survey2"]["deadline"]
        ))

    # -------------------------
    # FINAL TABLE
    # -------------------------
    return f"""
    <section class="trial-checklist">
        <h3>Action Checklist</h3>

        <table class="checklist-table">
            <thead>
                <tr>
                    <th>Action</th>
                    <th>Description</th>
                    <th>Status</th>
                    <th>Deadline</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </section>
    """

from app.services.active_trial import build_active_trial_context

def _render_active_trials_list(trials: list[dict]) -> str:
    items = []

    for raw in trials:
        t = build_active_trial_context(raw)

        logistics_html = _render_logistics_section(t)
        checklist_html = _render_action_checklist(t)

        if t["needs_replacement"]:
            warning_html = """
            <div class="trial-warning">
                ⚠ Action Required: Participant may be replaced due to missed onboarding deadline.
            </div>
            """
        else:
            warning_html = ""

        items.append(f"""
        <div class="trial-card">

            <div class="trial-header">
                <div class="trial-title">
                    <h2>{raw['ProjectName']}</h2>
                    <span class="trial-round">{raw['RoundName']}</span>
                </div>

                <div class="trial-meta">
                    <div class="meta-row">
                        <span class="meta-label">Product</span>
                        <span class="meta-value">{raw['ProductType']}</span>
                    </div>
                    <div class="meta-row">
                        <span class="meta-label">Dates</span>
                        <span class="meta-value">{raw['StartDate']} → {raw['EndDate']}</span>
                    </div>
                </div>
            </div>

            {warning_html}

            {logistics_html}
            {checklist_html}

        </div>
        """)

    return f"""
    <section class="trials-section">
        <h1>Active Trials</h1>
        {''.join(items)}
    </section>
    """

#-------------------
# Upcoming Trials Section
#-------------------

from app.db.project_rounds import get_upcoming_project_rounds
from app.db.user_pool import get_all_users
from app.db.user_pool_country_codes import get_user_country

def render_upcoming_trials(user_id: str) -> str:
    """
    Upcoming Trials – table view only.
    Read-only + interest intent scaffold.
    """

    from app.services.trial_visibility import get_visible_upcoming_rounds

    rounds = get_visible_upcoming_rounds(user_id=user_id)

    for r in rounds:
        print(
            "ROUND:",
            r.get("RoundID"),
            "|",
            r.get("RoundName"),
            "| REGION:",
            r.get("Region"),
            "| START:",
            r.get("StartDate")
        )

    if not rounds:
        return """
        <section>
            <h1>Upcoming Trials</h1>

            <p>
                There are no upcoming trials available right now.
            </p>

            <p>
                When new trials are scheduled, they will appear here.
            </p>
        </section>
        """

    rows = []

    for i, r in enumerate(rounds):

        row_bg = "#ffffff" if i % 2 == 0 else "#fafafa"

        round_id = r["RoundID"]

        if user_has_interest(user_id=user_id, round_id=round_id):
            cta_html = '<span style="color:#2a7a2a;font-weight:600;">✓ Watching</span>'
        else:
            cta_html = f'<a href="/trials/interest?round_id={round_id}">Notify when recruiting opens</a>'

        rows.append(f"""
        <tr bgcolor="{row_bg}">
            <td valign="top">
                {r['RoundName']}
            </td>
            <td valign="top" nowrap>
                {r.get('StartDate') or "—"}
            </td>
            <td valign="top" nowrap>
                {cta_html}
            </td>
        </tr>
        <tr>
            <td colspan="3" bgcolor="#eaeaea" height="1"></td>
        </tr>
        """)

    return f"""
    <section>
        <h1>Upcoming Trials</h1>

        <table cellpadding="10" cellspacing="0" width="100%" border="0">
            <thead>
                <tr>
                    <th align="left" bgcolor="#f2f2f2">Trial</th>
                    <th align="left" bgcolor="#f2f2f2">Start Date</th>
                    <th align="left" bgcolor="#f2f2f2"></th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </section>
    """

#-------------------
# Currently Recruiting Trials Section
#-------------------

from app.services.trial_visibility import get_visible_recruiting_rounds
from app.db.project_applicants import has_applied


def render_recruiting_trials(user_id: str) -> str:
    rounds = get_visible_recruiting_rounds(user_id=user_id)

    from app.db.user_trial_lead import get_round_surveys

    def build_apply_cta(r):
        round_id = r["RoundID"]
        round_name = r.get("RoundName", "Trial")

        status = (r.get("Status") or "").lower()

        from app.db.user_trial_lead import get_round_surveys

        # 🔹 Detect external recruiting survey
        surveys = get_round_surveys(round_id)

        has_external_recruiting = False

        for s in surveys:
            survey_name = (s.get("SurveyTypeName") or "").lower()
            link = (s.get("DistributionLink") or "").strip()

            if "recruit" in survey_name and link:
                has_external_recruiting = True
                break

        # -------------------------
        # BASE APPLY UI
        # -------------------------

        if has_applied(user_id, round_id):

            base_html = f"""
            <span style="color:green;font-weight:bold;">✓ Applied</span>

            <form method="POST" action="/trials/withdraw" style="display:inline;">
                <input type="hidden" name="round_id" value="{round_id}">
                <button type="submit" style="margin-left:8px;">
                    Withdraw
                </button>
            </form>
            """

        else:

            # Scenario 2: External survey
            if has_external_recruiting:
                base_html = f"""
                <button
                    class="apply-toggle"
                    data-round-id="{round_id}"
                >
                    Apply & Continue
                </button>

                <div class="apply-form hidden" id="apply-form-{round_id}">

                    <form method="POST" action="/trials/apply">

                        <input type="hidden" name="round_id" value="{round_id}">

                        <p style="margin-bottom:8px;">
                            You will be redirected to a short survey after applying.
                        </p>

                        <textarea
                            name="motivation_text"
                            maxlength="300"
                            placeholder="In your own words, can you briefly tell us why you would like to join this trial? (Optional)"
                            style="width:100%; margin-bottom:8px;"
                        ></textarea>

                        <button type="submit">
                            Continue to Survey
                        </button>

                    </form>

                </div>
                """
            else:
                # Scenario 1: Internal
                base_html = f"""
                <button
                    class="apply-toggle"
                    data-round-id="{round_id}"
                >
                    Apply
                </button>

                <div class="apply-form hidden" id="apply-form-{round_id}">

                    <form method="POST" action="/trials/apply">

                        <input type="hidden" name="round_id" value="{round_id}">

                        <textarea
                            name="motivation_text"
                            maxlength="300"
                            placeholder="In your own words, Can you briefly tell us why would you like to join this trial? (Optional)"
                        ></textarea>

                        <button type="submit">
                            Submit Application
                        </button>

                    </form>

                </div>
                """

        # -------------------------
        # STATUS CONTROLS
        # -------------------------

        controls_html = ""

        if status == "recruiting":
            controls_html = f"""
            <form method="POST" action="/trials/end-recruiting" style="margin-top:8px;">
                <input type="hidden" name="round_id" value="{round_id}">
                <button type="submit" style="background:#d9534f;color:white;">
                    End Recruiting
                </button>
            </form>
            """

        elif status == "closed":
            controls_html = f"""
            <div style="margin-top:8px;">
                <a href="/trials/selection?round_id={round_id}">
                    <button>
                        Continue to Selection →
                    </button>
                </a>
            </div>
            """

        return base_html + controls_html

    table_html = _render_trials_table(
        title="Currently Recruiting Trials",
        rounds=rounds,
        cta_label="Apply",
        cta_url_builder=build_apply_cta,
    )

    return table_html


def _render_trials_table(
    *,
    title: str,
    rounds: list[dict],
    cta_label: str,
    cta_url_builder,
) -> str:

    if not rounds:
        return f"""
        <section>
            <h1>{title}</h1>
            <p>No trials available at this time.</p>
        </section>
        """

    rows = []

    for i, r in enumerate(rounds):

        row_bg = "#ffffff" if i % 2 == 0 else "#fafafa"

        round_name = r.get("RoundName", "(Unnamed Trial)")
        start_date = r.get("StartDate") or "TBD"
        round_id = r.get("RoundID")

        if round_id:
            try:
                cta_html = cta_url_builder(r)
            except Exception:
                cta_html = '<span style="color:#b00;">Error</span>'
        else:
            cta_html = '<span style="color:#888;">Unavailable</span>'

        rows.append(f"""
        <tr bgcolor="{row_bg}">
            <td valign="top">
                {round_name}
            </td>

            <td valign="top" nowrap>
                {start_date}
            </td>

            <td valign="top" nowrap style="text-align:right;">
                {cta_html}
            </td>
        </tr>

        <tr>
            <td colspan="3" bgcolor="#eaeaea" height="1"></td>
        </tr>
        """)

    return f"""
    <section>
        <h1>{title}</h1>

        <table cellpadding="10" cellspacing="0" width="100%" border="0">
            <thead>
                <tr>
                    <th align="left" bgcolor="#f2f2f2">Trial</th>
                    <th align="left" bgcolor="#f2f2f2">Start Date</th>
                    <th align="right" bgcolor="#f2f2f2">Action</th>
                </tr>
            </thead>

            <tbody>
                {''.join(rows)}
            </tbody>

        </table>
    </section>
    """

def render_active_trials_get(*, user_id: str, base_template: str, inject_nav):
    body = render_active_trials(user_id)

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Active Trials")
    html = html.replace("{{ body }}", body)

    return {"html": html}

def render_upcoming_trials_get(*, user_id: str, base_template: str, inject_nav):
    body = render_upcoming_trials(user_id)

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Upcoming Trials")
    html = html.replace("{{ body }}", body)

    return {"html": html}

def render_recruiting_trials_get(*, user_id: str, base_template: str, inject_nav):
    body = render_recruiting_trials(user_id)

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Currently Recruiting Trials")
    html = html.replace("{{ body }}", body)

    return {"html": html}

def render_past_trials_get(*, user_id: str, base_template: str, inject_nav):
    body = """
        <section>
            <h1>Past Trials</h1>
            <p>These are trials you have completed.</p>
            <p style="color:#888;">🚧 Trial history coming soon.</p>
        </section>
    """

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Past Trials")
    html = html.replace("{{ body }}", body)

    return {"html": html}

def handle_trial_interest(*, user_id: str, round_id: int):

    if not round_id or not user_id:
        return {"redirect": "/dashboard"}

    from app.services.round_access import validate_round_access

    validated_round = validate_round_access(
        actor_user_id=user_id,
        round_id=round_id,
        required_role="participant",
        allow_admin=True,
    )

    if not validated_round:
        return {"redirect": "/dashboard"}

    record_round_interest(
        user_id=user_id,
        round_id=round_id,
    )

    return {"redirect": "/trials/upcoming"}

from app.db.project_ndas import get_round_nda_status, insert_signed_round_nda


# ==================================================
# GET — Render Trial NDA Page
# ==================================================
def render_trial_nda_get(*, user_id, base_template, inject_nav, query_params):

    round_id = query_params.get("round_id", [None])[0]

    if not round_id:
        return {"redirect": "/dashboard"}

    from app.services.round_access import validate_round_access

    validated_round = validate_round_access(
        actor_user_id=user_id,
        round_id=round_id,
        required_role="participant",
        allow_admin=True,
    )

    if not validated_round:
        return {"redirect": "/dashboard"}

    round_id = int(round_id)

    # -------------------------
    # Get NDA status
    # -------------------------
    nda = get_round_nda_status(
        user_id=user_id,
        round_id=round_id
    )

    # Already signed → skip
    if nda["signed"]:
        return {"redirect": "/trials/active"}

    # -------------------------
    # Build UI
    # -------------------------
    from app.handlers.legal_documents import render_legal_document_view

    result = render_legal_document_view(
        document_type="round_nda",
        user_id=user_id,
    )

    nda_html = result.get("html", "")

    # -------------------------
    # FETCH REAL DATA
    # -------------------------
    from app.db.user_pool import get_user_by_userid

    user = get_user_by_userid(user_id)

    participant_name = ""
    if user:
        first = (user.get("FirstName") or "").strip()
        last = (user.get("LastName") or "").strip()
        participant_name = f"{first} {last}".strip()

    project_name = validated_round.get("ProjectName", "")
    product_name = validated_round.get("ProductType", "")
    program_name = "User Trial"

    # -------------------------
    # Signature injection
    # -------------------------
    from datetime import datetime

    participant_name = f"{user.get('FirstName','')} {user.get('LastName','')}".strip()

    nda_html = nda_html.replace("{{signature}}", participant_name)

    # If already signed → show actual date
    nda_status = get_round_nda_status(
        user_id=user_id,
        round_id=round_id
    )

    signed_at = nda_status.get("signed_at")

    if signed_at:
        signature_date = signed_at.strftime("%Y-%m-%d")
    else:
        signature_date = ""

    nda_html = nda_html.replace("{{signature_date}}", signature_date)

    # -------------------------
    # VARIABLE INJECTION
    # -------------------------
    nda_html = nda_html.replace("{{participant_name}}", participant_name)
    nda_html = nda_html.replace("{{project_name}}", project_name)
    nda_html = nda_html.replace("{{product_name}}", product_name)
    nda_html = nda_html.replace("{{program_name}}", program_name)

    # Optional (safe fallback)
    birth_year = user.get("BirthYear")

    if birth_year and 1900 <= int(birth_year) <= 2026:
        birth_year_str = str(birth_year)
    else:
        birth_year_str = ""

    nda_html = nda_html.replace("{{date_of_birth}}", birth_year_str)

    body = f"""
    <h2>Trial NDA Required</h2>

    <p><b>Project:</b> {validated_round["ProjectName"]}</p>
    <p><b>Round:</b> {validated_round["RoundName"]}</p>

    <hr>

    <div class="nda-document">
        {nda_html}
    </div>

    <form method="POST" action="/trials/nda" onsubmit="return validateNDAForm();" style="margin-top:20px;">
        <input type="hidden" name="round_id" value="{round_id}">

        <label>
            <input type="checkbox" name="agree_data" required>
            I agree to the collection and use of my personal data
        </label><br>

        <label>
            <input type="checkbox" name="agree_contact">
            I agree to be contacted for future trials
        </label><br><br>

        <button type="submit">I Agree & Sign</button>
    </form>

    <script>
    function validateNDAForm() {{
        const data = document.querySelector('input[name="agree_data"]');

        if (!data.checked) {{
            alert("You must agree to the data usage terms to participate.");
            return false;
        }}

        return true;
    }}
    </script>
    """
    
    html = base_template
    html = inject_nav(html)
    html = html.replace("{{ body }}", body)

    return {"html": html}


# ==================================================
# POST — Handle NDA Signing
# ==================================================
def handle_trial_nda_post(*, user_id, data):

    round_id = data.get("round_id")

    if not round_id:
        return {"redirect": "/dashboard"}

    from app.services.round_access import validate_round_access

    validated_round = validate_round_access(
        actor_user_id=user_id,
        round_id=round_id,
        required_role="participant",
        allow_admin=True,
    )

    if not validated_round:
        return {"redirect": "/dashboard"}

    round_id = int(round_id)

    # -------------------------
    # Sign NDA
    # -------------------------
    agree_data = data.get("agree_data")

    if not agree_data:
        return {
            "redirect": f"/trials/nda?round_id={round_id}&error=must_accept"
        }

    insert_signed_round_nda(
        user_id=user_id,
        round_id=round_id
    )

    return {
        "redirect": "/trials/active"
    }

def handle_shipping_save_post(*, user_id: str, data: dict):

    round_id = data.get("round_id")

    if not round_id:
        return {"redirect": "/trials/active"}

    try:
        round_id = int(round_id)
    except ValueError:
        return {"redirect": "/trials/active"}

    from app.services.round_access import validate_round_access

    validated_round = validate_round_access(
        actor_user_id=user_id,
        round_id=round_id,
        required_role="participant",
        allow_admin=True,
    )

    if not validated_round:
        return {"redirect": "/dashboard"}

    # -------------------------
    # Extract form data
    # -------------------------
    delivery_type = data.get("delivery_type") or "Home"

    save_globally = data.get("save_globally") == "1"

    address_data = {
        "line1": data.get("line1"),
        "line2": data.get("line2"),
        "city": data.get("city"),
        "state": data.get("state"),
        "postal": data.get("postal"),
        "country": data.get("country"),
    }

    office_id = data.get("office_id")

    # -------------------------
    # Guardrails
    # -------------------------
    # External users cannot use office
    from app.db.user_pool import get_user_by_userid

    user = get_user_by_userid(user_id)

    is_internal = bool(user and user.get("InternalUser"))

    if not is_internal and delivery_type == "Office":
        return {"redirect": "/trials/active"}

    # -------------------------
    # Save
    # -------------------------
    from app.services.shipping_service import save_shipping_address

    save_shipping_address(
        user_id=user_id,
        round_id=round_id,
        delivery_type=delivery_type,
        address_data=address_data,
        office_id=office_id,
        save_globally=save_globally,
    )

    return {"redirect": "/trials/active"}