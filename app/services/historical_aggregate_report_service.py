# app/services/historical_aggregate_report_service.py

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from decimal import Decimal

from app.db.connection import get_db_connection
from app.db.historical_aggregate_reports import upsert_historical_aggregate_report
from app.db.survey_kpis import calculate_product_kpis_from_answer_rows
from app.services.product_trial_report_service import (
    _apply_historical_ai_outputs,
    _build_historical_style_sections,
)


REPORT_VERSION = "historical_aggregate_report_product_clone_v1"

_SURVEY_1_EXCLUDED_KPI_TYPE_ID = "UTSurveyType1001"


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _to_float(value: object) -> float | None:
    text = _normalize_text(value)
    if not text:
        return None

    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _answer_value(row: dict) -> str:
    for key in ("answer_text", "answer_option", "answer_numeric"):
        value = row.get(key)
        if value not in (None, ""):
            return _normalize_text(value)
    return ""


def _answer_numeric(row: dict) -> float | None:
    numeric = _to_float(row.get("answer_numeric"))
    if numeric is not None:
        return numeric

    numeric = _to_float(row.get("answer_option"))
    if numeric is not None:
        return numeric

    return _to_float(row.get("answer_text"))


def _dataset_sort_value(value: object) -> tuple[int, str]:
    try:
        return (0, f"{int(value):012d}")
    except (TypeError, ValueError):
        return (1, str(value or ""))


def _survey_type_id_for_dataset(dataset_id: object) -> str:
    return f"legacy_dataset_{_normalize_text(dataset_id)}"


def _is_survey_one_name(value: object) -> bool:
    text = _normalize_text(value).lower()
    if not text:
        return False

    return (
        "survey 1" in text
        or "first impression" in text
        or "first impressions" in text
        or "oobe" in text
        or "out of box" in text
        or "out-of-box" in text
    )


def _build_dataset_metadata(source_rows: list[dict]) -> dict[str, dict]:
    metadata: dict[str, dict] = {}

    for row in source_rows or []:
        dataset_id = row.get("dataset_id")
        if dataset_id in (None, ""):
            continue

        survey_type_id = _survey_type_id_for_dataset(dataset_id)
        if survey_type_id in metadata:
            continue

        dataset_name = row.get("dataset_type") or "Untitled survey"
        context_id = row.get("context_id")

        metadata[survey_type_id] = {
            "survey_type_id": survey_type_id,
            "dataset_id": dataset_id,
            "context_id": context_id,
            "survey_name": dataset_name,
            "trial_purpose": row.get("trial_purpose") or "",
            "lifecycle_stage": row.get("lifecycle_stage") or "",
            "source_file_name": row.get("source_file_name") or "",
            "source_href": f"/historical/context?context_id={context_id}" if context_id else "",
            "is_survey_one": _is_survey_one_name(dataset_name) or _is_survey_one_name(row.get("trial_purpose")),
        }

    return metadata


def _build_distribution_id_map(source_rows: list[dict]) -> dict[tuple[str, str], int]:
    distribution_ids: dict[tuple[str, str], int] = {}
    next_distribution_id = 1

    for row in sorted(
        source_rows or [],
        key=lambda item: (
            _dataset_sort_value(item.get("dataset_id")),
            str(item.get("response_group_id") or ""),
            int(item.get("answer_id") or 0),
        ),
    ):
        dataset_key = str(row.get("dataset_id") or "unknown")
        response_key = str(row.get("response_group_id") or f"answer:{row.get('answer_id')}")
        key = (dataset_key, response_key)

        if key not in distribution_ids:
            distribution_ids[key] = next_distribution_id
            next_distribution_id += 1

    return distribution_ids


def _to_product_trial_answer_rows(*, source_rows: list[dict], kpi_mode: bool = False) -> list[dict]:
    """
    Convert historical upload rows into the same row contract used by the
    Product Trial report service.

    kpi_mode intentionally maps Survey 1 / first-impressions datasets to the
    same excluded SurveyTypeID used by current Product Trial KPI calculation.
    That makes legacy aggregate KPI math follow the same rules as Product Trial:
    Survey 1/OOBE ratings can still appear in sections, but they do not pollute
    project-level KPIs.
    """

    dataset_metadata = _build_dataset_metadata(source_rows)
    distribution_ids = _build_distribution_id_map(source_rows)
    answer_rows = []

    for row in source_rows or []:
        dataset_id = row.get("dataset_id")
        survey_type_id = _survey_type_id_for_dataset(dataset_id)
        metadata = dataset_metadata.get(survey_type_id) or {}

        if kpi_mode and metadata.get("is_survey_one"):
            row_survey_type_id = _SURVEY_1_EXCLUDED_KPI_TYPE_ID
        else:
            row_survey_type_id = survey_type_id

        dataset_key = str(dataset_id or "unknown")
        response_key = str(row.get("response_group_id") or f"answer:{row.get('answer_id')}")
        distribution_id = distribution_ids.get((dataset_key, response_key), 0)

        answer_rows.append({
            "AnswerID": int(row.get("answer_id") or 0),
            "SurveyID": int(dataset_id or 0) if str(dataset_id or "").isdigit() else dataset_id,
            "DistributionID": distribution_id,
            "user_id": None,
            "SurveyTypeID": row_survey_type_id,
            "SurveyTypeName": metadata.get("survey_name") or row.get("dataset_type") or "Survey",
            "QuestionID": row.get("question_hash"),
            "QuestionText": _normalize_text(row.get("question_text")) or "Untitled question",
            "QuestionPosition": int(row.get("question_position") or 0),
            "AnswerValue": _answer_value(row),
            "AnswerNumeric": _answer_numeric(row),
            "UpdatedAt": _json_safe(row.get("response_submitted_at")),
        })

    return sorted(
        answer_rows,
        key=lambda item: (
            str(item.get("SurveyTypeID") or ""),
            int(item.get("QuestionPosition") or 0),
            int(item.get("DistributionID") or 0),
            int(item.get("AnswerID") or 0),
        ),
    )


def _build_source_hash(rows: list[dict]) -> str:
    stable_rows = []
    for row in rows:
        stable_rows.append({
            "context_id": row.get("context_id"),
            "dataset_id": row.get("dataset_id"),
            "response_group_id": row.get("response_group_id"),
            "question_hash": row.get("question_hash"),
            "question_position": row.get("question_position"),
            "answer_text": row.get("answer_text"),
            "answer_numeric": str(row.get("answer_numeric")) if row.get("answer_numeric") is not None else None,
            "answer_option": row.get("answer_option"),
        })

    payload = json.dumps(stable_rows, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _get_aggregate_source_rows(*, product_id: int, round_number: int) -> list[dict]:
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                hc.context_id,
                hc.product_id,
                COALESCE(hc.round_number, hd.round_number) AS round_number,
                hc.lifecycle_stage,
                hc.trial_purpose,
                hc.created_at AS context_created_at,

                p.internal_name,
                p.market_name,
                p.product_type_display,
                p.business_group,

                hd.dataset_id,
                hd.dataset_type,
                hd.source_file_name,
                hd.created_at AS dataset_created_at,

                hsa.id AS answer_id,
                hsa.response_group_id,
                hsa.question_text,
                hsa.question_hash,
                hsa.question_position,
                hsa.answer_text,
                hsa.answer_numeric,
                hsa.answer_option,
                hsa.response_submitted_at,
                hsa.metadata_json

            FROM historical_trial_contexts hc
            JOIN products p
                ON p.product_id = hc.product_id
            JOIN historical_datasets hd
                ON hd.context_id = hc.context_id
            JOIN historical_survey_answers hsa
                ON hsa.dataset_id = hd.dataset_id

            WHERE hc.source = 'legacy'
              AND hc.product_id = %s
              AND COALESCE(hc.round_number, hd.round_number) = %s

            ORDER BY
                hc.created_at ASC,
                hc.context_id ASC,
                hd.dataset_id ASC,
                hsa.question_position ASC,
                hsa.response_group_id ASC,
                hsa.id ASC
            """,
            (int(product_id), int(round_number)),
        )

        return cur.fetchall()

    finally:
        cur.close()
        conn.close()


def _clean_source_surveys(*, source_surveys: list[dict], dataset_metadata: dict[str, dict]) -> list[dict]:
    cleaned = []

    for survey in source_surveys or []:
        survey_type_id = str(survey.get("survey_type_id") or "")
        metadata = dataset_metadata.get(survey_type_id) or {}

        cleaned.append({
            **survey,
            "dataset_id": metadata.get("dataset_id"),
            "context_id": metadata.get("context_id"),
            "survey_name": metadata.get("survey_name") or survey.get("survey_name") or "Survey",
            "trial_purpose": metadata.get("trial_purpose") or "",
            "lifecycle_stage": metadata.get("lifecycle_stage") or "",
            "source_file_name": metadata.get("source_file_name") or "",
            "source_href": metadata.get("source_href") or "",
        })

    return cleaned


def _clean_sections(*, sections: list[dict], dataset_metadata: dict[str, dict]) -> list[dict]:
    cleaned = []

    for section in sections or []:
        survey_type_id = str(section.get("survey_type_id") or "")
        metadata = dataset_metadata.get(survey_type_id) or {}
        updated = dict(section)

        updated["dataset_id"] = metadata.get("dataset_id")
        updated["context_id"] = metadata.get("context_id")
        updated["trial_purpose"] = metadata.get("trial_purpose") or ""
        updated["lifecycle_stage"] = metadata.get("lifecycle_stage") or ""
        updated["source_href"] = metadata.get("source_href") or ""

        cleaned.append(updated)

    return cleaned


def _build_executive_summary(*, source_surveys: list[dict], sections: list[dict], kpis: dict) -> str:
    # Match Product Trial report behavior for now: keep this blank until a
    # dedicated report-summary generation step creates real synthesis.
    return ""


def _build_aggregate_report(*, product_id: int, round_number: int, source_rows: list[dict], data_hash: str) -> dict:
    first_row = source_rows[0]
    dataset_metadata = _build_dataset_metadata(source_rows)

    section_answer_rows = _to_product_trial_answer_rows(
        source_rows=source_rows,
        kpi_mode=False,
    )
    source_surveys, sections = _build_historical_style_sections(section_answer_rows)

    source_surveys = _clean_source_surveys(
        source_surveys=source_surveys,
        dataset_metadata=dataset_metadata,
    )
    sections = _clean_sections(
        sections=sections,
        dataset_metadata=dataset_metadata,
    )

    kpi_answer_rows = _to_product_trial_answer_rows(
        source_rows=source_rows,
        kpi_mode=True,
    )
    kpis = calculate_product_kpis_from_answer_rows(kpi_answer_rows)

    total_responses = sum(int(survey.get("response_count") or 0) for survey in source_surveys)
    total_answers = sum(int(survey.get("answer_count") or 0) for survey in source_surveys)

    report = {
        "metadata": {
            "version": REPORT_VERSION,
            "generation_mode": "product_trial_report_clone",
            "data_hash": data_hash,
            "product_id": int(product_id),
            "round_number": int(round_number),
        },
        "product": {
            "product_id": int(product_id),
            "internal_name": first_row.get("internal_name"),
            "market_name": first_row.get("market_name"),
            "product_type_display": first_row.get("product_type_display"),
            "business_group": first_row.get("business_group"),
        },
        "summary": {
            "executive_summary": _build_executive_summary(
                source_surveys=source_surveys,
                sections=sections,
                kpis=kpis,
            ),
            "response_count": total_responses,
            "answer_count": total_answers,
            "survey_count": len(source_surveys),
            "section_count": len(sections),
            "insight_count": 0,
        },
        "kpis": kpis,
        "source_surveys": source_surveys,
        "sections": sections,
        "insights": [],
    }

    return _apply_historical_ai_outputs(report)


def generate_historical_aggregate_report(*, product_id: int, round_number: int, generated_by_user_id: str) -> dict:
    """
    Build and persist the aggregate report for one legacy product round.

    This POST-only service converts legacy historical rows into the same row
    contract used by Product Trial reports, then reuses the Product Trial report
    sectioning, KPI, and SWOT generation logic. It does not mutate source survey
    answers or individual survey reports.
    """

    source_rows = _get_aggregate_source_rows(
        product_id=int(product_id),
        round_number=int(round_number),
    )

    if not source_rows:
        return {
            "success": False,
            "error": "no_data",
            "report": None,
        }

    data_hash = _build_source_hash(source_rows)
    report = _build_aggregate_report(
        product_id=int(product_id),
        round_number=int(round_number),
        source_rows=source_rows,
        data_hash=data_hash,
    )

    upsert_historical_aggregate_report(
        product_id=int(product_id),
        round_number=int(round_number),
        report=report,
        generated_by_user_id=generated_by_user_id,
        generation_version=REPORT_VERSION,
        data_hash=data_hash,
    )

    return {
        "success": True,
        "error": None,
        "report": report,
    }