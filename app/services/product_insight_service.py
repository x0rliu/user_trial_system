# app/services/product_insight_service.py

from __future__ import annotations

import json
import re
from decimal import Decimal

from app.db.product_insights import (
    ProductInsightsTableMissing,
    create_product_insight_evidence,
    create_product_insight_signal,
    list_product_insight_signals_for_project,
    list_product_insights_for_matching,
)
from app.services.ai_service import call_ai

INSIGHT_EXTRACTION_VERSION = "product_insight_project_signal_v1"


# -------------------------
# Basic helpers
# -------------------------

def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _clip_text(value: object, *, limit: int = 500) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _safe_int(value: object, fallback: int = 0) -> int:
    try:
        if value in (None, ""):
            return fallback
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _safe_float(value: object) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_safe(value: object):
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _extract_json_object(text: object) -> dict | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None

    try:
        parsed = json.loads(raw[start:end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _safe_key(value: object) -> str:
    text = _clean_text(value).lower()
    if not text:
        return "unknown"
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:80] or "unknown"


# -------------------------
# Project report normalization
# -------------------------

def project_insight_taxonomy_from_report(report: dict) -> dict:
    """
    Build the Product Insight Library taxonomy from a saved project report.

    Read-only. No inference. Empty strings are allowed when report metadata is
    incomplete; the matching service will then use broader matching later.
    """

    product = report.get("product") if isinstance(report, dict) else {}
    if not isinstance(product, dict):
        product = {}

    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}

    product_type_display = _clean_text(product.get("product_type_display"))
    business_group = _clean_text(product.get("business_group"))
    subgroup = _clean_text(product.get("subgroup"))
    tier = _clean_text(
        product.get("target_tier")
        or product.get("tier")
        or summary.get("kpi_target_tier")
    )

    taxonomy_parts = [
        part for part in [product_type_display, business_group, subgroup, tier]
        if part
    ]

    return {
        "product_type_display": product_type_display,
        "business_group": business_group,
        "subgroup": subgroup,
        "tier": tier,
        "taxonomy_path": " > ".join(taxonomy_parts),
    }


def _project_key_from_report(report: dict) -> str:
    metadata = report.get("metadata") if isinstance(report.get("metadata"), dict) else {}
    project_key = _clean_text(metadata.get("project_key"))
    if project_key:
        return project_key

    product = report.get("product") if isinstance(report.get("product"), dict) else {}
    project_label = _clean_text(product.get("project_label"))
    if project_label:
        return f"project_label:{project_label}"

    return "unknown_project"


def _project_report_id_from_report(report: dict) -> int | None:
    metadata = report.get("metadata") if isinstance(report.get("metadata"), dict) else {}
    value = _safe_int(metadata.get("project_report_id"), fallback=0)
    return value or None


def _source_report_key_from_report(report: dict) -> str:
    metadata = report.get("metadata") if isinstance(report.get("metadata"), dict) else {}
    data_hash = _clean_text(metadata.get("data_hash"))
    project_key = _project_key_from_report(report)
    if data_hash:
        return f"project_report:{project_key}:{data_hash}"
    return f"project_report:{project_key}"


def _compact_kpi_progression(report: dict) -> list[dict]:
    rows = []
    for item in report.get("kpi_progression") or []:
        if not isinstance(item, dict):
            continue
        rows.append({
            "key": item.get("key"),
            "label": item.get("label"),
            "first_value": item.get("first_value"),
            "final_value": item.get("final_value"),
            "delta": item.get("delta"),
            "target": item.get("target"),
            "status": item.get("status"),
            "suffix": item.get("suffix"),
            "rounds": item.get("rounds") or [],
        })
    return rows[:8]


def _compact_issue_progression(report: dict) -> list[dict]:
    rows = []
    for issue in report.get("issue_progression") or []:
        if not isinstance(issue, dict):
            continue
        rows.append({
            "issue_name": issue.get("issue_name"),
            "status": issue.get("status"),
            "first_seen_round": issue.get("first_seen_round"),
            "latest_seen_round": issue.get("latest_seen_round"),
            "affected_rounds": issue.get("affected_rounds") or [],
            "total_evidence_count": issue.get("total_evidence_count"),
            "recommendation": issue.get("recommendation"),
            "watchout": issue.get("watchout"),
            "evidence": (issue.get("evidence") or [])[:4],
        })
    return rows[:25]


def _compact_project_report_for_ai(report: dict) -> dict:
    product = report.get("product") if isinstance(report.get("product"), dict) else {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    final_recommendation = report.get("final_recommendation") if isinstance(report.get("final_recommendation"), dict) else {}

    return {
        "product": {
            "project_label": product.get("project_label"),
            "internal_name": product.get("internal_name"),
            "market_name": product.get("market_name"),
            "product_type_display": product.get("product_type_display"),
            "business_group": product.get("business_group"),
            "target_tier": product.get("target_tier"),
            "target_label": product.get("target_label"),
        },
        "summary": {
            "checkpoint_conclusion": summary.get("checkpoint_conclusion"),
            "next_action": summary.get("next_action"),
            "executive_summary": _clip_text(summary.get("executive_summary"), limit=1200),
            "source_report_count": summary.get("source_report_count"),
            "analytical_source_report_count": summary.get("analytical_source_report_count"),
            "validation_kpi_source_count": summary.get("validation_kpi_source_count"),
            "issue_count": summary.get("issue_count"),
            "final_watchout_count": summary.get("final_watchout_count"),
        },
        "kpis": report.get("kpis") if isinstance(report.get("kpis"), dict) else {},
        "kpi_progression": _compact_kpi_progression(report),
        "issue_progression": _compact_issue_progression(report),
        "risk_assessment": (report.get("risk_assessment") or [])[:12],
        "final_recommendation": {
            "conclusion": final_recommendation.get("conclusion"),
            "remaining_risks": final_recommendation.get("remaining_risks") or [],
            "accepted_watchouts": final_recommendation.get("accepted_watchouts") or [],
            "next_action": final_recommendation.get("next_action"),
        },
    }


# -------------------------
# AI prompts
# -------------------------

def _build_project_signal_prompt(*, report: dict, known_insights: list[dict]) -> str:
    known = []
    for insight in known_insights[:12]:
        if not isinstance(insight, dict):
            continue
        known.append({
            "insight_id": insight.get("insight_id"),
            "title": insight.get("canonical_title"),
            "summary": _clip_text(insight.get("canonical_summary"), limit=400),
            "status": insight.get("status"),
            "confidence_label": insight.get("confidence_label"),
            "feature_domain": insight.get("feature_domain"),
            "insight_type": insight.get("insight_type"),
        })

    compact_report = _compact_project_report_for_ai(report)

    return f"""
You extract auditable Product Insight Library signals from one published LogiTrials project report.

Return JSON only. No markdown. No extra text.

Required JSON shape:
{{
  "signals": [
    {{
      "signal_title": "short concrete project-level signal",
      "signal_summary": "one defensible statement about what this project showed",
      "signal_type": "proposes|supports|strengthens|weakens|contradicts|neutral",
      "matched_insight_id": null,
      "feature_domain": "Connectivity|Comfort|Software|Packaging|Audio|Mic|Battery|Design|Setup|Other",
      "insight_type": "recurring_risk|delight_driver|kpi_driver|fix_pattern|segment_sensitivity|launch_watchout|survey_design_lesson|support_qsg_lesson|other",
      "affected_user_count": 0,
      "kpi_impact": {{"star_rating": "positive|negative|neutral|unknown", "nps": "positive|negative|neutral|unknown", "ready_for_sales": "positive|negative|neutral|unknown"}},
      "evidence": [
        {{
          "evidence_type": "comment_bucket|kpi_movement|section_score|project_decision|source_report|other",
          "evidence_direction": "supports|contradicts|weakens|neutral",
          "section_name": "optional section or issue name",
          "bucket_label": "optional bucket or issue label",
          "metric_name": "optional metric name",
          "metric_value": null,
          "affected_user_count": 0,
          "evidence_summary": "short evidence summary",
          "evidence_excerpt": "short source excerpt or empty string"
        }}
      ]
    }}
  ]
}}

Rules:
- Use only facts in PROJECT_REPORT_JSON and KNOWN_INSIGHTS_JSON.
- Do not invent user counts, KPI values, product claims, causes, fixes, or source details.
- Do not treat loud emotional comments as signal by themselves.
- Prefer project-level learnings, not generic restatements of the report.
- A signal may matter despite low count only when KPI drag, RFS blocking, final-round persistence, critical product promise, or repeated issue evidence supports it.
- If a known insight is clearly supported, weakened, or contradicted, set matched_insight_id to that ID and use the appropriate signal_type.
- If no known insight clearly matches, set matched_insight_id to null and signal_type to proposes.
- Return 0 to 8 signals.
- Each signal must include at least one evidence item.

KNOWN_INSIGHTS_JSON:
{json.dumps(known, ensure_ascii=False, sort_keys=True, default=_json_safe)}

PROJECT_REPORT_JSON:
{json.dumps(compact_report, ensure_ascii=False, sort_keys=True, default=_json_safe)}
""".strip()


# -------------------------
# Public service functions
# -------------------------

def build_known_pattern_check_for_project_report(*, report: dict) -> dict:
    """
    Read-only comparison of one project report against active library insights.

    This does not write DB state. It is safe for preview/report rendering flows.
    """

    if not isinstance(report, dict) or not report:
        return {
            "success": False,
            "error": "missing_report",
            "taxonomy": {},
            "known_insights": [],
            "matched_signal_preview": [],
        }

    taxonomy = project_insight_taxonomy_from_report(report)
    known_insights = list_product_insights_for_matching(taxonomy=taxonomy, limit=40)

    return {
        "success": True,
        "error": None,
        "taxonomy": taxonomy,
        "known_insights": known_insights,
        "matched_signal_preview": [],
    }


def extract_project_insight_signals(
    *,
    report: dict,
    project_key: str | None = None,
    project_report_id: int | None = None,
    force: bool = False,
    generated_by_model: str | None = None,
) -> dict:
    """
    Extract project-level Product Insight signals from one published project report.

    This writes proposed signal/evidence rows only. It does not mutate canonical
    insight wording/status. Durable insight promotion is intentionally separate.
    """

    if not isinstance(report, dict) or not report:
        return {"success": False, "error": "missing_report", "signals_created": 0, "evidence_created": 0}

    safe_project_key = _clean_text(project_key) or _project_key_from_report(report)
    safe_project_report_id = project_report_id or _project_report_id_from_report(report)
    source_report_key = _source_report_key_from_report(report)

    if not force:
        existing_signals = list_product_insight_signals_for_project(
            project_key=safe_project_key,
            project_report_id=safe_project_report_id,
            limit=10,
        )
        if existing_signals:
            return {
                "success": True,
                "error": None,
                "skipped": True,
                "skip_reason": "signals_already_exist_for_project",
                "existing_signal_count": len(existing_signals),
                "signals_created": 0,
                "evidence_created": 0,
            }

    taxonomy = project_insight_taxonomy_from_report(report)
    known_insights = list_product_insights_for_matching(taxonomy=taxonomy, limit=40)

    ai_call_kwargs = {
        "prompt": _build_project_signal_prompt(report=report, known_insights=known_insights),
        "system_prompt": (
            "You extract auditable product insight signals from published Logitech user trial reports. "
            "Use only provided facts and return JSON only."
        ),
        "temperature": 0.2,
        "max_tokens": 2200,
    }
    if _clean_text(generated_by_model):
        ai_call_kwargs["model"] = _clean_text(generated_by_model)

    ai_result = call_ai(**ai_call_kwargs)

    if not ai_result.get("success"):
        return {
            "success": False,
            "error": f"ai_failed__{_safe_key(ai_result.get('error'))}",
            "signals_created": 0,
            "evidence_created": 0,
        }

    parsed = _extract_json_object(ai_result.get("response") or ai_result.get("content") or "")
    if not isinstance(parsed, dict):
        return {
            "success": False,
            "error": "invalid_ai_json",
            "signals_created": 0,
            "evidence_created": 0,
        }

    raw_signals = parsed.get("signals") if isinstance(parsed.get("signals"), list) else []
    created_signal_ids = []
    created_evidence_ids = []
    errors = []

    for raw_signal in raw_signals[:8]:
        if not isinstance(raw_signal, dict):
            continue

        title = _clean_text(raw_signal.get("signal_title"))
        summary = _clean_text(raw_signal.get("signal_summary"))
        evidence_items = raw_signal.get("evidence") if isinstance(raw_signal.get("evidence"), list) else []
        if not title or not summary or not evidence_items:
            continue

        matched_insight_id = _safe_int(raw_signal.get("matched_insight_id"), fallback=0) or None
        signal_type = _clean_text(raw_signal.get("signal_type")) or "proposes"

        try:
            signal_result = create_product_insight_signal(
                signal_title=title,
                signal_summary=summary,
                insight_id=matched_insight_id,
                project_key=safe_project_key,
                project_report_id=safe_project_report_id,
                source_report_key=source_report_key,
                signal_type=signal_type,
                signal_status="proposed",
                product_type_display=taxonomy.get("product_type_display"),
                business_group=taxonomy.get("business_group"),
                subgroup=taxonomy.get("subgroup"),
                tier=taxonomy.get("tier"),
                feature_domain=_clean_text(raw_signal.get("feature_domain")) or None,
                insight_type=_clean_text(raw_signal.get("insight_type")) or None,
                evidence_count=len(evidence_items),
                affected_user_count=_safe_int(raw_signal.get("affected_user_count")),
                kpi_impact=raw_signal.get("kpi_impact") if isinstance(raw_signal.get("kpi_impact"), dict) else {},
                source_payload={
                    "extraction_version": INSIGHT_EXTRACTION_VERSION,
                    "taxonomy": taxonomy,
                    "raw_signal": raw_signal,
                },
                extraction_version=INSIGHT_EXTRACTION_VERSION,
                generated_by_model=generated_by_model,
            )
        except ProductInsightsTableMissing:
            return {
                "success": False,
                "error": "table_missing",
                "signals_created": len(created_signal_ids),
                "evidence_created": len(created_evidence_ids),
            }

        if not signal_result.get("success"):
            errors.append(signal_result.get("error") or "signal_create_failed")
            continue

        signal_id = signal_result.get("signal_id")
        created_signal_ids.append(signal_id)

        for raw_evidence in evidence_items[:6]:
            if not isinstance(raw_evidence, dict):
                continue

            evidence_summary = _clean_text(raw_evidence.get("evidence_summary"))
            if not evidence_summary:
                continue

            try:
                evidence_result = create_product_insight_evidence(
                    evidence_summary=evidence_summary,
                    insight_id=matched_insight_id,
                    signal_id=signal_id,
                    evidence_type=_clean_text(raw_evidence.get("evidence_type")) or "other",
                    evidence_direction=_clean_text(raw_evidence.get("evidence_direction")) or "supports",
                    source_system="project_report",
                    source_table="reporting_project_reports",
                    source_id=str(safe_project_report_id or ""),
                    source_report_key=source_report_key,
                    project_key=safe_project_key,
                    project_report_id=safe_project_report_id,
                    section_name=_clean_text(raw_evidence.get("section_name")) or None,
                    bucket_label=_clean_text(raw_evidence.get("bucket_label")) or None,
                    metric_name=_clean_text(raw_evidence.get("metric_name")) or None,
                    metric_value=_safe_float(raw_evidence.get("metric_value")),
                    affected_user_count=_safe_int(raw_evidence.get("affected_user_count")),
                    evidence_excerpt=_clip_text(raw_evidence.get("evidence_excerpt"), limit=500),
                    source_payload={
                        "extraction_version": INSIGHT_EXTRACTION_VERSION,
                        "raw_evidence": raw_evidence,
                    },
                )
            except ProductInsightsTableMissing:
                return {
                    "success": False,
                    "error": "table_missing",
                    "signals_created": len(created_signal_ids),
                    "evidence_created": len(created_evidence_ids),
                }

            if evidence_result.get("success"):
                created_evidence_ids.append(evidence_result.get("evidence_id"))
            else:
                errors.append(evidence_result.get("error") or "evidence_create_failed")

    return {
        "success": True,
        "error": None if not errors else ";".join(errors[:5]),
        "skipped": False,
        "taxonomy": taxonomy,
        "known_insight_count": len(known_insights),
        "signals_created": len(created_signal_ids),
        "evidence_created": len(created_evidence_ids),
        "signal_ids": created_signal_ids,
        "evidence_ids": created_evidence_ids,
    }