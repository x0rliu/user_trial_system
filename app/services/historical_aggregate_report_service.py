# app/services/historical_aggregate_report_service.py

from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from app.db.connection import get_db_connection
from app.db.historical_aggregate_reports import upsert_historical_aggregate_report


REPORT_VERSION = "historical_aggregate_report_v1"


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


def _normal_section_name(*, section: dict, section_index: int, saved_names: dict) -> str:
    saved_name = saved_names.get(section_index)
    if saved_name:
        return str(saved_name)

    existing = section.get("section_name")
    if existing:
        return str(existing)

    return f"Section {section_index}"


def _build_aggregate_report(*, product_id: int, round_number: int, source_rows: list[dict], data_hash: str) -> dict:
    from app.db.historical import get_latest_insights_by_context, get_section_names, get_section_summaries
    from app.handlers.historical import build_sections_from_rows

    first_row = source_rows[0]
    rows_by_dataset: dict[int, list[dict]] = defaultdict(list)

    for row in source_rows:
        rows_by_dataset[int(row.get("dataset_id"))].append(row)

    source_surveys = []
    aggregate_sections = []
    aggregate_insights = []

    total_answers = 0
    response_ids = set()

    for dataset_id, dataset_rows in rows_by_dataset.items():
        dataset_rows = sorted(
            dataset_rows,
            key=lambda row: (
                row.get("question_position") or 0,
                str(row.get("response_group_id") or ""),
                row.get("answer_id") or 0,
            ),
        )

        context_id = int(dataset_rows[0].get("context_id"))
        dataset_name = dataset_rows[0].get("dataset_type") or "Untitled survey"
        trial_purpose = dataset_rows[0].get("trial_purpose") or ""
        lifecycle_stage = dataset_rows[0].get("lifecycle_stage") or ""

        dataset_response_ids = {
            str(row.get("response_group_id"))
            for row in dataset_rows
            if row.get("response_group_id") not in (None, "")
        }
        response_ids.update(f"{dataset_id}:{response_id}" for response_id in dataset_response_ids)
        total_answers += len(dataset_rows)

        source_surveys.append({
            "context_id": context_id,
            "dataset_id": dataset_id,
            "survey_name": dataset_name,
            "trial_purpose": trial_purpose,
            "lifecycle_stage": lifecycle_stage,
            "response_count": len(dataset_response_ids),
            "answer_count": len(dataset_rows),
            "source_file_name": dataset_rows[0].get("source_file_name") or "",
        })

        saved_names = get_section_names(dataset_id)
        saved_summaries = get_section_summaries(dataset_id)
        sections = build_sections_from_rows(dataset_rows)

        for section_index, section in enumerate(sections, start=1):
            section_name = _normal_section_name(
                section=section,
                section_index=section_index,
                saved_names=saved_names,
            )
            summary_json = saved_summaries.get(section_index)

            aggregate_sections.append({
                "context_id": context_id,
                "dataset_id": dataset_id,
                "survey_name": dataset_name,
                "trial_purpose": trial_purpose,
                "lifecycle_stage": lifecycle_stage,
                "section_index": len(aggregate_sections) + 1,
                "source_section_index": section_index,
                "section_name": section_name,
                "quant_questions": section.get("quant_questions") or [],
                "qual_question": section.get("qual_question"),
                "summary_json": summary_json,
            })

        for insight in get_latest_insights_by_context(context_id) or []:
            aggregate_insights.append({
                "context_id": context_id,
                "dataset_id": dataset_id,
                "survey_name": dataset_name,
                "section_name": insight.get("section_name"),
                "insight_type": insight.get("insight_type"),
                "insight_summary": insight.get("insight_summary"),
                "insight_json": insight.get("insight_json"),
                "source_sample_size": insight.get("source_sample_size"),
            })

    return {
        "metadata": {
            "version": REPORT_VERSION,
            "generation_mode": "legacy_round_aggregate",
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
            "response_count": len(response_ids),
            "answer_count": total_answers,
            "survey_count": len(source_surveys),
            "section_count": len(aggregate_sections),
            "insight_count": len(aggregate_insights),
        },
        "source_surveys": source_surveys,
        "sections": aggregate_sections,
        "insights": aggregate_insights,
    }


def generate_historical_aggregate_report(*, product_id: int, round_number: int, generated_by_user_id: str) -> dict:
    """
    Build and persist the aggregate report for one legacy project round.

    This POST-only service combines all uploaded survey datasets for a product + round.
    It does not mutate source survey answers or individual survey reports.
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