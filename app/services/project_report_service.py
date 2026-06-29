# app/services/project_report_service.py

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal

from app.db.reporting_project_reports import (
    ReportingProjectReportsTableMissing,
    list_reporting_project_source_reports_for_generation,
    upsert_reporting_project_report,
)

GENERATION_VERSION = "reporting_project_report_v4_tiered_targets"


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _safe_error_key(value: object) -> str:
    text = _clean_text(value).lower()
    if not text:
        return "unknown"
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:80] or "unknown"


def _json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _project_identity_key(report: dict) -> str:
    product_id = report.get("product_id")
    if product_id not in (None, ""):
        return f"product:{product_id}"

    project_id = report.get("project_id")
    if project_id not in (None, ""):
        return f"project:{project_id}"

    internal_name = _clean_text(report.get("internal_name")).lower()
    market_name = _clean_text(report.get("market_name")).lower()
    business_group = _clean_text(report.get("business_group")).lower()
    product_type = _clean_text(report.get("product_type_display")).lower()

    return f"fallback:{internal_name}|{market_name}|{business_group}|{product_type}"


def _format_project_label(report: dict) -> str:
    internal_name = _clean_text(report.get("internal_name"))
    market_name = _clean_text(report.get("market_name"))

    if internal_name and market_name:
        return f"{internal_name} ({market_name})"
    if internal_name:
        return internal_name
    if market_name:
        return market_name
    return "Unnamed Project"


def _load_published_reports() -> list[dict]:
    from app.db.historical import list_published_historical_survey_reports_for_reporting_insights
    from app.db.historical_aggregate_reports import list_published_historical_aggregate_reports_for_reporting_insights
    from app.db.product_trial_reports import list_published_product_trial_reports_for_reporting_insights

    reports = list_published_historical_aggregate_reports_for_reporting_insights()
    reports.extend(list_published_historical_survey_reports_for_reporting_insights())
    reports.extend(list_published_product_trial_reports_for_reporting_insights())
    return reports


def _published_reports_for_project(project_key: str) -> list[dict]:
    safe_project_key = _clean_text(project_key)
    if not safe_project_key:
        return []

    return [
        report for report in _load_published_reports()
        if _project_identity_key(report) == safe_project_key
    ]


def _report_sort_key(report: dict) -> tuple[int, str]:
    try:
        round_number = int(report.get("round_number") or 0)
    except (TypeError, ValueError):
        round_number = 0
    activity = str(report.get("published_at") or report.get("updated_at") or "")
    return (round_number, activity)


def _data_hash(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=_json_safe)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _source_report_section(source_report: dict) -> dict:
    """
    Represent one included source report as a canonical report section.

    This keeps the first project-report pass useful without inventing deeper
    cross-round synthesis. AI synthesis can be layered on after the project
    report object and view are stable.
    """

    round_number = source_report.get("round_number")
    round_label = f"Round {round_number}" if round_number not in (None, "") else "Source Report"
    source_label = _clean_text(source_report.get("report_source_label")) or "Published Report"

    return {
        "section_name": round_label,
        "report_group": "Published Source Reports",
        "survey_name": source_label,
        "dataset_type": source_label,
        "average_score": None,
        "quant_questions": [
            {
                "question": "Published surveys included",
                "type": "count",
                "average": source_report.get("survey_count"),
                "values": [source_report.get("survey_count")],
            },
            {
                "question": "Datasets included",
                "type": "count",
                "average": source_report.get("dataset_count"),
                "values": [source_report.get("dataset_count")],
            },
            {
                "question": "Participant responses represented",
                "type": "count",
                "average": source_report.get("response_count"),
                "values": [source_report.get("response_count")],
            },
            {
                "question": "Answer records represented",
                "type": "count",
                "average": source_report.get("answer_count"),
                "values": [source_report.get("answer_count")],
            },
        ],
        "qual_question": None,
        "swot": {
            "strengths": [
                f"{round_label} is included as a published {source_label} source report."
            ],
            "weaknesses": [
                "This project report pass has not yet generated cross-round AI synthesis."
            ],
            "opportunities": [
                "Use the included source reports to identify what persisted, improved, or regressed across rounds."
            ],
            "threats": [
                "Treat this as a structured rollup until the project-level synthesis layer is added."
            ],
        },
        "section_analysis": {
            "key_findings": [
                f"{round_label} contributes {int(source_report.get('survey_count') or 0)} survey(s), "
                f"{int(source_report.get('dataset_count') or 0)} dataset(s), "
                f"and {int(source_report.get('response_count') or 0)} response(s) to this project report."
            ]
        },
        "source_report": source_report,
    }


_PROJECT_TIER_1_PRODUCT_TYPE_TOKENS = {
    "combo",
    "keyboard",
    "mouse",
}


_KPI_TARGETS_BY_TIER = {
    "tier_1": {
        "label": "Tier 1",
        "star_rating": 4.4,
        "nps": 50.0,
        "ready_for_sales": 95.0,
        "software_rating": 4.2,
    },
    "tier_2": {
        "label": "Tier 2",
        "star_rating": 4.2,
        "nps": 45.0,
        "ready_for_sales": 95.0,
        "software_rating": 4.2,
    },
}


_KPI_DEFINITIONS = [
    {
        "key": "star_rating",
        "label": "Star Rating",
        "count_key": "star_rating_count",
        "target": 4.2,
        "suffix": " / 5",
    },
    {
        "key": "nps",
        "label": "NPS",
        "count_key": "nps_count",
        "target": 45.0,
        "suffix": "",
    },
    {
        "key": "ready_for_sales",
        "label": "Ready for Sales",
        "count_key": "ready_for_sales_count",
        "target": 95.0,
        "suffix": "%",
    },
    {
        "key": "software_rating",
        "label": "Software Readiness",
        "count_key": "software_rating_count",
        "target": 4.2,
        "suffix": " / 5",
    },
]


def _to_float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int_or_none(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _project_target_tier(product_type_display: object) -> str:
    product_type = _clean_text(product_type_display).lower()

    if any(token in product_type for token in _PROJECT_TIER_1_PRODUCT_TYPE_TOKENS):
        return "tier_1"

    return "tier_2"


def _target_profile_for_project(representative: dict) -> dict:
    product_type_display = _clean_text(representative.get("product_type_display"))
    target_tier = _project_target_tier(product_type_display)
    target_config = _KPI_TARGETS_BY_TIER.get(target_tier) or _KPI_TARGETS_BY_TIER["tier_2"]

    return {
        "target_tier": target_tier,
        "target_label": target_config.get("label") or "Tier 2",
        "product_type_display": product_type_display,
        "targets": {
            key: value
            for key, value in target_config.items()
            if key != "label"
        },
        "rules": [
            "Tier 1 targets apply to Combo, Keyboard, and Mouse product types.",
            "Tier 2 targets apply to all other product types unless a stored tier is added later.",
            "Ready for Sales target remains 95%; calculation is adjusted blocker-based RFS, not simple raw preference.",
        ],
    }


def _kpi_definitions_for_target_profile(target_profile: dict) -> list[dict]:
    targets = target_profile.get("targets") if isinstance(target_profile.get("targets"), dict) else {}

    definitions = []
    for definition in _KPI_DEFINITIONS:
        item = dict(definition)
        key = item.get("key")
        if key in targets:
            item["target"] = targets[key]
        definitions.append(item)

    return definitions


def _metric_display(value: object, *, suffix: str = "", decimals: int = 1) -> str:
    numeric_value = _to_float_or_none(value)
    if numeric_value is None:
        return "—"

    text = f"{numeric_value:.{decimals}f}"
    if text.endswith(".0"):
        text = text[:-2]

    return f"{text}{suffix}"


def _source_report_json(source_report: dict) -> dict:
    report_json = source_report.get("source_report_json")
    return report_json if isinstance(report_json, dict) else {}


def _source_report_digest(source_report_json: dict) -> str:
    if not isinstance(source_report_json, dict) or not source_report_json:
        return ""
    return _data_hash(source_report_json)


def _round_number(source_report: dict, fallback: int) -> int:
    return _to_int_or_none(source_report.get("round_number")) or fallback


def _round_label(round_number: int | None) -> str:
    if round_number not in (None, 0):
        return f"Round {round_number}"
    return "Source Report"


def _source_report_audit_row(source_report: dict, *, fallback_round_number: int) -> dict:
    report_json = _source_report_json(source_report)
    round_number = _round_number(source_report, fallback_round_number)

    validation_kpis = source_report.get("validation_kpis")
    if not isinstance(validation_kpis, dict):
        validation_kpis = {}

    return {
        "report_key": _clean_text(source_report.get("report_key")),
        "report_source": _clean_text(source_report.get("report_source")),
        "report_source_label": _clean_text(source_report.get("report_source_label")) or "Published Report",
        "report_scope": _clean_text(source_report.get("report_scope")),
        "report_href": _clean_text(source_report.get("report_href")),
        "round_number": round_number,
        "round_label": _round_label(round_number),
        "survey_count": int(source_report.get("survey_count") or 0),
        "dataset_count": int(source_report.get("dataset_count") or 0),
        "section_count": int(source_report.get("section_count") or 0),
        "response_count": int(source_report.get("response_count") or 0),
        "answer_count": int(source_report.get("answer_count") or 0),
        "published_at": str(source_report.get("published_at") or ""),
        "updated_at": str(source_report.get("updated_at") or ""),
        "has_saved_report_json": bool(report_json),
        "has_validation_kpis": bool(validation_kpis.get("kpis")),
        "validation_kpis": validation_kpis,
        "source_report_digest": _source_report_digest(report_json),
    }


def _source_surveys_from_audit_rows(source_reports: list[dict]) -> list[dict]:
    source_surveys = []

    for source_report in source_reports:
        source_label = source_report.get("report_source_label") or "Published Report"
        round_label = source_report.get("round_label") or "Source Report"

        source_surveys.append({
            "survey_name": f"{round_label} — {source_label}",
            "dataset_type": source_report.get("report_scope") or source_label,
            "response_count": source_report.get("response_count") or 0,
            "answer_count": source_report.get("answer_count") or 0,
            "question_count": source_report.get("section_count") or 0,
            "source_href": source_report.get("report_href") or "",
            "source_file_name": "Saved report JSON" if source_report.get("has_saved_report_json") else "Audit-only source",
        })

    return source_surveys


def _validation_kpi_source_reports(source_reports: list[dict]) -> list[dict]:
    return [
        source_report for source_report in source_reports or []
        if isinstance(source_report, dict)
        and not source_report.get("has_saved_report_json")
        and source_report.get("has_validation_kpis")
    ]


def _audit_only_source_reports(source_reports: list[dict]) -> list[dict]:
    return [
        source_report for source_report in source_reports or []
        if isinstance(source_report, dict)
        and not source_report.get("has_saved_report_json")
        and not source_report.get("has_validation_kpis")
    ]


def _audit_only_source_label(source_report: dict) -> str:
    round_label = _clean_text(source_report.get("round_label"))
    if round_label:
        return round_label

    round_number = source_report.get("round_number")
    if round_number not in (None, ""):
        return f"Round {round_number}"

    return _clean_text(source_report.get("report_key")) or "Source Report"


def _audit_only_source_summaries(source_reports: list[dict]) -> list[dict]:
    summaries = []

    for source_report in _audit_only_source_reports(source_reports):
        summaries.append({
            "report_key": _clean_text(source_report.get("report_key")),
            "round_number": source_report.get("round_number"),
            "round_label": _audit_only_source_label(source_report),
            "report_source": _clean_text(source_report.get("report_source")),
            "report_source_label": _clean_text(source_report.get("report_source_label")) or "Source Report",
            "report_scope": _clean_text(source_report.get("report_scope")) or "audit-only",
            "report_href": _clean_text(source_report.get("report_href")),
            "reason": "No saved round report JSON",
        })

    return summaries


def _audit_only_source_summary_text(source_reports: list[dict]) -> str:
    audit_only_sources = _audit_only_source_summaries(source_reports)
    if not audit_only_sources:
        return ""

    labels = [
        source.get("round_label") or source.get("report_key") or "source report"
        for source in audit_only_sources
    ]

    return (
        f" Audit-only source(s) were also found: {', '.join(labels)}. "
        "They are included in Source Details / Audit Trail but excluded from KPI progression and issue progression "
        "because they do not have saved round report JSON."
    )


def _validation_kpi_source_summaries(source_reports: list[dict]) -> list[dict]:
    summaries = []

    for source_report in _validation_kpi_source_reports(source_reports):
        validation_kpis = source_report.get("validation_kpis")
        if not isinstance(validation_kpis, dict):
            validation_kpis = {}

        summaries.append({
            "report_key": _clean_text(source_report.get("report_key")),
            "round_number": source_report.get("round_number"),
            "round_label": _audit_only_source_label(source_report),
            "report_source": _clean_text(source_report.get("report_source")),
            "report_source_label": _clean_text(source_report.get("report_source_label")) or "Validation Source",
            "report_scope": _clean_text(source_report.get("report_scope")) or "validation",
            "report_href": _clean_text(source_report.get("report_href")),
            "reason": "Validation KPI evidence synthesized from survey answers",
            "kpis": validation_kpis.get("kpis") if isinstance(validation_kpis.get("kpis"), dict) else {},
            "kpi_questions": validation_kpis.get("kpi_questions") if isinstance(validation_kpis.get("kpi_questions"), list) else [],
        })

    return summaries


def _validation_kpi_source_summary_text(source_reports: list[dict]) -> str:
    validation_sources = _validation_kpi_source_summaries(source_reports)
    if not validation_sources:
        return ""

    labels = [
        source.get("round_label") or source.get("report_key") or "validation source"
        for source in validation_sources
    ]

    return (
        f" Validation KPI source(s) were also found: {', '.join(labels)}. "
        "They are included in KPI progression as validation evidence, even though they do not have saved round report JSON."
    )


def _validation_kpi_pass_summary(
    validation_kpi_sources: list[dict],
    *,
    kpi_definitions: list[dict] | None = None,
) -> dict:
    checked = []
    failed = []
    active_definitions = kpi_definitions or _KPI_DEFINITIONS

    for source in validation_kpi_sources or []:
        if not isinstance(source, dict):
            continue

        round_label = _clean_text(source.get("round_label")) or "Validation source"
        kpis = source.get("kpis") if isinstance(source.get("kpis"), dict) else {}

        for definition in active_definitions:
            key = definition["key"]
            if key not in kpis:
                continue

            value = _to_float_or_none(kpis.get(key))
            target = _to_float_or_none(definition.get("target"))
            suffix = definition.get("suffix") or ""
            label = definition.get("label") or key

            if value is None or target is None:
                continue

            status = _kpi_status(value, target=target)
            evidence_text = (
                f"{round_label} {label}: {_metric_display(value, suffix=suffix)} "
                f"against target {_metric_display(target, suffix=suffix)}."
            )

            checked.append({
                "round_label": round_label,
                "kpi_key": key,
                "kpi_label": label,
                "value": value,
                "target": target,
                "status": status,
                "evidence_text": evidence_text,
            })

            if status != "pass":
                failed.append({
                    "round_label": round_label,
                    "kpi_key": key,
                    "kpi_label": label,
                    "value": value,
                    "target": target,
                    "status": status,
                    "evidence_text": evidence_text,
                })

    return {
        "has_validation_kpis": bool(checked),
        "all_validation_kpis_pass": bool(checked) and not failed,
        "checked": checked,
        "failed": failed,
        "evidence": [
            item["evidence_text"]
            for item in checked
        ],
    }


def _apply_validation_outcomes_to_issue_progression(
    issue_progression: list[dict],
    *,
    validation_kpi_sources: list[dict],
    kpi_definitions: list[dict] | None = None,
) -> list[dict]:
    if not issue_progression:
        return []

    validation_summary = _validation_kpi_pass_summary(
        validation_kpi_sources,
        kpi_definitions=kpi_definitions,
    )
    if not validation_summary.get("has_validation_kpis"):
        return issue_progression

    validation_round_numbers = [
        _to_int_or_none(source.get("round_number"))
        for source in validation_kpi_sources or []
        if isinstance(source, dict)
    ]
    validation_round_numbers = [
        round_number for round_number in validation_round_numbers
        if round_number is not None
    ]

    if not validation_round_numbers:
        return issue_progression

    latest_validation_round = max(validation_round_numbers)
    validation_round_labels = [
        _clean_text(source.get("round_label")) or _round_label(_to_int_or_none(source.get("round_number")))
        for source in validation_kpi_sources or []
        if isinstance(source, dict)
    ]

    updated_issues = []

    for issue in issue_progression:
        if not isinstance(issue, dict):
            continue

        updated_issue = dict(issue)
        original_status = _clean_text(updated_issue.get("status")) or "watchout"
        latest_seen_round = _to_int_or_none(updated_issue.get("latest_seen_round"))

        updated_issue["pre_validation_status"] = original_status
        updated_issue["validation_sources"] = validation_round_labels
        updated_issue["validation_evidence"] = validation_summary.get("evidence") or []
        updated_issue["validation_failed_kpis"] = validation_summary.get("failed") or []

        if (
            latest_seen_round is not None
            and latest_seen_round < latest_validation_round
            and validation_summary.get("all_validation_kpis_pass")
            and original_status in {"new", "persistent", "improved", "worsened", "watchout"}
        ):
            updated_issue["status"] = "validated"
            updated_issue["validation_status"] = "validation_passed"
            updated_issue["latest_validation_round"] = latest_validation_round
            updated_issue["latest_validation_label"] = _round_label(latest_validation_round)
            updated_issue["final_recommendation"] = (
                f"Final validation KPI evidence passed in {_round_label(latest_validation_round)}. "
                "Treat this as validated fix evidence, while keeping any qualitative concern visible as a closed watchout."
            )
        elif validation_summary.get("failed"):
            updated_issue["validation_status"] = "validation_failed_or_mixed"
            updated_issue["latest_validation_round"] = latest_validation_round
            updated_issue["latest_validation_label"] = _round_label(latest_validation_round)
            updated_issue["final_recommendation"] = (
                "Validation KPI evidence is present but at least one validation KPI missed threshold. "
                "Keep this as an active watchout until Product Team reviews the validation source."
            )
        else:
            updated_issue["validation_status"] = "validation_present"
            updated_issue["latest_validation_round"] = latest_validation_round
            updated_issue["latest_validation_label"] = _round_label(latest_validation_round)

        updated_issues.append(updated_issue)

    return updated_issues


def _round_metrics(source_report: dict, *, fallback_round_number: int) -> dict:
    report_json = _source_report_json(source_report)
    kpis = report_json.get("kpis") if isinstance(report_json.get("kpis"), dict) else {}

    source_type = "saved_round_report_json"

    if not kpis:
        validation_kpis = source_report.get("validation_kpis")
        if isinstance(validation_kpis, dict):
            validation_payload_kpis = validation_kpis.get("kpis")
            if isinstance(validation_payload_kpis, dict):
                kpis = validation_payload_kpis
                source_type = "validation_kpi_source"

    round_number = _round_number(source_report, fallback_round_number)
    round_label = _round_label(round_number)

    if source_type == "validation_kpi_source":
        round_label = f"{round_label} validation"

    values = {}
    counts = {}

    for definition in _KPI_DEFINITIONS:
        key = definition["key"]
        count_key = definition["count_key"]

        values[key] = _to_float_or_none(kpis.get(key))
        counts[count_key] = _to_int_or_none(kpis.get(count_key))

    return {
        "report_key": _clean_text(source_report.get("report_key")),
        "round_number": round_number,
        "round_label": round_label,
        "source_type": source_type,
        "values": values,
        "counts": counts,
        "raw_kpis": kpis,
    }


def _kpi_status(value: object, *, target: float) -> str:
    numeric_value = _to_float_or_none(value)
    if numeric_value is None:
        return "missing"
    if numeric_value >= target:
        return "pass"
    return "fail"


def _build_kpi_progression(
    kpi_source_reports: list[dict],
    *,
    kpi_definitions: list[dict] | None = None,
) -> list[dict]:
    round_metrics = [
        _round_metrics(source_report, fallback_round_number=index)
        for index, source_report in enumerate(kpi_source_reports, start=1)
    ]

    progression = []
    active_definitions = kpi_definitions or _KPI_DEFINITIONS

    for definition in active_definitions:
        key = definition["key"]
        count_key = definition["count_key"]

        round_values = []
        for metrics in round_metrics:
            value = metrics["values"].get(key)
            if value is None:
                continue

            round_values.append({
                "round_number": metrics.get("round_number"),
                "round_label": metrics.get("round_label"),
                "report_key": metrics.get("report_key"),
                "source_type": metrics.get("source_type"),
                "value": value,
                "count": metrics["counts"].get(count_key),
            })

        if not round_values:
            continue

        first_value = round_values[0]["value"]
        final_value = round_values[-1]["value"]
        delta = final_value - first_value

        progression.append({
            "key": key,
            "label": definition["label"],
            "suffix": definition["suffix"],
            "target": definition["target"],
            "first_value": first_value,
            "final_value": final_value,
            "delta": delta,
            "status": _kpi_status(final_value, target=definition["target"]),
            "round_values": round_values,
            "round_values_text": " → ".join(
                f"{item['round_label']}: {_metric_display(item['value'], suffix=definition['suffix'])}"
                for item in round_values
            ),
        })

    return progression


def _final_kpis_from_saved_report(
    *,
    analytical_reports: list[dict],
    kpi_progression: list[dict],
) -> dict:
    final_kpis = {}

    if analytical_reports:
        final_report_json = _source_report_json(analytical_reports[-1])
        final_kpis = dict(final_report_json.get("kpis") or {})

    for item in kpi_progression:
        key = item.get("key")
        if not key:
            continue

        final_kpis[key] = item.get("final_value")

        for definition in _KPI_DEFINITIONS:
            if definition["key"] != key:
                continue

            count_key = definition["count_key"]
            round_values = item.get("round_values") or []
            if round_values:
                final_kpis[count_key] = round_values[-1].get("count")

    return final_kpis


def _swot_from_section(section: dict) -> dict:
    swot = section.get("swot")
    if isinstance(swot, dict):
        return swot

    summary_json = section.get("summary_json")
    if isinstance(summary_json, dict):
        return summary_json

    return {}


def _issue_signature(value: object) -> str:
    text = _clean_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:100] or "unknown_issue"


def _issue_candidates_from_source_report(source_report: dict, *, fallback_round_number: int) -> list[dict]:
    report_json = _source_report_json(source_report)
    round_number = _round_number(source_report, fallback_round_number)
    round_label = _round_label(round_number)
    candidates = []

    sections = report_json.get("sections") if isinstance(report_json.get("sections"), list) else []
    for section in sections:
        if not isinstance(section, dict):
            continue

        section_name = _clean_text(section.get("section_name")) or "Report Section"

        for bucket in section.get("comment_buckets") or []:
            if not isinstance(bucket, dict):
                continue

            label = _clean_text(bucket.get("label"))
            if not label:
                continue

            sentiment = _clean_text(bucket.get("sentiment")).lower() or "neutral"
            if sentiment == "positive":
                continue

            evidence = []
            for value in (bucket.get("evidence") or [])[:3]:
                clean_value = _clean_text(value)
                if clean_value:
                    evidence.append(clean_value)

            for value in (bucket.get("subpoints") or [])[:3]:
                clean_value = _clean_text(value)
                if clean_value:
                    evidence.append(clean_value)

            candidates.append({
                "issue_name": label,
                "round_number": round_number,
                "round_label": round_label,
                "section_name": section_name,
                "sentiment": sentiment,
                "evidence_count": int(bucket.get("user_count") or bucket.get("comment_count") or 1),
                "evidence": evidence[:4],
                "source": "comment_bucket",
            })

        swot = _swot_from_section(section)
        for category in ("weaknesses", "threats"):
            values = swot.get(category) if isinstance(swot.get(category), list) else []
            for value in values:
                label = _clean_text(value)
                if not label:
                    continue

                candidates.append({
                    "issue_name": label[:140],
                    "round_number": round_number,
                    "round_label": round_label,
                    "section_name": section_name,
                    "sentiment": "negative" if category == "threats" else "mixed",
                    "evidence_count": 1,
                    "evidence": [label],
                    "source": f"swot_{category}",
                })

    insights = report_json.get("insights") if isinstance(report_json.get("insights"), list) else []
    for insight in insights:
        if not isinstance(insight, dict):
            continue

        sentiment = _clean_text(insight.get("sentiment")).lower()
        if sentiment not in {"negative", "mixed"}:
            continue

        title = _clean_text(insight.get("title") or insight.get("insight_type"))
        explanation = _clean_text(insight.get("explanation") or insight.get("insight_summary"))
        label = title or explanation
        if not label:
            continue

        candidates.append({
            "issue_name": label[:140],
            "round_number": round_number,
            "round_label": round_label,
            "section_name": _clean_text(insight.get("section_name")) or "Insight",
            "sentiment": sentiment,
            "evidence_count": 1,
            "evidence": [explanation or label],
            "source": "insight",
        })

    return candidates


def _issue_status(*, first_round: int, latest_round: int, final_round: int, first_count: int, latest_count: int) -> str:
    if latest_round < final_round:
        return "resolved"
    if first_round == final_round:
        return "new"
    if latest_count > first_count:
        return "worsened"
    if latest_count < first_count:
        return "improved"
    return "persistent"


def _build_issue_progression(analytical_reports: list[dict]) -> list[dict]:
    if not analytical_reports:
        return []

    final_round = max(
        _round_number(source_report, index)
        for index, source_report in enumerate(analytical_reports, start=1)
    )

    issue_map = {}

    for index, source_report in enumerate(analytical_reports, start=1):
        for candidate in _issue_candidates_from_source_report(source_report, fallback_round_number=index):
            issue_name = candidate["issue_name"]
            signature = _issue_signature(issue_name)
            round_number = candidate["round_number"]

            if signature not in issue_map:
                issue_map[signature] = {
                    "issue_name": issue_name,
                    "rounds": {},
                    "sections": set(),
                    "sources": set(),
                    "sentiments": set(),
                    "evidence": [],
                }

            issue = issue_map[signature]
            issue["sections"].add(candidate.get("section_name") or "Report Section")
            issue["sources"].add(candidate.get("source") or "saved_report_json")
            issue["sentiments"].add(candidate.get("sentiment") or "mixed")

            if round_number not in issue["rounds"]:
                issue["rounds"][round_number] = {
                    "round_number": round_number,
                    "round_label": candidate.get("round_label") or _round_label(round_number),
                    "evidence_count": 0,
                }

            issue["rounds"][round_number]["evidence_count"] += int(candidate.get("evidence_count") or 1)

            for evidence in candidate.get("evidence") or []:
                clean_evidence = _clean_text(evidence)
                if clean_evidence and clean_evidence not in issue["evidence"]:
                    issue["evidence"].append(clean_evidence)

    results = []

    for issue in issue_map.values():
        round_numbers = sorted(issue["rounds"])
        if not round_numbers:
            continue

        first_round = round_numbers[0]
        latest_round = round_numbers[-1]
        first_count = int(issue["rounds"][first_round].get("evidence_count") or 0)
        latest_count = int(issue["rounds"][latest_round].get("evidence_count") or 0)

        status = _issue_status(
            first_round=first_round,
            latest_round=latest_round,
            final_round=final_round,
            first_count=first_count,
            latest_count=latest_count,
        )

        if status == "resolved":
            recommendation = "No final-round evidence found. Keep in audit trail unless the Product Team wants targeted confirmation."
        elif status == "improved":
            recommendation = "Improved, but still present in the final round. Carry as an accepted watchout or validate one more fix pass."
        elif status == "new":
            recommendation = "New in the final round. Review before checkpoint approval."
        elif status == "worsened":
            recommendation = "Worsened by the final round. Hold for fix validation unless Product Team explicitly accepts the risk."
        else:
            recommendation = "Persistent through the final round. Carry as a final watchout."

        results.append({
            "issue_name": issue["issue_name"],
            "first_seen_round": first_round,
            "latest_seen_round": latest_round,
            "affected_rounds": [
                issue["rounds"][round_number]["round_label"]
                for round_number in round_numbers
            ],
            "affected_round_numbers": round_numbers,
            "status": status,
            "first_evidence_count": first_count,
            "latest_evidence_count": latest_count,
            "total_evidence_count": sum(
                int(issue["rounds"][round_number].get("evidence_count") or 0)
                for round_number in round_numbers
            ),
            "sections": sorted(issue["sections"]),
            "sources": sorted(issue["sources"]),
            "sentiments": sorted(issue["sentiments"]),
            "evidence": issue["evidence"][:6],
            "final_recommendation": recommendation,
        })

    status_rank = {
        "worsened": 0,
        "new": 1,
        "persistent": 2,
        "improved": 3,
        "resolved": 4,
    }

    return sorted(
        results,
        key=lambda item: (
            status_rank.get(item.get("status"), 9),
            -int(item.get("latest_evidence_count") or 0),
            str(item.get("issue_name") or "").lower(),
        ),
    )


def _build_kpi_progression_sections(kpi_progression: list[dict]) -> list[dict]:
    sections = []

    for item in kpi_progression:
        label = item.get("label") or "KPI"
        suffix = item.get("suffix") or ""
        status = item.get("status") or "missing"
        delta = item.get("delta")
        final_value = item.get("final_value")
        target = item.get("target")

        sections.append({
            "section_name": f"{label} Progression",
            "report_group": "KPI Summary and Progression",
            "survey_name": "Project Report",
            "dataset_type": "Saved source report JSON",
            "average_score": final_value,
            "quant_questions": [
                {
                    "question": f"{label} round-by-round values",
                    "type": "progression",
                    "average": final_value,
                    "values": [
                        round_value.get("value")
                        for round_value in item.get("round_values") or []
                        if round_value.get("value") is not None
                    ],
                },
                {
                    "question": f"{label} delta from first to final",
                    "type": "delta",
                    "average": delta,
                    "values": [delta],
                },
                {
                    "question": f"{label} target threshold",
                    "type": "target",
                    "average": target,
                    "values": [target],
                },
            ],
            "qual_question": None,
            "swot": {
                "strengths": [
                    f"Final {label}: {_metric_display(final_value, suffix=suffix)}."
                ],
                "weaknesses": [
                    f"Status against current report threshold: {status}."
                ],
                "opportunities": [
                    f"Use the round progression to verify whether final-round performance is stable enough for the checkpoint."
                ],
                "threats": [
                    f"Threshold used by this deterministic pass: {_metric_display(target, suffix=suffix)}."
                ],
            },
            "section_analysis": {
                "key_findings": [
                    item.get("round_values_text") or f"No saved {label} progression available.",
                    f"Delta from first to final: {_metric_display(delta, suffix=suffix)}.",
                    f"Final status: {status}.",
                ]
            },
        })

    return sections


def _build_round_reason_sections(
    *,
    analytical_reports: list[dict],
    issue_progression: list[dict],
) -> list[dict]:
    if len(analytical_reports) <= 1:
        return []

    sections = []

    for index, source_report in enumerate(analytical_reports[1:], start=2):
        current_round = _round_number(source_report, index)
        previous_round = _round_number(analytical_reports[index - 2], index - 1)

        previous_issues = [
            issue for issue in issue_progression
            if previous_round in (issue.get("affected_round_numbers") or [])
        ][:3]

        current_issues = [
            issue for issue in issue_progression
            if current_round in (issue.get("affected_round_numbers") or [])
        ][:3]

        previous_issue_text = ", ".join(
            issue.get("issue_name") or "unnamed issue"
            for issue in previous_issues
        ) or "no saved issue evidence"

        current_issue_text = ", ".join(
            issue.get("issue_name") or "unnamed issue"
            for issue in current_issues
        ) or "no saved issue evidence"

        sections.append({
            "section_name": f"Why Round {current_round} Existed",
            "report_group": "Why Multiple Rounds Were Needed",
            "survey_name": "Project Report",
            "dataset_type": "Saved source report JSON",
            "average_score": None,
            "quant_questions": [
                {
                    "question": "Prior round number",
                    "type": "round",
                    "average": previous_round,
                    "values": [previous_round],
                },
                {
                    "question": "Validation round number",
                    "type": "round",
                    "average": current_round,
                    "values": [current_round],
                },
            ],
            "qual_question": None,
            "swot": {
                "strengths": [
                    f"Round {current_round} has a saved report JSON artifact and can be compared against Round {previous_round}."
                ],
                "weaknesses": [
                    "Saved report JSON does not currently store an explicit Product Team fix/change note between rounds."
                ],
                "opportunities": [
                    f"Use Round {current_round} to validate whether Round {previous_round} issues improved, persisted, or worsened."
                ],
                "threats": [
                    f"Round {previous_round} issue evidence: {previous_issue_text}."
                ],
            },
            "section_analysis": {
                "key_findings": [
                    f"Round {previous_round} showed: {previous_issue_text}.",
                    f"Round {current_round} showed: {current_issue_text}.",
                    "This deterministic pass does not invent the Product Team change list when it is not stored in the saved report JSON.",
                ]
            },
        })

    return sections


def _build_validation_kpi_source_sections(
    validation_kpi_sources: list[dict],
    *,
    kpi_definitions: list[dict] | None = None,
) -> list[dict]:
    sections = []
    active_definitions = kpi_definitions or _KPI_DEFINITIONS

    definition_map = {
        definition["key"]: definition
        for definition in active_definitions
    }

    for source in validation_kpi_sources or []:
        if not isinstance(source, dict):
            continue

        round_label = _clean_text(source.get("round_label")) or "Validation Source"
        report_source_label = _clean_text(source.get("report_source_label")) or "Validation Source"
        report_scope = _clean_text(source.get("report_scope")) or "validation"
        kpis = source.get("kpis") if isinstance(source.get("kpis"), dict) else {}
        kpi_questions = source.get("kpi_questions") if isinstance(source.get("kpi_questions"), list) else []

        if not kpis:
            continue

        question_by_key = {}
        for question in kpi_questions:
            if not isinstance(question, dict):
                continue
            key = _clean_text(question.get("kpi_key"))
            if key:
                question_by_key[key] = question

        quant_questions = []
        key_findings = [
            f"{round_label} is included as validation KPI evidence synthesized from survey answers.",
            "This source does not have saved round report JSON, so it should validate KPI movement rather than replace full issue-level round synthesis.",
        ]

        strength_items = []
        threat_items = []

        for key in ("star_rating", "nps", "ready_for_sales"):
            if key not in kpis:
                continue

            definition = definition_map.get(key) or {}
            label = definition.get("label") or key
            suffix = definition.get("suffix") or ""
            target = definition.get("target")
            value = kpis.get(key)
            count = kpis.get(f"{key}_count")
            question = question_by_key.get(key) or {}
            question_text = _clean_text(question.get("question_text")) or f"{label} validation KPI"
            status = _kpi_status(value, target=target) if target is not None else "missing"

            quant_questions.append({
                "question": question_text,
                "type": "validation_kpi",
                "average": value,
                "values": [value],
                "count": count,
                "target": target,
                "status": status,
            })

            finding = (
                f"{label}: {_metric_display(value, suffix=suffix)}"
                f"{f' (n={count})' if count not in (None, '') else ''}"
                f"{f'; target {_metric_display(target, suffix=suffix)}' if target is not None else ''}."
            )
            key_findings.append(finding)

            if status == "pass":
                strength_items.append(finding)
            else:
                threat_items.append(finding)

        if not quant_questions:
            continue

        if not strength_items:
            strength_items = [
                f"{round_label} provides validation KPI evidence for the final checkpoint."
            ]

        if not threat_items:
            threat_items = [
                "No validation KPI in this source missed the current deterministic threshold."
            ]

        sections.append({
            "section_name": f"{round_label} Validation KPI Evidence",
            "report_group": "Validation KPI Evidence",
            "survey_name": report_source_label,
            "dataset_type": report_scope,
            "average_score": None,
            "quant_questions": quant_questions,
            "qual_question": None,
            "swot": {
                "strengths": strength_items,
                "weaknesses": [
                    "This validation source is synthesized from survey answers and does not yet provide saved issue-level report JSON."
                ],
                "opportunities": [
                    "Use this validation KPI evidence to confirm whether the prior-round fix was effective enough for checkpoint approval."
                ],
                "threats": threat_items,
            },
            "section_analysis": {
                "key_findings": key_findings,
            },
        })

    return sections


def _build_issue_progression_sections(issue_progression: list[dict]) -> list[dict]:
    if not issue_progression:
        return [{
            "section_name": "Issue Progression",
            "report_group": "Detailed Issue Progression",
            "survey_name": "Project Report",
            "dataset_type": "Saved source report JSON",
            "average_score": None,
            "quant_questions": [],
            "qual_question": None,
            "swot": {
                "strengths": [
                    "No saved issue progression was detected from comment buckets, SWOT weaknesses, SWOT threats, or saved insights."
                ],
                "weaknesses": [
                    "This may mean the source reports predate saved comment bucket generation or do not include issue-level synthesis."
                ],
                "opportunities": [
                    "Once source round reports include comment buckets, the Project Report can track resolved, improved, persistent, new, and worsened issues."
                ],
                "threats": [
                    "Do not infer issue resolution from raw answer-row counts."
                ],
            },
            "section_analysis": {
                "key_findings": [
                    "No issue progression could be built from saved report JSON.",
                    "Source report audit details remain available at the bottom of the Project Report page.",
                ]
            },
        }]

    sections = []

    for issue in issue_progression[:12]:
        issue_name = issue.get("issue_name") or "Issue"
        status = issue.get("status") or "watchout"
        affected_rounds = issue.get("affected_rounds") or []
        evidence = issue.get("evidence") or []

        sections.append({
            "section_name": issue_name,
            "report_group": "Detailed Issue Progression",
            "survey_name": "Project Report",
            "dataset_type": "Saved source report JSON",
            "average_score": None,
            "quant_questions": [
                {
                    "question": "First seen round",
                    "type": "round",
                    "average": issue.get("first_seen_round"),
                    "values": [issue.get("first_seen_round")],
                },
                {
                    "question": "Latest seen round",
                    "type": "round",
                    "average": issue.get("latest_seen_round"),
                    "values": [issue.get("latest_seen_round")],
                },
                {
                    "question": "Total evidence count",
                    "type": "count",
                    "average": issue.get("total_evidence_count"),
                    "values": [issue.get("total_evidence_count")],
                },
            ],
            "qual_question": None,
            "comment_buckets": [{
                "label": issue_name,
                "sentiment": "negative" if status in {"new", "persistent", "worsened"} else "mixed",
                "user_count": issue.get("latest_evidence_count") or 1,
                "comment_count": issue.get("total_evidence_count") or 1,
                "evidence": evidence[:3],
                "subpoints": [
                    f"Status: {status}",
                    f"Affected rounds: {', '.join(affected_rounds)}",
                ],
            }],
            "swot": {
                "strengths": [
                    f"Status: {status}."
                ],
                "weaknesses": [
                    f"Affected rounds: {', '.join(affected_rounds)}."
                ],
                "opportunities": [
                    issue.get("final_recommendation") or "Review before checkpoint approval."
                ],
                "threats": evidence[:3] or [
                    "No short evidence excerpt stored."
                ],
            },
            "section_analysis": {
                "key_findings": [
                    f"First seen: Round {issue.get('first_seen_round')}.",
                    f"Latest seen: Round {issue.get('latest_seen_round')}.",
                    f"Status: {status}.",
                    issue.get("final_recommendation") or "Review before checkpoint approval.",
                ]
            },
        })

    return sections


def _unresolved_issues(issue_progression: list[dict]) -> list[dict]:
    return [
        issue for issue in issue_progression
        if issue.get("status") in {"improved", "persistent", "new", "worsened", "watchout"}
    ]


def _checkpoint_conclusion(
    *,
    analytical_report_count: int,
    kpi_progression: list[dict],
    issue_progression: list[dict],
) -> str:
    if analytical_report_count <= 0 or not kpi_progression:
        return "Insufficient data"

    failed_kpis = [
        item for item in kpi_progression
        if item.get("status") == "fail"
    ]
    if failed_kpis:
        return "Hold for fix validation"

    unresolved = _unresolved_issues(issue_progression)
    if analytical_report_count == 1 and unresolved:
        return "Run another round"

    if unresolved:
        return "Proceed with watchouts"

    return "Proceed"


def _next_action_for_conclusion(
    conclusion: str,
    *,
    validation_kpi_source_count: int = 0,
) -> str:
    has_validation_kpi_source = validation_kpi_source_count > 0

    if conclusion == "Proceed":
        if has_validation_kpi_source:
            return "Proceed to the next checkpoint using the validation KPI source as final fix-confirmation evidence."
        return "Proceed to the next checkpoint."

    if conclusion == "Proceed with watchouts":
        if has_validation_kpi_source:
            return "Proceed with Product Team acceptance of the listed analytical watchouts; validation KPI evidence is present for the final check."
        return "Proceed only with Product Team acceptance of the listed watchouts."

    if conclusion == "Hold for fix validation":
        return "Hold until the failed KPI or unresolved blocking issue is validated in a follow-up round."

    if conclusion == "Run another round":
        return "Run another round focused on the final-round watchouts."

    return "Do not use this Project Report for checkpoint approval until saved round report JSON or validation KPI evidence is available."


def _build_executive_summary(
    *,
    project_label: str,
    conclusion: str,
    analytical_report_count: int,
    source_reports: list[dict],
    kpi_progression: list[dict],
    issue_progression: list[dict],
) -> str:
    final_metric_map = {
        item.get("key"): item
        for item in kpi_progression
        if item.get("key")
    }

    star = final_metric_map.get("star_rating") or {}
    nps = final_metric_map.get("nps") or {}
    rfs = final_metric_map.get("ready_for_sales") or {}

    failed_kpis = [
        item.get("label") or item.get("key")
        for item in kpi_progression
        if item.get("status") == "fail"
    ]

    unresolved = _unresolved_issues(issue_progression)
    resolved = [
        issue for issue in issue_progression
        if issue.get("status") == "resolved"
    ]
    new_issues = [
        issue for issue in issue_progression
        if issue.get("status") == "new"
    ]

    main_issues = issue_progression[:3]
    main_issue_text = ", ".join(
        issue.get("issue_name") or "unnamed issue"
        for issue in main_issues
    ) or "no saved issue progression"

    threshold_text = (
        "within the current report thresholds"
        if not failed_kpis and kpi_progression
        else f"not within threshold for {', '.join(failed_kpis)}"
    )

    resolved_text = ", ".join(
        issue.get("issue_name") or "unnamed issue"
        for issue in resolved[:2]
    ) or "no resolved issues detected"

    watchout_text = ", ".join(
        issue.get("issue_name") or "unnamed issue"
        for issue in unresolved[:3]
    ) or "no final watchouts detected"

    new_text = ", ".join(
        issue.get("issue_name") or "unnamed issue"
        for issue in new_issues[:2]
    ) or "no newly emerged issue detected"

    validation_kpi_text = _validation_kpi_source_summary_text(source_reports)
    audit_only_text = _audit_only_source_summary_text(source_reports)

    return (
        f"Checkpoint conclusion: {conclusion}. "
        f"After {analytical_report_count} saved analytical round report(s), {project_label} ended with "
        f"Star Rating {_metric_display(star.get('final_value'), suffix=' / 5')}, "
        f"NPS {_metric_display(nps.get('final_value'))}, and "
        f"Ready for Sales {_metric_display(rfs.get('final_value'), suffix='%')}. "
        f"These are {threshold_text} for this deterministic report pass. "
        f"The main issues tracked across saved analytical rounds were {main_issue_text}. "
        f"By the final saved analytical round, resolved/improved issue evidence included {resolved_text}; "
        f"pre-validation analytical watchouts included {watchout_text}; and newly emerged analytical issue evidence included {new_text}."
        f"{validation_kpi_text}"
        f"{audit_only_text}"
    )


def _build_project_insights(
    *,
    conclusion: str,
    next_action: str,
    kpi_progression: list[dict],
    issue_progression: list[dict],
    validation_kpi_sources: list[dict],
) -> list[dict]:
    insights = [{
        "title": f"Checkpoint Conclusion: {conclusion}",
        "section_name": "Executive Checkpoint",
        "impact": "high",
        "sentiment": "positive" if conclusion == "Proceed" else "mixed",
        "explanation": next_action,
        "evidence": [
            "Generated from saved source report JSON and validation KPI sources.",
            "Raw answer-row counts remain audit context; validation KPI rows may be synthesized into KPI progression when source report JSON is unavailable.",
        ],
    }]

    if validation_kpi_sources:
        validation_evidence = []

        for source in validation_kpi_sources[:3]:
            if not isinstance(source, dict):
                continue

            round_label = _clean_text(source.get("round_label")) or "Validation source"
            kpis = source.get("kpis") if isinstance(source.get("kpis"), dict) else {}
            parts = []

            for definition in _KPI_DEFINITIONS:
                key = definition["key"]
                if key not in kpis:
                    continue

                parts.append(
                    f"{definition['label']} {_metric_display(kpis.get(key), suffix=definition.get('suffix') or '')}"
                )

            if parts:
                validation_evidence.append(f"{round_label}: {', '.join(parts)}.")
            else:
                validation_evidence.append(f"{round_label}: validation KPI payload present.")

        insights.append({
            "title": "Validation KPI evidence included",
            "section_name": "Validation KPI Evidence",
            "impact": "high",
            "sentiment": "positive",
            "explanation": "A validation survey without saved round report JSON is included as final KPI evidence for the checkpoint.",
            "evidence": validation_evidence or [
                "Validation KPI source is present."
            ],
        })

    failed_kpis = [
        item for item in kpi_progression
        if item.get("status") == "fail"
    ]
    if failed_kpis:
        insights.append({
            "title": "KPI threshold miss",
            "section_name": "KPI Summary and Progression",
            "impact": "high",
            "sentiment": "negative",
            "explanation": "One or more final-round KPIs are below the current report threshold.",
            "evidence": [
                f"{item.get('label')}: final {_metric_display(item.get('final_value'), suffix=item.get('suffix') or '')}; target {_metric_display(item.get('target'), suffix=item.get('suffix') or '')}"
                for item in failed_kpis
            ],
        })

    unresolved = _unresolved_issues(issue_progression)
    if unresolved:
        insights.append({
            "title": "Final watchouts remain",
            "section_name": "Detailed Issue Progression",
            "impact": "high" if conclusion in {"Hold for fix validation", "Run another round"} else "medium",
            "sentiment": "mixed",
            "explanation": "Some issue evidence remains active in the final saved round report.",
            "evidence": [
                f"{issue.get('issue_name')} — {issue.get('status')}"
                for issue in unresolved[:5]
            ],
        })

    return insights


def generate_project_report(*, project_key: str, generated_by_user_id: str) -> dict:
    """
    Generate a DB-backed project-level report from saved published report JSON.

    Source report JSON is the analytical source of truth. Raw answer-row counts
    remain audit metadata only.
    """

    safe_project_key = _clean_text(project_key)
    if not safe_project_key:
        return {"success": False, "error": "missing_project_key", "report": None}

    try:
        reports = list_reporting_project_source_reports_for_generation(
            project_key=safe_project_key
        )
    except Exception as exc:
        return {
            "success": False,
            "error": f"source_report_lookup_failed__{_safe_error_key(exc)}",
            "report": None,
        }

    if not reports:
        return {"success": False, "error": "project_not_found", "report": None}

    reports = sorted(reports, key=_report_sort_key)
    representative = reports[0]

    source_reports = [
        _source_report_audit_row(report, fallback_round_number=index)
        for index, report in enumerate(reports, start=1)
    ]

    analytical_reports = [
        report for report in reports
        if isinstance(report.get("source_report_json"), dict)
        and report.get("source_report_json")
    ]
    analytical_reports = sorted(analytical_reports, key=_report_sort_key)

    validation_kpi_reports = [
        report for report in reports
        if not report.get("source_report_json")
        and report.get("has_validation_kpis")
    ]
    validation_kpi_reports = sorted(validation_kpi_reports, key=_report_sort_key)

    kpi_source_reports = sorted(
        analytical_reports + validation_kpi_reports,
        key=_report_sort_key,
    )

    total_surveys = sum(item["survey_count"] for item in source_reports)
    total_datasets = sum(item["dataset_count"] for item in source_reports)
    total_responses = sum(item["response_count"] for item in source_reports)
    total_answers = sum(item["answer_count"] for item in source_reports)

    project_label = _format_project_label(representative)
    target_profile = _target_profile_for_project(representative)
    kpi_definitions = _kpi_definitions_for_target_profile(target_profile)

    kpi_progression = _build_kpi_progression(
        kpi_source_reports,
        kpi_definitions=kpi_definitions,
    )
    issue_progression = _build_issue_progression(analytical_reports)

    validation_kpi_source_summaries = _validation_kpi_source_summaries(source_reports)
    audit_only_source_summaries = _audit_only_source_summaries(source_reports)

    issue_progression = _apply_validation_outcomes_to_issue_progression(
        issue_progression,
        validation_kpi_sources=validation_kpi_source_summaries,
        kpi_definitions=kpi_definitions,
    )

    conclusion = _checkpoint_conclusion(
        analytical_report_count=len(analytical_reports),
        kpi_progression=kpi_progression,
        issue_progression=issue_progression,
    )

    next_action = _next_action_for_conclusion(
        conclusion,
        validation_kpi_source_count=len(validation_kpi_source_summaries),
    )

    sections = []
    sections.extend(_build_kpi_progression_sections(kpi_progression))
    sections.extend(
        _build_round_reason_sections(
            analytical_reports=analytical_reports,
            issue_progression=issue_progression,
        )
    )
    sections.extend(
        _build_validation_kpi_source_sections(
            validation_kpi_source_summaries,
            kpi_definitions=kpi_definitions,
        )
    )
    sections.extend(_build_issue_progression_sections(issue_progression))

    summary = {
        "executive_summary": _build_executive_summary(
            project_label=project_label,
            conclusion=conclusion,
            analytical_report_count=len(analytical_reports),
            source_reports=source_reports,
            kpi_progression=kpi_progression,
            issue_progression=issue_progression,
        ),
        "checkpoint_conclusion": conclusion,
        "next_action": next_action,
        "source_report_count": len(source_reports),
        "analytical_source_report_count": len(analytical_reports),
        "validation_kpi_source_count": len(validation_kpi_source_summaries),
        "kpi_source_report_count": len(kpi_source_reports),
        "audit_only_source_count": len(audit_only_source_summaries),
        "survey_count": total_surveys,
        "dataset_count": total_datasets,
        "response_count": total_responses,
        "answer_count": total_answers,
        "issue_count": len(issue_progression),
        "final_watchout_count": len(_unresolved_issues(issue_progression)),
        "kpi_target_tier": target_profile.get("target_tier"),
        "kpi_target_label": target_profile.get("target_label"),
        "kpi_targets": target_profile.get("targets"),
    }

    input_payload = {
        "project_key": safe_project_key,
        "generation_source": "saved_source_report_json_and_validation_kpis",
        "source_reports": source_reports,
        "validation_kpi_sources": validation_kpi_source_summaries,
        "target_profile": target_profile,
        "kpi_progression": kpi_progression,
        "issue_progression": issue_progression,
    }
    data_hash = _data_hash(input_payload)

    report = {
        "metadata": {
            "version": GENERATION_VERSION,
            "generation_mode": "deterministic_project_synthesis_from_saved_source_json_and_validation_kpis",
            "project_key": safe_project_key,
            "target_profile": target_profile,
            "data_hash": data_hash,
        },
        "product": {
            "project_label": project_label,
            "internal_name": _clean_text(representative.get("internal_name")),
            "market_name": _clean_text(representative.get("market_name")),
            "product_type_display": _clean_text(representative.get("product_type_display")),
            "business_group": _clean_text(representative.get("business_group")),
            "target_tier": target_profile.get("target_tier"),
            "target_label": target_profile.get("target_label"),
        },
        "summary": summary,
        "kpis": _final_kpis_from_saved_report(
            analytical_reports=analytical_reports,
            kpi_progression=kpi_progression,
        ),
        "target_profile": target_profile,
        "kpi_progression": kpi_progression,
        "issue_progression": issue_progression,
        "validation_kpi_sources": validation_kpi_source_summaries,
        "audit_only_sources": audit_only_source_summaries,
        "final_recommendation": {
            "conclusion": conclusion,
            "remaining_risks": [
                issue.get("issue_name")
                for issue in _unresolved_issues(issue_progression)[:5]
                if issue.get("issue_name")
            ],
            "accepted_watchouts": [
                issue.get("issue_name")
                for issue in issue_progression
                if issue.get("status") in {"improved", "persistent"}
                and issue.get("issue_name")
            ][:5],
            "validation_kpi_sources": validation_kpi_source_summaries,
            "audit_only_sources": audit_only_source_summaries,
            "next_action": next_action,
        },
        "source_surveys": _source_surveys_from_audit_rows(source_reports),
        "source_reports": source_reports,
        "insights": _build_project_insights(
            conclusion=conclusion,
            next_action=next_action,
            kpi_progression=kpi_progression,
            issue_progression=issue_progression,
            validation_kpi_sources=validation_kpi_source_summaries,
        ),
        "sections": sections,
    }

    included_report_keys = [
        item["report_key"]
        for item in source_reports
        if item.get("report_key")
    ]

    try:
        upsert_reporting_project_report(
            project_key=safe_project_key,
            project_source="mixed",
            project_label=project_label,
            internal_name=_clean_text(representative.get("internal_name")),
            market_name=_clean_text(representative.get("market_name")),
            product_type_display=_clean_text(representative.get("product_type_display")),
            business_group=_clean_text(representative.get("business_group")),
            report=report,
            input_payload=input_payload,
            included_report_keys=included_report_keys,
            generated_by_user_id=generated_by_user_id,
            generation_version=GENERATION_VERSION,
            data_hash=data_hash,
        )
    except ReportingProjectReportsTableMissing:
        return {"success": False, "error": "table_missing", "report": None}
    except Exception as exc:
        return {
            "success": False,
            "error": f"generation_failed__{_safe_error_key(exc)}",
            "report": None,
        }

    return {"success": True, "error": None, "report": report}