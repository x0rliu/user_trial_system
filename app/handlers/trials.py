# app/handlers/trials.py

from app.db.project_participants import get_active_trials_for_user
from app.db.project_round_interest import record_round_interest
from app.db.project_round_interest import user_has_interest


def _normalize_trial(t: dict) -> dict:
    logistics = t.get("Logistics", {})

    return {
        **t,
        # flatten logistics
        "DeliveryType": logistics.get("DeliveryType", t.get("DeliveryType")),
        "Courier": logistics.get("Courier", t.get("Courier")),
        "TrackingNumber": logistics.get("TrackingNumber", t.get("TrackingNumber")),
        "TrackingURL": logistics.get("TrackingURL", t.get("TrackingURL")),
        "ShippedAt": logistics.get("ShippedAt", t.get("ShippedAt")),
        "DeliveredAt": logistics.get("DeliveredAt", t.get("DeliveredAt")),
    }

def _render_nda_section(t: dict) -> str:
    """
    NDA visibility block.
    Explicit, non-negotiable proof of agreement.
    """

    if not t.get("NDARequired"):
        return ""

    if not t.get("NDASignedAt"):
        return ""  # checklist owns the CTA


    signed_at = str(t["NDASignedAt"])[:16]

    return f"""
    <section class="trial-nda nda-signed">
        <h3>Non-Disclosure Agreement</h3>

        <div class="nda-row">
            <span class="label">Agreement</span>
            <span class="value">
                <a href="{t['NDADocumentURL']}" target="_blank">
                    {t['NDAName']}
                </a>
            </span>
        </div>

        <div class="nda-row">
            <span class="label">Signed On</span>
            <span class="value">{signed_at}</span>
        </div>

        <div class="nda-row">
            <span class="label">Between</span>
            <span class="value">
                {t['NDAPartyUser']} and {t['NDAPartyCompany']}
            </span>
        </div>

        <p class="nda-confirmation">
            This agreement is on record and applies to your participation in this trial.
        </p>
    </section>
    """

def render_active_trials(user_id: str) -> str:
    
    # TEMP: fake active trial
    trials=[{"ProjectName":"MX Master 4 Internal Trial","RoundName":"Round 1","TrialNickname":"Precision Mouse Trial","ProductType":"Mouse – Productivity","StartDate":"2026-01-01","EndDate":"2026-02-15","Logistics":{"DeliveryType":"Home","ShippingStatus":"Shipped","Courier":"FedEx","TrackingNumber":"FE123456789US","TrackingURL":"https://www.fedex.com/fedextrack/?tracknumbers=FE123456789US","ShippedAt":"2026-01-03 14:22","DeliveredAt":None},"Checklist":[{"id":"nda","label":"NDA Signed","status":"completed","cta":None},{"id":"shipping_address","label":"Confirm Shipping Address","status":"completed","cta":None},{"id":"survey_1","label":"Survey 1: Initial Impressions","status":"available","cta":{"label":"Start Survey","url":"/surveys/initial"}},{"id":"survey_2","label":"Survey 2: Usage Feedback","status":"locked","unlock_date":"2026-01-20"},{"id":"survey_x","label":"Survey X (Optional)","status":"not_required"}],"NDA":{"AgreementName":"Logitech Mutual NDA – User Trials","SignedAt":"2025-12-28 09:41","SignedBy":"Richard Liu","Counterparty":"Logitech International S.A.","DocumentURL":"/nda/view/current"}}]
    
    """
    Active Trials view.
    Fragment only. No base.html. No redirects.
    """
    # trials = get_active_trials_for_user(user_id)

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
    Logistics section for an active trial.
    Conditionally renders based on available fields.
    """

    shipped_at = t.get("ShippedAt")
    delivered_at = t.get("DeliveredAt")
    tracking = t.get("TrackingNumber")
    courier = t.get("Courier")
    delivery_type = t.get("DeliveryType")
    url = t.get("TrackingURL", "#")

    # If delivered → collapse by default
    collapsed_attr = " data-collapsed='true'" if delivered_at else ""

    rows = []

    if delivery_type:
        rows.append(f"""
        <div class="logistics-row">
            <span class="label">Delivery Type</span>
            <span class="value">{delivery_type}</span>
        </div>
        """)

    # Shipping status logic
    if not shipped_at:
        rows.append("""
        <div class="logistics-row status pending">
            <span class="value">Preparing shipment</span>
        </div>
        """)
    else:
        rows.append(f"""
        <div class="logistics-row">
            <span class="label">Shipped At</span>
            <span class="value">{shipped_at}</span>
        </div>
        """)

    if courier:
        rows.append(f"""
        <div class="logistics-row">
            <span class="label">Courier</span>
            <span class="value">{courier}</span>
        </div>
        """)

    if tracking:
        rows.append(f"""
        <div class="logistics-row">
            <span class="label">Tracking</span>
            <span class="value">
                <a href="{url}" target="_blank" class="tracking-link">Track Package</a>
            </span>
        </div>
        """)

    if delivered_at:
        rows.append(f"""
        <div class="logistics-row delivered">
            <span class="label">Delivered At</span>
            <span class="value">{delivered_at}</span>
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
    Deterministic action checklist for an active trial.
    Hides irrelevant items. No future CTAs.
    """

    items = []

    def row(status, label, cta=None):
        icon = {
            "completed": "✓",
            "available": "⏳",
            "locked": "🔒",
            "not_required": "⛔",
        }[status]

        cta_html = f'<a href="{cta}" class="checklist-cta">Start</a>' if cta else ""

        return f"""
        <div class="checklist-item status-{status}">
            <span class="icon">{icon}</span>
            <span class="label">{label}</span>
            <span class="cta">{cta_html}</span>
        </div>
        """

    # --- NDA ---
    if t.get("NDARequired"):
        if t.get("NDASignedAt"):
            items.append(row("completed", "NDA Signed"))
        else:
            items.append(row("available", "Sign NDA", "/nda"))
    else:
        items.append(row("not_required", "NDA"))

    # --- Shipping address ---
    if t.get("DeliveryType") == "Home":
        if t.get("DeliveryAddressID"):
            items.append(row("completed", "Confirm Shipping Address"))
        else:
            items.append(row("available", "Confirm Shipping Address", "/settings"))
    else:
        items.append(row("not_required", "Shipping Address"))

    # --- Survey 1 ---
    if t.get("Survey1Required"):
        if t.get("Survey1CompletedAt"):
            items.append(row("completed", "Survey 1: Initial Impressions"))
        elif t.get("Survey1Available"):
            items.append(row(
                "available",
                "Survey 1: Initial Impressions",
                t.get("Survey1URL")
            ))
        else:
            items.append(row("locked", "Survey 1: Initial Impressions"))
    # (else: hidden entirely)

    # --- Survey 2 ---
    if t.get("Survey2Required"):
        if t.get("Survey2CompletedAt"):
            items.append(row("completed", "Survey 2: Usage Feedback"))
        elif t.get("Survey2Available"):
             items.append(row(
                "available",
                "Survey 2: Usage Feedback",
                t.get("Survey2URL")
            ))            
        else:
            items.append(row("locked", "Survey 2: Usage Feedback"))

    # --- Optional survey ---
    if t.get("SurveyXRequired"):
        if t.get("SurveyXCompletedAt"):
            items.append(row("completed", "Optional Survey"))
        elif t.get("SurveyXAvailable"):
            items.append(row(
            "available",
            "Optional Survey",
            t.get("SurveyXURL")
            ))
        else:
            items.append(row("locked", "Optional Survey"))
    else:
        items.append(row("not_required", "Optional Survey"))

    return f"""
    <section class="trial-checklist">
        <h3>Action Checklist</h3>
        <div class="checklist-body">
            {''.join(items)}
        </div>
    </section>
    """

def _render_active_trials_list(trials: list[dict]) -> str:
    items = []

    for raw in trials:
        t = _normalize_trial(raw)
        logistics_html = _render_logistics_section(t)
        checklist_html = _render_action_checklist(t)
        nda_html = _render_nda_section(t)

        items.append(f"""
        <div class="trial-card">
            <h2>{t['ProjectName']}</h2>

            <p><strong>Round:</strong> {t['RoundName']}</p>
            <p><strong>Product:</strong> {t['ProductType']}</p>
            <p><strong>Dates:</strong> {t['StartDate']} → {t['EndDate']}</p>

            {logistics_html}
            {checklist_html}
            {nda_html}
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

    rounds = get_upcoming_project_rounds(user_id=user_id)

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

from app.db.project_rounds import get_recruiting_project_rounds
from app.db.project_applicants import has_applied


def render_recruiting_trials(user_id: str) -> str:
    rounds = get_recruiting_project_rounds(user_id=user_id)

    def build_apply_cta(r):
        round_id = r["RoundID"]
        round_name = r.get("RoundName", "Trial")

        if has_applied(user_id, round_id):

            return f"""
            <span style="color:green;font-weight:bold;">✓ Applied</span>

            <form method="POST" action="/trials/withdraw" style="display:inline;">
                <input type="hidden" name="round_id" value="{round_id}">
                <button type="submit" style="margin-left:8px;">
                    Withdraw
                </button>
            </form>
            """

        return f"""
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
        return {"redirect": "/trials/upcoming"}

    record_round_interest(
        user_id=user_id,
        round_id=round_id,
    )

    return {"redirect": "/trials/upcoming"}