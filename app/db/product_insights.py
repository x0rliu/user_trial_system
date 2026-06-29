# app/db/product_insights.py

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import mysql.connector
from mysql.connector import errorcode

from app.db.connection import get_db_connection


class ProductInsightsTableMissing(RuntimeError):
    """Raised when the Product Insight Library DB tables have not been created."""


_VALID_INSIGHT_STATUSES = {
    "proposed",
    "observed",
    "strengthened",
    "confirmed",
    "contradicted",
    "retired",
}

_VALID_CONFIDENCE_LABELS = {"low", "medium", "high"}

_VALID_SIGNAL_TYPES = {
    "proposes",
    "supports",
    "strengthens",
    "weakens",
    "contradicts",
    "neutral",
}

_VALID_SIGNAL_STATUSES = {"proposed", "accepted", "dismissed"}

_VALID_EVIDENCE_TYPES = {
    "comment_bucket",
    "kpi_movement",
    "section_score",
    "project_decision",
    "source_report",
    "product_team_feedback",
    "raw_verbatim_pointer",
    "other",
}

_VALID_EVIDENCE_DIRECTIONS = {"supports", "contradicts", "weakens", "neutral"}

_VALID_SOURCE_SYSTEMS = {
    "current",
    "legacy",
    "project_report",
    "product_report",
    "portfolio_report",
    "product_team",
    "system",
}

_VALID_FEEDBACK_VALUES = {
    "thumbs_up",
    "thumbs_down",
    "useful",
    "not_useful",
    "important",
    "not_important",
    "actionable",
    "not_actionable",
    "too_vague",
    "wrong",
    "confirmed",
    "other",
}

_VALID_ACTOR_TYPES = {"ai", "user", "system"}

_VALID_AUDIT_ACTIONS = {
    "created",
    "updated",
    "status_changed",
    "confidence_changed",
    "evidence_added",
    "signal_added",
    "feedback_recorded",
    "merged",
    "retired",
    "restored",
    "locked",
    "unlocked",
    "dismissed",
    "other",
}


# -------------------------
# Basic helpers
# -------------------------

def _is_missing_table_error(exc: Exception) -> bool:
    return isinstance(exc, mysql.connector.Error) and exc.errno == errorcode.ER_NO_SUCH_TABLE


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _clean_optional_text(value: object) -> str | None:
    text = _clean_text(value)
    return text or None


def _limited_text(value: object, limit: int) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip()


def _validated(value: object, valid_values: set[str], fallback: str) -> str:
    cleaned = _clean_text(value).lower()
    return cleaned if cleaned in valid_values else fallback


def _safe_int(value: object, fallback: int = 0) -> int:
    try:
        if value in (None, ""):
            return fallback
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _safe_decimal(value: object, fallback: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _json_dumps(value: object) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _json_loads(value: object, fallback):
    try:
        parsed = json.loads(value or "")
        return parsed if parsed is not None else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def _json_safe(value: object):
    if isinstance(value, Decimal):
        return float(value)
    return value


def _datetime_to_text(value: object) -> str:
    return str(value or "")


# -------------------------
# Row formatters
# -------------------------

def _format_insight_row(row: dict | None) -> dict | None:
    if not row:
        return None

    formatted = dict(row)
    formatted["confidence_score"] = _json_safe(formatted.get("confidence_score"))
    formatted["human_locked"] = bool(formatted.get("human_locked"))
    formatted["needs_review"] = bool(formatted.get("needs_review"))
    formatted["spec_tags"] = _json_loads(formatted.pop("spec_tags_json", None), [])
    formatted["kpi_links"] = _json_loads(formatted.pop("kpi_links_json", None), [])
    formatted["kpi_impact"] = _json_loads(formatted.pop("kpi_impact_json", None), {})

    for key in ("first_seen_at", "last_seen_at", "retired_at", "created_at", "updated_at"):
        formatted[key] = _datetime_to_text(formatted.get(key))

    return formatted


def _format_signal_row(row: dict | None) -> dict | None:
    if not row:
        return None

    formatted = dict(row)
    formatted["kpi_impact"] = _json_loads(formatted.pop("kpi_impact_json", None), {})
    formatted["source_payload"] = _json_loads(formatted.pop("source_payload_json", None), {})

    for key in ("created_at", "updated_at"):
        formatted[key] = _datetime_to_text(formatted.get(key))

    return formatted


def _format_evidence_row(row: dict | None) -> dict | None:
    if not row:
        return None

    formatted = dict(row)
    formatted["metric_value"] = _json_safe(formatted.get("metric_value"))
    formatted["source_payload"] = _json_loads(formatted.pop("source_payload_json", None), {})
    formatted["created_at"] = _datetime_to_text(formatted.get("created_at"))

    return formatted


def _format_feedback_row(row: dict | None) -> dict | None:
    if not row:
        return None

    formatted = dict(row)
    formatted["created_at"] = _datetime_to_text(formatted.get("created_at"))
    return formatted


def _format_audit_row(row: dict | None) -> dict | None:
    if not row:
        return None

    formatted = dict(row)
    formatted["before"] = _json_loads(formatted.pop("before_json", None), None)
    formatted["after"] = _json_loads(formatted.pop("after_json", None), None)
    formatted["created_at"] = _datetime_to_text(formatted.get("created_at"))
    return formatted


# -------------------------
# Audit log
# -------------------------

def insert_product_insight_audit_log(
    *,
    insight_id: int | None = None,
    signal_id: int | None = None,
    evidence_id: int | None = None,
    actor_type: str = "system",
    actor_user_id: str | None = None,
    action_type: str = "other",
    before: dict | None = None,
    after: dict | None = None,
    note: str | None = None,
) -> dict:
    """Insert one audit row for Product Insight Library changes."""

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO product_insight_audit_log (
                insight_id,
                signal_id,
                evidence_id,
                actor_type,
                actor_user_id,
                action_type,
                before_json,
                after_json,
                note
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                insight_id,
                signal_id,
                evidence_id,
                _validated(actor_type, _VALID_ACTOR_TYPES, "system"),
                _clean_optional_text(actor_user_id),
                _validated(action_type, _VALID_AUDIT_ACTIONS, "other"),
                _json_dumps(before) if before is not None else None,
                _json_dumps(after) if after is not None else None,
                _clean_optional_text(note),
            ),
        )
        conn.commit()
        return {"success": True, "error": None, "audit_id": cur.lastrowid}

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            return {"success": False, "error": "table_missing", "audit_id": None}
        raise

    finally:
        cur.close()
        conn.close()


# -------------------------
# Insight reads
# -------------------------

def list_product_insights(
    *,
    include_retired: bool = False,
    statuses: list[str] | None = None,
    product_type_display: str | None = None,
    business_group: str | None = None,
    subgroup: str | None = None,
    tier: str | None = None,
    feature_domain: str | None = None,
    needs_review: bool | None = None,
    limit: int = 100,
) -> list[dict]:
    """List Product Insight Library rows for admin and matching workflows."""

    safe_limit = max(1, min(int(limit or 100), 500))
    where_sql = []
    params: list[Any] = []

    if not include_retired:
        where_sql.append("status <> 'retired'")

    clean_statuses = [
        status for status in (_validated(item, _VALID_INSIGHT_STATUSES, "") for item in statuses or [])
        if status
    ]
    if clean_statuses:
        where_sql.append("status IN (" + ",".join(["%s"] * len(clean_statuses)) + ")")
        params.extend(clean_statuses)

    for column, value in (
        ("product_type_display", product_type_display),
        ("business_group", business_group),
        ("subgroup", subgroup),
        ("tier", tier),
        ("feature_domain", feature_domain),
    ):
        cleaned = _clean_optional_text(value)
        if cleaned:
            where_sql.append(f"{column} = %s")
            params.append(cleaned)

    if needs_review is not None:
        where_sql.append("needs_review = %s")
        params.append(1 if needs_review else 0)

    sql = """
        SELECT
            insight_id,
            canonical_title,
            canonical_summary,
            so_what,
            recommended_action,
            do_not_overgeneralize,
            product_type_display,
            business_group,
            subgroup,
            tier,
            feature_domain,
            insight_type,
            taxonomy_path,
            spec_tags_json,
            kpi_links_json,
            kpi_impact_json,
            status,
            confidence_label,
            confidence_score,
            evidence_count,
            project_count,
            round_count,
            affected_user_count,
            first_seen_at,
            last_seen_at,
            human_locked,
            needs_review,
            created_by_source,
            created_by_user_id,
            updated_by_user_id,
            retired_at,
            created_at,
            updated_at
        FROM product_insights
    """

    if where_sql:
        sql += " WHERE " + " AND ".join(where_sql)

    sql += " ORDER BY confidence_score DESC, updated_at DESC, insight_id DESC LIMIT %s"
    params.append(safe_limit)

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(sql, tuple(params))
        return [
            formatted for formatted in (_format_insight_row(row) for row in cur.fetchall())
            if formatted
        ]

    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise

    finally:
        cur.close()
        conn.close()


def list_product_insights_for_matching(*, taxonomy: dict | None = None, limit: int = 40) -> list[dict]:
    """
    Return active insights likely relevant to a project taxonomy.

    Matching is intentionally conservative and DB-backed. The service layer can
    decide how to rank or compare the returned rows.
    """

    taxonomy = taxonomy or {}
    return list_product_insights(
        include_retired=False,
        statuses=["observed", "strengthened", "confirmed", "contradicted"],
        product_type_display=taxonomy.get("product_type_display"),
        business_group=taxonomy.get("business_group"),
        subgroup=taxonomy.get("subgroup"),
        tier=taxonomy.get("tier"),
        limit=limit,
    )


def get_product_insight_detail(*, insight_id: int) -> dict:
    """Read one insight with recent signals, evidence, feedback, and audit rows."""

    safe_insight_id = _safe_int(insight_id)
    if safe_insight_id <= 0:
        return {"success": False, "error": "missing_insight_id", "insight": None}

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT *
            FROM product_insights
            WHERE insight_id = %s
            LIMIT 1
            """,
            (safe_insight_id,),
        )
        insight = _format_insight_row(cur.fetchone())
        if not insight:
            return {"success": False, "error": "not_found", "insight": None}

        cur.execute(
            """
            SELECT *
            FROM product_insight_signals
            WHERE insight_id = %s
            ORDER BY created_at DESC, signal_id DESC
            LIMIT 50
            """,
            (safe_insight_id,),
        )
        signals = [
            formatted for formatted in (_format_signal_row(row) for row in cur.fetchall())
            if formatted
        ]

        cur.execute(
            """
            SELECT *
            FROM product_insight_evidence
            WHERE insight_id = %s
            ORDER BY created_at DESC, evidence_id DESC
            LIMIT 100
            """,
            (safe_insight_id,),
        )
        evidence = [
            formatted for formatted in (_format_evidence_row(row) for row in cur.fetchall())
            if formatted
        ]

        cur.execute(
            """
            SELECT *
            FROM product_insight_feedback
            WHERE insight_id = %s
            ORDER BY created_at DESC, feedback_id DESC
            LIMIT 100
            """,
            (safe_insight_id,),
        )
        feedback = [
            formatted for formatted in (_format_feedback_row(row) for row in cur.fetchall())
            if formatted
        ]

        cur.execute(
            """
            SELECT *
            FROM product_insight_audit_log
            WHERE insight_id = %s
            ORDER BY created_at DESC, audit_id DESC
            LIMIT 100
            """,
            (safe_insight_id,),
        )
        audit_log = [
            formatted for formatted in (_format_audit_row(row) for row in cur.fetchall())
            if formatted
        ]

        return {
            "success": True,
            "error": None,
            "insight": insight,
            "signals": signals,
            "evidence": evidence,
            "feedback": feedback,
            "audit_log": audit_log,
        }

    except Exception as exc:
        if _is_missing_table_error(exc):
            return {"success": False, "error": "table_missing", "insight": None}
        raise

    finally:
        cur.close()
        conn.close()


# -------------------------
# Insight writes
# -------------------------

def create_product_insight(
    *,
    canonical_title: str,
    canonical_summary: str,
    so_what: str | None = None,
    recommended_action: str | None = None,
    do_not_overgeneralize: str | None = None,
    product_type_display: str | None = None,
    business_group: str | None = None,
    subgroup: str | None = None,
    tier: str | None = None,
    feature_domain: str | None = None,
    insight_type: str | None = None,
    taxonomy_path: str | None = None,
    spec_tags: list | None = None,
    kpi_links: list | None = None,
    kpi_impact: dict | None = None,
    status: str = "proposed",
    confidence_label: str = "low",
    confidence_score: float = 0.0,
    evidence_count: int = 0,
    project_count: int = 0,
    round_count: int = 0,
    affected_user_count: int = 0,
    created_by_source: str = "ai",
    created_by_user_id: str | None = None,
    needs_review: bool = True,
) -> dict:
    """Create one durable Product Insight Library row and audit it."""

    title = _limited_text(canonical_title, 255)
    summary = _clean_text(canonical_summary)
    if not title or not summary:
        return {"success": False, "error": "missing_required_fields", "insight_id": None}

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO product_insights (
                canonical_title,
                canonical_summary,
                so_what,
                recommended_action,
                do_not_overgeneralize,
                product_type_display,
                business_group,
                subgroup,
                tier,
                feature_domain,
                insight_type,
                taxonomy_path,
                spec_tags_json,
                kpi_links_json,
                kpi_impact_json,
                status,
                confidence_label,
                confidence_score,
                evidence_count,
                project_count,
                round_count,
                affected_user_count,
                first_seen_at,
                last_seen_at,
                needs_review,
                created_by_source,
                created_by_user_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s, %s, %s)
            """,
            (
                title,
                summary,
                _clean_optional_text(so_what),
                _clean_optional_text(recommended_action),
                _clean_optional_text(do_not_overgeneralize),
                _clean_optional_text(product_type_display),
                _clean_optional_text(business_group),
                _clean_optional_text(subgroup),
                _clean_optional_text(tier),
                _clean_optional_text(feature_domain),
                _clean_optional_text(insight_type),
                _clean_optional_text(taxonomy_path),
                _json_dumps(spec_tags or []),
                _json_dumps(kpi_links or []),
                _json_dumps(kpi_impact or {}),
                _validated(status, _VALID_INSIGHT_STATUSES, "proposed"),
                _validated(confidence_label, _VALID_CONFIDENCE_LABELS, "low"),
                _safe_decimal(confidence_score),
                _safe_int(evidence_count),
                _safe_int(project_count),
                _safe_int(round_count),
                _safe_int(affected_user_count),
                1 if needs_review else 0,
                _validated(created_by_source, {"ai", "user", "system"}, "ai"),
                _clean_optional_text(created_by_user_id),
            ),
        )
        insight_id = cur.lastrowid

        cur.execute(
            """
            INSERT INTO product_insight_audit_log (
                insight_id,
                actor_type,
                actor_user_id,
                action_type,
                after_json,
                note
            )
            VALUES (%s, %s, %s, 'created', %s, %s)
            """,
            (
                insight_id,
                _validated(created_by_source, _VALID_ACTOR_TYPES, "ai"),
                _clean_optional_text(created_by_user_id),
                _json_dumps({
                    "canonical_title": title,
                    "status": _validated(status, _VALID_INSIGHT_STATUSES, "proposed"),
                    "confidence_label": _validated(confidence_label, _VALID_CONFIDENCE_LABELS, "low"),
                }),
                "Product insight created.",
            ),
        )

        conn.commit()
        return {"success": True, "error": None, "insight_id": insight_id}

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            raise ProductInsightsTableMissing("Product Insight Library tables do not exist") from exc
        raise

    finally:
        cur.close()
        conn.close()


def update_product_insight_status(
    *,
    insight_id: int,
    status: str,
    updated_by_user_id: str | None = None,
    actor_type: str = "user",
    note: str | None = None,
) -> dict:
    """Update only lifecycle status for one insight and audit the change."""

    safe_insight_id = _safe_int(insight_id)
    safe_status = _validated(status, _VALID_INSIGHT_STATUSES, "")
    if safe_insight_id <= 0 or not safe_status:
        return {"success": False, "error": "invalid_input"}

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("SELECT insight_id, status FROM product_insights WHERE insight_id = %s LIMIT 1", (safe_insight_id,))
        before = cur.fetchone()
        if not before:
            return {"success": False, "error": "not_found"}

        cur.execute(
            """
            UPDATE product_insights
            SET
                status = %s,
                retired_at = CASE WHEN %s = 'retired' THEN CURRENT_TIMESTAMP ELSE retired_at END,
                updated_by_user_id = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE insight_id = %s
            """,
            (safe_status, safe_status, _clean_optional_text(updated_by_user_id), safe_insight_id),
        )

        cur.execute(
            """
            INSERT INTO product_insight_audit_log (
                insight_id,
                actor_type,
                actor_user_id,
                action_type,
                before_json,
                after_json,
                note
            )
            VALUES (%s, %s, %s, 'status_changed', %s, %s, %s)
            """,
            (
                safe_insight_id,
                _validated(actor_type, _VALID_ACTOR_TYPES, "user"),
                _clean_optional_text(updated_by_user_id),
                _json_dumps({"status": before.get("status")}),
                _json_dumps({"status": safe_status}),
                _clean_optional_text(note),
            ),
        )

        conn.commit()
        return {"success": True, "error": None}

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            return {"success": False, "error": "table_missing"}
        raise

    finally:
        cur.close()
        conn.close()


def set_product_insight_lock(
    *,
    insight_id: int,
    human_locked: bool,
    updated_by_user_id: str,
) -> dict:
    """Lock or unlock AI changes to one insight's canonical wording/status."""

    safe_insight_id = _safe_int(insight_id)
    if safe_insight_id <= 0:
        return {"success": False, "error": "missing_insight_id"}

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("SELECT insight_id, human_locked FROM product_insights WHERE insight_id = %s LIMIT 1", (safe_insight_id,))
        before = cur.fetchone()
        if not before:
            return {"success": False, "error": "not_found"}

        cur.execute(
            """
            UPDATE product_insights
            SET
                human_locked = %s,
                updated_by_user_id = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE insight_id = %s
            """,
            (1 if human_locked else 0, _clean_optional_text(updated_by_user_id), safe_insight_id),
        )

        cur.execute(
            """
            INSERT INTO product_insight_audit_log (
                insight_id,
                actor_type,
                actor_user_id,
                action_type,
                before_json,
                after_json,
                note
            )
            VALUES (%s, 'user', %s, %s, %s, %s, %s)
            """,
            (
                safe_insight_id,
                _clean_optional_text(updated_by_user_id),
                "locked" if human_locked else "unlocked",
                _json_dumps({"human_locked": bool(before.get("human_locked"))}),
                _json_dumps({"human_locked": bool(human_locked)}),
                "Product insight lock state changed.",
            ),
        )

        conn.commit()
        return {"success": True, "error": None}

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            return {"success": False, "error": "table_missing"}
        raise

    finally:
        cur.close()
        conn.close()


# -------------------------
# Signals and evidence
# -------------------------

def create_product_insight_signal(
    *,
    signal_title: str,
    signal_summary: str,
    insight_id: int | None = None,
    project_key: str,
    project_report_id: int | None = None,
    source_report_key: str | None = None,
    signal_type: str = "proposes",
    signal_status: str = "proposed",
    product_type_display: str | None = None,
    business_group: str | None = None,
    subgroup: str | None = None,
    tier: str | None = None,
    feature_domain: str | None = None,
    insight_type: str | None = None,
    round_number: int | None = None,
    evidence_count: int = 0,
    affected_user_count: int = 0,
    kpi_impact: dict | None = None,
    source_payload: dict | None = None,
    extraction_version: str = "product_insight_signal_v1",
    generated_by_model: str | None = None,
) -> dict:
    """Create one project-level signal row and audit it."""

    title = _limited_text(signal_title, 255)
    summary = _clean_text(signal_summary)
    safe_project_key = _limited_text(project_key, 255)
    if not title or not summary or not safe_project_key:
        return {"success": False, "error": "missing_required_fields", "signal_id": None}

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO product_insight_signals (
                insight_id,
                project_key,
                project_report_id,
                source_report_key,
                signal_type,
                signal_status,
                signal_title,
                signal_summary,
                product_type_display,
                business_group,
                subgroup,
                tier,
                feature_domain,
                insight_type,
                round_number,
                evidence_count,
                affected_user_count,
                kpi_impact_json,
                source_payload_json,
                extraction_version,
                generated_by_model
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                _safe_int(insight_id) or None,
                safe_project_key,
                _safe_int(project_report_id) or None,
                _clean_optional_text(source_report_key),
                _validated(signal_type, _VALID_SIGNAL_TYPES, "proposes"),
                _validated(signal_status, _VALID_SIGNAL_STATUSES, "proposed"),
                title,
                summary,
                _clean_optional_text(product_type_display),
                _clean_optional_text(business_group),
                _clean_optional_text(subgroup),
                _clean_optional_text(tier),
                _clean_optional_text(feature_domain),
                _clean_optional_text(insight_type),
                _safe_int(round_number) or None,
                _safe_int(evidence_count),
                _safe_int(affected_user_count),
                _json_dumps(kpi_impact or {}),
                _json_dumps(source_payload or {}),
                _limited_text(extraction_version, 64) or "product_insight_signal_v1",
                _clean_optional_text(generated_by_model),
            ),
        )
        signal_id = cur.lastrowid

        cur.execute(
            """
            INSERT INTO product_insight_audit_log (
                insight_id,
                signal_id,
                actor_type,
                action_type,
                after_json,
                note
            )
            VALUES (%s, %s, 'ai', 'signal_added', %s, %s)
            """,
            (
                _safe_int(insight_id) or None,
                signal_id,
                _json_dumps({
                    "signal_title": title,
                    "signal_type": _validated(signal_type, _VALID_SIGNAL_TYPES, "proposes"),
                    "project_key": safe_project_key,
                }),
                "Product insight signal created.",
            ),
        )

        conn.commit()
        return {"success": True, "error": None, "signal_id": signal_id}

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            raise ProductInsightsTableMissing("Product Insight Library tables do not exist") from exc
        raise

    finally:
        cur.close()
        conn.close()


def create_product_insight_evidence(
    *,
    evidence_summary: str,
    insight_id: int | None = None,
    signal_id: int | None = None,
    evidence_type: str = "other",
    evidence_direction: str = "supports",
    source_system: str = "project_report",
    source_table: str | None = None,
    source_id: str | None = None,
    source_report_key: str | None = None,
    project_key: str | None = None,
    project_report_id: int | None = None,
    round_id: int | None = None,
    round_number: int | None = None,
    section_name: str | None = None,
    bucket_label: str | None = None,
    metric_name: str | None = None,
    metric_value: float | None = None,
    affected_user_count: int = 0,
    evidence_excerpt: str | None = None,
    source_payload: dict | None = None,
) -> dict:
    """Create one auditable evidence row for a signal or insight."""

    summary = _clean_text(evidence_summary)
    if not summary:
        return {"success": False, "error": "missing_evidence_summary", "evidence_id": None}

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO product_insight_evidence (
                insight_id,
                signal_id,
                evidence_type,
                evidence_direction,
                source_system,
                source_table,
                source_id,
                source_report_key,
                project_key,
                project_report_id,
                round_id,
                round_number,
                section_name,
                bucket_label,
                metric_name,
                metric_value,
                affected_user_count,
                evidence_summary,
                evidence_excerpt,
                source_payload_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                _safe_int(insight_id) or None,
                _safe_int(signal_id) or None,
                _validated(evidence_type, _VALID_EVIDENCE_TYPES, "other"),
                _validated(evidence_direction, _VALID_EVIDENCE_DIRECTIONS, "supports"),
                _validated(source_system, _VALID_SOURCE_SYSTEMS, "project_report"),
                _clean_optional_text(source_table),
                _clean_optional_text(source_id),
                _clean_optional_text(source_report_key),
                _clean_optional_text(project_key),
                _safe_int(project_report_id) or None,
                _safe_int(round_id) or None,
                _safe_int(round_number) or None,
                _clean_optional_text(section_name),
                _clean_optional_text(bucket_label),
                _clean_optional_text(metric_name),
                metric_value,
                _safe_int(affected_user_count),
                summary,
                _clean_optional_text(evidence_excerpt),
                _json_dumps(source_payload or {}),
            ),
        )
        evidence_id = cur.lastrowid

        cur.execute(
            """
            INSERT INTO product_insight_audit_log (
                insight_id,
                signal_id,
                evidence_id,
                actor_type,
                action_type,
                after_json,
                note
            )
            VALUES (%s, %s, %s, 'system', 'evidence_added', %s, %s)
            """,
            (
                _safe_int(insight_id) or None,
                _safe_int(signal_id) or None,
                evidence_id,
                _json_dumps({
                    "evidence_type": _validated(evidence_type, _VALID_EVIDENCE_TYPES, "other"),
                    "evidence_direction": _validated(evidence_direction, _VALID_EVIDENCE_DIRECTIONS, "supports"),
                    "project_key": _clean_optional_text(project_key),
                }),
                "Product insight evidence created.",
            ),
        )

        conn.commit()
        return {"success": True, "error": None, "evidence_id": evidence_id}

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            raise ProductInsightsTableMissing("Product Insight Library tables do not exist") from exc
        raise

    finally:
        cur.close()
        conn.close()


def attach_signal_to_insight(
    *,
    signal_id: int,
    insight_id: int,
    signal_type: str = "supports",
    signal_status: str = "accepted",
    actor_type: str = "system",
    actor_user_id: str | None = None,
    note: str | None = None,
) -> dict:
    """Attach an existing signal and its evidence to a durable insight."""

    safe_signal_id = _safe_int(signal_id)
    safe_insight_id = _safe_int(insight_id)
    if safe_signal_id <= 0 or safe_insight_id <= 0:
        return {"success": False, "error": "invalid_input"}

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("SELECT signal_id, insight_id, signal_type, signal_status FROM product_insight_signals WHERE signal_id = %s LIMIT 1", (safe_signal_id,))
        before = cur.fetchone()
        if not before:
            return {"success": False, "error": "signal_not_found"}

        cur.execute("SELECT insight_id FROM product_insights WHERE insight_id = %s LIMIT 1", (safe_insight_id,))
        if not cur.fetchone():
            return {"success": False, "error": "insight_not_found"}

        cur.execute(
            """
            UPDATE product_insight_signals
            SET
                insight_id = %s,
                signal_type = %s,
                signal_status = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE signal_id = %s
            """,
            (
                safe_insight_id,
                _validated(signal_type, _VALID_SIGNAL_TYPES, "supports"),
                _validated(signal_status, _VALID_SIGNAL_STATUSES, "accepted"),
                safe_signal_id,
            ),
        )

        cur.execute(
            """
            UPDATE product_insight_evidence
            SET insight_id = %s
            WHERE signal_id = %s AND insight_id IS NULL
            """,
            (safe_insight_id, safe_signal_id),
        )

        cur.execute(
            """
            INSERT INTO product_insight_audit_log (
                insight_id,
                signal_id,
                actor_type,
                actor_user_id,
                action_type,
                before_json,
                after_json,
                note
            )
            VALUES (%s, %s, %s, %s, 'updated', %s, %s, %s)
            """,
            (
                safe_insight_id,
                safe_signal_id,
                _validated(actor_type, _VALID_ACTOR_TYPES, "system"),
                _clean_optional_text(actor_user_id),
                _json_dumps(before),
                _json_dumps({
                    "insight_id": safe_insight_id,
                    "signal_type": _validated(signal_type, _VALID_SIGNAL_TYPES, "supports"),
                    "signal_status": _validated(signal_status, _VALID_SIGNAL_STATUSES, "accepted"),
                }),
                _clean_optional_text(note),
            ),
        )

        conn.commit()
        return {"success": True, "error": None}

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            return {"success": False, "error": "table_missing"}
        raise

    finally:
        cur.close()
        conn.close()


def list_product_insight_signals_for_project(
    *,
    project_key: str | None = None,
    project_report_id: int | None = None,
    limit: int = 100,
) -> list[dict]:
    """List signals already extracted for one project/report."""

    where_sql = []
    params: list[Any] = []

    if _clean_optional_text(project_key):
        where_sql.append("project_key = %s")
        params.append(_clean_text(project_key))

    if _safe_int(project_report_id) > 0:
        where_sql.append("project_report_id = %s")
        params.append(_safe_int(project_report_id))

    if not where_sql:
        return []

    safe_limit = max(1, min(int(limit or 100), 500))
    params.append(safe_limit)

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            f"""
            SELECT *
            FROM product_insight_signals
            WHERE {' AND '.join(where_sql)}
            ORDER BY created_at DESC, signal_id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [
            formatted for formatted in (_format_signal_row(row) for row in cur.fetchall())
            if formatted
        ]

    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise

    finally:
        cur.close()
        conn.close()


# -------------------------
# Feedback
# -------------------------

def record_product_insight_feedback(
    *,
    insight_id: int,
    user_id: str,
    feedback_value: str,
    feedback_comment: str | None = None,
    project_report_id: int | None = None,
) -> dict:
    """Record Product Team or UT Admin feedback on one insight."""

    safe_insight_id = _safe_int(insight_id)
    safe_user_id = _clean_text(user_id)
    safe_feedback = _validated(feedback_value, _VALID_FEEDBACK_VALUES, "other")

    if safe_insight_id <= 0 or not safe_user_id:
        return {"success": False, "error": "invalid_input", "feedback_id": None}

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO product_insight_feedback (
                insight_id,
                project_report_id,
                user_id,
                feedback_value,
                feedback_comment
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                safe_insight_id,
                _safe_int(project_report_id) or None,
                safe_user_id,
                safe_feedback,
                _clean_optional_text(feedback_comment),
            ),
        )
        feedback_id = cur.lastrowid

        cur.execute(
            """
            INSERT INTO product_insight_audit_log (
                insight_id,
                actor_type,
                actor_user_id,
                action_type,
                after_json,
                note
            )
            VALUES (%s, 'user', %s, 'feedback_recorded', %s, %s)
            """,
            (
                safe_insight_id,
                safe_user_id,
                _json_dumps({
                    "feedback_value": safe_feedback,
                    "project_report_id": _safe_int(project_report_id) or None,
                }),
                "Product insight feedback recorded.",
            ),
        )

        conn.commit()
        return {"success": True, "error": None, "feedback_id": feedback_id}

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            return {"success": False, "error": "table_missing", "feedback_id": None}
        raise

    finally:
        cur.close()
        conn.close()