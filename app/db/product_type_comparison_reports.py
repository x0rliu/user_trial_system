# app/db/product_type_comparison_reports.py

from __future__ import annotations

import json

import mysql.connector
from mysql.connector import errorcode

from app.config.config import DB_CONFIG


class ProductTypeComparisonReportsTableMissing(RuntimeError):
    """Raised when the DB migration for product_type_comparison_reports has not been applied."""


def _is_missing_table_error(exc: Exception) -> bool:
    return isinstance(exc, mysql.connector.Error) and exc.errno == errorcode.ER_NO_SUCH_TABLE

def _is_missing_column_error(exc: Exception) -> bool:
    return isinstance(exc, mysql.connector.Error) and exc.errno == errorcode.ER_BAD_FIELD_ERROR

def _loads_json(value: object, fallback):
    try:
        parsed = json.loads(value or "")
        return parsed if parsed is not None else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _legacy_survey_insights_for_context(cur, context_id: int) -> list[dict]:
    """
    Return the latest AI insight rows for one published historical single-survey report.
    """

    cur.execute(
        """
        SELECT MAX(insight_run_id) AS latest_ai_run_id
        FROM historical_insight_runs
        WHERE context_id = %s
          AND trigger_type LIKE '%%ai%%'
        """,
        (int(context_id),),
    )
    latest = cur.fetchone() or {}
    latest_ai_run_id = latest.get("latest_ai_run_id")

    if latest_ai_run_id:
        cur.execute(
            """
            SELECT
                section_name,
                insight_type,
                insight_summary,
                insight_json,
                source_sample_size
            FROM historical_trial_insights
            WHERE context_id = %s
              AND insight_run_id = %s
            ORDER BY id ASC
            """,
            (int(context_id), int(latest_ai_run_id)),
        )
        return cur.fetchall()

    cur.execute(
        """
        SELECT
            section_name,
            insight_type,
            insight_summary,
            insight_json,
            source_sample_size
        FROM historical_trial_insights
        WHERE context_id = %s
        ORDER BY id ASC
        """,
        (int(context_id),),
    )
    return cur.fetchall()


def _legacy_survey_report_json(row: dict, insight_rows: list[dict]) -> str:
    """
    Adapt a published historical single-survey report into the same structured
    JSON shape used by aggregate reports. This intentionally uses stored
    report/insight outputs, not raw comments.
    """

    insights = []
    sections = []
    summary_text = ""

    for insight_row in insight_rows or []:
        insight_type = _clean_text(insight_row.get("insight_type"))
        payload = _loads_json(insight_row.get("insight_json"), {})
        if not isinstance(payload, dict):
            payload = {}

        if insight_type == "ai_summary" and not summary_text:
            summary_text = _clean_text(payload.get("summary") or insight_row.get("insight_summary"))
            continue

        if insight_type not in {"ai_insight", "canonical_ai_insight"}:
            continue

        title = _clean_text(payload.get("title") or insight_row.get("insight_summary"))
        explanation = _clean_text(payload.get("explanation") or payload.get("summary"))
        evidence = payload.get("evidence") if isinstance(payload.get("evidence"), list) else []
        sentiment = _clean_text(payload.get("sentiment"))
        impact = _clean_text(payload.get("impact"))
        section_name = _clean_text(insight_row.get("section_name")) or "Overall"

        insight = {
            "section_name": section_name,
            "title": title,
            "explanation": explanation,
            "evidence": [_clean_text(item) for item in evidence[:5] if _clean_text(item)],
            "impact": impact,
            "sentiment": sentiment,
        }
        insights.append(insight)

        swot = {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}
        if sentiment.lower() == "positive":
            swot["strengths"].append(title)
        elif sentiment.lower() == "negative":
            swot["weaknesses"].append(title)
        elif sentiment.lower() == "mixed":
            swot["opportunities"].append(title)
        elif title:
            swot["opportunities"].append(title)

        sections.append({
            "section_name": title or section_name,
            "survey_name": _clean_text(row.get("dataset_type")),
            "trial_purpose": _clean_text(row.get("trial_purpose")),
            "dataset_id": row.get("dataset_id"),
            "context_id": row.get("context_id"),
            "response_count": int(row.get("response_count") or 0),
            "quant_questions": [],
            "qual_question": {},
            "swot": swot,
            "section_analysis": {
                "key_findings": [item for item in [title, explanation] if item],
                "evidence": insight["evidence"],
            },
        })

    if not summary_text:
        summary_text = (
            f"{_clean_text(row.get('internal_name')) or 'This product'} Round {row.get('round_number') or '-'} "
            f"has one published historical survey report with {int(row.get('response_count') or 0)} response(s)."
        )

    report = {
        "metadata": {
            "version": "legacy_survey_report_adapter_v1",
            "generation_mode": "published_single_survey_report_adapter",
            "context_id": row.get("context_id"),
            "dataset_id": row.get("dataset_id"),
            "report_source": "legacy_survey",
        },
        "product": {
            "product_id": row.get("product_id"),
            "internal_name": _clean_text(row.get("internal_name")),
            "market_name": _clean_text(row.get("market_name")),
            "product_type_display": _clean_text(row.get("product_type_display")),
            "business_group": _clean_text(row.get("business_group")),
            "round_number": row.get("round_number"),
        },
        "summary": {
            "executive_summary": summary_text,
            "response_count": int(row.get("response_count") or 0),
            "answer_count": int(row.get("answer_count") or 0),
            "survey_count": 1,
            "section_count": len(sections),
            "insight_count": len(insights),
        },
        "kpis": {},
        "source_surveys": [
            {
                "survey_name": _clean_text(row.get("dataset_type")),
                "trial_purpose": _clean_text(row.get("trial_purpose")),
                "source_file_name": _clean_text(row.get("source_file_name")),
                "dataset_id": row.get("dataset_id"),
                "response_count": int(row.get("response_count") or 0),
                "question_count": None,
            }
        ],
        "sections": sections,
        "insights": insights,
    }

    return json.dumps(report, ensure_ascii=False, default=str)


def _attach_legacy_survey_report_jsons(cur, rows: list[dict]) -> None:
    for row in rows:
        if row.get("report_source") != "legacy_survey":
            continue
        context_id = row.get("context_id")
        if context_id in (None, ""):
            row["report_json"] = json.dumps({}, ensure_ascii=False)
            continue
        row["report_json"] = _legacy_survey_report_json(
            row,
            _legacy_survey_insights_for_context(cur, int(context_id)),
        )


def list_latest_product_type_comparison_reports() -> list[dict]:
    """
    Return saved product-type comparison report status rows for the R&I hub.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                comparison_report_id,
                product_type_key,
                product_type_display,
                generation_version,
                data_hash,
                generated_by_user_id,
                created_at,
                updated_at
            FROM product_type_comparison_reports
            ORDER BY updated_at DESC, product_type_display ASC
            """
        )
        return cur.fetchall()

    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise

    finally:
        cur.close()
        conn.close()


def get_latest_product_type_comparison_report(*, product_type_display: str) -> dict:
    """
    Read the saved comparison report for one product type.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                comparison_report_id,
                product_type_key,
                product_type_display,
                comparison_report_json,
                input_payload_json,
                included_report_keys_json,
                generated_by_user_id,
                generation_version,
                data_hash,
                created_at,
                updated_at
            FROM product_type_comparison_reports
            WHERE LOWER(product_type_display) = LOWER(%s)
            LIMIT 1
            """,
            (str(product_type_display or "").strip(),),
        )

        row = cur.fetchone()
        if not row:
            return {
                "success": False,
                "report": None,
                "input_payload": None,
                "row": None,
                "error": "not_found",
            }

        report = _loads_json(row.get("comparison_report_json"), {})
        if not isinstance(report, dict):
            return {
                "success": False,
                "report": None,
                "input_payload": None,
                "row": row,
                "error": "invalid_report_json",
            }

        input_payload = _loads_json(row.get("input_payload_json"), {})
        included_report_keys = _loads_json(row.get("included_report_keys_json"), [])

        report.setdefault("metadata", {})
        report["metadata"].update({
            "comparison_report_id": row.get("comparison_report_id"),
            "product_type_key": row.get("product_type_key"),
            "product_type_display": row.get("product_type_display"),
            "generated_by_user_id": row.get("generated_by_user_id"),
            "generation_version": row.get("generation_version"),
            "data_hash": row.get("data_hash"),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
        })

        return {
            "success": True,
            "report": report,
            "input_payload": input_payload if isinstance(input_payload, dict) else {},
            "included_report_keys": included_report_keys if isinstance(included_report_keys, list) else [],
            "row": row,
            "error": None,
        }

    except Exception as exc:
        if _is_missing_table_error(exc):
            return {
                "success": False,
                "report": None,
                "input_payload": None,
                "row": None,
                "error": "table_missing",
            }
        raise

    finally:
        cur.close()
        conn.close()


def list_published_report_objects_for_product_type(*, product_type_display: str) -> list[dict]:
    """
    Return published R&I report objects for a product type, including report_json.

    Historical and Product Trial reports are both published report objects once
    they are explicitly exposed to Reporting & Insights.
    """

    safe_product_type = str(product_type_display or "").strip()

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                CONCAT('legacy_round:', har.product_id, ':', har.round_number) AS report_key,
                'legacy' AS report_source,
                'Legacy' AS report_source_label,
                'aggregate_round' AS report_scope,

                hrp.publication_id,
                hrp.published_at,
                hrp.updated_at AS publication_updated_at,

                har.aggregate_report_id,
                har.product_id,
                har.round_number,
                har.report_json,
                har.data_hash,
                har.updated_at AS report_updated_at,

                p.internal_name,
                p.market_name,
                p.product_type_key,
                p.product_type_display,
                p.business_group

            FROM historical_report_publications hrp
            JOIN historical_aggregate_reports har
                ON har.product_id = hrp.product_id
               AND har.round_number = hrp.round_number
            JOIN products p
                ON p.product_id = har.product_id

            WHERE hrp.publication_scope = 'round'
              AND hrp.status = 'published'
              AND hrp.visible_to_reporting_insights = 1
              AND LOWER(p.product_type_display) = LOWER(%s)

            ORDER BY
                hrp.published_at DESC,
                p.internal_name ASC,
                p.market_name ASC,
                har.round_number ASC
            """,
            (safe_product_type,),
        )
        rows = cur.fetchall()

        try:
            cur.execute(
                """
                SELECT
                    CONCAT('product_trial_round:', ptr.project_id, ':', ptr.round_id) AS report_key,
                    'product_trial' AS report_source,
                    'Product Trial' AS report_source_label,
                    'product_trial_round' AS report_scope,

                    NULL AS publication_id,
                    ptr.published_at,
                    ptr.updated_at AS publication_updated_at,

                    ptr.report_id AS aggregate_report_id,
                    ptr.project_id,
                    ptr.round_id,
                    pr.RoundNumber AS round_number,
                    ptr.report_json,
                    ptr.data_hash,
                    ptr.updated_at AS report_updated_at,

                    pp.ProjectName AS internal_name,
                    pp.MarketName AS market_name,
                    LOWER(REPLACE(pp.ProductType, ' ', '_')) AS product_type_key,
                    pp.ProductType AS product_type_display,
                    pp.BusinessGroup AS business_group

                FROM product_trial_reports ptr
                JOIN project_rounds pr
                    ON pr.RoundID = ptr.round_id
                JOIN project_projects pp
                    ON pp.ProjectID = ptr.project_id

                WHERE ptr.publication_status = 'published'
                  AND ptr.visible_to_reporting_insights = 1
                  AND LOWER(pp.ProductType) = LOWER(%s)

                ORDER BY
                    ptr.published_at DESC,
                    pp.ProjectName ASC,
                    pp.MarketName ASC,
                    pr.RoundNumber ASC
                """,
                (safe_product_type,),
            )
            rows.extend(cur.fetchall())
        except Exception as exc:
            if not (_is_missing_table_error(exc) or _is_missing_column_error(exc)):
                raise

        try:
            cur.execute(
                """
                SELECT
                    CONCAT('legacy_survey:', hc.context_id) AS report_key,
                    'legacy_survey' AS report_source,
                    'Legacy Survey' AS report_source_label,
                    'survey' AS report_scope,

                    hrp.publication_id,
                    hrp.published_at,
                    hrp.updated_at AS publication_updated_at,

                    NULL AS aggregate_report_id,
                    hc.product_id,
                    COALESCE(hc.round_number, hd.round_number) AS round_number,
                    hc.context_id,
                    hd.dataset_id,
                    hd.dataset_type,
                    hd.source_file_name,
                    NULL AS report_json,
                    NULL AS data_hash,
                    hrp.updated_at AS report_updated_at,

                    p.internal_name,
                    p.market_name,
                    p.product_type_key,
                    p.product_type_display,
                    p.business_group,
                    hc.trial_purpose,

                    COUNT(ha.id) AS answer_count,
                    COUNT(DISTINCT ha.response_group_id) AS response_count

                FROM historical_report_publications hrp
                JOIN historical_trial_contexts hc
                    ON hc.context_id = hrp.context_id
                JOIN historical_datasets hd
                    ON hd.context_id = hc.context_id
                JOIN products p
                    ON p.product_id = hc.product_id
                LEFT JOIN historical_survey_answers ha
                    ON ha.dataset_id = hd.dataset_id

                WHERE hrp.publication_scope = 'survey'
                  AND hrp.status = 'published'
                  AND hrp.visible_to_reporting_insights = 1
                  AND LOWER(p.product_type_display) = LOWER(%s)

                GROUP BY
                    hrp.publication_id,
                    hrp.published_at,
                    hrp.updated_at,
                    hc.product_id,
                    hc.round_number,
                    hc.context_id,
                    hd.round_number,
                    hd.dataset_id,
                    hd.dataset_type,
                    hd.source_file_name,
                    p.internal_name,
                    p.market_name,
                    p.product_type_key,
                    p.product_type_display,
                    p.business_group,
                    hc.trial_purpose

                ORDER BY
                    hrp.published_at DESC,
                    p.internal_name ASC,
                    p.market_name ASC,
                    round_number ASC
                """,
                (safe_product_type,),
            )
            survey_rows = cur.fetchall()
            _attach_legacy_survey_report_jsons(cur, survey_rows)
            rows.extend(survey_rows)
        except Exception as exc:
            if not (_is_missing_table_error(exc) or _is_missing_column_error(exc)):
                raise

        return rows

    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise

    finally:
        cur.close()
        conn.close()


def upsert_product_type_comparison_report(
    *,
    product_type_key: str,
    product_type_display: str,
    report: dict,
    input_payload: dict,
    included_report_keys: list[str],
    generated_by_user_id: str,
    generation_version: str,
    data_hash: str | None,
) -> None:
    """
    Save or replace the generated product-type comparison report.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO product_type_comparison_reports (
                product_type_key,
                product_type_display,
                comparison_report_json,
                input_payload_json,
                included_report_keys_json,
                generated_by_user_id,
                generation_version,
                data_hash
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                product_type_display = VALUES(product_type_display),
                comparison_report_json = VALUES(comparison_report_json),
                input_payload_json = VALUES(input_payload_json),
                included_report_keys_json = VALUES(included_report_keys_json),
                generated_by_user_id = VALUES(generated_by_user_id),
                generation_version = VALUES(generation_version),
                data_hash = VALUES(data_hash),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                str(product_type_key or "").strip().lower(),
                str(product_type_display or "").strip(),
                json.dumps(report, ensure_ascii=False, default=str),
                json.dumps(input_payload, ensure_ascii=False, default=str),
                json.dumps(included_report_keys, ensure_ascii=False, default=str),
                generated_by_user_id,
                generation_version,
                data_hash,
            ),
        )
        conn.commit()

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            raise ProductTypeComparisonReportsTableMissing(
                "product_type_comparison_reports table does not exist"
            ) from exc
        raise

    finally:
        cur.close()
        conn.close()