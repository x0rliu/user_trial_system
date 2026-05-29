# app/services/project_report_service.py

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal

from app.db.reporting_project_reports import (
    ReportingProjectReportsTableMissing,
    upsert_reporting_project_report,
)

GENERATION_VERSION = "reporting_project_report_v1"


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

def generate_project_report(*, project_key: str, generated_by_user_id: str) -> dict:
    """
    Generate a DB-backed project-level report from published round/survey reports.
    """

    safe_project_key = _clean_text(project_key)
    if not safe_project_key:
        return {"success": False, "error": "missing_project_key", "report": None}

    reports = _published_reports_for_project(safe_project_key)
    if not reports:
        return {"success": False, "error": "project_not_found", "report": None}

    reports = sorted(reports, key=_report_sort_key)
    representative = reports[0]

    source_reports = []
    for report in reports:
        source_reports.append({
            "report_key": _clean_text(report.get("report_key")),
            "report_source": _clean_text(report.get("report_source")),
            "report_source_label": _clean_text(report.get("report_source_label")),
            "report_scope": _clean_text(report.get("report_scope")),
            "report_href": _clean_text(report.get("report_href")),
            "round_number": report.get("round_number"),
            "survey_count": int(report.get("survey_count") or 0),
            "dataset_count": int(report.get("dataset_count") or 0),
            "response_count": int(report.get("response_count") or 0),
            "answer_count": int(report.get("answer_count") or 0),
            "published_at": str(report.get("published_at") or ""),
            "updated_at": str(report.get("updated_at") or ""),
        })

    input_payload = {
        "project_key": safe_project_key,
        "source_reports": source_reports,
    }
    data_hash = _data_hash(input_payload)

    total_surveys = sum(item["survey_count"] for item in source_reports)
    total_datasets = sum(item["dataset_count"] for item in source_reports)
    total_responses = sum(item["response_count"] for item in source_reports)
    total_answers = sum(item["answer_count"] for item in source_reports)
    project_label = _format_project_label(representative)
    source_report_sections = [
        _source_report_section(source_report)
        for source_report in source_reports
    ]

    report = {
        "metadata": {
            "version": GENERATION_VERSION,
            "generation_mode": "deterministic_project_rollup_with_source_sections",
            "project_key": safe_project_key,
            "data_hash": data_hash,
        },
        "product": {
            "project_label": project_label,
            "internal_name": _clean_text(representative.get("internal_name")),
            "market_name": _clean_text(representative.get("market_name")),
            "product_type_display": _clean_text(representative.get("product_type_display")),
            "business_group": _clean_text(representative.get("business_group")),
        },
        "summary": {
            "executive_summary": (
                f"{project_label} currently has {len(source_reports)} published round-level report"
                f"{'s' if len(source_reports) != 1 else ''} in Reporting & Insights, covering "
                f"{total_surveys} survey{'s' if total_surveys != 1 else ''} and "
                f"{total_datasets} dataset{'s' if total_datasets != 1 else ''}. "
                "This first project-level report is a structured rollup of the published source reports; "
                "deeper cross-round synthesis can be layered on after the project report object model is stable."
            ),
            "source_report_count": len(source_reports),
            "survey_count": total_surveys,
            "dataset_count": total_datasets,
            "response_count": total_responses,
            "answer_count": total_answers,
        },
        "source_reports": source_reports,
        "insights": [],
        "sections": source_report_sections,
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