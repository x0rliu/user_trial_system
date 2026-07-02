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
        <div class="reputation-page-header reputation-page-header-standard">
            <h1>LogiTrials Reputation</h1>
        </div>

        {_render_hero_summary(summary=summary, rollup=rollup, selection_signal=selection_signal)}
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

    status_label = summary.get("status_label") or "Building history"
    band_label = selection_signal.get("band_label") or "Reputation signal"

    return f"""
    <section class="reputation-hero-card">
        <div class="reputation-hero-main">
            <div>
                <p class="reputation-status-label">Your LogiTrials Reputation:</p>
                <h2>{e(status_label)}</h2>
            </div>
            <span class="reputation-band-pill">
                {e(band_label)}
            </span>
        </div>

        <div class="reputation-hero-stats">
            {stat_cards}
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

    content_html = f"""
        <div class="reputation-detail-grid">
            {_render_detail_panel("Survey follow-through", survey_rows)}
            {_render_detail_panel("Trial history", trial_rows)}
            {_render_detail_panel("Operational signals", operational_rows)}
        </div>
    """

    return _render_collapsible_section(
        eyebrow="Current signals",
        title="Breakdown",
        summary="Survey returns, trial participation, reminders, and operational follow-through.",
        content_html=content_html,
        extra_class="reputation-breakdown-section",
        open_by_default=True,
    )


def _render_recovery_section(*, rollup: dict[str, Any], summary: dict[str, Any]) -> str:
    active_trial_count = _as_int(rollup.get("ActiveTrialCount"))

    status_rows = [
        ("Current activity", _active_trial_text(active_trial_count)),
        ("Last updated", _date_text(rollup.get("LastCalculatedAt"))),
        ("Update status", _reputation_update_status_label(rollup.get("RecoveryPausedReason"))),
    ]

    content_html = f"""
        {_render_detail_panel("Status details", status_rows)}
        <p class="reputation-section-more-link">
            Questions about how this works?
            <a href="/how-user-trials-work#reputation">Read the reputation explanation</a>.
        </p>
    """

    return _render_collapsible_section(
        eyebrow="Status",
        title="Reputation status",
        summary="Current activity and latest reputation update timing.",
        content_html=content_html,
        extra_class="reputation-status-section",
    )


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

    content_html = f"""
        <div class="reputation-event-list">
            {event_html}
        </div>
    """

    return _render_collapsible_section(
        eyebrow="Audit trail",
        title="Reputation event history",
        summary="Newest reputation events appear first.",
        content_html=content_html,
        extra_class="reputation-events-section",
    )


def _render_collapsible_section(
    *,
    eyebrow: str,
    title: str,
    summary: str,
    content_html: str,
    extra_class: str = "",
    open_by_default: bool = False,
) -> str:
    open_attr = " open" if open_by_default else ""
    class_attr = f"reputation-section reputation-collapsible-section {extra_class}".strip()

    return f"""
    <details class="{e(class_attr)}"{open_attr}>
        <summary class="reputation-section-summary">
            <div>
                <p class="eyebrow">{e(eyebrow)}</p>
                <h2>{e(title)}</h2>
                <p>{e(summary)}</p>
            </div>
            <span class="reputation-section-toggle" aria-hidden="true">Expand</span>
        </summary>
        <div class="reputation-collapsible-content">
            {content_html}
        </div>
    </details>
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


def _active_trial_text(active_trial_count: int) -> str:
    if active_trial_count == 1:
        return "Active in 1 trial"
    if active_trial_count > 1:
        return f"Active in {active_trial_count} trials"
    return "No active trials"


def _reputation_update_status_label(value: Any) -> str:
    labels = {
        "active_trial": "Active trial in progress",
        "active_blacklist": "Manual review required",
        "at_recovery_cap": "Current status is stable",
        "not_due": "No update due yet",
        "none": "Available for normal updates",
    }
    return labels.get(str(value or "none"), "Available for normal updates")


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
