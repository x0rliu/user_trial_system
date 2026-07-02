# app/db/user_reputation.py

from __future__ import annotations

from datetime import datetime
from typing import Any

import mysql.connector

from app.config.config import DB_CONFIG


# Participant-result surveys are completion-gated. These types are excluded by
# existing participant survey flows and should not count as official reputation
# follow-through signals.
_EXCLUDED_OFFICIAL_SURVEY_TYPE_IDS = (
    "UTSurveyType0001",  # Recruiting
    "UTSurveyType0027",  # Consolidated/internal results
    "UTSurveyType0028",  # Report issue; always-on issue reporting
)

_ROLLUP_DEFAULTS = {
    "ReputationPoints": 50.00,
    "ReputationStatus": "building_history",
    "ConfidenceLevel": "unknown",
    "SelectionTieBreakerBand": "none",
    "OfficialSurveysSent": 0,
    "OfficialSurveysCompleted": 0,
    "OfficialSurveysMissed": 0,
    "OfficialSurveysLate": 0,
    "OfficialSurveyCompletionRate": None,
    "CompletedTrials": 0,
    "DroppedTrials": 0,
    "DisqualifiedTrials": 0,
    "ActiveTrialCount": 0,
    "ReminderCount": 0,
    "OperationalCheckpointsCompleted": 0,
    "OperationalCheckpointsExpected": 0,
    "BonusSurveysCompleted": 0,
    "RecentPositiveEvents": 0,
    "RecentNegativeEvents": 0,
    "RecoveryPointsApplied": 0.00,
    "LastRecoveryAppliedAt": None,
    "RecoveryPausedReason": "none",
    "LastEventAt": None,
    "LastCalculatedAt": None,
}

_ROLLUP_FIELDS = tuple(_ROLLUP_DEFAULTS.keys())


def _get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def _clamp_limit(limit: int | None, default: int = 20, maximum: int = 100) -> int:
    try:
        parsed = int(limit or default)
    except (TypeError, ValueError):
        parsed = default

    return max(1, min(parsed, maximum))


def get_reputation_rollup(user_id: str) -> dict[str, Any] | None:
    """
    Read the cached reputation rollup for one participant.

    Source of truth for the displayed rollup:
    - user_reliability_score

    This function never mutates state.
    """

    conn = _get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                user_id,
                ReputationPoints,
                ReputationStatus,
                ConfidenceLevel,
                SelectionTieBreakerBand,
                OfficialSurveysSent,
                OfficialSurveysCompleted,
                OfficialSurveysMissed,
                OfficialSurveysLate,
                OfficialSurveyCompletionRate,
                CompletedTrials,
                DroppedTrials,
                DisqualifiedTrials,
                ActiveTrialCount,
                ReminderCount,
                OperationalCheckpointsCompleted,
                OperationalCheckpointsExpected,
                BonusSurveysCompleted,
                RecentPositiveEvents,
                RecentNegativeEvents,
                RecoveryPointsApplied,
                LastRecoveryAppliedAt,
                RecoveryPausedReason,
                LastEventAt,
                LastCalculatedAt,
                UpdatedAt
            FROM user_reliability_score
            WHERE user_id = %s
            LIMIT 1
            """,
            (user_id,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def get_reputation_events(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """
    Read the explicit reputation event audit trail for one participant.

    Source of truth for reputation movement/explanation:
    - user_reliability_events

    This function never mutates state.
    """

    safe_limit = _clamp_limit(limit)

    conn = _get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            f"""
            SELECT
                EventID,
                user_id,
                RoundID,
                EventType,
                EventCategory,
                ImpactDirection,
                ImpactPoints,
                Value,
                WeightApplied,
                Reason,
                Source,
                SourceTable,
                SourceRecordID,
                DecayEligible,
                EventState,
                CreatedAt
            FROM user_reliability_events
            WHERE user_id = %s
            ORDER BY CreatedAt DESC, EventID DESC
            LIMIT {safe_limit}
            """,
            (user_id,),
        )
        return cur.fetchall()
    finally:
        conn.close()


def get_reputation_source_facts(user_id: str) -> dict[str, Any]:
    """
    Read raw DB facts used by the reputation service.

    This helper intentionally returns facts, not final reputation meaning.
    The service layer decides how much each fact matters.
    """

    conn = _get_connection()
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT
                COUNT(DISTINCT CASE
                    WHEN sd.has_distribution = 1
                      OR prs.ParticipantActivatedAt IS NOT NULL
                      OR pr.CompletedAt IS NOT NULL
                      OR LOWER(pr.Status) IN ('closed', 'completed', 'cancelled', 'canceled')
                    THEN prs.RoundSurveyID
                    ELSE NULL
                END) AS official_surveys_sent,

                COUNT(DISTINCT CASE
                    WHEN sd.is_completed = 1
                    THEN prs.RoundSurveyID
                    ELSE NULL
                END) AS official_surveys_completed,

                COUNT(DISTINCT CASE
                    WHEN (
                        sd.has_distribution = 1
                        OR prs.ParticipantActivatedAt IS NOT NULL
                        OR pr.CompletedAt IS NOT NULL
                        OR LOWER(pr.Status) IN ('closed', 'completed', 'cancelled', 'canceled')
                    )
                    AND COALESCE(sd.is_completed, 0) = 0
                    AND (
                        COALESCE(sd.deadline_missed, 0) = 1
                        OR pr.CompletedAt IS NOT NULL
                        OR LOWER(pr.Status) IN ('closed', 'completed', 'cancelled', 'canceled')
                    )
                    THEN prs.RoundSurveyID
                    ELSE NULL
                END) AS official_surveys_missed,

                COUNT(DISTINCT CASE
                    WHEN sd.is_late = 1
                    THEN prs.RoundSurveyID
                    ELSE NULL
                END) AS official_surveys_late,

                COALESCE(SUM(COALESCE(sd.reminder_count, 0)), 0) AS reminder_count
            FROM project_participants pp
            JOIN project_rounds pr
              ON pr.RoundID = pp.RoundID
            JOIN project_round_surveys prs
              ON prs.RoundID = pp.RoundID
             AND prs.IsActive = 1
             AND prs.SurveyTypeID LIKE 'UTSurveyType1%'
            LEFT JOIN (
                SELECT
                    user_id,
                    RoundID,
                    SurveyTypeID,
                    1 AS has_distribution,
                    MAX(CASE
                        WHEN CompletedAt IS NOT NULL OR Status = 'completed'
                        THEN 1 ELSE 0
                    END) AS is_completed,
                    MAX(CASE
                        WHEN (
                            Deadline IS NOT NULL
                            AND CompletedAt IS NOT NULL
                            AND CompletedAt > Deadline
                        ) OR Status = 'late'
                        THEN 1 ELSE 0
                    END) AS is_late,
                    MAX(CASE
                        WHEN Deadline IS NOT NULL
                         AND CompletedAt IS NULL
                         AND Status <> 'completed'
                         AND Deadline < NOW()
                        THEN 1 ELSE 0
                    END) AS deadline_missed,
                    SUM(COALESCE(ReminderCount, 0)) AS reminder_count
                FROM survey_distribution
                WHERE user_id = %s
                GROUP BY
                    user_id,
                    RoundID,
                    SurveyTypeID
            ) sd
              ON sd.user_id = pp.user_id
             AND sd.RoundID = pp.RoundID
             AND sd.SurveyTypeID = prs.SurveyTypeID
            WHERE pp.user_id = %s
            """,
            (user_id, user_id),
        )
        survey_facts = cur.fetchone() or {}

        cur.execute(
            """
            SELECT
                SUM(CASE WHEN pp.ParticipantStatus = 'Completed' THEN 1 ELSE 0 END) AS completed_trials,
                SUM(CASE WHEN pp.ParticipantStatus = 'Dropped' THEN 1 ELSE 0 END) AS dropped_trials,
                SUM(CASE WHEN pp.ParticipantStatus = 'Disqualified' THEN 1 ELSE 0 END) AS disqualified_trials,
                SUM(CASE
                    WHEN pp.ParticipantStatus IN ('Selected', 'Active')
                     AND pp.CompletedAt IS NULL
                     AND pr.CompletedAt IS NULL
                     AND LOWER(pr.Status) NOT IN ('closed', 'completed', 'cancelled', 'canceled')
                    THEN 1 ELSE 0
                END) AS active_trial_count,
                SUM(CASE WHEN pp.ShippingAddressConfirmedAt IS NOT NULL THEN 1 ELSE 0 END) AS shipping_address_confirmed_count,
                SUM(CASE WHEN pp.ResponsibilitiesAcceptedAt IS NOT NULL THEN 1 ELSE 0 END) AS responsibilities_accepted_count,
                SUM(CASE WHEN pp.DeviceReceivedConfirmedAt IS NOT NULL THEN 1 ELSE 0 END) AS device_receipt_confirmed_count,
                COUNT(*) AS participant_trial_rows
            FROM project_participants pp
            JOIN project_rounds pr
              ON pr.RoundID = pp.RoundID
            WHERE pp.user_id = %s
            """,
            (user_id,),
        )
        trial_facts = cur.fetchone() or {}

        cur.execute(
            """
            SELECT
                COUNT(*) AS nda_sent_count,
                SUM(CASE
                    WHEN NDAStatus = 'Signed' OR DateSigned IS NOT NULL
                    THEN 1 ELSE 0
                END) AS nda_signed_count
            FROM project_ndas
            WHERE user_id = %s
            """,
            (user_id,),
        )
        nda_facts = cur.fetchone() or {}

        cur.execute(
            """
            SELECT
                COUNT(*) AS bonus_surveys_completed
            FROM bonus_survey_participation
            WHERE user_id = %s
              AND completed_at IS NOT NULL
            """,
            (user_id,),
        )
        bonus_facts = cur.fetchone() or {}

        cur.execute(
            """
            SELECT
                SUM(CASE WHEN ImpactDirection IN ('positive', 'recovery') THEN 1 ELSE 0 END) AS recent_positive_events,
                SUM(CASE WHEN ImpactDirection = 'negative' THEN 1 ELSE 0 END) AS recent_negative_events
            FROM user_reliability_events
            WHERE user_id = %s
              AND EventState = 'active'
              AND CreatedAt >= DATE_SUB(NOW(), INTERVAL 180 DAY)
              AND ImpactDirection IN ('positive', 'negative', 'recovery')
            """,
            (user_id,),
        )
        event_facts = cur.fetchone() or {}

        cur.execute(
            """
            SELECT
                CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END AS active_blacklist_count
            FROM user_pool up
            JOIN user_blacklist ub
              ON ub.IsActive = 1
             AND (ub.ExpiresAt IS NULL OR ub.ExpiresAt > NOW())
             AND (
                    (ub.user_id IS NOT NULL AND ub.user_id = up.user_id)
                 OR (ub.BlacklistType = 'email' AND LOWER(ub.Email) = LOWER(up.Email))
                 OR (ub.BlacklistType = 'domain' AND LOWER(ub.Domain) = LOWER(up.EmailDomain))
             )
            WHERE up.user_id = %s
            """,
            (user_id,),
        )
        blacklist_facts = cur.fetchone() or {}

        facts: dict[str, Any] = {}
        facts.update(survey_facts)
        facts.update(trial_facts)
        facts.update(nda_facts)
        facts.update(bonus_facts)
        facts.update(event_facts)
        facts.update(blacklist_facts)
        return facts
    finally:
        conn.close()


def upsert_reputation_rollup(user_id: str, payload: dict[str, Any]) -> None:
    """
    Insert or update the cached reputation rollup.

    Callers should calculate the payload in the service layer. This function only
    persists the explicit fields in user_reliability_score.
    """

    columns = ["user_id", *_ROLLUP_FIELDS]
    values = [user_id] + [
        payload.get(field)
        if payload.get(field) is not None
        else (datetime.now() if field == "LastCalculatedAt" else _ROLLUP_DEFAULTS[field])
        for field in _ROLLUP_FIELDS
    ]
    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(f"`{column}`" for column in columns)
    update_sql = ",\n                ".join(
        f"`{field}` = VALUES(`{field}`)" for field in _ROLLUP_FIELDS
    )

    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            INSERT INTO user_reliability_score ({column_sql})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE
                {update_sql},
                UpdatedAt = CURRENT_TIMESTAMP
            """,
            tuple(values),
        )
        conn.commit()
    finally:
        conn.close()


def insert_reputation_event(
    *,
    user_id: str,
    event_type: str,
    event_category: str = "system",
    impact_direction: str = "neutral",
    impact_points: float = 0.0,
    source: str = "System",
    round_id: int | None = None,
    value: float | None = None,
    weight_applied: float | None = None,
    reason: str | None = None,
    source_table: str | None = None,
    source_record_id: str | None = None,
    decay_eligible: bool = True,
    event_state: str = "active",
) -> int:
    """
    Insert one explicit reputation event and return its EventID.

    This is the audit trail. It does not recalculate the rollup by itself.
    """

    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO user_reliability_events (
                user_id,
                RoundID,
                EventType,
                EventCategory,
                ImpactDirection,
                ImpactPoints,
                Value,
                WeightApplied,
                Reason,
                Source,
                SourceTable,
                SourceRecordID,
                DecayEligible,
                EventState
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                user_id,
                round_id,
                event_type,
                event_category,
                impact_direction,
                impact_points,
                value,
                weight_applied,
                reason,
                source,
                source_table,
                source_record_id,
                1 if decay_eligible else 0,
                event_state,
            ),
        )
        event_id = int(cur.lastrowid)
        conn.commit()
        return event_id
    finally:
        conn.close()


def get_users_due_for_reputation_recovery(limit: int = 100) -> list[dict[str, Any]]:
    """
    Return users who are eligible for passive recovery review.

    The service layer still decides whether and how much recovery to apply.
    """

    safe_limit = _clamp_limit(limit, default=100, maximum=500)

    conn = _get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            f"""
            SELECT
                urs.user_id,
                urs.ReputationPoints,
                urs.LastRecoveryAppliedAt,
                urs.RecoveryPausedReason,
                urs.ActiveTrialCount,
                CASE WHEN COUNT(ub.BlacklistID) > 0 THEN 1 ELSE 0 END AS active_blacklist_count
            FROM user_reliability_score urs
            JOIN user_pool up
              ON up.user_id = urs.user_id
            LEFT JOIN user_blacklist ub
              ON ub.IsActive = 1
             AND (ub.ExpiresAt IS NULL OR ub.ExpiresAt > NOW())
             AND (
                    (ub.user_id IS NOT NULL AND ub.user_id = up.user_id)
                 OR (ub.BlacklistType = 'email' AND LOWER(ub.Email) = LOWER(up.Email))
                 OR (ub.BlacklistType = 'domain' AND LOWER(ub.Domain) = LOWER(up.EmailDomain))
             )
            WHERE urs.ReputationPoints < 70.00
              AND urs.ActiveTrialCount = 0
              AND (
                    urs.LastRecoveryAppliedAt IS NULL
                 OR urs.LastRecoveryAppliedAt <= DATE_SUB(NOW(), INTERVAL 7 DAY)
              )
            GROUP BY
                urs.user_id,
                urs.ReputationPoints,
                urs.LastRecoveryAppliedAt,
                urs.RecoveryPausedReason,
                urs.ActiveTrialCount
            HAVING active_blacklist_count = 0
            ORDER BY urs.LastRecoveryAppliedAt IS NULL DESC, urs.LastRecoveryAppliedAt ASC
            LIMIT {safe_limit}
            """
        )
        return cur.fetchall()
    finally:
        conn.close()