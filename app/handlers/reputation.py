# app/handlers/reputation.py

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.db import user_reputation as reputation_db
from app.services.user_reputation_service import (
    calculate_user_reputation,
    get_dashboard_reputation_summary,
    get_selection_reputation_signal,
)
from app.utils.html_escape import escape_html as e


def render_reputation_page_get(*, user_id: str, base_template: str, inject_nav) -> dict[str, str]:
    """
    GET /dashboard/reputation

    Participant-facing reputation detail page.
    Read-only: this renderer does not refresh cached scores, apply recovery,
    or write reputation events.
    """

    rollup = reputation_db.get_reputation_rollup(user_id) or calculate_user_reputation(user_id)
    summary = get_dashboard_reputation_summary(user_id)
    selection_signal = get_selection_reputation_signal(user_id)
    events = reputation_db.get_reputation_events(user_id, limit=25)

    body = f"""
    <section class="reputation-page">
        <div class="reputation-page-header">
            <div>
                <h1>LogiTrials Reputation</h1>
                <p class="reputation-page-subtitle">
                    Review your participation history, follow-through signals, and reputation recovery status.
                </p>
            </div>
            <a class="back-link" href="/dashboard">? Back to dashboard</a>
        </div>

        {_render_hero_summary(summary=summary, rollup=rollup, selection_signal=selection_signal)}
        {_render_how_it_works_section()}
        {_render_signal_breakdown_section(rollup)}
        {_render_recovery_section(rollup=rollup, summary=summary)}
        {_render_event_history_section(events)}
    </section>
    """

    html = inject_nav(base_template)
    html = html.replace("__BODY_CLASS__", "reputation-page-body")
    html = html.replace("{{ title }}", "LogiTrials Reputation")
    html = html.replace("__BODY__", body)

    return {"html": html}


def _render_hero_summary(
    *,
    summary: dict[str, Any],
    rollup: dict[str, Any],
    selection_signal: dict[str, Any],
) -> str:
    stats = [
        (
            "Official surveys",
            _ratio_text(
                rollup.get("OfficialSurveysCompleted"),
                rollup.get("OfficialSurveysSent"),
                empty="Building history",
            ),
        ),
        ("Reminder burden", _reminder_burden_label(rollup.get("ReminderCount"))),
        ("Completed trials", str(_as_int(rollup.get("CompletedTrials")))),
        ("Active trials", str(_as_int(rollup.get("ActiveTrialCount")))),
    ]

    stat_cards = "".join(
        f"""
        <div class="reputation-hero-stat">
            <span>{e(label)}</span>
            <strong>{e(value)}</strong>
        </div>
        """
        for label, value in stats
    )

    return f"""
    <section class="reputation-hero-card">
        <div class="reputation-hero-main">
            <div>
                <p class="reputation-status-label">{e(summary.get("confidence_label") or "Participation history")}</p>
                <h2>{e(summary.get("status_label") or "Building history")}</h2>
            </div>
            <span class="reputation-band-pill">
                {e(selection_signal.get("band_label") or "Reputation signal")}
            </span>
        </div>

        <div class="reputation-hero-stats">
            {stat_cards}
        </div>

        <p class="reputation-principle-note">
            Reputation is a confidence signal, not an eligibility gate. Profile fit comes first for trial selection.
        </p>
    </section>
    """


def _render_how_it_works_section() -> str:
    cards = [
        (
            "Follow-through",
            "Completing official surveys and required trial steps builds participation history.",
        ),
        (
            "Responsiveness",
            "Repeated reminders and missed deadlines lower confidence, but do not block eligibility by themselves.",
        ),
        (
            "Recovery",
            "Reputation can rebuild over time while you are not active in a trial, unless an explicit block exists.",
        ),
        (
            "Feedback neutrality",
            "Reputation does not depend on whether your product feedback is positive or negative.",
        ),
    ]

    card_html = "".join(
        f"""
        <article class="reputation-explainer-card">
            <h3>{e(title)}</h3>
            <p>{e(description)}</p>
        </article>
        """
        for title, description in cards
    )

    return f"""
    <section class="reputation-section">
        <div class="reputation-section-heading">
            <p class="eyebrow">How it works</p>
            <h2>What reputation reflects</h2>
        </div>
        <div class="reputation-explainer-grid">
            {card_html}
        </div>
    </section>
    """


def _render_signal_breakdown_section(rollup: dict[str, Any]) -> str:
    survey_rows = [
        ("Official surveys sent", _number_text(rollup.get("OfficialSurveysSent"))),
        ("Official surveys completed", _number_text(rollup.get("OfficialSurveysCompleted"))),
        ("Official surveys missed", _number_text(rollup.get("OfficialSurveysMissed"))),
        ("Official surveys late", _number_text(rollup.get("OfficialSurveysLate"))),
        ("Completion rate", _percent_text(rollup.get("OfficialSurveyCompletionRate"))),
        ("Reminder count", _number_text(rollup.get("ReminderCount"))),
    ]

    trial_rows = [
        ("Completed trials", _number_text(rollup.get("CompletedTrials"))),
        ("Active trials", _number_text(rollup.get("ActiveTrialCount"))),
        ("Dropped trials", _number_text(rollup.get("DroppedTrials"))),
        ("Disqualified trials", _number_text(rollup.get("DisqualifiedTrials"))),
        ("Bonus surveys completed", _number_text(rollup.get("BonusSurveysCompleted"))),
    ]

    operational_rows = [
        (
            "Operational checkpoints",
            _ratio_text(
                rollup.get("OperationalCheckpointsCompleted"),
                rollup.get("OperationalCheckpointsExpected"),
                empty="Not started",
            ),
        ),
        ("Recent positive events", _number_text(rollup.get("RecentPositiveEvents"))),
        ("Recent negative events", _number_text(rollup.get("RecentNegativeEvents"))),
        ("Last calculated", _date_text(rollup.get("LastCalculatedAt"))),
    ]

    return f"""
    <section class="reputation-section">
        <div class="reputation-section-heading">
            <p class="eyebrow">Current signals</p>
            <h2>Breakdown</h2>
        </div>
        <div class="reputation-detail-grid">
            {_render_detail_panel("Survey follow-through", survey_rows)}
            {_render_detail_panel("Trial history", trial_rows)}
            {_render_detail_panel("Operational signals", operational_rows)}
        </div>
    </section>
    """


def _render_recovery_section(*, rollup: dict[str, Any], summary: dict[str, Any]) -> str:
    recovery_rows = [
        ("Recovery applied", _points_text(rollup.get("RecoveryPointsApplied"))),
        ("Last recovery", _date_text(rollup.get("LastRecoveryAppliedAt"))),
        ("Recovery status", _recovery_reason_label(rollup.get("RecoveryPausedReason"))),
    ]

    return f"""
    <section class="reputation-section reputation-recovery-section">
        <div class="reputation-section-heading">
            <p class="eyebrow">Recovery</p>
            <h2>How reputation rebuilds</h2>
            <p>{e(summary.get("recovery_note") or "Reputation can recover over time while you are not active in a trial.")}</p>
        </div>
        {_render_detail_panel("Recovery details", recovery_rows)}
    </section>
    """


def _render_event_history_section(events: list[dict[str, Any]]) -> str:
    if not events:
        event_html = """
        <div class="reputation-empty-events">
            <p>No reputation events have been recorded yet.</p>
            <p>Your current summary is calculated from source participation records.</p>
        </div>
        """
    else:
        event_html = "".join(_render_event_card(event) for event in events)

    return f"""
    <section class="reputation-section reputation-events-section">
        <div class="reputation-section-heading">
            <p class="eyebrow">Audit trail</p>
            <h2>Reputation event history</h2>
            <p>Newest reputation events appear first.</p>
        </div>
        <div class="reputation-event-list">
            {event_html}
        </div>
    </section>
    """


def _render_detail_panel(title: str, rows: list[tuple[str, str]]) -> str:
    row_html = "".join(
        f"""
        <div class="reputation-detail-row">
            <span>{e(label)}</span>
            <strong>{e(value)}</strong>
        </div>
        """
        for label, value in rows
    )

    return f"""
    <article class="reputation-detail-panel">
        <h3>{e(title)}</h3>
        <div class="reputation-detail-rows">
            {row_html}
        </div>
    </article>
    """


def _render_event_card(event: dict[str, Any]) -> str:
    event_type = _event_type_label(event.get("EventType"))
    category = _event_category_label(event.get("EventCategory"))
    direction = _impact_direction_label(event.get("ImpactDirection"))
    reason = event.get("Reason") or "No reason recorded."

    return f"""
    <article class="reputation-event-card">
        <div class="reputation-event-card-header">
            <div>
                <h3>{e(event_type)}</h3>
                <p>{e(category)} · {e(direction)} · {e(_date_text(event.get("CreatedAt")))}</p>
            </div>
            <span>{e(_points_text(event.get("ImpactPoints")))}</span>
        </div>
        <p>{e(reason)}</p>
    </article>
    """


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _number_text(value: Any) -> str:
    return str(_as_int(value))


def _points_text(value: Any) -> str:
    return f"{_as_float(value):.2f}"


def _percent_text(value: Any) -> str:
    if value is None:
        return "Not enough history"
    return f"{_as_float(value):.2f}%"


def _ratio_text(numerator: Any, denominator: Any, *, empty: str) -> str:
    top = _as_int(numerator)
    bottom = _as_int(denominator)
    if bottom <= 0:
        return empty
    return f"{top} / {bottom}"


def _date_text(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _reminder_burden_label(value: Any) -> str:
    count = _as_int(value)
    if count <= 0:
        return "Low"
    if count <= 2:
        return "Moderate"
    return "High"


def _recovery_reason_label(value: Any) -> str:
    labels = {
        "active_trial": "Paused while active in a trial",
        "active_blacklist": "Paused by explicit eligibility block",
        "at_recovery_cap": "At recovery cap",
        "not_due": "Not due yet",
        "none": "Available when due",
    }
    return labels.get(str(value or "none"), "Available when due")


def _event_type_label(value: Any) -> str:
    raw = str(value or "SystemAdjustment")
    labels = {
        "OfficialSurveyCompleted": "Official survey completed",
        "OfficialSurveyMissed": "Official survey missed",
        "OfficialSurveyLate": "Official survey late",
        "BonusSurveyCompleted": "Bonus survey completed",
        "BonusSurveyMissed": "Bonus survey missed",
        "TrialCompleted": "Trial completed",
        "TrialDropped": "Trial dropped",
        "TrialDisqualified": "Trial disqualified",
        "NDACompleted": "NDA completed",
        "ShippingAddressConfirmed": "Shipping address confirmed",
        "ResponsibilitiesAccepted": "Responsibilities accepted",
        "DeviceReceiptConfirmed": "Device receipt confirmed",
        "InactiveRecoveryApplied": "Inactive recovery applied",
        "LowEffortSurveyFlag": "Low-effort survey flag",
        "ManualOverride": "Manual override",
        "SystemAdjustment": "System adjustment",
        "PenaltyApplied": "Adjustment applied",
        "Redemption": "Recovery adjustment",
    }
    return labels.get(raw, raw)


def _event_category_label(value: Any) -> str:
    labels = {
        "survey": "Survey",
        "trial": "Trial",
        "operations": "Operations",
        "feedback": "Feedback",
        "recovery": "Recovery",
        "manual": "Manual",
        "system": "System",
    }
    return labels.get(str(value or "system"), "System")


def _impact_direction_label(value: Any) -> str:
    labels = {
        "positive": "Positive signal",
        "negative": "Negative signal",
        "neutral": "Neutral signal",
        "recovery": "Recovery signal",
    }
    return labels.get(str(value or "neutral"), "Neutral signal")
