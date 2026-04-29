# app/handlers/trials.py

from app.db.project_participants import get_active_trials_for_user
from app.db.project_round_interest import record_round_interest
from app.db.project_round_interest import user_has_interest
from app.services.trial_visibility import get_visible_upcoming_rounds
from app.utils.html_escape import escape_html as e
from app.services.active_trial import build_active_trial_context

def render_active_trials(user_id: str) -> str:
    """
    Active Trials view.
    Fragment only. No base.html. No redirects.
    """

    raw_trials = get_active_trials_for_user(user_id)

    if not raw_trials:
        return _render_no_active_trials()

    trials = [
        build_active_trial_context(row)
        for row in raw_trials
    ]

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

def _format_date(val):
    if not val:
        return "—"

    try:
        return val.strftime("%Y-%m-%d")
    except Exception:
        return str(val)

def _render_logistics_section(t: dict) -> str:
    """
    Render logistics information for a trial.
    SAFE VERSION — all dynamic values escaped.
    """

    def safe(val):
        return e(str(val or ""))

    device = t["device"]
    device_name = device.get("name") or "Assigned device"

    label = ""
    link_html = ""

    if device["state"] == "pending":
        label = "Shipment pending"

    elif device["state"] == "in_transit":
        label = "In transit"

        if device.get("tracking_url"):
            safe_url = safe(device["tracking_url"])

            link_html = f"""
            <div style="margin-top:6px;">
                <a href="{safe_url}" target="_blank" rel="noopener noreferrer">
                    Track shipment
                </a>
            </div>
            """

    elif device["state"] == "awaiting_confirmation":
        label = "Delivered – confirmation required"

    else:
        label = "Delivered"

    return f"""
    <section class="trial-logistics">
        <h3>Logistics</h3>

        <div class="logistics-card">
            <div class="logistics-row">
                <div class="logistics-label">Device</div>
                <div class="logistics-value">{safe(device_name)}</div>
            </div>

            <div class="logistics-row">
                <div class="logistics-label">Status</div>
                <div class="logistics-value">{safe(label)}</div>
            </div>

            {link_html}
        </div>
    </section>
    """

def _render_action_checklist(t: dict) -> str:
    """
    Table-based deterministic checklist using structured service output.
    SAFE VERSION — all dynamic values escaped.
    """

    def safe(val):
        return e(str(val or ""))

    # -------------------------
    # STATUS SYSTEM
    # -------------------------
    def status_completed():
        return '<span class="status-badge status-completed">Completed</span>'

    def status_pending():
        return '<span class="status-badge status-locked">Pending</span>'

    def status_attention():
        return '<span class="status-badge status-attention">Action Required</span>'

    def status_blocked(text="Not Available"):
        return f'<span class="status-badge status-locked">{safe(text)}</span>'

    # -------------------------
    # ROW BUILDER
    # -------------------------
    def row(label, desc, status, actions="", deadline=None):
        deadline_html = "—"

        if deadline:
            try:
                deadline_html = safe(deadline.strftime("%Y-%m-%d"))
            except Exception:
                deadline_html = safe(deadline)

        return f"""
        <tr>
            <td>{safe(label)}</td>
            <td>{safe(desc)}</td>
            <td>{status}</td>
            <td>{actions}</td>
            <td>{deadline_html}</td>
        </tr>
        """

    rows = []

    # -------------------------
    # NDA
    # -------------------------
    if t["nda"]["required"]:
        if t["nda"]["signed"]:
            status = status_completed()
            actions = ""
        else:
            status = status_attention()
            actions = f"""
            <a href="/trials/nda?round_id={safe(t['RoundID'])}" class="action-btn">
                Sign
            </a>
            """

        rows.append(row(
            "NDA",
            "Review and sign the trial NDA",
            status,
            actions,
            t["deadlines"]["effective_deadline"]
        ))

    # -------------------------
    # SHIPPING ADDRESS
    # -------------------------
    if t["shipping"]["required"]:

        address_text = t.get("shipping_address_display") or "No address on file"
        expand_id = f"shipping-edit-{t['RoundID']}"

        safe_round_id = safe(t["RoundID"])
        safe_expand_id = safe(expand_id)

        # -------------------------
        # DELIVERY COMPLETENESS
        # -------------------------
        recipient = (t.get("first_name") or "") + " " + (t.get("last_name") or "")
        phone = t.get("phone_number")

        has_address = bool(t["prefill"].get("line1"))
        has_recipient = bool(recipient.strip())
        has_phone = bool(phone)

        delivery_ready = has_address and has_recipient and has_phone

        # -------------------------
        # STATUS + ACTIONS
        # -------------------------
        if not t["nda"]["signed"]:
            status = status_blocked("Locked")
            actions = ""

        else:
            if not delivery_ready:
                status = status_attention()

                actions = f"""
                <button 
                    type="button"
                    class="action-btn"
                    id="btn-{safe_expand_id}"
                    onclick="toggleShipping('{safe_expand_id}', 'btn-{safe_expand_id}')"
                >
                    Provide Details
                </button>
                """

            elif not t["shipping"]["confirmed"]:
                status = status_attention()

                actions = f"""
                <button 
                    type="button"
                    class="action-btn"
                    id="btn-{safe_expand_id}"
                    onclick="toggleShipping('{safe_expand_id}', 'btn-{safe_expand_id}')"
                >
                    Confirm Details
                </button>
                """

            else:
                status = status_completed()

                actions = f"""
                <button 
                    type="button"
                    class="action-btn"
                    id="btn-{safe_expand_id}"
                    onclick="toggleShipping('{safe_expand_id}', 'btn-{safe_expand_id}')"
                >
                    Edit
                </button>
                """

        rows.append(row(
            "Shipping Address",
            f"Confirm delivery location: {safe(address_text)}",
            status,
            actions,
            t["deadlines"]["effective_deadline"]
        ))

        # -------------------------
        # EXPAND PANEL
        # -------------------------
        expand_html = f"""
        <div class="shipping-panel" style="margin-top:10px;padding:16px;border:1px solid #ddd;background:#fafafa;">

            <form method="POST" action="/trials/save-shipping" class="shipping-form">

                <input type="hidden" name="round_id" value="{safe_round_id}">

                <div class="shipping-group">
                    <label>Recipient Name</label>

                    <div class="shipping-row">
                        <input 
                            name="first_name"
                            value="{safe(t.get('first_name') or '')}"
                            placeholder="First Name"
                            required
                        >
                        <input 
                            name="last_name"
                            value="{safe(t.get('last_name') or '')}"
                            placeholder="Last Name"
                            required
                        >
                    </div>
                </div>

                <div class="shipping-group">
                    <label>Phone Number</label>

                    <div class="shipping-row">
                        <input 
                            name="country_code"
                            value="{safe(t.get('phone_country_code') or '')}"
                            placeholder="+"
                            style="max-width:120px"
                            required
                        >

                        <input 
                            name="phone_number"
                            value="{safe(t.get('phone_national') or '')}"
                            placeholder="(Area Code) Phone Number"
                            required
                        >
                    </div>
                </div>

                <div class="shipping-group">
                    <label>Address</label>

                    <div class="shipping-row">
                        <input name="line1" value="{safe(t['prefill']['line1'])}" placeholder="Address Line 1" required>
                        <input name="line2" value="{safe(t['prefill']['line2'])}" placeholder="Address Line 2">
                        <input name="city" value="{safe(t['prefill']['city'])}" placeholder="City" required>
                        <input name="state" value="{safe(t['prefill']['state'])}" placeholder="State/Region">
                        <input name="postal" value="{safe(t['prefill']['postal'])}" placeholder="Postal Code">
                        <input name="country" value="{safe(t['prefill']['country'])}" placeholder="Country" required>
                    </div>
                </div>

                <div class="shipping-checkbox">
                    <label class="checkbox-inline">
                        <input type="checkbox" name="save_globally" value="1">
                        Save this address for future trials
                    </label>
                </div>

                <div class="shipping-actions">
                    <button type="submit" class="action-btn small">Save</button>
                </div>

            </form>
        </div>
        """

        rows.append(f"""
        <tr id="{safe_expand_id}" style="display:none;">
            <td colspan="5">{expand_html}</td>
        </tr>
        """)

    # -------------------------
    # RESPONSIBILITIES
    # -------------------------
    if not t["nda"]["signed"]:
        status = status_blocked("Locked")
        actions = ""

    else:
        if t["responsibilities"]["accepted"]:
            status = status_completed()
            actions = ""

        else:
            status = status_attention()

            actions = f"""
            <a href="/trials/responsibilities?round_id={safe(t['RoundID'])}" class="action-btn">
                Review & Accept
            </a>
            """

    rows.append(row(
        "Responsibilities",
        "Review expectations and confirm participation",
        status,
        actions,
        t["deadlines"]["effective_deadline"]
    ))

    # -------------------------
    # DEVICE
    # -------------------------
    device_state = t["device"]["state"]

    if device_state == "pending":
        status = status_pending()

    elif device_state == "in_transit":
        status = status_pending()

    elif device_state == "awaiting_confirmation":
        status = status_attention()

    else:
        status = status_completed()

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
            status = status_completed()
        elif t["survey1"]["available"]:
            status = status_attention()
        else:
            status = status_blocked("Not Available")

        rows.append(row(
            "Survey 1",
            "Initial feedback survey",
            status,
            t["survey1"]["deadline"]
        ))

    # -------------------------
    # SURVEY 2
    # -------------------------
    if t["survey2"]["required"]:

        if t["survey2"]["completed"]:
            status = status_completed()
        elif t["survey2"]["available"]:
            status = status_attention()
        else:
            status = status_blocked("Not Available")

        rows.append(row(
            "Survey 2",
            "Follow-up feedback survey",
            status,
            t["survey2"]["deadline"]
        ))

    return f"""
    <section class="trial-checklist">
        <h3>User Trial Checklist</h3>

        <table class="checklist-table">
            <thead>
                <tr>
                    <th>Requirement</th>
                    <th>Description</th>
                    <th>Status</th>
                    <th>Actions</th>
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
    """
    Render list of active trials.
    SAFE VERSION — all dynamic values escaped.
    """

    def safe(val):
        return e(str(val or ""))

    if not trials:
        return _render_no_active_trials()

    cards = []

    for raw in trials:
        safe_project = safe(raw.get("ProjectName"))
        safe_round = safe(raw.get("RoundName"))

        cards.append(f"""
        <div class="trial-card">

            <div class="trial-card-header">
                <h2>{safe_project}</h2>
                <span class="trial-subtitle">{safe_round}</span>
            </div>

            {_render_action_checklist(raw)}
            {_render_logistics_section(raw)}

        </div>
        """)

    return "".join(cards)

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

    def safe(val):
        return e(str(val or ""))

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

        safe_round_name = safe(r.get("RoundName"))
        safe_start_date = safe(r.get("StartDate") or "—")
        safe_round_id = safe(round_id)

    if user_has_interest(user_id=user_id, round_id=round_id):
        cta_html = '<span style="color:#2a7a2a;font-weight:600;">✓ Watching</span>'
    else:
        cta_html = f"""
        <form method="POST" action="/trials/interest" style="display:inline;">
            <input type="hidden" name="round_id" value="{safe_round_id}">
            <button type="submit" style="background:none;border:none;color:#0066cc;cursor:pointer;padding:0;">
                Notify when recruiting opens
            </button>
        </form>
        """
        rows.append(f"""
        <tr bgcolor="{row_bg}">
            <td valign="top">
                {safe_round_name}
            </td>
            <td valign="top" nowrap>
                {safe_start_date}
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

    def safe(val):
        return e(str(val or ""))

    def build_apply_cta(r):
        round_id = r["RoundID"]
        safe_round_id = safe(round_id)

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
                <input type="hidden" name="round_id" value="{safe_round_id}">
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
                    data-round-id="{safe_round_id}"
                >
                    Apply & Continue
                </button>

                <div class="apply-form hidden" id="apply-form-{safe_round_id}">

                    <form method="POST" action="/trials/apply">

                        <input type="hidden" name="round_id" value="{safe_round_id}">

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
                    data-round-id="{safe_round_id}"
                >
                    Apply
                </button>

                <div class="apply-form hidden" id="apply-form-{safe_round_id}">

                    <form method="POST" action="/trials/apply">

                        <input type="hidden" name="round_id" value="{safe_round_id}">

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
                <input type="hidden" name="round_id" value="{safe_round_id}">
                <button type="submit" style="background:#d9534f;color:white;">
                    End Recruiting
                </button>
            </form>
            """

        elif status == "closed":
            controls_html = f"""
            <div style="margin-top:8px;">
                <a href="/trials/selection?round_id={safe_round_id}">
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
    cta_url_builder
) -> str:
    """
    Render generic trials table.

    - title: section title
    - rounds: list of round dicts
    - cta_label: label for CTA (not used directly, kept for extensibility)
    - cta_url_builder: function to build CTA HTML per row

    SAFE VERSION — escape data, preserve CTA HTML.
    """

    def safe(val):
        return e(str(val or ""))

    rows = []

    for r in rounds:
        round_name = r.get("RoundName", "—")
        start_date = _format_date(r.get("StartDate"))

        cta_html = cta_url_builder(r)

        safe_round = safe(round_name)
        safe_date = safe(start_date)

        rows.append(f"""
        <tr>
            <td>{safe_round}</td>
            <td>{safe_date}</td>
            <td>{cta_html}</td>
        </tr>
        """)

    return f"""
    <h2>{safe(title)}</h2>

    <table class="trials-table">
        <thead>
            <tr>
                <th>Round</th>
                <th>Start Date</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
    """

def render_active_trials_get(*, user_id: str, base_template: str, inject_nav):
    body = render_active_trials(user_id)

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Active Trials")
    html = html.replace("__BODY__", body)

    return {"html": html}

def render_upcoming_trials_get(*, user_id: str, base_template: str, inject_nav):
    body = render_upcoming_trials(user_id)

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Upcoming Trials")
    html = html.replace("__BODY__", body)

    return {"html": html}

def render_recruiting_trials_get(*, user_id: str, base_template: str, inject_nav):
    body = render_recruiting_trials(user_id)

    html = inject_nav(base_template)
    html = html.replace("{{ title }}", "Currently Recruiting Trials")
    html = html.replace("__BODY__", body)

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
    html = html.replace("__BODY__", body)

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

    def safe(val):
        return e(str(val or ""))

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
    # Signature injection (ESCAPED)
    # -------------------------
    participant_name_safe = safe(participant_name)

    nda_html = nda_html.replace("{{signature}}", participant_name_safe)

    nda_status = get_round_nda_status(
        user_id=user_id,
        round_id=round_id
    )

    signed_at = nda_status.get("signed_at")

    if signed_at:
        signature_date = signed_at.strftime("%Y-%m-%d")
    else:
        signature_date = ""

    nda_html = nda_html.replace("{{signature_date}}", safe(signature_date))

    # -------------------------
    # VARIABLE INJECTION (ESCAPED)
    # -------------------------
    nda_html = nda_html.replace("{{participant_name}}", participant_name_safe)
    nda_html = nda_html.replace("{{project_name}}", safe(project_name))
    nda_html = nda_html.replace("{{product_name}}", safe(product_name))
    nda_html = nda_html.replace("{{program_name}}", safe(program_name))

    # -------------------------
    # Optional DOB (ESCAPED)
    # -------------------------
    birth_year = user.get("BirthYear") if user else None

    if birth_year and 1900 <= int(birth_year) <= 2026:
        birth_year_str = str(birth_year)
    else:
        birth_year_str = ""

    nda_html = nda_html.replace("{{date_of_birth}}", safe(birth_year_str))

    # -------------------------
    # FINAL BODY (ESCAPED WRAPPING VALUES)
    # -------------------------
    safe_project = safe(validated_round.get("ProjectName"))
    safe_round_name = safe(validated_round.get("RoundName"))
    safe_round_id = safe(round_id)

    body = f"""
    <h2>Trial NDA Required</h2>

    <p><b>Project:</b> {safe_project}</p>
    <p><b>Round:</b> {safe_round_name}</p>

    <hr>

    <div class="nda-document">
        {nda_html}
    </div>

    <form method="POST" action="/trials/nda" onsubmit="return validateNDAForm();" style="margin-top:20px;">
        <input type="hidden" name="round_id" value="{safe_round_id}">

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
    html = html.replace("__BODY__", body)

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
    # 🔥 Phone normalization (CC + NATIONAL ONLY)
    # -------------------------
    def normalize_phone(country_code, phone_number):
        def clean(val):
            return (val or "").strip().replace(" ", "").replace("-", "")

        cc = clean(country_code)
        pn = clean(phone_number)

        if not cc or not pn:
            return None

        # -------------------------
        # 🔥 Enforce "+"
        # -------------------------
        if not cc.startswith("+"):
            cc = f"+{cc}"

        # -------------------------
        # 🔥 Remove ALL instances of CC (handles duplication safely)
        # -------------------------
        while pn.startswith(cc):
            pn = pn[len(cc):]

        # 🔥 Also handle case where "+" was stripped inconsistently
        cc_no_plus = cc.replace("+", "")
        while pn.startswith(cc_no_plus):
            pn = pn[len(cc_no_plus):]

        # -------------------------
        # 🔥 Remove trunk prefix (leading 0)
        # Global rule (Taiwan, UK, JP, etc.)
        # -------------------------
        if pn.startswith("0"):
            pn = pn[1:]

        # -------------------------
        # 🔥 Final canonical format
        # -------------------------
        return f"{cc}{pn}"


    full_phone = normalize_phone(
        data.get("country_code"),
        data.get("phone_number"),
    )

    # -------------------------
    # 🔥 Recipient data
    # -------------------------
    recipient_data = {
        "first_name": data.get("first_name"),
        "last_name": data.get("last_name"),
        "phone": full_phone,
    }

    # -------------------------
    # 🔥 Save via service
    # -------------------------
    from app.services.shipping_service import save_shipping_address

    save_shipping_address(
        user_id=user_id,
        round_id=round_id,
        delivery_type=delivery_type,
        address_data=address_data,
        recipient_data=recipient_data,
        office_id=office_id,
        save_globally=save_globally,
    )

    return {"redirect": "/trials/active"}