# app/services/user_reputation_service.py

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from app.db import user_reputation as reputation_db


# =========================
# CONFIG (KEEP EXPLICIT)
# =========================

NEUTRAL_REPUTATION_POINTS = 50.00
MIN_REPUTATION_POINTS = 0.00
MAX_REPUTATION_POINTS = 100.00
PASSIVE_RECOVERY_POINTS = 1.00
PASSIVE_RECOVERY_DAYS = 7
PASSIVE_RECOVERY_CAP = 70.00


# =========================
# PUBLIC API
# =========================


def calculate_user_reputation(user_id: str) -> dict[str, Any]:
    """
    Calculate one user's reputation rollup from DB-backed source facts.

    Important design rules:
    - Reputation starts from a neutral baseline, not 100.
    - Reputation is a recoverable confidence signal, not an eligibility gate.
    - Blacklist remains separate and is not represented as reputation.
    - Selection should use the tie-breaker band, not raw points as a primary rank.

    This function reads only. It does not write to DB.
    """

    facts = reputation_db.get_reputation_source_facts(user_id)
    existing_rollup = reputation_db.get_reputation_rollup(user_id) or {}

    official_sent = _as_int(facts.get("official_surveys_sent"))
    official_completed = _as_int(facts.get("official_surveys_completed"))
    official_missed = _as_int(facts.get("official_surveys_missed"))
    official_late = _as_int(facts.get("official_surveys_late"))
    reminder_count = _as_int(facts.get("reminder_count"))

    completed_trials = _as_int(facts.get("completed_trials"))
    dropped_trials = _as_int(facts.get("dropped_trials"))
    disqualified_trials = _as_int(facts.get("disqualified_trials"))
    active_trial_count = _as_int(facts.get("active_trial_count"))
    participant_trial_rows = _as_int(facts.get("participant_trial_rows"))

    shipping_confirmed = _as_int(facts.get("shipping_address_confirmed_count"))
    responsibilities_accepted = _as_int(facts.get("responsibilities_accepted_count"))
    device_receipt_confirmed = _as_int(facts.get("device_receipt_confirmed_count"))
    nda_sent = _as_int(facts.get("nda_sent_count"))
    nda_signed = _as_int(facts.get("nda_signed_count"))

    bonus_completed = _as_int(facts.get("bonus_surveys_completed"))
    recent_positive_events = _as_int(facts.get("recent_positive_events"))
    recent_negative_events = _as_int(facts.get("recent_negative_events"))

    recovery_points_applied = _as_float(existing_rollup.get("RecoveryPointsApplied"))

    official_completion_rate = _completion_rate(official_completed, official_sent)

    operational_expected = participant_trial_rows * 3 + nda_sent
    operational_completed = (
        shipping_confirmed
        + responsibilities_accepted
        + device_receipt_confirmed
        + nda_signed
    )

    evidence_count = (
        official_sent
        + participant_trial_rows
        + nda_sent
        + bonus_completed
        + recent_positive_events
        + recent_negative_events
    )

    points = NEUTRAL_REPUTATION_POINTS

    # Positive participation confidence. These are intentionally bounded so the
    # model is not just a school grade or a runaway points game.
    points += min(official_completed * 3.0, 21.0)
    points += min(completed_trials * 5.0, 15.0)
    points += min(bonus_completed * 1.0, 5.0)
    points += min(recent_positive_events * 2.0, 10.0)

    if operational_expected > 0:
        points += min((operational_completed / operational_expected) * 8.0, 8.0)

    # Negative signals lower confidence but do not determine eligibility.
    points -= official_missed * 10.0
    points -= official_late * 2.0
    points -= min(reminder_count * 1.0, 10.0)
    points -= dropped_trials * 12.0
    points -= disqualified_trials * 20.0
    points -= recent_negative_events * 5.0

    # Passive recovery is explicit and capped. Time alone can move someone back
    # toward neutral/healthy, but it does not make them a top-history participant.
    points += min(recovery_points_applied, PASSIVE_RECOVERY_CAP - NEUTRAL_REPUTATION_POINTS)

    reputation_points = _clamp(points, MIN_REPUTATION_POINTS, MAX_REPUTATION_POINTS)
    confidence_level = _determine_confidence_level(evidence_count)
    reputation_status = _determine_reputation_status(
        points=reputation_points,
        confidence_level=confidence_level,
        evidence_count=evidence_count,
        recent_negative_events=recent_negative_events,
    )
    tie_breaker_band = _determine_selection_tie_breaker_band(
        points=reputation_points,
        confidence_level=confidence_level,
        status=reputation_status,
    )

    recovery_paused_reason = _determine_recovery_paused_reason(
        reputation_points=reputation_points,
        active_trial_count=active_trial_count,
        active_blacklist_count=_as_int(facts.get("active_blacklist_count")),
        last_recovery_applied_at=existing_rollup.get("LastRecoveryAppliedAt"),
    )

    return {
        "ReputationPoints": round(reputation_points, 2),
        "ReputationStatus": reputation_status,
        "ConfidenceLevel": confidence_level,
        "SelectionTieBreakerBand": tie_breaker_band,
        "OfficialSurveysSent": official_sent,
        "OfficialSurveysCompleted": official_completed,
        "OfficialSurveysMissed": official_missed,
        "OfficialSurveysLate": official_late,
        "OfficialSurveyCompletionRate": official_completion_rate,
        "CompletedTrials": completed_trials,
        "DroppedTrials": dropped_trials,
        "DisqualifiedTrials": disqualified_trials,
        "ActiveTrialCount": active_trial_count,
        "ReminderCount": reminder_count,
        "OperationalCheckpointsCompleted": operational_completed,
        "OperationalCheckpointsExpected": operational_expected,
        "BonusSurveysCompleted": bonus_completed,
        "RecentPositiveEvents": recent_positive_events,
        "RecentNegativeEvents": recent_negative_events,
        "RecoveryPointsApplied": round(recovery_points_applied, 2),
        "LastRecoveryAppliedAt": existing_rollup.get("LastRecoveryAppliedAt"),
        "RecoveryPausedReason": recovery_paused_reason,
        "LastEventAt": existing_rollup.get("LastEventAt"),
        "LastCalculatedAt": datetime.now(),
    }


def refresh_user_reputation(user_id: str) -> dict[str, Any]:
    """
    Calculate and persist one user's cached reputation rollup.

    This is a mutation function. Do not call it from a GET renderer.
    """

    rollup = calculate_user_reputation(user_id)
    reputation_db.upsert_reputation_rollup(user_id, rollup)
    return rollup


def apply_inactive_recovery(user_id: str) -> dict[str, Any]:
    """
    Apply passive self-healing if the participant is eligible for recovery.

    Rules:
    - User must not be active in a trial.
    - User must not be actively blacklisted.
    - Recovery applies at most once per 7 days.
    - Recovery only moves users toward the recovery cap, not to excellent.
    """

    existing_rollup = reputation_db.get_reputation_rollup(user_id)

    if not existing_rollup:
        existing_rollup = refresh_user_reputation(user_id)

    facts = reputation_db.get_reputation_source_facts(user_id)
    active_trial_count = _as_int(facts.get("active_trial_count"))
    active_blacklist_count = _as_int(facts.get("active_blacklist_count"))
    reputation_points = _as_float(existing_rollup.get("ReputationPoints"), NEUTRAL_REPUTATION_POINTS)
    last_recovery_at = existing_rollup.get("LastRecoveryAppliedAt")

    if active_trial_count > 0:
        return _recovery_result(False, "active_trial", 0.0, existing_rollup)

    if active_blacklist_count > 0:
        return _recovery_result(False, "active_blacklist", 0.0, existing_rollup)

    if reputation_points >= PASSIVE_RECOVERY_CAP:
        return _recovery_result(False, "at_recovery_cap", 0.0, existing_rollup)

    if not _recovery_due(last_recovery_at):
        return _recovery_result(False, "not_due", 0.0, existing_rollup)

    points_to_apply = min(PASSIVE_RECOVERY_POINTS, PASSIVE_RECOVERY_CAP - reputation_points)
    prior_recovery_points = _as_float(existing_rollup.get("RecoveryPointsApplied"))

    reputation_db.insert_reputation_event(
        user_id=user_id,
        event_type="InactiveRecoveryApplied",
        event_category="recovery",
        impact_direction="recovery",
        impact_points=points_to_apply,
        source="System",
        value=points_to_apply,
        weight_applied=1.0,
        reason="Passive weekly recovery while not active in a trial.",
        source_table="user_reliability_score",
        source_record_id=user_id,
        decay_eligible=False,
    )

    updated_rollup = calculate_user_reputation(user_id)
    updated_rollup["RecoveryPointsApplied"] = round(prior_recovery_points + points_to_apply, 2)
    updated_rollup["LastRecoveryAppliedAt"] = datetime.now()
    updated_rollup["RecoveryPausedReason"] = "none"
    updated_rollup["LastEventAt"] = datetime.now()
    updated_rollup["ReputationPoints"] = round(
        min(reputation_points + points_to_apply, PASSIVE_RECOVERY_CAP),
        2,
    )
    updated_rollup["ReputationStatus"] = _determine_reputation_status(
        points=updated_rollup["ReputationPoints"],
        confidence_level=updated_rollup["ConfidenceLevel"],
        evidence_count=(
            _as_int(updated_rollup.get("OfficialSurveysSent"))
            + _as_int(updated_rollup.get("CompletedTrials"))
            + _as_int(updated_rollup.get("DroppedTrials"))
            + _as_int(updated_rollup.get("DisqualifiedTrials"))
        ),
        recent_negative_events=_as_int(updated_rollup.get("RecentNegativeEvents")),
    )
    updated_rollup["SelectionTieBreakerBand"] = _determine_selection_tie_breaker_band(
        points=updated_rollup["ReputationPoints"],
        confidence_level=updated_rollup["ConfidenceLevel"],
        status=updated_rollup["ReputationStatus"],
    )

    reputation_db.upsert_reputation_rollup(user_id, updated_rollup)
    return _recovery_result(True, "none", points_to_apply, updated_rollup)


def get_dashboard_reputation_summary(user_id: str) -> dict[str, Any]:
    """
    Return participant-facing reputation copy for the dashboard card.

    This function does not write to DB. If no cached rollup exists, it calculates
    a read-only preview from source facts so GET rendering remains non-mutating.
    """

    rollup = reputation_db.get_reputation_rollup(user_id) or calculate_user_reputation(user_id)
    status = rollup.get("ReputationStatus") or "building_history"
    confidence = rollup.get("ConfidenceLevel") or "unknown"

    signals = _build_dashboard_signals(rollup)

    return {
        "status": status,
        "status_label": _status_label(status),
        "confidence_level": confidence,
        "confidence_label": _confidence_label(confidence),
        "body": _dashboard_body(status, confidence),
        "signals": signals,
        "recovery_note": _recovery_note(rollup),
        "is_eligible_message": "You are still eligible for trials. Reputation is a confidence signal, not a hard gate.",
        "selection_note": "Profile fit comes first. Reputation is only a secondary signal when candidates are otherwise similarly matched.",
    }


def get_selection_reputation_signal(user_id: str) -> dict[str, Any]:
    """
    Return a UT Lead-facing reputation tie-breaker signal.

    Selection callers should use this as supporting context only. They should not
    use reputation as the first-pass candidate filter.
    """

    rollup = reputation_db.get_reputation_rollup(user_id) or calculate_user_reputation(user_id)
    status = rollup.get("ReputationStatus") or "building_history"
    band = rollup.get("SelectionTieBreakerBand") or "none"
    confidence = rollup.get("ConfidenceLevel") or "unknown"

    return {
        "band": band,
        "band_label": _tie_breaker_label(band),
        "status": status,
        "status_label": _status_label(status),
        "confidence_level": confidence,
        "confidence_label": _confidence_label(confidence),
        "supporting_facts": {
            "official_surveys_completed": _as_int(rollup.get("OfficialSurveysCompleted")),
            "official_surveys_sent": _as_int(rollup.get("OfficialSurveysSent")),
            "completed_trials": _as_int(rollup.get("CompletedTrials")),
            "active_trial_count": _as_int(rollup.get("ActiveTrialCount")),
        },
        "selection_rule": "Use only as a secondary tie-breaker after profile fit and trial targeting needs.",
    }


# =========================
# INTERNAL HELPERS
# =========================


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


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def _completion_rate(completed: int, sent: int) -> float | None:
    if sent <= 0:
        return None
    return round((completed / sent) * 100.0, 2)


def _determine_confidence_level(evidence_count: int) -> str:
    if evidence_count <= 0:
        return "unknown"
    if evidence_count < 3:
        return "low"
    if evidence_count < 8:
        return "medium"
    return "high"


def _determine_reputation_status(
    *,
    points: float,
    confidence_level: str,
    evidence_count: int,
    recent_negative_events: int,
) -> str:
    if evidence_count <= 0 or confidence_level == "unknown":
        return "building_history"

    if points < 35:
        return "needs_attention"

    if points < NEUTRAL_REPUTATION_POINTS or recent_negative_events > 0:
        return "rebuilding_history"

    if confidence_level == "low":
        return "limited_history"

    if points >= 85 and confidence_level in {"medium", "high"}:
        return "strong_history"

    return "steady_history"


def _determine_selection_tie_breaker_band(
    *,
    points: float,
    confidence_level: str,
    status: str,
) -> str:
    if confidence_level == "unknown":
        return "none"

    if confidence_level == "low":
        return "low_confidence"

    if status == "strong_history" and points >= 85:
        return "strong"

    if status in {"steady_history", "strong_history"} and points >= 70:
        return "positive"

    if status == "needs_attention" or points < 40:
        return "low_confidence"

    return "neutral"


def _determine_recovery_paused_reason(
    *,
    reputation_points: float,
    active_trial_count: int,
    active_blacklist_count: int,
    last_recovery_applied_at: Any,
) -> str:
    if active_trial_count > 0:
        return "active_trial"
    if active_blacklist_count > 0:
        return "active_blacklist"
    if reputation_points >= PASSIVE_RECOVERY_CAP:
        return "at_recovery_cap"
    if not _recovery_due(last_recovery_applied_at):
        return "not_due"
    return "none"


def _recovery_due(last_recovery_applied_at: Any) -> bool:
    if not last_recovery_applied_at:
        return True

    if isinstance(last_recovery_applied_at, str):
        try:
            last_recovery_applied_at = datetime.fromisoformat(last_recovery_applied_at)
        except ValueError:
            return False

    if not isinstance(last_recovery_applied_at, datetime):
        return False

    return last_recovery_applied_at <= datetime.now() - timedelta(days=PASSIVE_RECOVERY_DAYS)


def _recovery_result(
    applied: bool,
    paused_reason: str,
    points_applied: float,
    rollup: dict[str, Any],
) -> dict[str, Any]:
    return {
        "applied": applied,
        "points_applied": round(points_applied, 2),
        "paused_reason": paused_reason,
        "rollup": rollup,
    }


def _status_label(status: str) -> str:
    labels = {
        "building_history": "Building history",
        "steady_history": "Reliable participant",
        "strong_history": "Strong trial history",
        "rebuilding_history": "Rebuilding history",
        "limited_history": "Limited history",
        "needs_attention": "Needs attention",
    }
    return labels.get(status, "Building history")


def _confidence_label(confidence_level: str) -> str:
    labels = {
        "unknown": "Not enough history yet",
        "low": "Limited history",
        "medium": "Some history",
        "high": "Established history",
    }
    return labels.get(confidence_level, "Not enough history yet")


def _tie_breaker_label(band: str) -> str:
    labels = {
        "none": "No reputation tie-breaker yet",
        "low_confidence": "Limited confidence signal",
        "neutral": "Neutral history signal",
        "positive": "Positive history signal",
        "strong": "Strong history signal",
    }
    return labels.get(band, "No reputation tie-breaker yet")


def _dashboard_body(status: str, confidence_level: str) -> str:
    if confidence_level == "unknown":
        return "You are eligible for trials. Your history will build as you complete trial steps and surveys."

    if status == "needs_attention":
        return "You are still eligible for trials. Completing future steps and surveys on time will help rebuild confidence."

    if status == "rebuilding_history":
        return "Your recent history is rebuilding. Continued follow-through will improve this over time."

    if status == "strong_history":
        return "You have a strong participation history. Profile fit still comes first for trial selection."

    return "Your participation history reflects recent follow-through and survey completion behavior."


def _build_dashboard_signals(rollup: dict[str, Any]) -> list[str]:
    signals: list[str] = []

    official_sent = _as_int(rollup.get("OfficialSurveysSent"))
    official_completed = _as_int(rollup.get("OfficialSurveysCompleted"))
    official_missed = _as_int(rollup.get("OfficialSurveysMissed"))
    official_late = _as_int(rollup.get("OfficialSurveysLate"))
    reminder_count = _as_int(rollup.get("ReminderCount"))
    completed_trials = _as_int(rollup.get("CompletedTrials"))
    active_trial_count = _as_int(rollup.get("ActiveTrialCount"))
    bonus_completed = _as_int(rollup.get("BonusSurveysCompleted"))

    if official_sent > 0:
        signals.append(f"Official surveys returned: {official_completed} / {official_sent}")
    else:
        signals.append("Official surveys returned: building history")

    if official_missed > 0:
        signals.append(f"Missed official surveys: {official_missed}")
    elif official_sent > 0:
        signals.append("No missed official surveys in tracked history")

    if official_late > 0:
        signals.append(f"Late official surveys: {official_late}")

    if reminder_count > 0:
        signals.append(f"Reminder count: {reminder_count}")
    elif official_sent > 0:
        signals.append("Reminder burden: low")

    if completed_trials > 0:
        signals.append(f"Completed trials: {completed_trials}")

    if active_trial_count > 0:
        signals.append("Recovery pauses while you are active in a trial")

    if bonus_completed > 0:
        signals.append(f"Bonus surveys completed: {bonus_completed}")

    return signals[:5]


def _recovery_note(rollup: dict[str, Any]) -> str:
    paused_reason = rollup.get("RecoveryPausedReason") or "none"

    if paused_reason == "active_trial":
        return "Reputation recovery pauses while you are active in a trial."

    if paused_reason == "active_blacklist":
        return "Passive recovery is paused because an explicit eligibility block is active."

    if paused_reason == "at_recovery_cap":
        return "Passive recovery has reached its current cap. Stronger history comes from future participation."

    if paused_reason == "not_due":
        return "Passive recovery is not due yet."

    return "Reputation can recover over time while you are not active in a trial."
