# app/handlers/historical.py

import json

from app.services.historical_ingestion import ingest_historical_csv
from app.utils.html_escape import escape_html as e
from app.utils.report_answer_values import split_countable_answer_value
from app.db.historical import get_latest_insights_by_context
from app.utils.csrf import generate_csrf_token
from app.utils.upload_security import require_csv_upload
from urllib.parse import urlencode
from app.services.upload_controls import render_csv_dropzone


def _historical_nav_item(label, href, active=False, disabled=False):
    active_class = " is-active" if active else ""

    if disabled:
        return f"""
            <span class="historical-subnav-item is-disabled">
                {e(label)}
            </span>
        """

    return f"""
        <a class="historical-subnav-item{active_class}" href="{e(href)}">
            {e(label)}
        </a>
    """


def _render_historical_subnav(active_key=None, context_id=None, dataset_id=None, product_id=None):
    safe_context_id = None
    safe_dataset_id = None
    safe_product_id = None

    try:
        safe_context_id = int(context_id) if context_id else None
    except (TypeError, ValueError):
        safe_context_id = None

    try:
        safe_dataset_id = int(dataset_id) if dataset_id else None
    except (TypeError, ValueError):
        safe_dataset_id = None

    try:
        safe_product_id = int(product_id) if product_id else None
    except (TypeError, ValueError):
        safe_product_id = None

    items = [
        _historical_nav_item(
            "Legacy Projects",
            "/historical",
            active=(active_key == "projects"),
        ),
        _historical_nav_item(
            "Create Context",
            "/historical/create-context",
            active=(active_key == "create"),
        ),
        _historical_nav_item(
            "Product Taxonomy",
            "/historical/product-taxonomy",
            active=(active_key == "taxonomy"),
        ),
    ]

    if safe_product_id:
        items.append(
            _historical_nav_item(
                "Product Lifecycle",
                f"/historical/product?product_id={safe_product_id}",
                active=(active_key == "product"),
            )
        )

    if safe_context_id:
        items.extend([
            _historical_nav_item(
                "Current Report",
                f"/historical/context?context_id={safe_context_id}",
                active=(active_key == "context"),
            ),
            _historical_nav_item(
                "Pattern Comparison",
                f"/historical/comparison?context_id={safe_context_id}",
                active=(active_key == "comparison"),
            ),
        ])

        if safe_dataset_id:
            items.append(
                _historical_nav_item(
                    "Raw Data",
                    f"/historical/raw?context_id={safe_context_id}&dataset_id={safe_dataset_id}",
                    active=(active_key == "raw"),
                )
            )

    return f"""
    <div class="historical-subnav" aria-label="Historical workflow navigation">
        {''.join(items)}
    </div>
    """


def _render_delete_draft_context_form(*, context_id, csrf_token, label="Delete Draft"):
    try:
        safe_context_id = int(context_id)
    except (TypeError, ValueError):
        return ""

    return f"""
        <form method="POST" action="/historical/context/delete" class="historical-inline-form"
            onsubmit="return confirm('Delete this draft round? This is only allowed before survey data has been uploaded.');">
            <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
            <input type="hidden" name="context_id" value="{e(str(safe_context_id))}">
            <button type="submit" class="historical-action-pill is-danger">{e(label)}</button>
        </form>
    """


def _can_access_historical_context(*, user_id, context_id) -> bool:
    if not user_id or not context_id:
        return False

    from app.db.user_roles import get_effective_permission_level
    from app.db.historical import (
        get_context_with_product,
        historical_context_is_visible_to_reporting_insights,
    )

    permission_level = get_effective_permission_level(user_id)

    if permission_level >= 70:
        return get_context_with_product(context_id) is not None

    if permission_level >= 50:
        return historical_context_is_visible_to_reporting_insights(context_id)

    return False


def _dataset_belongs_to_context(*, dataset_id, context_id) -> bool:
    if not dataset_id or not context_id:
        return False

    from app.db.historical import get_context_id_for_dataset

    dataset_context_id = get_context_id_for_dataset(dataset_id)
    if dataset_context_id is None:
        return False

    return int(dataset_context_id) == int(context_id)


def _historical_product_has_legacy_lifecycle(*, product_id) -> bool:
    """
    Confirm that a submitted product_id belongs to a real legacy lifecycle.

    Historical product publication/access actions should only operate on products
    that have legacy historical contexts, not on arbitrary product rows.
    """

    try:
        safe_product_id = int(product_id)
    except (TypeError, ValueError):
        return False

    from app.db.historical import get_legacy_product_lifecycle

    lifecycle = get_legacy_product_lifecycle(safe_product_id)
    if not lifecycle:
        return False

    return bool(lifecycle.get("rounds") or [])


def _historical_product_round_has_legacy_lifecycle(*, product_id, round_number) -> bool:
    """
    Confirm that a submitted product_id + round_number is a real legacy round.

    Aggregate report generation/publication should only operate on historical
    rounds that exist in the legacy lifecycle, not arbitrary product/round pairs.
    """

    try:
        safe_product_id = int(product_id)
        safe_round_number = int(round_number)
    except (TypeError, ValueError):
        return False

    from app.db.historical import get_legacy_product_lifecycle

    lifecycle = get_legacy_product_lifecycle(safe_product_id)
    if not lifecycle:
        return False

    for round_group in lifecycle.get("rounds") or []:
        try:
            lifecycle_round = int(round_group.get("round_number"))
        except (TypeError, ValueError):
            continue

        if lifecycle_round == safe_round_number:
            return True

    return False


def _validate_historical_aggregate_target(*, data):
    """
    Parse and validate a submitted historical aggregate product/round target.

    These values come from hidden form fields. Return the normalized target only
    when the pair exists as a real legacy historical lifecycle round.
    """

    product_id = _posted_int(data.get("product_id"))
    round_number = _posted_int(data.get("round_number"))

    if not product_id or not round_number:
        return None, None

    if not _historical_product_round_has_legacy_lifecycle(
        product_id=product_id,
        round_number=round_number,
    ):
        return None, None

    return product_id, round_number


def _posted_scalar(value):
    """Return the first submitted value from either flat or parse_qs-style data."""

    if isinstance(value, list):
        return value[0] if value else None

    return value


def _posted_int(value):
    """Safely parse an integer from flat or parse_qs-style submitted data."""

    value = _posted_scalar(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _validate_historical_context_dataset_target(*, user_id, data):
    """
    Validate a submitted context_id + dataset_id pair for historical actions.

    These IDs arrive from hidden form fields, so POST handlers must prove both
    that the user can access the context and that the dataset belongs to it.
    """

    context_id = _posted_int(data.get("context_id"))
    dataset_id = _posted_int(data.get("dataset_id"))

    if not context_id or not dataset_id:
        return None, None

    if not _can_access_historical_context(
        user_id=user_id,
        context_id=context_id,
    ):
        return None, None

    if not _dataset_belongs_to_context(
        dataset_id=dataset_id,
        context_id=context_id,
    ):
        return None, None

    return context_id, dataset_id


def _prepare_historical_upload_from_form(*, data, fallback_round_number=None):
    dataset_type = _posted_scalar(data.get("dataset_type"))
    file_item = data.get("file")
    round_number = _posted_int(data.get("upload_round_number"))

    dataset_type = str(dataset_type or "").split("\r\n")[0].strip()

    if round_number is None:
        round_number = fallback_round_number

    has_dataset_name = bool(dataset_type)
    has_file = bool(file_item and file_item.get("filename"))

    if not has_dataset_name and not has_file:
        return {"ok": True, "should_upload": False}

    if not has_dataset_name or not has_file:
        return {"ok": False, "error": "missing_upload_fields"}

    file_bytes = file_item.get("file")
    if not file_bytes:
        return {"ok": False, "error": "missing_upload_fields"}

    try:
        safe_filename = require_csv_upload(
            filename=file_item.get("filename"),
            file_bytes=file_bytes,
            content_type=file_item.get("content_type"),
        )
    except ValueError:
        return {"ok": False, "error": "invalid_file"}

    return {
        "ok": True,
        "should_upload": True,
        "dataset_type": dataset_type,
        "file_bytes": file_bytes,
        "safe_filename": safe_filename,
        "round_number": round_number,
    }


def _ingest_prepared_historical_upload(*, context_id, upload):
    from io import BytesIO

    ingest_historical_csv(
        context_id=context_id,
        dataset_type=upload["dataset_type"],
        file_obj=BytesIO(upload["file_bytes"]),
        filename=upload["safe_filename"],
        round_number=upload.get("round_number"),
    )

    if upload.get("round_number") is not None:
        from app.db.historical import update_context_round
        update_context_round(context_id, upload.get("round_number"))

from app.db.historical import (
    get_context_with_product,
    get_datasets_by_context,
    get_historical_metrics_by_context
)


def _clean_historical_report_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _historical_context_survey_type_id(*, context: dict, dataset: dict | None) -> str:
    label = " ".join([
        _clean_historical_report_text(context.get("trial_purpose")),
        _clean_historical_report_text((dataset or {}).get("dataset_type")),
    ]).lower()

    if any(marker in label for marker in ("first impression", "first impressions", "out of box", "oobe")):
        return "UTSurveyType1001"

    return f"HistoricalContext{context.get('context_id') or 'Unknown'}"


def _to_float_or_none_for_historical(value: object):
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _historical_rows_to_kpi_answer_rows(*, rows: list[dict], context: dict, dataset: dict | None) -> list[dict]:
    survey_type_id = _historical_context_survey_type_id(context=context, dataset=dataset)
    distribution_ids = {}
    next_distribution_id = 1
    answer_rows = []

    for row in sorted(rows or [], key=lambda item: (str(item.get("response_group_id") or ""), int(item.get("question_position") or 0))):
        response_key = str(row.get("response_group_id") or "")
        if response_key not in distribution_ids:
            distribution_ids[response_key] = next_distribution_id
            next_distribution_id += 1

        distribution_id = distribution_ids[response_key]
        question_position = int(row.get("question_position") or 0)
        answer_value = row.get("answer_text")
        answer_numeric = _to_float_or_none_for_historical(answer_value)

        answer_rows.append({
            "AnswerID": (distribution_id * 100000) + question_position,
            "SurveyID": (dataset or {}).get("dataset_id") or 0,
            "DistributionID": distribution_id,
            "user_id": None,
            "SurveyTypeID": survey_type_id,
            "QuestionText": _clean_historical_report_text(row.get("question_text")) or "Untitled question",
            "QuestionPosition": question_position,
            "AnswerValue": answer_value,
            "AnswerNumeric": answer_numeric,
        })

    return answer_rows


def _historical_profile_questions_for_canonical(profile_stats: dict) -> list[dict]:
    profile_questions = []

    for question, counts in (profile_stats or {}).items():
        if not counts:
            continue

        options = [
            {"label": label, "count": count}
            for label, count in sorted(
                counts.items(),
                key=lambda item: (-int(item[1] or 0), str(item[0]).lower()),
            )
        ]

        profile_questions.append({
            "question": _clean_historical_report_text(question) or "Profile question",
            "total_count": sum(int(option.get("count") or 0) for option in options),
            "options": options,
        })

    return profile_questions


def _historical_section_question_blob(section: dict) -> str:
    question_bits = []

    for question in section.get("quant_questions") or []:
        if isinstance(question, dict):
            question_bits.append(_clean_historical_report_text(question.get("question")))

    qual_question = section.get("qual_question")
    if isinstance(qual_question, dict):
        question_bits.append(_clean_historical_report_text(qual_question.get("question")))

    return " ".join(bit for bit in question_bits if bit).lower()


def _historical_section_is_kpi(section: dict) -> bool:
    question_blob = _historical_section_question_blob(section)
    if not question_blob:
        return False

    if "software rating" in question_blob:
        return True

    product_rating_patterns = (
        "overall, how would you rate this product",
        "overall how would you rate this product",
        "how would you rate this product on a scale",
        "rate this product on a scale",
        "rate this product",
    )
    if any(pattern in question_blob for pattern in product_rating_patterns) and "software" not in question_blob:
        return True

    if "star rating" in question_blob and "software" not in question_blob:
        return True

    has_recommendation_question = (
        "recommend this product" in question_blob
        and ("colleague" in question_blob or "friend" in question_blob)
    )
    if has_recommendation_question:
        return True

    readiness_markers = (
        "ready for sales",
        "ready for market",
        "ready for a market",
        "ready for market release",
        "ready to go to market",
        "ready for launch",
        "ready to launch",
        "functional hurdles",
    )
    if any(marker in question_blob for marker in readiness_markers):
        return True

    return False


def _historical_section_report_group(*, section: dict, survey_name: str) -> str:
    if _historical_section_is_kpi(section):
        return "KPIs"

    safe_survey_name = _clean_historical_report_text(survey_name).lower()
    question_blob = _historical_section_question_blob(section)

    if any(marker in question_blob for marker in (
        "box",
        "package",
        "packaging",
        "unbox",
        "unboxing",
        "component",
        "cable",
        "quick start",
    )):
        return "OOBE"

    if "survey 1" in safe_survey_name or "first impression" in safe_survey_name or "oobe" in safe_survey_name:
        return "First Impressions"

    if "survey 2" in safe_survey_name or "usage" in safe_survey_name or "experience" in safe_survey_name or "kpi" in safe_survey_name:
        return "Usage"

    return "Other"


def _historical_section_summary_payload(summary_text: object) -> dict:
    if isinstance(summary_text, dict):
        return summary_text

    raw = _clean_historical_report_text(summary_text)
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _historical_sections_for_canonical(*, sections: list[dict], section_names: dict, section_summaries: dict, survey_name: str) -> list[dict]:
    canonical_sections = []

    for index, section in enumerate(sections or [], start=1):
        summary_text = section_summaries.get(index)
        summary_payload = _historical_section_summary_payload(summary_text)
        comment_buckets = summary_payload.get("comment_buckets") if isinstance(summary_payload.get("comment_buckets"), list) else []

        canonical_sections.append({
            "section_name": section_names.get(index) or f"Section {index}",
            "survey_name": survey_name,
            "dataset_type": survey_name,
            "report_group": _historical_section_report_group(section=section, survey_name=survey_name),
            "summary_json": summary_text,
            "quant_questions": section.get("quant_questions") or [],
            "qual_question": section.get("qual_question"),
            "comment_buckets": comment_buckets,
        })

    return canonical_sections


def _historical_parse_insight_json(insight: dict) -> dict:
    raw_json = insight.get("insight_json") if isinstance(insight, dict) else None
    if not raw_json:
        return {}

    try:
        parsed = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError):
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _historical_normalized_insight_section_name(insight: dict, payload: dict) -> str:
    section_name = (
        _clean_historical_report_text(payload.get("section_name"))
        or _clean_historical_report_text(insight.get("section_name"))
    )

    if not section_name or section_name.lower() in {"overall", "summary", "historical insights"}:
        return "Historical Insights"

    return section_name


def _historical_insight_evidence(payload: dict) -> list[str]:
    raw_items = payload.get("evidence")
    if raw_items is None:
        raw_items = payload.get("quotes")
    if raw_items is None:
        raw_items = payload.get("supporting_quotes")

    if isinstance(raw_items, str):
        raw_items = [raw_items]

    evidence = []
    for item in raw_items or []:
        cleaned = _clean_historical_report_text(item)
        if cleaned and cleaned not in evidence:
            evidence.append(cleaned)
        if len(evidence) >= 4:
            break

    return evidence


def _historical_context_insights_for_canonical(insights: list[dict]) -> list[dict]:
    canonical_insights = []
    seen_keys = set()

    for insight in insights or []:
        if not isinstance(insight, dict):
            continue

        insight_type = _clean_historical_report_text(insight.get("insight_type")).lower()

        # The old deterministic summary/pattern rows are useful as raw audit
        # artifacts, but they create weak report cards such as "Summary" and
        # "Pattern". Survey report insight cards should use AI-generated
        # finding payloads with titles, explanations, and evidence.
        if insight_type not in {"ai_insight", "canonical_ai_insight"}:
            continue

        payload = _historical_parse_insight_json(insight)
        title = (
            _clean_historical_report_text(payload.get("title"))
            or _clean_historical_report_text(insight.get("insight_summary"))
        )
        explanation = (
            _clean_historical_report_text(payload.get("explanation"))
            or _clean_historical_report_text(insight.get("insight_summary"))
        )

        if not title or not explanation:
            continue

        section_name = _historical_normalized_insight_section_name(insight, payload)
        evidence = _historical_insight_evidence(payload)
        impact = _clean_historical_report_text(payload.get("impact")).lower() or "medium"
        sentiment = _clean_historical_report_text(payload.get("sentiment")).lower() or "mixed"

        if impact not in {"high", "medium", "low"}:
            impact = "medium"
        if sentiment not in {"positive", "negative", "mixed", "neutral"}:
            sentiment = "mixed"

        dedupe_key = (section_name.lower(), title.lower())
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        canonical_insights.append({
            "title": title,
            "section_name": section_name,
            "insight_type": insight_type or "historical_insight",
            "impact": impact,
            "sentiment": sentiment,
            "explanation": explanation,
            "evidence": evidence,
        })

        if len(canonical_insights) >= 7:
            break

    return canonical_insights


def _build_historical_context_canonical_report(*, context: dict, datasets: list[dict], rows: list[dict], profile_stats: dict, sections: list[dict], insights: list[dict], latest_dataset_id: int | None) -> dict:
    from app.db.historical import get_section_names, get_section_summaries
    from app.db.survey_kpis import calculate_product_kpis_from_answer_rows

    latest_dataset = datasets[-1] if datasets else {}
    survey_name = (
        _clean_historical_report_text(latest_dataset.get("dataset_type"))
        or _clean_historical_report_text(context.get("trial_purpose"))
        or "Historical Survey"
    )

    section_names = get_section_names(latest_dataset_id) if latest_dataset_id else {}
    section_summaries = get_section_summaries(latest_dataset_id) if latest_dataset_id else {}
    kpi_rows = _historical_rows_to_kpi_answer_rows(
        rows=rows,
        context=context,
        dataset=latest_dataset,
    )
    kpis = calculate_product_kpis_from_answer_rows(kpi_rows) if kpi_rows else {}

    response_count = len({row.get("response_group_id") for row in rows or [] if row.get("response_group_id") is not None})
    answer_count = len(rows or [])
    question_count = len({row.get("question_position") for row in rows or [] if row.get("question_position") is not None})

    executive_summary = ""
    for insight in insights or []:
        if isinstance(insight, dict) and insight.get("insight_type") == "ai_summary":
            executive_summary = _clean_historical_report_text(insight.get("insight_summary"))
            break

    has_generated_report = bool(section_names or section_summaries or insights)

    return {
        "metadata": {
            "version": "historical_context_canonical_v1",
            "generation_mode": "historical_context_runtime_adapter",
            "context_id": context.get("context_id"),
            "dataset_id": latest_dataset_id,
            "created_at": latest_dataset.get("created_at"),
            "has_generated_report": has_generated_report,
        },
        "product": {
            "product_id": context.get("product_id"),
            "internal_name": context.get("internal_name"),
            "market_name": context.get("market_name"),
            "product_type_display": context.get("product_type_display"),
            "business_group": context.get("business_group"),
        },
        "summary": {
            "executive_summary": executive_summary,
            "response_count": response_count,
            "answer_count": answer_count,
            "survey_count": 1 if latest_dataset_id else 0,
            "section_count": len(sections or []),
            "insight_count": len(insights or []),
        },
        "kpis": kpis,
        "source_surveys": [{
            "survey_name": survey_name,
            "dataset_type": survey_name,
            "context_id": context.get("context_id"),
            "dataset_id": latest_dataset_id,
            "question_count": question_count,
            "response_count": response_count,
            "answer_count": answer_count,
            "source_file_name": latest_dataset.get("source_file_name"),
            "source_href": f"/historical/context?context_id={context.get('context_id')}",
        }] if latest_dataset_id else [],
        "participant_profile": {
            "title": "Participant Profile / User Context",
            "questions": _historical_profile_questions_for_canonical(profile_stats),
        },
        "sections": _historical_sections_for_canonical(
            sections=sections,
            section_names=section_names,
            section_summaries=section_summaries,
            survey_name=survey_name,
        ),
        "insights": _historical_context_insights_for_canonical(insights),
    }


def render_historical_context_get(
    user_id,
    base_template,
    inject_nav,
    context_id,
    query_params,
    can_manage_report=True,
):

    if not _can_access_historical_context(
        user_id=user_id,
        context_id=context_id,
    ):
        return {"redirect": "/historical"}

    # -------------------------
    # Fetch data (NO raw SQL here)
    # -------------------------
    context = get_context_with_product(context_id)
    datasets = get_datasets_by_context(context_id)
    metrics = get_historical_metrics_by_context(context_id)
    insights = get_latest_insights_by_context(context_id)

    if not context:
        return {"redirect": "/historical"}

    action_csrf_token = generate_csrf_token(user_id) if can_manage_report else ""

    from app.db.historical import get_historical_answers_by_dataset

    # -------------------------
    # Build Profile Stats
    # -------------------------
    profile_stats = {}
    profile_segments = []
    profile_outliers = []
    sections = []
    latest_dataset_id = None
    rows = []

    if datasets:
        latest_dataset_id = datasets[-1].get("dataset_id")

    if latest_dataset_id:
        rows = get_historical_answers_by_dataset(latest_dataset_id)

        responses = {}

        for r in rows:
            gid = r["response_group_id"]
            q = r["question_text"]
            a = r["answer_text"]

            if gid not in responses:
                responses[gid] = {}

            responses[gid][q] = a

        gid_list = sorted(responses.keys())

        import re

        for gid in gid_list:
            for q, val in responses[gid].items():

                if not val:
                    continue

                if not is_profile_question(q):
                    continue

                if q not in profile_stats:
                    profile_stats[q] = {}

                raw_val = str(val).strip()

                # -------------------------
                # SAFE SPLIT LOGIC (no guessing)
                # -------------------------
                parts = [raw_val]

                if "," in raw_val:

                    candidates = [p.strip() for p in raw_val.split(",") if p.strip()]

                    def is_clean_token(token):
                        # Reject obvious fragments
                        if len(token) < 2:
                            return False

                        # Reject trailing fragments like "etc.)"
                        if token.lower().endswith("etc.)") or token.endswith(".)"):
                            return False

                        # If original value contains parentheses, assume it's a single label
                        if "(" in raw_val and ")" in raw_val:
                            return False

                        return True

                    clean_tokens = [t for t in candidates if is_clean_token(t)]

                    # Only split if ALL tokens are clean
                    if len(clean_tokens) == len(candidates):
                        parts = clean_tokens

                # -------------------------
                # Process parts
                # -------------------------
                for part in parts:

                    cleaned = part.strip()

                    # -------------------------
                    # Normalize numeric values
                    # -------------------------
                    numeric_match = re.match(r"^\d+(\.\d+)?%?$", cleaned)

                    if numeric_match:
                        number = cleaned.replace("%", "")

                        try:
                            number = float(number)

                            if number.is_integer():
                                key = f"{int(number)}%"
                            else:
                                key = f"{number:.1f}%"

                        except:
                            key = cleaned
                    else:
                        key = cleaned

                    if key not in profile_stats[q]:
                        profile_stats[q][key] = 0

                    profile_stats[q][key] += 1

        profile_segments, profile_outliers = build_profile_segments(
            responses,
            max_segments=5,
            min_segment_size=3
        )

        sections = build_sections_from_rows(rows)

    # -------------------------
    # NORMALIZE PROFILE STATS (FOR UI)
    # -------------------------
    normalized_segments = {}

    for question, counts in profile_stats.items():

        total = sum(counts.values()) if counts else 0

        rows_formatted = []

        for label, count in counts.items():
            percent = round((count / total) * 100, 1) if total > 0 else 0

            rows_formatted.append({
                "label": label,
                "count": count,
                "percent": percent
            })

        # sort descending by count
        rows_formatted.sort(key=lambda x: x["count"], reverse=True)

        normalized_segments[question] = rows_formatted

    # -------------------------
    # Format context
    # -------------------------
    internal = e(context.get("internal_name") or "")
    market = e(context.get("market_name") or "")
    product_name = f"{internal} ({market})" if market else internal

    round_number = context.get("round_number") or "-"
    lifecycle = e(context.get("lifecycle_stage") or "-")
    purpose = e(context.get("trial_purpose") or "-")
    invited = context.get("invited_user_count") or "-"

    from app.services.canonical_report_renderer import render_canonical_report_panel

    latest_dataset = datasets[-1] if datasets else {}
    canonical_report = _build_historical_context_canonical_report(
        context=context,
        datasets=datasets,
        rows=rows,
        profile_stats=profile_stats,
        sections=sections,
        insights=insights,
        latest_dataset_id=latest_dataset_id,
    )

    section_actions_html = ""
    panel_actions_html = ""
    has_generated_report = bool(canonical_report.get("metadata", {}).get("has_generated_report"))
    report_action_label = "Regenerate Report" if has_generated_report else "Generate Report"

    if can_manage_report and latest_dataset_id:
        panel_actions_html = f"""
            <form method="POST" action="/historical/generate-report" style="margin:0;" onsubmit="startAnalysisLoading()">
                <input type="hidden" name="csrf_token" value="{e(action_csrf_token)}">
                <input type="hidden" name="dataset_id" value="{e(latest_dataset_id)}">
                <input type="hidden" name="context_id" value="{e(context_id)}">
                <button type="submit" class="historical-action-pill">{e(report_action_label)}</button>
            </form>
            <a class="historical-action-pill is-secondary" href="/historical/raw?context_id={e(context_id)}&dataset_id={e(latest_dataset_id)}">Raw Data</a>
        """
    elif can_manage_report:
        panel_actions_html = _render_delete_draft_context_form(
            context_id=context_id,
            csrf_token=action_csrf_token,
        )

    internal_raw = context.get("internal_name") or "Unnamed Project"
    market_raw = context.get("market_name") or "-"
    product_type = context.get("product_type_display") or "-"
    business_group = context.get("business_group") or "-"
    survey_name = (
        _clean_historical_report_text(latest_dataset.get("dataset_type"))
        or _clean_historical_report_text(context.get("trial_purpose"))
        or "Historical Survey"
    )

    report_panel_html = render_canonical_report_panel(
        report=canonical_report,
        panel_id="historical-survey-report",
        panel_title="Survey Report",
        panel_status=("Generated" if has_generated_report else "Raw Data Ready") if latest_dataset_id else "No Data",
        primary_action_html=panel_actions_html,
        primary_action_placement="summary",
        section_actions_html=section_actions_html,
        source_title="Survey Source Details",
    )

    html = f"""
    <div class="results-section historical-page">
        <div class="historical-product-hero">
            <div>
                <h2>Historical Survey Report: {e(internal_raw)} <span class="historical-heading-muted">({e(market_raw)}) · Round {e(round_number)}</span></h2>
                <p class="historical-page-description">
                    {e(survey_name)} · {e(context.get("lifecycle_stage") or "-")} · {e(context.get("trial_purpose") or "-")}
                </p>
            </div>
            <div class="historical-product-meta-card">
                <div><strong>{e(business_group)}</strong> / {e(product_type)}</div>
                <div>{e(canonical_report.get("summary", {}).get("response_count") or 0)} responses</div>
                <div>{e(canonical_report.get("summary", {}).get("section_count") or 0)} sections · {e(canonical_report.get("summary", {}).get("answer_count") or 0)} answers</div>
                <div>Dataset: {e(latest_dataset.get("source_file_name") or "—")}</div>
            </div>
        </div>

        {_render_historical_subnav(active_key="context", context_id=context_id, dataset_id=latest_dataset_id) if can_manage_report else ""}

        {report_panel_html}
    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def handle_historical_create_context_post(data):

    product_id = str(_posted_scalar(data.get("product_id")) or "").strip()
    new_internal_name = str(_posted_scalar(data.get("new_internal_name")) or "").strip()
    new_market_name = str(_posted_scalar(data.get("new_market_name")) or "").strip()
    new_product_type_key = str(_posted_scalar(data.get("new_product_type_key")) or "").strip().lower()
    new_business_group = str(_posted_scalar(data.get("new_business_group")) or "").strip()
    round_number = _posted_scalar(data.get("round_number"))
    lifecycle_stage = str(_posted_scalar(data.get("lifecycle_stage")) or "").strip()
    trial_purpose = str(_posted_scalar(data.get("trial_purpose")) or "").strip()
    mix = str(_posted_scalar(data.get("internal_vs_external_mix")) or "").strip()
    invited = _posted_scalar(data.get("invited_user_count"))
    description = str(_posted_scalar(data.get("description")) or "").strip()

# -------------------------
# Validate required fields
# -------------------------

    is_new_project = product_id == "__new__"
    has_existing_project = bool(product_id) and not is_new_project

    if not product_id:
        return {"error": "missing_project"}

    if not lifecycle_stage:
        return {"error": "missing_stage"}

    if not trial_purpose:
        return {"error": "missing_purpose"}

    if not mix:
        return {"error": "missing_scope"}

    try:
        round_number = int(round_number) if str(round_number or "").strip() else None
    except (TypeError, ValueError):
        return {"error": "invalid_round"}

    try:
        invited = int(invited) if str(invited or "").strip() else None
    except (TypeError, ValueError):
        return {"error": "invalid_invited"}

    prepared_upload = _prepare_historical_upload_from_form(
        data=data,
        fallback_round_number=round_number,
    )
    if not prepared_upload.get("ok"):
        return {"error": prepared_upload.get("error") or "invalid_upload"}

    if has_existing_project:
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            return {"error": "invalid_product"}

        from app.db.historical import product_exists_for_context_creation

        if not product_exists_for_context_creation(product_id):
            return {"error": "invalid_product"}

    elif is_new_project:
        if not new_internal_name:
            return {"error": "missing_project"}

        if not new_product_type_key:
            return {"error": "missing_product_type"}

        if not new_business_group:
            return {"error": "missing_business_group"}

        from app.db.products import (
            business_group_is_valid_for_creation,
            create_product,
            find_project_creation_duplicate_candidates,
            product_type_key_is_valid_for_creation,
        )

        if not product_type_key_is_valid_for_creation(new_product_type_key):
            return {"error": "invalid_product_type"}

        if not business_group_is_valid_for_creation(new_business_group):
            return {"error": "invalid_business_group"}

        duplicate_candidates = find_project_creation_duplicate_candidates(
            internal_name=new_internal_name,
            market_name=new_market_name,
            product_type_key=new_product_type_key,
            business_group=new_business_group,
        )

        if duplicate_candidates.get("exact_matches"):
            return {"error": "duplicate_project"}

        if duplicate_candidates.get("near_matches"):
            return {"error": "possible_duplicate_project"}

        product_id = create_product(
            new_internal_name,
            new_market_name,
            new_product_type_key,
            new_business_group,
        )

    from app.db.historical import create_historical_context

    context_id = create_historical_context(
        product_id,
        round_number,
        lifecycle_stage,
        trial_purpose,
        mix,
        invited,
        description
    )

    if prepared_upload.get("should_upload"):
        try:
            _ingest_prepared_historical_upload(
                context_id=context_id,
                upload=prepared_upload,
            )
        except Exception:
            return {
                "redirect": f"/historical/context?context_id={context_id}&error=ingest_failed"
            }

    return {
        "redirect": f"/historical/context?context_id={context_id}"
    }


def handle_historical_delete_draft_context_post(*, user_id, data):
    context_id = _posted_int(data.get("context_id"))
    if not context_id:
        return {"redirect": "/historical?draft_delete=invalid_context"}

    from app.db.historical import delete_draft_historical_context

    result = delete_draft_historical_context(context_id)
    product_id = result.get("product_id")

    if result.get("success"):
        if product_id:
            return {"redirect": f"/historical/product?product_id={int(product_id)}&draft_delete=deleted"}
        return {"redirect": "/historical?draft_delete=deleted"}

    reason = result.get("reason") or "blocked"
    if product_id:
        return {"redirect": f"/historical/product?product_id={int(product_id)}&draft_delete={reason}"}

    return {"redirect": f"/historical?draft_delete={reason}"}


from app.db.connection import get_db_connection

def render_historical_create_context_get(user_id, base_template, inject_nav, query_params=None):

    from app.db.historical import get_all_products_for_context_creation
    from app.db.products import (
        list_business_group_options_for_creation,
        list_product_type_options_for_creation,
    )

    query_params = query_params or {}
    error = _posted_scalar(query_params.get("error"))
    csrf_token = generate_csrf_token(user_id)

    products = get_all_products_for_context_creation()
    product_type_options = list_product_type_options_for_creation()
    business_group_options = list_business_group_options_for_creation()

    product_options = ""
    product_type_options_html = ""
    business_group_options_html = ""

    for p in products:
        internal = e(p.get("internal_name") or "")
        market = e(p.get("market_name") or "")

        label = internal
        if market:
            label += f" ({market})"

        product_options += f"<option value='{e(str(p['product_id']))}'>{label}</option>"

    product_options += "<option value='__new__'>+ Create new project</option>"

    for option in product_type_options:
        product_type_key = e(option.get("product_type_key") or "")
        product_type_display = e(option.get("product_type_display") or option.get("product_type_key") or "")
        if not product_type_key:
            continue

        product_type_options_html += f"<option value='{product_type_key}'>{product_type_display}</option>"

    for business_group in business_group_options:
        safe_business_group = e(business_group)
        business_group_options_html += f"<option value='{safe_business_group}'>{safe_business_group}</option>"

    error_messages = {
        "duplicate_project": "A project with that name already exists. Select the existing project instead of creating a duplicate.",
        "possible_duplicate_project": "That project name looks similar to an existing project. Check the project dropdown before creating a new project.",
        "missing_upload_fields": "To upload survey data now, enter both a survey name and a CSV file. Leave both blank to create the round without data.",
        "invalid_file": "Upload a valid CSV file.",
        "ingest_failed": "The round was created, but the survey file could not be ingested. Open the round and try adding the survey again.",
        "missing_project": "Select a project or choose + Create new project.",
        "missing_product_type": "Select a product type for the new project.",
        "missing_business_group": "Select a business group for the new project.",
        "invalid_product_type": "Select a valid product type.",
        "invalid_business_group": "Select a valid business group.",
        "invalid_round": "Enter a valid round number.",
        "invalid_invited": "Enter a valid invited-user count.",
        "invalid_csrf": "This form expired. Please try again.",
    }
    error_html = ""
    if error:
        error_html = f"""
        <div class="alert alert-error">
            {e(error_messages.get(error, "The round could not be created. Please review the form and try again."))}
        </div>
        """

    html = f"""
    <div class="results-section historical-page historical-create-context-page">
        {_render_historical_subnav(active_key="create")}

        <div class="historical-create-header">
            <div>
                <div class="historical-create-eyebrow">Historical Intake</div>
                <h2>Create Historical Round</h2>
                <p class="historical-page-description">
                    Select or create the project, define the round, and upload the first survey file in one step.
                </p>
            </div>
            <a class="historical-action-pill is-secondary" href="/historical">Back to Legacy Projects</a>
        </div>

        <div class="historical-create-layout">
            <form method="POST" action="/historical/create-context" enctype="multipart/form-data" class="historical-create-card historical-form" onsubmit="startAnalysisLoading();">
                <input type="hidden" name="csrf_token" value="{e(csrf_token)}">

                <div class="historical-card-kicker">Project</div>
                <div class="historical-project-choice-copy">
                    Choose the project this round belongs to. Select <strong>+ Create new project</strong> if it is not listed yet.
                </div>

                <div class="historical-form-grid">
                    <div class="historical-field historical-field-span-2">
                        <label for="historical_product_id">Project</label>
                        <select id="historical_product_id" name="product_id" class="form-input" required>
                            <option value="" disabled selected>Select existing project</option>
                            {product_options}
                        </select>
                        <div class="historical-form-note">
                            Existing projects create a new round context immediately. New project fields appear only when <strong>+ Create new project</strong> is selected.
                        </div>
                    </div>
                </div>

                <div id="historical_new_project_panel" class="historical-new-project-panel is-hidden" aria-hidden="true">
                    <div class="historical-form-grid">
                        <div class="historical-field">
                            <label for="historical_new_internal_name">Project name</label>
                            <input id="historical_new_internal_name" type="text" name="new_internal_name" class="form-input" placeholder="Example: Alice Plus" data-new-project-field data-required-for-new-project disabled>
                        </div>

                        <div class="historical-field">
                            <label for="historical_new_market_name">Market name <span class="historical-label-muted">Optional</span></label>
                            <input id="historical_new_market_name" type="text" name="new_market_name" class="form-input" placeholder="Example: Zone Wireless Plus" data-new-project-field disabled>
                        </div>

                        <div class="historical-field">
                            <label for="historical_new_product_type_key">Product type</label>
                            <select id="historical_new_product_type_key" name="new_product_type_key" class="form-input" data-new-project-field data-required-for-new-project disabled>
                                <option value="" selected>Select product type for new project</option>
                                {product_type_options_html}
                            </select>
                        </div>

                        <div class="historical-field">
                            <label for="historical_new_business_group">Business group</label>
                            <select id="historical_new_business_group" name="new_business_group" class="form-input" data-new-project-field data-required-for-new-project disabled>
                                <option value="" selected>Select business group for new project</option>
                                {business_group_options_html}
                            </select>
                        </div>
                    </div>
                    <div class="historical-form-note historical-new-project-note">
                        New projects are saved to the products table, then this round context is created under that project.
                    </div>
                </div>

                <div class="historical-card-kicker">Round Details</div>
                <div class="historical-form-grid">
                    <div class="historical-field">
                        <label for="historical_round_number">Round</label>
                        <input id="historical_round_number" type="number" name="round_number" class="form-input" value="1" min="1">
                    </div>

                    <div class="historical-field">
                        <label for="historical_lifecycle_stage">Lifecycle Stage</label>
                        <select id="historical_lifecycle_stage" name="lifecycle_stage" class="form-input" required>
                            <option value="" disabled selected>Select your stage</option>
                            <option value="Pre G1">Pre G1</option>
                            <option value="PB1">PB1</option>
                            <option value="PB2">PB2</option>
                            <option value="PBX">PBX</option>
                            <option value="GX">GX</option>
                        </select>
                    </div>

                    <div class="historical-field historical-field-span-2">
                        <label for="historical_trial_purpose">Trial Purpose</label>
                        <select id="historical_trial_purpose" name="trial_purpose" class="form-input" required>
                            <option value="" disabled selected>Select your purpose</option>
                            <option value="Out of Box and First Impressions Survey">Out of Box and First Impressions Survey</option>
                            <option value="Usage Experience and KPIs Survey">Usage Experience and KPIs Survey</option>
                            <option value="Other">Other</option>
                        </select>
                    </div>

                    <div class="historical-field">
                        <label for="historical_internal_vs_external_mix">Internal vs External</label>
                        <select id="historical_internal_vs_external_mix" name="internal_vs_external_mix" class="form-input" required>
                            <option value="" disabled selected>Set user scope</option>
                            <option value="Internal">Internal</option>
                            <option value="External">External</option>
                            <option value="Hybrid">Hybrid</option>
                        </select>
                    </div>

                    <div class="historical-field">
                        <label for="historical_invited_user_count">Invited User Count</label>
                        <input id="historical_invited_user_count" type="number" name="invited_user_count" class="form-input" value="30" min="0">
                    </div>
                </div>

                <div class="historical-card-kicker">Survey Upload</div>
                <div class="historical-form-grid">
                    <div class="historical-field historical-field-span-2">
                        <label for="historical_dataset_type">Survey name <span class="historical-label-muted">Optional</span></label>
                        <input id="historical_dataset_type" type="text" name="dataset_type" class="form-input" placeholder="Example: Round 1 First Impressions">
                        <div class="historical-form-note">
                            Add the first survey now, or leave the survey name and file blank to create the round without data.
                        </div>
                    </div>

                    <input type="hidden" name="upload_round_number" value="">

                    <div class="historical-field historical-field-span-2">
                        {render_csv_dropzone(
                            input_name="file",
                            input_id="historical_initial_csv_file",
                            label="Drop the first historical CSV here or click to choose",
                        )}
                    </div>
                </div>

                <div class="historical-card-kicker">Notes</div>
                <div class="historical-form-grid">
                    <div class="historical-field historical-field-span-2">
                        <label for="historical_description">Description <span class="historical-label-muted">Optional</span></label>
                        <textarea id="historical_description" name="description" class="form-input" rows="5" placeholder="Add context that will help future report readers understand this round."></textarea>
                    </div>
                </div>

                <div class="historical-form-actions">
                    <button type="submit" class="historical-primary-action">Create Round</button>
                    <span class="historical-next-step-note">Creates the round and ingests the survey file when one is attached.</span>
                </div>
            </form>

            <aside class="historical-create-sidebar">
                <div class="historical-create-info-card">
                    <div class="historical-card-kicker">Hierarchy</div>
                    <h3>Where this fits</h3>
                    <ol>
                        <li>Project</li>
                        <li>Round context</li>
                        <li>Survey upload</li>
                        <li>Survey report</li>
                        <li>Round report</li>
                    </ol>
                </div>

                <div class="historical-create-info-card">
                    <div class="historical-card-kicker">Project creation</div>
                    <h3>Select or create</h3>
                    <p>
                        Select an existing project when one already exists. Choose <strong>+ Create new project</strong> only when this is the first historical round for that product.
                    </p>
                </div>
            </aside>
        </div>

        <script>
        (function () {{
            const projectSelect = document.getElementById("historical_product_id");
            const newProjectPanel = document.getElementById("historical_new_project_panel");
            const newProjectFields = newProjectPanel ? newProjectPanel.querySelectorAll("[data-new-project-field]") : [];

            function syncNewProjectPanel() {{
                const shouldShow = projectSelect && projectSelect.value === "__new__";

                if (!newProjectPanel) {{
                    return;
                }}

                newProjectPanel.classList.toggle("is-hidden", !shouldShow);
                newProjectPanel.setAttribute("aria-hidden", shouldShow ? "false" : "true");

                newProjectFields.forEach(function (field) {{
                    field.disabled = !shouldShow;
                    if (field.hasAttribute("data-required-for-new-project")) {{
                        field.required = shouldShow;
                    }}
                    if (!shouldShow) {{
                        field.value = "";
                    }}
                }});
            }}

            if (projectSelect) {{
                projectSelect.addEventListener("change", syncNewProjectPanel);
                syncNewProjectPanel();
            }}
        }})();
        </script>
    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}

from app.db.historical import get_legacy_project_groups


def _render_survey_report_publication_actions(*, context_id, dataset_count, status, csrf_token, return_to="historical", product_id=None):
    try:
        safe_context_id = int(context_id)
    except (TypeError, ValueError):
        safe_context_id = 0

    try:
        safe_product_id = int(product_id) if product_id not in (None, "") else 0
    except (TypeError, ValueError):
        safe_product_id = 0

    if not safe_context_id:
        return '<span class="historical-action-pill is-disabled">Survey unavailable</span>'

    report_href = f"/historical/context?context_id={safe_context_id}"

    if int(dataset_count or 0) <= 0 or not status.get("has_data"):
        return f"""
            <a class="historical-action-pill" href="{e(report_href)}" onclick="event.stopPropagation();">
                Survey Report
            </a>
            <span class="historical-action-pill is-disabled">Needs data</span>
        """

    publish_action = "withdraw" if status.get("is_published") else "publish"
    publish_label = "Withdraw" if status.get("is_published") else "Publish to R&I"
    publish_class = "historical-action-pill is-secondary" if status.get("is_published") else "historical-action-pill"
    state_badge = (
        '<span class="historical-status-chip historical-publication-state is-ready">Published</span>'
        if status.get("is_published")
        else ""
    )

    safe_return_to = str(return_to or "historical").strip()
    if safe_return_to not in ("historical", "product"):
        safe_return_to = "historical"

    product_input = f'<input type="hidden" name="product_id" value="{safe_product_id}">' if safe_product_id else ""

    return f"""
        <a class="historical-action-pill" href="{e(report_href)}" onclick="event.stopPropagation();">
            Survey Report
        </a>
        {state_badge}
        <form method="POST" action="/historical/survey-report/publish" style="margin:0;"
            onclick="event.stopPropagation();">
            <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
            <input type="hidden" name="context_id" value="{safe_context_id}">
            <input type="hidden" name="action" value="{publish_action}">
            <input type="hidden" name="return_to" value="{e(safe_return_to)}">
            {product_input}
            <button type="submit" class="{publish_class}">{e(publish_label)}</button>
        </form>
    """


def _render_aggregate_report_actions(*, product_id, round_number, dataset_count, status, csrf_token):
    try:
        safe_product_id = int(product_id)
    except (TypeError, ValueError):
        safe_product_id = 0

    try:
        safe_round_number = int(round_number) if round_number is not None else None
    except (TypeError, ValueError):
        safe_round_number = None

    if not safe_product_id:
        return '<span class="historical-action-pill is-disabled">Aggregate unavailable</span>'

    if safe_round_number is None:
        return '<span class="historical-action-pill is-disabled">Needs round</span>'

    if status.get("error") == "table_missing":
        return '<span class="historical-action-pill is-disabled">Run aggregate migration</span>'

    if int(dataset_count or 0) <= 0:
        return '<span class="historical-action-pill is-disabled">Needs data</span>'

    hidden_inputs = f"""
        <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
        <input type="hidden" name="product_id" value="{safe_product_id}">
        <input type="hidden" name="round_number" value="{safe_round_number}">
    """

    if not status.get("exists"):
        return f"""
            <form method="POST" action="/historical/aggregate-report/generate" style="margin:0;"
                onsubmit="startAnalysisLoading();" onclick="event.stopPropagation();">
                {hidden_inputs}
                <button type="submit" class="historical-action-pill">Create Aggregate Report</button>
            </form>
        """

    report_href = f"/historical/aggregate-report?product_id={safe_product_id}&round_number={safe_round_number}"
    publish_action = "withdraw" if status.get("is_published") else "publish"
    if status.get("is_published"):
        publish_action = "withdraw"
        publish_label = "Withdraw"
        publish_class = "historical-action-pill is-secondary"
        state_badge = '<span class="historical-status-chip historical-publication-state is-ready">Published</span>'
    else:
        publish_action = "publish"
        publish_label = "Publish Now"
        publish_class = "historical-action-pill"
        state_badge = ""

    return f"""
        <a class="historical-action-pill" href="{e(report_href)}" onclick="event.stopPropagation();">
            Aggregate Report
        </a>
        {state_badge}
        <form method="POST" action="/historical/aggregate-report/publish" style="margin:0;"
            onclick="event.stopPropagation();">
            {hidden_inputs}
            <input type="hidden" name="action" value="{publish_action}">
            <button type="submit" class="{publish_class}">{publish_label}</button>
        </form>
    """


def render_historical_landing_get(user_id, base_template, inject_nav):

    from app.db.historical import get_historical_survey_report_publication_status
    from app.db.historical_aggregate_reports import get_historical_aggregate_report_status

    project_groups = get_legacy_project_groups()
    csrf_token = generate_csrf_token(user_id)

    html = f"""
    <div class="results-section historical-page">
        <div class="historical-page-header">
            <div>
                <h2>Legacy Projects</h2>
                <p class="historical-page-description">
                    Contexts with the same product and round are grouped together as one legacy project.
                    Expand a project to review the individual survey contexts, reports, raw data, and upload actions.
                </p>
            </div>
        </div>

        {_render_historical_subnav(active_key="projects")}
    """

    if not project_groups:
        html += "<p>No historical projects loaded yet.</p>"
    else:
        html += """
        <div class="historical-project-list" role="table" aria-label="Legacy projects">
            <div class="historical-project-list-header" role="row">
                <div>#</div>
                <div>Project</div>
                <div>Product</div>
                <div class="is-centered">Round</div>
                <div>Surveys</div>
                <div class="is-centered">Lifecycle</div>
                <div class="is-action-cell">State</div>
            </div>
        """

        for idx, group in enumerate(project_groups, start=1):

            product_id = group.get("product_id")
            product_href = f"/historical/product?product_id={int(product_id)}" if product_id else "/historical"
            internal = e(group.get("internal_name") or "-")
            market = e(group.get("market_name") or "-")
            product_type = e(group.get("product_type_display") or "-")
            business_group = e(group.get("business_group") or "-")
            round_number = group.get("round_number")
            round_display = e(str(round_number)) if round_number is not None else "<span class='historical-warning-chip'>Needs round</span>"
            context_count = int(group.get("context_count") or 0)
            dataset_count = int(group.get("dataset_count") or 0)
            latest_context_id = group.get("latest_context_id")
            contexts = group.get("contexts") or []
            if context_count == 1 and latest_context_id:
                survey_publication_status = get_historical_survey_report_publication_status(latest_context_id)
                aggregate_actions = _render_survey_report_publication_actions(
                    context_id=latest_context_id,
                    dataset_count=dataset_count,
                    status=survey_publication_status,
                    csrf_token=csrf_token,
                    return_to="historical",
                )
            else:
                aggregate_status = get_historical_aggregate_report_status(
                    product_id=product_id,
                    round_number=round_number,
                )
                aggregate_actions = _render_aggregate_report_actions(
                    product_id=product_id,
                    round_number=round_number,
                    dataset_count=dataset_count,
                    status=aggregate_status,
                    csrf_token=csrf_token,
                )

            survey_label = "survey" if context_count == 1 else "surveys"
            dataset_label = "dataset" if dataset_count == 1 else "datasets"
            survey_summary = f"{context_count} {survey_label} ({dataset_count} {dataset_label})"

            lifecycle_values = []
            for context in contexts:
                lifecycle = context.get("lifecycle_stage")
                if lifecycle and lifecycle not in lifecycle_values:
                    lifecycle_values.append(lifecycle)

            lifecycle_display = e(", ".join(lifecycle_values) if lifecycle_values else "-")

            survey_rows = ""
            for survey_idx, context in enumerate(contexts, start=1):
                context_id = context.get("context_id")
                dataset_id = context.get("dataset_id")
                dataset_name = context.get("dataset_name") or "Untitled survey"
                purpose = context.get("trial_purpose") or "-"
                lifecycle = context.get("lifecycle_stage") or "-"

                if dataset_id:
                    data_status = "<span class='historical-status-chip is-ready'>Data uploaded</span>"
                    raw_action = f"""
                        <a class="historical-action-pill is-secondary" href="/historical/raw?context_id={context_id}&dataset_id={dataset_id}">
                            Raw Data
                        </a>
                    """
                    delete_draft_action = ""
                else:
                    data_status = "<span class='historical-status-chip is-muted'>No data yet</span>"
                    raw_action = "<span class='historical-action-pill is-disabled'>Raw Data</span>"
                    delete_draft_action = _render_delete_draft_context_form(
                        context_id=context_id,
                        csrf_token=csrf_token,
                    )

                survey_rows += f"""
                    <tr>
                        <td>{survey_idx}</td>
                        <td>
                            <div class="historical-project-title">{e(dataset_name)}</div>
                            <div class="historical-muted">{e(purpose)}</div>
                        </td>
                        <td>{e(lifecycle)}</td>
                        <td>{data_status}</td>
                        <td>
                            <div class="historical-action-row">
                                <a class="historical-action-pill" href="/historical/context?context_id={context_id}">
                                    Survey Report
                                </a>
                                {raw_action}
                                {delete_draft_action}
                            </div>
                        </td>
                    </tr>
                """

            html += f"""
            <details class="historical-project-card">
                <summary class="historical-project-summary-row">
                    <span class="historical-project-caret" aria-hidden="true">▸</span>
                    <span class="historical-project-index">{idx}</span>
                    <span class="historical-project-cell historical-project-inline-cell">
                        <a class="historical-inline-link historical-project-title" href="{e(product_href)}" onclick="event.stopPropagation();">{internal}</a><span class="historical-inline-muted">({market})</span>
                    </span>
                    <span class="historical-project-cell historical-project-inline-cell">
                        <span class="historical-inline-text">{business_group} / {product_type}</span>
                    </span>
                    <span class="historical-project-cell is-centered">{round_display}</span>
                    <span class="historical-project-cell historical-project-inline-cell">
                        <span class="historical-inline-text historical-count-inline">{e(survey_summary)}</span>
                    </span>
                    <span class="historical-project-cell is-centered"><span class="historical-lifecycle-pill">{lifecycle_display}</span></span>
                    <span class="historical-project-actions is-action-cell">
                        {aggregate_actions}
                        <a class="historical-action-pill is-secondary" href="/historical/create-context" onclick="event.stopPropagation();">
                            Add Survey
                        </a>
                    </span>
                </summary>

                <div class="historical-project-detail">
                    <div class="historical-project-detail-heading">
                        Surveys in this project round
                    </div>
                    <div class="table-scroll">
                        <table class="data-table historical-survey-detail-table">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Survey</th>
                                    <th>Lifecycle</th>
                                    <th>Dataset</th>
                                    <th>Survey Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {survey_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </details>
            """

        html += """
        </div>
        """

    html += "</div>"

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def _json_to_swot_columns(summary_json):
    import json

    if not summary_json:
        return ""

    parsed = summary_json
    if isinstance(summary_json, str):
        try:
            parsed = json.loads(summary_json)
        except (TypeError, json.JSONDecodeError):
            return f"""
            <div class="historical-muted">{e(summary_json)}</div>
            """

    if not isinstance(parsed, dict):
        return ""

    columns = []
    labels = [
        ("strengths", "Strengths"),
        ("weaknesses", "Weaknesses"),
        ("opportunities", "Opportunities"),
        ("threats", "Threats"),
    ]

    for key, label in labels:
        values = parsed.get(key) or []
        if not isinstance(values, list):
            values = [values]

        items = "".join(f"<li>{e(value)}</li>" for value in values if value)
        if not items:
            items = "<li class='historical-muted'>No saved summary yet.</li>"

        columns.append(f"""
            <div class="historical-swot-column">
                <h5>{e(label)}</h5>
                <ul>{items}</ul>
            </div>
        """)

    return f"""
        <div class="historical-swot-grid">
            {''.join(columns)}
        </div>
    """


def render_historical_aggregate_report_get(
    user_id,
    base_template,
    inject_nav,
    product_id,
    round_number,
    query_params,
    can_manage_report=True,
    view_mode="historical",
):
    from app.db.historical_aggregate_reports import (
        get_historical_aggregate_report,
        get_historical_aggregate_report_status,
    )
    from app.services.canonical_report_renderer import render_canonical_report_panel

    report_result = get_historical_aggregate_report(
        product_id=int(product_id),
        round_number=int(round_number),
    )

    if not report_result.get("success"):
        error_key = report_result.get("error") or "not_found"
        return {"redirect": f"/historical?error=aggregate_{error_key}"}

    report = report_result.get("report") or {}
    product = report.get("product") or {}
    summary = report.get("summary") or {}
    metadata = report.get("metadata") or {}
    is_reporting_view = view_mode == "reporting"

    aggregate_status = get_historical_aggregate_report_status(
        product_id=int(product_id),
        round_number=int(round_number),
    )

    status = query_params.get("aggregate", [None])[0]
    notice_html = ""
    if status == "generated":
        notice_html = """
        <div class="alert alert-success">
            Aggregate report generated from the uploaded survey datasets for this project round.
        </div>
        """
    elif status == "published":
        notice_html = """
        <div class="alert alert-success">
            Aggregate report published to Reporting & Insights.
        </div>
        """
    elif status == "withdrawn":
        notice_html = """
        <div class="alert alert-success">
            Aggregate report withdrawn from Reporting & Insights.
        </div>
        """
    elif status == "ai_generated":
        notice_html = """
        <div class="alert alert-success">
            Executive summary and insights generated for this aggregate report.
        </div>
        """

    internal = product.get("internal_name") or "Unnamed Project"
    market = product.get("market_name") or "-"
    product_type = product.get("product_type_display") or "-"
    business_group = product.get("business_group") or "-"

    action_html = ""
    if can_manage_report:
        csrf_token = generate_csrf_token(user_id)
        publish_action = "withdraw" if aggregate_status.get("is_published") else "publish"
        publish_label = "Withdraw from Reports & Insights" if aggregate_status.get("is_published") else "Publish to Reports & Insights"
        publish_class = "historical-action-pill is-secondary" if aggregate_status.get("is_published") else "historical-action-pill"

        action_html = f"""
            <form method="POST" action="/historical/aggregate-report/generate" style="margin:0;" onsubmit="startAnalysisLoading();">
                <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
                <input type="hidden" name="product_id" value="{e(product_id)}">
                <input type="hidden" name="round_number" value="{e(round_number)}">
                <button type="submit" class="historical-action-pill">Regenerate Aggregate + Insights</button>
            </form>
            <form method="POST" action="/historical/aggregate-report/publish" style="margin:0;">
                <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
                <input type="hidden" name="product_id" value="{e(product_id)}">
                <input type="hidden" name="round_number" value="{e(round_number)}">
                <input type="hidden" name="action" value="{e(publish_action)}">
                <button type="submit" class="{e(publish_class)}">{e(publish_label)}</button>
            </form>
        """

    page_title = "Published Project Report" if is_reporting_view else "Aggregate Project Round Report"
    page_description = (
        "This is the published project-round report available through Reporting & Insights."
        if is_reporting_view
        else "This report combines all uploaded survey datasets for this project round. This is the artifact that should be published to Reports & Insights."
    )
    report_status = "Published" if aggregate_status.get("is_published") else "Draft"
    historical_subnav_html = _render_historical_subnav(active_key="projects") if (can_manage_report and not is_reporting_view) else ""

    report_panel_html = render_canonical_report_panel(
        report=report,
        panel_id="historical-aggregate-report",
        panel_title=page_title,
        panel_status=report_status,
        notice_html=notice_html,
        primary_action_html=action_html,
        primary_action_placement="summary",
        source_title="Included Surveys",
    )

    html = f"""
    <div class="results-section historical-page">
        <div class="historical-product-hero">
            <div>
                <h2>{e(page_title)}: {e(internal)} <span class="historical-heading-muted">({e(market)}) · Round {e(round_number)}</span></h2>
                <p class="historical-page-description">
                    {e(page_description)}
                </p>
            </div>
            <div class="historical-product-meta-card">
                <div><strong>{e(business_group)}</strong> / {e(product_type)}</div>
                <div>{e(summary.get('survey_count') or 0)} surveys</div>
                <div>{e(summary.get('response_count') or 0)} responses · {e(summary.get('answer_count') or 0)} answers</div>
                <div>Generated: {e(metadata.get('updated_at') or metadata.get('created_at') or '-')}</div>
            </div>
        </div>

        {historical_subnav_html}

        {report_panel_html}
    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def handle_historical_aggregate_report_generate_post(user_id, data):
    product_id, round_number = _validate_historical_aggregate_target(data=data)
    if not product_id or not round_number:
        return {"redirect": "/historical?error=invalid_aggregate_target"}

    from app.db.historical_aggregate_reports import HistoricalAggregateReportsTableMissing
    from app.services.historical_aggregate_report_service import generate_historical_aggregate_report

    try:
        result = generate_historical_aggregate_report(
            product_id=product_id,
            round_number=round_number,
            generated_by_user_id=user_id,
        )
    except HistoricalAggregateReportsTableMissing:
        return {"redirect": "/historical?error=aggregate_table_missing"}
    except Exception:
        return {"redirect": f"/historical?error=aggregate_failed"}

    if not result.get("success"):
        error_key = result.get("error") or "failed"
        return {"redirect": f"/historical?error=aggregate_{error_key}"}

    return {
        "redirect": f"/historical/aggregate-report?product_id={product_id}&round_number={round_number}&aggregate=generated"
    }


def handle_historical_aggregate_report_generate_ai_post(user_id, data):
    product_id, round_number = _validate_historical_aggregate_target(data=data)
    if not product_id or not round_number:
        return {"redirect": "/historical?error=invalid_aggregate_target"}

    from app.db.historical_aggregate_reports import (
        HistoricalAggregateReportsTableMissing,
        get_historical_aggregate_report,
        upsert_historical_aggregate_report,
    )
    from app.services.canonical_report_ai_service import generate_canonical_report_ai_outputs

    try:
        report_result = get_historical_aggregate_report(
            product_id=product_id,
            round_number=round_number,
        )
    except HistoricalAggregateReportsTableMissing:
        return {"redirect": "/historical?error=aggregate_table_missing"}

    if not report_result.get("success"):
        error_key = report_result.get("error") or "not_found"
        return {
            "redirect": f"/historical/aggregate-report?product_id={product_id}&round_number={round_number}&error=aggregate_{error_key}"
        }

    report = report_result.get("report") or {}

    ai_result = generate_canonical_report_ai_outputs(
        report=report,
        report_type_label="Historical Aggregate Report",
        blocked_section_names={
            "Star Rating",
            "Net Promoter Score",
            "Ready for Sales",
            "Software Rating",
        },
        max_insights=7,
    )

    if not ai_result.get("success"):
        error_key = ai_result.get("error") or "ai_failed"
        return {
            "redirect": f"/historical/aggregate-report?product_id={product_id}&round_number={round_number}&error=aggregate_ai_{error_key}"
        }

    updated_report = ai_result.get("report") or report
    metadata = updated_report.get("metadata") if isinstance(updated_report.get("metadata"), dict) else {}

    try:
        upsert_historical_aggregate_report(
            product_id=product_id,
            round_number=round_number,
            report=updated_report,
            generated_by_user_id=user_id,
            generation_version=metadata.get("generation_version") or "historical_aggregate_report_product_clone_v1",
            data_hash=metadata.get("data_hash"),
        )
    except HistoricalAggregateReportsTableMissing:
        return {"redirect": "/historical?error=aggregate_table_missing"}
    except Exception:
        return {
            "redirect": f"/historical/aggregate-report?product_id={product_id}&round_number={round_number}&error=aggregate_ai_save_failed"
        }

    return {
        "redirect": f"/historical/aggregate-report?product_id={product_id}&round_number={round_number}&aggregate=ai_generated"
    }


def handle_historical_survey_report_publish_post(user_id, data):
    context_id = _posted_int(data.get("context_id"))
    action = str(_posted_scalar(data.get("action")) or "").strip().lower()
    return_to = str(_posted_scalar(data.get("return_to")) or "historical").strip().lower()
    product_id = _posted_int(data.get("product_id"))

    if not context_id:
        return {"redirect": "/historical?survey_publish=invalid_context"}

    if action == "publish":
        from app.db.historical import publish_historical_survey_report

        success = publish_historical_survey_report(context_id, user_id)
        status_key = "published"
    elif action == "withdraw":
        from app.db.historical import withdraw_historical_survey_report

        success = withdraw_historical_survey_report(context_id, user_id)
        status_key = "withdrawn"
    else:
        return {"redirect": f"/historical/context?context_id={context_id}&survey_publish=invalid_action"}

    if not success:
        status_key = "failed"

    if return_to == "product" and product_id:
        return {"redirect": f"/historical/product?product_id={product_id}&survey_publish={status_key}"}

    return {"redirect": f"/historical?survey_publish={status_key}"}


def handle_historical_aggregate_report_publish_post(user_id, data):
    product_id, round_number = _validate_historical_aggregate_target(data=data)
    if not product_id or not round_number:
        return {"redirect": "/historical?error=invalid_aggregate_target"}

    action = str(_posted_scalar(data.get("action")) or "").strip().lower()

    if action == "publish":
        from app.db.historical_aggregate_reports import publish_historical_aggregate_report

        success = publish_historical_aggregate_report(
            product_id=product_id,
            round_number=round_number,
            user_id=user_id,
        )
        status_key = "published"
    elif action == "withdraw":
        from app.db.historical_aggregate_reports import withdraw_historical_aggregate_report

        success = withdraw_historical_aggregate_report(
            product_id=product_id,
            round_number=round_number,
            user_id=user_id,
        )
        status_key = "withdrawn"
    else:
        return {"redirect": f"/historical/aggregate-report?product_id={product_id}&round_number={round_number}&error=invalid_action"}

    if not success:
        return {"redirect": f"/historical?error=aggregate_publish_failed"}

    return {
        "redirect": f"/historical/aggregate-report?product_id={product_id}&round_number={round_number}&aggregate={status_key}"
    }


def handle_historical_product_publish_post(user_id, data):
    product_id = _posted_int(data.get("product_id"))
    action = str(_posted_scalar(data.get("action")) or "").strip().lower()

    if not product_id:
        return {"redirect": "/historical?error=invalid_product"}

    if not _historical_product_has_legacy_lifecycle(product_id=product_id):
        return {"redirect": "/historical?error=invalid_product"}

    if action == "publish":
        from app.db.historical import publish_historical_product_lifecycle

        success = publish_historical_product_lifecycle(product_id, user_id)
    elif action == "withdraw":
        from app.db.historical import withdraw_historical_product_lifecycle

        success = withdraw_historical_product_lifecycle(product_id, user_id)
    else:
        return {"redirect": f"/historical/product?product_id={product_id}&error=invalid_action"}

    if not success:
        return {"redirect": "/historical?error=invalid_product"}

    return {"redirect": f"/historical/product?product_id={product_id}"}


def handle_historical_product_access_post(user_id, data):
    product_id = _posted_int(data.get("product_id"))
    action = str(_posted_scalar(data.get("action")) or "").strip().lower()

    if not product_id:
        return {"redirect": "/historical?error=invalid_product"}

    if not _historical_product_has_legacy_lifecycle(product_id=product_id):
        return {"redirect": "/historical?error=invalid_product"}

    if action == "grant":
        raw_email = str(_posted_scalar(data.get("target_email")) or "").strip()
        raw_role = str(_posted_scalar(data.get("access_role")) or "manual").strip() or "manual"

        from app.db.historical import grant_historical_product_publication_access_by_email

        result = grant_historical_product_publication_access_by_email(
            product_id=product_id,
            target_email=raw_email,
            granted_by_user_id=user_id,
            access_role=raw_role,
        )

        return {"redirect": f"/historical/product?product_id={product_id}&access={result}"}

    if action == "revoke":
        target_user_id = str(_posted_scalar(data.get("target_user_id")) or "").strip()
        if not target_user_id:
            return {"redirect": f"/historical/product?product_id={product_id}&access=missing_user"}

        from app.db.historical import revoke_historical_product_publication_access

        success = revoke_historical_product_publication_access(
            product_id=product_id,
            target_user_id=target_user_id,
            revoked_by_user_id=user_id,
        )

        result = "revoked" if success else "revoke_not_found"
        return {"redirect": f"/historical/product?product_id={product_id}&access={result}"}

    return {"redirect": f"/historical/product?product_id={product_id}&access=invalid_action"}


def render_historical_product_lifecycle_get(
    user_id,
    base_template,
    inject_nav,
    product_id,
    query_params=None,
    can_manage_publication=True,
):
    from app.db.historical import (
        get_historical_product_publication,
        get_historical_product_publication_access,
        get_historical_survey_report_publication_status,
        get_legacy_product_lifecycle,
    )

    lifecycle = get_legacy_product_lifecycle(product_id)
    if not lifecycle:
        return {"redirect": "/historical"}

    product = lifecycle.get("product") or {}
    rounds = lifecycle.get("rounds") or []

    internal = e(product.get("internal_name") or "-")
    market = e(product.get("market_name") or "-")
    product_type = e(product.get("product_type_display") or "-")
    business_group = e(product.get("business_group") or "-")

    round_count = len(rounds)
    survey_count = sum(int(round_group.get("context_count") or 0) for round_group in rounds)
    dataset_count = sum(int(round_group.get("dataset_count") or 0) for round_group in rounds)
    round_label = "round" if round_count == 1 else "rounds"
    survey_label = "survey" if survey_count == 1 else "surveys"
    dataset_label = "dataset" if dataset_count == 1 else "datasets"

    publication = get_historical_product_publication(product_id)
    publication_status = (publication or {}).get("status")
    is_published = publication_status == "published"
    access_grants = get_historical_product_publication_access(product_id) if can_manage_publication else []
    access_message_key = ""
    if query_params:
        raw_access_message = query_params.get("access", [""])
        access_message_key = raw_access_message[0] if isinstance(raw_access_message, list) and raw_access_message else ""

    access_messages = {
        "granted": "Access granted.",
        "revoked": "Access revoked.",
        "user_not_found": "No registered user was found for that email.",
        "missing_email": "Enter a registered email before granting access.",
        "publication_not_found": "Publish the product lifecycle before granting Product Team access.",
        "missing_user": "No user was selected for access removal.",
        "revoke_not_found": "That active access grant was not found.",
        "invalid_action": "That access action is not supported.",
    }
    access_message_html = ""
    if access_message_key in access_messages:
        access_message_class = "is-success" if access_message_key in ("granted", "revoked") else "is-warning"
        access_message_html = f"""
            <div class="historical-access-message {access_message_class}">
                {e(access_messages[access_message_key])}
            </div>
        """

    draft_delete_key = ""
    if query_params:
        raw_draft_delete = query_params.get("draft_delete", [""])
        draft_delete_key = raw_draft_delete[0] if isinstance(raw_draft_delete, list) and raw_draft_delete else ""

    draft_delete_messages = {
        "deleted": "Draft round deleted.",
        "has_data": "That draft cannot be deleted because survey data or generated report artifacts already exist.",
        "not_found": "That draft round was not found.",
        "invalid_context": "That draft round could not be identified.",
        "invalid_csrf": "This form expired. Please try again.",
    }
    draft_delete_notice_html = ""
    if draft_delete_key in draft_delete_messages:
        draft_delete_class = "is-success" if draft_delete_key == "deleted" else "is-warning"
        draft_delete_notice_html = f"""
            <div class="historical-access-message {draft_delete_class}">
                {e(draft_delete_messages[draft_delete_key])}
            </div>
        """ 

    if can_manage_publication:
        publish_csrf_token = generate_csrf_token(user_id)
        access_csrf_token = generate_csrf_token(user_id)

        if is_published:
            published_at = publication.get("published_at") or ""
            publication_status_html = f"""
                <div class="historical-publication-status is-published">
                    Published to Reporting & Insights
                </div>
                <div class="historical-muted">Published {e(str(published_at)) if published_at else ""}. Product Team visibility is limited to explicit report access.</div>
            """
            publication_action_html = f"""
                <form method="POST" action="/historical/product/publish" class="historical-publish-form">
                    <input type="hidden" name="csrf_token" value="{e(publish_csrf_token)}">
                    <input type="hidden" name="product_id" value="{e(str(product_id))}">
                    <input type="hidden" name="action" value="withdraw">
                    <button type="submit" class="historical-action-pill is-secondary">Withdraw</button>
                </form>
            """
        else:
            publication_status_html = """
                <div class="historical-publication-status is-draft">
                    Not published yet
                </div>
                <div class="historical-muted">Publishing will make this product lifecycle visible in Reporting & Insights. Product Team menu visibility requires explicit report access.</div>
            """
            publication_action_html = f"""
                <form method="POST" action="/historical/product/publish" class="historical-publish-form">
                    <input type="hidden" name="csrf_token" value="{e(publish_csrf_token)}">
                    <input type="hidden" name="product_id" value="{e(str(product_id))}">
                    <input type="hidden" name="action" value="publish">
                    <button type="submit" class="historical-action-pill">Publish Product Lifecycle</button>
                </form>
            """
    else:
        published_at = (publication or {}).get("published_at") or ""
        publication_status_html = f"""
            <div class="historical-publication-status is-published">
                Published report
            </div>
            <div class="historical-muted">Published {e(str(published_at)) if published_at else ""}</div>
        """
        publication_action_html = ""

    access_management_html = ""
    if can_manage_publication:
        if not is_published:
            access_management_html = f"""
            <section class="historical-access-card">
                <div>
                    <h3>Product Team report access</h3>
                    <p>Publish this product lifecycle before granting Product Team report access.</p>
                </div>
                {access_message_html}
            </section>
            """
        else:
            grant_rows_html = ""
            for grant in access_grants:
                target_user_id = grant.get("user_id") or ""
                first_name = grant.get("FirstName") or ""
                last_name = grant.get("LastName") or ""
                email = grant.get("Email") or ""
                access_role = grant.get("access_role") or "manual"
                display_name = " ".join(part for part in [first_name, last_name] if part).strip() or email

                grant_rows_html += f"""
                <tr>
                    <td>
                        <div class="historical-project-title">{e(display_name)}</div>
                        <div class="historical-muted">{e(email)}</div>
                    </td>
                    <td><span class="historical-lifecycle-pill">{e(access_role)}</span></td>
                    <td>
                        <form method="POST" action="/historical/product/access" class="historical-inline-form">
                            <input type="hidden" name="csrf_token" value="{e(access_csrf_token)}">
                            <input type="hidden" name="product_id" value="{e(str(product_id))}">
                            <input type="hidden" name="action" value="revoke">
                            <input type="hidden" name="target_user_id" value="{e(str(target_user_id))}">
                            <button type="submit" class="historical-action-pill is-secondary">Remove</button>
                        </form>
                    </td>
                </tr>
                """

            if not grant_rows_html:
                grant_rows_html = """
                <tr>
                    <td colspan="3">
                        <div class="historical-muted">No Product Team users have explicit access yet.</div>
                    </td>
                </tr>
                """

            access_management_html = f"""
            <section class="historical-access-card">
                <div class="historical-access-card-header">
                    <div>
                        <h3>Product Team report access</h3>
                        <p>Grant access to Product Team users who should see this report under their Reports & Summaries menu.</p>
                    </div>
                </div>

                {access_message_html}

                <form method="POST" action="/historical/product/access" class="historical-access-form">
                    <input type="hidden" name="csrf_token" value="{e(access_csrf_token)}">
                    <input type="hidden" name="product_id" value="{e(str(product_id))}">
                    <input type="hidden" name="action" value="grant">

                    <div class="historical-access-row">
                        <div class="historical-access-field">
                            <label>Registered user email</label>
                            <input type="email" name="target_email" class="form-input" placeholder="name@logitech.com" required>
                        </div>

                        <div class="historical-access-field">
                            <label>Access role</label>
                            <select name="access_role" class="form-input">
                                <option value="requestor">Requestor</option>
                                <option value="stakeholder">Stakeholder</option>
                                <option value="manual" selected>Manual viewer</option>
                            </select>
                        </div>

                        <div class="historical-access-action-field">
                            <button type="submit" class="historical-action-pill historical-access-submit">Grant Access</button>
                        </div>
                    </div>
                </form>

                <div class="table-scroll">
                    <table class="data-table historical-access-table">
                        <thead>
                            <tr>
                                <th>User</th>
                                <th>Role</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {grant_rows_html}
                        </tbody>
                    </table>
                </div>
            </section>
            """

    nav_html = _render_historical_subnav(
        active_key="product",
        product_id=product_id,
    ) if can_manage_publication else ""

    html = f"""
    <div class="results-section historical-page">
        <div class="historical-product-hero">
            <div>
                <h2>Product Lifecycle: {internal} <span class="historical-heading-muted">({market})</span></h2>
                <p class="historical-page-description">
                    Review this product across historical rounds so earlier findings are treated as iteration history,
                    not as equal-weight final product conclusions.
                </p>
            </div>
            <div class="historical-product-meta-card">
                <div><strong>{business_group}</strong> / {product_type}</div>
                <div>{round_count} {round_label}</div>
                <div>{survey_count} {survey_label} · {dataset_count} {dataset_label}</div>
                <div class="historical-product-publication-block">
                    {publication_status_html}
                    {publication_action_html}
                </div>
            </div>
        </div>

        {nav_html}
        {draft_delete_notice_html}

        <div class="historical-lifecycle-note">
            Product-level publishing is intentionally separate from round-level reports. The final product conclusion should
            preserve the sequence: what each round found, what changed afterward, and which findings remain current.
        </div>

        {access_management_html}
    """

    if not rounds:
        html += "<p>No historical rounds have been loaded for this product yet.</p>"
    else:
        html += "<div class='historical-product-round-list'>"

        for round_idx, round_group in enumerate(rounds, start=1):
            round_number = round_group.get("round_number")
            round_display = e(str(round_number)) if round_number is not None else "<span class='historical-warning-chip'>Needs round</span>"
            context_count = int(round_group.get("context_count") or 0)
            dataset_count = int(round_group.get("dataset_count") or 0)
            latest_context_id = round_group.get("latest_context_id")
            lifecycle_values = round_group.get("lifecycle_values") or []
            lifecycle_display = e(", ".join(lifecycle_values) if lifecycle_values else "-")

            survey_label = "survey" if context_count == 1 else "surveys"
            dataset_label = "dataset" if dataset_count == 1 else "datasets"
            round_summary = f"{context_count} {survey_label} ({dataset_count} {dataset_label})"

            survey_rows = ""
            for survey_idx, context in enumerate(round_group.get("contexts") or [], start=1):
                context_id = context.get("context_id")
                dataset_id = context.get("dataset_id")
                dataset_name = context.get("dataset_name") or "Untitled survey"
                purpose = context.get("trial_purpose") or "-"
                lifecycle_stage = context.get("lifecycle_stage") or "-"

                if dataset_id:
                    data_status = "<span class='historical-status-chip is-ready'>Data uploaded</span>"
                    raw_action = f"""
                        <a class="historical-action-pill is-secondary" href="/historical/raw?context_id={context_id}&dataset_id={dataset_id}">
                            Raw Data
                        </a>
                    """
                    delete_draft_action = ""
                else:
                    data_status = "<span class='historical-status-chip is-muted'>No data yet</span>"
                    raw_action = "<span class='historical-action-pill is-disabled'>Raw Data</span>"
                    delete_draft_action = (
                        _render_delete_draft_context_form(
                            context_id=context_id,
                            csrf_token=publish_csrf_token,
                        )
                        if can_manage_publication
                        else ""
                    )

                survey_rows += f"""
                    <tr>
                        <td>{survey_idx}</td>
                        <td>
                            <div class="historical-project-title">{e(dataset_name)}</div>
                            <div class="historical-muted">{e(purpose)}</div>
                        </td>
                        <td><span class="historical-lifecycle-pill">{e(lifecycle_stage)}</span></td>
                        <td>{data_status}</td>
                        <td>
                            <div class="historical-action-row">
                                {f'<a class="historical-action-pill" href="/historical/context?context_id={context_id}">Survey Report</a>' if can_manage_publication else '<span class="historical-action-pill is-disabled">Managed by UT</span>'}
                                {raw_action if can_manage_publication else ""}
                                {delete_draft_action}
                            </div>
                        </td>
                    </tr>
                """

            if can_manage_publication and context_count == 1 and latest_context_id:
                round_action_html = _render_survey_report_publication_actions(
                    context_id=latest_context_id,
                    dataset_count=dataset_count,
                    status=get_historical_survey_report_publication_status(latest_context_id),
                    csrf_token=publish_csrf_token,
                    return_to="product",
                    product_id=product_id,
                )
            elif can_manage_publication and latest_context_id:
                round_action_html = f'<a class="historical-action-pill" href="/historical/context?context_id={latest_context_id}" onclick="event.stopPropagation();">Latest Round Report</a>'
            else:
                round_action_html = ""

            html += f"""
            <details class="historical-project-card historical-product-round-card" {'open' if round_idx == len(rounds) else ''}>
                <summary class="historical-product-round-summary">
                    <span class="historical-project-caret" aria-hidden="true">▸</span>
                    <span class="historical-round-title">Round {round_display}</span>
                    <span class="historical-inline-text">{e(round_summary)}</span>
                    <span class="historical-project-cell is-centered"><span class="historical-lifecycle-pill">{lifecycle_display}</span></span>
                    <span class="historical-project-actions is-action-cell">
                        {round_action_html}
                    </span>
                </summary>

                <div class="historical-project-detail">
                    <div class="historical-project-detail-heading">
                        Survey contexts in this round
                    </div>
                    <div class="table-scroll">
                        <table class="data-table historical-survey-detail-table">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Survey</th>
                                    <th>Lifecycle</th>
                                    <th>Dataset</th>
                                    <th>Survey Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {survey_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </details>
            """

        html += "</div>"

    html += "</div>"

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def render_historical_product_taxonomy_get(
    user_id,
    base_template,
    inject_nav,
):
    from app.services.product_taxonomy_service import (
        build_product_taxonomy_audit,
        build_product_taxonomy_summary,
    )

    audit = build_product_taxonomy_audit()
    summary = build_product_taxonomy_summary()

    products_total = audit.get("products_total") or 0
    products_ready = audit.get("products_ready") or 0
    readiness_rate = audit.get("readiness_rate")

    readiness_display = "—"
    if readiness_rate is not None:
        readiness_display = f"{readiness_rate}%"

    product_types = audit.get("product_types") or []
    business_groups = audit.get("business_groups") or []
    missing_type = audit.get("products_missing_type") or []
    missing_business_group = audit.get("products_missing_business_group") or []
    limitations = audit.get("limitations") or []

    def _display(value, fallback="—"):
        if value is None:
            return fallback

        value = str(value).strip()
        return value if value else fallback

    def _product_name(product):
        internal_name = _display(product.get("internal_name"), "")
        market_name = _display(product.get("market_name"), "")

        if internal_name and market_name:
            return f"{internal_name} ({market_name})"

        if internal_name:
            return internal_name

        if market_name:
            return market_name

        return f"Product {product.get('product_id') or '—'}"

    html = f"""
    <div class="results-section historical-page">
        {_render_historical_subnav(active_key="taxonomy")}

        <h2 style="margin-bottom:6px;">
            Product Taxonomy Audit
        </h2>

        <p class="muted" style="margin-top:0;">
            Read-only audit of DB-backed product classification fields used by historical comparison.
            Product type and business group are never inferred from names.
        </p>

        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Comparison Readiness</h3>

            <div class="info-grid">
                <div class="info-row"><strong>Total Products:</strong> {e(products_total)}</div>
                <div class="info-row"><strong>Comparison Ready:</strong> {e(products_ready)}</div>
                <div class="info-row"><strong>Readiness Rate:</strong> {e(readiness_display)}</div>
                <div class="info-row"><strong>Product Types:</strong> {e(summary.get("product_type_count") or 0)}</div>
                <div class="info-row"><strong>Business Groups:</strong> {e(summary.get("business_group_count") or 0)}</div>
                <div class="info-row"><strong>Missing Product Type:</strong> {e(summary.get("missing_type_count") or 0)}</div>
                <div class="info-row"><strong>Missing Business Group:</strong> {e(summary.get("missing_business_group_count") or 0)}</div>
            </div>
        </div>
    """

    if limitations:
        html += """
        <div class="card" style="margin-top:16px; border-left:4px solid #f59e0b;">
            <h3 style="margin-top:0;">Limitations</h3>
            <ul style="margin-bottom:0;">
        """

        for limitation in limitations:
            html += f"<li>{e(limitation)}</li>"

        html += """
            </ul>
        </div>
        """

    html += """
        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Product Types</h3>
    """

    if not product_types:
        html += """
            <p class="muted" style="margin-bottom:0;">
                No product types found.
            </p>
        """
    else:
        html += """
            <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Product Type Key</th>
                        <th>Display</th>
                        <th>Products</th>
                        <th>Business Groups</th>
                    </tr>
                </thead>
                <tbody>
        """

        for row in product_types:
            html += f"""
                    <tr>
                        <td>{e(_display(row.get("product_type_key")))}</td>
                        <td>{e(_display(row.get("product_type_display")))}</td>
                        <td>{e(row.get("product_count") or 0)}</td>
                        <td>{e(", ".join(row.get("business_groups") or []))}</td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
            </div>
        """

    html += """
        </div>

        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Business Groups</h3>
    """

    if not business_groups:
        html += """
            <p class="muted" style="margin-bottom:0;">
                No business groups found.
            </p>
        """
    else:
        html += """
            <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Business Group</th>
                        <th>Products</th>
                        <th>Product Types</th>
                    </tr>
                </thead>
                <tbody>
        """

        for row in business_groups:
            html += f"""
                    <tr>
                        <td>{e(_display(row.get("business_group")))}</td>
                        <td>{e(row.get("product_count") or 0)}</td>
                        <td>{e(", ".join(row.get("product_types") or []))}</td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
            </div>
        """

    html += """
        </div>

        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Products Missing Product Type</h3>
    """

    if not missing_type:
        html += """
            <p class="muted" style="margin-bottom:0;">
                No products are missing product_type_key.
            </p>
        """
    else:
        html += """
            <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Product</th>
                        <th>Business Group</th>
                    </tr>
                </thead>
                <tbody>
        """

        for product in missing_type:
            html += f"""
                    <tr>
                        <td>{e(_product_name(product))}</td>
                        <td>{e(_display(product.get("business_group")))}</td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
            </div>
        """

    html += """
        </div>

        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Products Missing Business Group</h3>
    """

    if not missing_business_group:
        html += """
            <p class="muted" style="margin-bottom:0;">
                No products are missing business_group.
            </p>
        """
    else:
        html += """
            <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Product</th>
                        <th>Product Type</th>
                    </tr>
                </thead>
                <tbody>
        """

        for product in missing_business_group:
            product_type = product.get("product_type_display") or product.get("product_type_key")
            html += f"""
                    <tr>
                        <td>{e(_product_name(product))}</td>
                        <td>{e(_display(product_type))}</td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
            </div>
        """

    html += """
        </div>

    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def render_historical_comparison_get(
    user_id,
    base_template,
    inject_nav,
    context_id,
    query_params
):
    try:
        context_id = int(context_id)
    except (TypeError, ValueError):
        return {"redirect": "/historical"}

    if not _can_access_historical_context(
        user_id=user_id,
        context_id=context_id,
    ):
        return {"redirect": "/historical"}

    from app.services.historical_comparison_service import (
        build_historical_pattern_comparison,
    )

    comparison = build_historical_pattern_comparison(context_id)

    target = comparison.get("target_context") or {}
    comparison_basis = comparison.get("comparison_basis") or {}
    metric_comparison = comparison.get("metric_comparison") or {}
    target_metrics = metric_comparison.get("target") or {}
    baseline_metrics = metric_comparison.get("baseline") or {}
    deltas = metric_comparison.get("deltas") or {}
    matched_contexts = comparison.get("matched_contexts") or []
    match_summary = comparison.get("match_summary") or {}
    target_readiness = comparison.get("target_readiness") or {}
    comparison_scope = comparison.get("comparison_scope") or {}
    repeated_patterns = comparison.get("repeated_patterns") or []
    limitations = comparison.get("limitations") or []
    data_quality = comparison.get("data_quality") or {}

    def _display(value, fallback="—"):
        if value is None:
            return fallback

        value = str(value).strip()
        return value if value else fallback

    def _metric_value(value):
        if value is None:
            return "—"

        try:
            numeric_value = float(value)
            if numeric_value.is_integer():
                return str(int(numeric_value))
            return f"{numeric_value:.2f}"
        except (TypeError, ValueError):
            return str(value)

    target_name = _display(target.get("product_name"), "Unknown product")
    target_product_type = _display(target.get("product_type_display") or target.get("product_type_key"))
    target_business_group = _display(target.get("business_group"))
    target_lifecycle = _display(target.get("lifecycle_stage"))
    target_purpose = _display(target.get("trial_purpose"))

    target_taxonomy_ready = "Yes" if target_readiness.get("is_taxonomy_ready") else "No"
    target_missing_fields = ", ".join(target_readiness.get("missing_fields") or []) or "—"

    comparison_mode = _display(comparison_scope.get("mode"))
    recommendation_status = "Yes" if comparison_scope.get("generates_recommendations") else "No"

    tier = _display(comparison_basis.get("tier"))
    tier_reason = _display(comparison_basis.get("reason"), "No comparison basis available.")
    match_count = comparison_basis.get("match_count") or 0

    target_metric_count = data_quality.get("target_metric_count") or 0
    baseline_metric_count = data_quality.get("baseline_metric_count") or 0
    repeated_pattern_count = data_quality.get("repeated_pattern_count") or 0
    limitation_count = data_quality.get("limitation_count") or len(limitations)
    coverage_note = _display(
        data_quality.get("coverage_note"),
        "Comparison data is available.",
    )

    strong_match_count = match_summary.get("strong") or 0
    medium_match_count = match_summary.get("medium") or 0
    weak_match_count = match_summary.get("weak") or 0
    broad_match_count = match_summary.get("broad") or 0

    top_match_reasons = match_summary.get("top_reasons") or []
    top_match_reason_text = "—"

    if top_match_reasons:
        top_match_reason_text = ", ".join([
            f"{item.get('reason')} ({item.get('count')})"
            for item in top_match_reasons[:4]
            if item.get("reason")
        ]) or "—"

    html = f"""
    <div class="results-section historical-page historical-comparison-page">
        <div class="historical-product-hero">
            <div>
                <h2>Historical Pattern Comparison</h2>
                <p class="historical-page-description">
                    Read-only comparison using explicit DB-backed product taxonomy, historical metrics,
                    and saved historical insight rows. This page does not generate recommendations.
                </p>
            </div>
            <div class="historical-product-meta-card">
                <div><strong>{e(target_name)}</strong></div>
                <div>{e(target_business_group)} / {e(target_product_type)}</div>
                <div>{e(match_count)} matched contexts · {e(strong_match_count)} strong</div>
                <div>Recommendations: {e(recommendation_status)}</div>
            </div>
        </div>

        {_render_historical_subnav(
            active_key="comparison",
            context_id=context_id,
        )}

        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Target Trial</h3>

            <div class="info-grid">
                <div class="info-row"><strong>Product:</strong> {e(target_name)}</div>
                <div class="info-row"><strong>Product Type:</strong> {e(target_product_type)}</div>
                <div class="info-row"><strong>Business Group:</strong> {e(target_business_group)}</div>
                <div class="info-row"><strong>Lifecycle:</strong> {e(target_lifecycle)}</div>
                <div class="info-row"><strong>Purpose:</strong> {e(target_purpose)}</div>
                <div class="info-row"><strong>Taxonomy Ready:</strong> {e(target_taxonomy_ready)}</div>
                <div class="info-row"><strong>Missing Taxonomy Fields:</strong> {e(target_missing_fields)}</div>
                <div class="info-row"><strong>Mode:</strong> {e(comparison_mode)}</div>
                <div class="info-row"><strong>Generates Recommendations:</strong> {e(recommendation_status)}</div>
            </div>
        </div>

        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Comparison Basis</h3>

            <div class="info-grid">
                <div class="info-row"><strong>Tier:</strong> {e(tier)}</div>
                <div class="info-row"><strong>Matched Contexts:</strong> {e(match_count)}</div>
                <div class="info-row"><strong>Strong Matches:</strong> {e(strong_match_count)}</div>
                <div class="info-row"><strong>Medium Matches:</strong> {e(medium_match_count)}</div>
                <div class="info-row"><strong>Weak Matches:</strong> {e(weak_match_count)}</div>
                <div class="info-row"><strong>Broad Baseline:</strong> {e(broad_match_count)}</div>
            </div>

            <p class="muted" style="margin-bottom:8px;">
                {e(tier_reason)}
            </p>

            <p class="muted" style="margin-bottom:0;">
                <strong>Top match reasons:</strong> {e(top_match_reason_text)}
            </p>
        </div>

        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Data Coverage</h3>

            <div class="info-grid">
                <div class="info-row"><strong>Target Metrics Available:</strong> {e(target_metric_count)}</div>
                <div class="info-row"><strong>Baseline Metrics Available:</strong> {e(baseline_metric_count)}</div>
                <div class="info-row"><strong>Repeated Patterns Found:</strong> {e(repeated_pattern_count)}</div>
                <div class="info-row"><strong>Limitations Listed:</strong> {e(limitation_count)}</div>
            </div>

            <p class="muted" style="margin-bottom:0;">
                {e(coverage_note)}
            </p>
        </div>
    """

    if limitations:
        html += """
        <div class="card" style="margin-top:16px; border-left:4px solid #f59e0b;">
            <h3 style="margin-top:0;">Limitations</h3>
            <ul style="margin-bottom:0;">
        """

        for limitation in limitations:
            html += f"<li>{e(limitation)}</li>"

        html += """
            </ul>
        </div>
        """

    html += """
        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Matched Historical Contexts</h3>
    """

    if not matched_contexts:
        html += """
            <p class="muted" style="margin-bottom:0;">
                No comparable historical contexts were found.
            </p>
        """
    else:
        html += """
            <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Product</th>
                        <th>Type</th>
                        <th>BG</th>
                        <th>Lifecycle</th>
                        <th>Purpose</th>
                        <th>Strength</th>
                        <th>Reasons</th>
                        <th>Datasets</th>
                    </tr>
                </thead>
                <tbody>
        """

        for item in matched_contexts:
            reasons = ", ".join(item.get("match_reasons") or [])
            html += f"""
                    <tr>
                        <td>
                            <a href="/historical/context?context_id={item.get('context_id')}">
                                {e(_display(item.get("product_name")))}
                            </a>
                        </td>
                        <td>{e(_display(item.get("product_type_display") or item.get("product_type_key")))}</td>
                        <td>{e(_display(item.get("business_group")))}</td>
                        <td>{e(_display(item.get("lifecycle_stage")))}</td>
                        <td>{e(_display(item.get("trial_purpose")))}</td>
                        <td>{e(_display(item.get("match_strength")))}</td>
                        <td>{e(reasons)}</td>
                        <td>{e(item.get("dataset_count") or 0)}</td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
            </div>
        """

    html += """
        </div>
    """

    metric_rows = [
        ("Total Responses", "total_responses"),
        ("Survey 1 Responses", "survey_1_responses"),
        ("Survey 2 Responses", "survey_2_responses"),
        ("Completion Rate", "completion_rate"),
        ("Drop-off Rate", "drop_off_rate"),
        ("Avg Response Length", "avg_response_length"),
        ("Median Response Length", "median_response_length"),
        ("Empty Response Rate", "empty_response_rate"),
        ("Quant Question Count", "quant_question_count"),
        ("Qual Question Count", "qual_question_count"),
    ]

    html += """
        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Metric Comparison</h3>
            <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Target</th>
                        <th>Historical Baseline</th>
                        <th>Delta</th>
                    </tr>
                </thead>
                <tbody>
    """

    for label, key in metric_rows:
        html += f"""
                    <tr>
                        <td>{e(label)}</td>
                        <td>{e(_metric_value(target_metrics.get(key)))}</td>
                        <td>{e(_metric_value(baseline_metrics.get(key)))}</td>
                        <td>{e(_metric_value(deltas.get(key)))}</td>
                    </tr>
        """

    html += """
                </tbody>
            </table>
            </div>
        </div>
    """

    html += """
        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Repeated Historical Patterns</h3>
    """

    if not repeated_patterns:
        html += """
            <p class="muted" style="margin-bottom:0;">
                No repeated saved insight patterns were found across matched contexts.
            </p>
        """
    else:
        html += """
            <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Pattern</th>
                        <th>Contexts</th>
                        <th>Confidence</th>
                        <th>Insight Types</th>
                    </tr>
                </thead>
                <tbody>
        """

        for pattern in repeated_patterns:
            insight_types = ", ".join(pattern.get("insight_types") or [])
            html += f"""
                    <tr>
                        <td>{e(_display(pattern.get("pattern")))}</td>
                        <td>{e(pattern.get("source_context_count") or 0)}</td>
                        <td>{e(_display(pattern.get("confidence")))}</td>
                        <td>{e(insight_types)}</td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
            </div>
        """

    html += """
        </div>

    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def render_historical_raw_get(user_id, base_template, inject_nav, dataset_id, context_id):
    from app.db.historical import get_historical_answers_by_dataset

    try:
        context_id = int(context_id)
        dataset_id = int(dataset_id)
    except (TypeError, ValueError):
        return {"redirect": "/historical"}

    if not _can_access_historical_context(
        user_id=user_id,
        context_id=context_id,
    ):
        return {"redirect": "/historical"}

    if not _dataset_belongs_to_context(
        dataset_id=dataset_id,
        context_id=context_id,
    ):
        return {"redirect": "/historical"}

    # -------------------------
    # Fetch data
    # -------------------------
    rows = get_historical_answers_by_dataset(dataset_id)

    if not rows:
        html = f"""
        <div class="results-section historical-page">
            {_render_historical_subnav(
                active_key="raw",
                context_id=context_id,
                dataset_id=dataset_id,
            )}

            <p>No data found.</p>
        </div>
        """
        full_html = base_template.replace("__BODY__", html)
        full_html = inject_nav(full_html, mode="internal")
        return {"html": full_html}

    # -------------------------
    # Pivot: build structure
    # -------------------------
    responses = {}
    profile_questions = []
    survey_questions = []

    for r in rows:
        gid = r["response_group_id"]
        q = r["question_text"]
        a = r["answer_text"]

        if gid not in responses:
            responses[gid] = {}

        q_lower = q.lower()

        # Remove PII columns entirely
        if any(token in q_lower for token in ["name", "email"]):
            continue

        # Split profile vs survey
        if is_profile_question(q):
            if q not in profile_questions:
                profile_questions.append(q)
        else:
            if q not in survey_questions:
                survey_questions.append(q)

        responses[gid][q] = a

    # Stable ordering
    gid_list = sorted(responses.keys())

    # -------------------------
    # Build HTML
    # -------------------------
    html = f"""
    <div class="results-section historical-page">
        {_render_historical_subnav(
            active_key="raw",
            context_id=context_id,
            dataset_id=dataset_id,
        )}

        <h2>Reconstructed Survey (Raw Data)</h2>
    """

    # -------------------------
    # SURVEY TABLE
    # -------------------------
    if survey_questions:
        html += """
        <h3 style="margin-top:30px;">Survey Responses</h3>
        <div class="table-scroll">
        <table class="data-table">
            <thead>
                <tr>
                    <th>User</th>
        """

        for q in survey_questions:
            html += f"<th>{e(q)}</th>"

        html += "</tr></thead><tbody>"

        for idx, gid in enumerate(gid_list, start=1):
            html += f"<tr><td>User {idx}</td>"

            for q in survey_questions:
                val = responses[gid].get(q, "")
                html += f"<td>{e(val or '')}</td>"

            html += "</tr>"

        html += """
            </tbody>
        </table>
        </div>
        """

    html += "</div>"

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}

def build_profile_segments(responses, *, max_segments=5, min_segment_size=3):
    """
    Deterministic segmentation engine.

    Input:
    - responses: {response_group_id: {question_text: answer_text}}

    Output:
    - segments: list of segment dicts
    - outlier_ids: response_group_ids not covered by any selected segment
    """

    from itertools import combinations

    # -------------------------
    # Build normalized profile map
    # -------------------------
    user_profiles = {}

    for gid, answers in responses.items():
        profile = {}

        for q, val in answers.items():
            if not val:
                continue

            if not is_profile_question(q):
                continue

            clean_val = str(val).strip()
            if not clean_val:
                continue

            profile[q] = clean_val

        user_profiles[gid] = profile

    total_users = len(user_profiles)

    if total_users == 0:
        return [], []

    # -------------------------
    # Generate candidate segments
    # -------------------------
    candidates = []

    for dimension_count in [2]:
        buckets = {}

        for gid, profile in user_profiles.items():
            items = sorted(profile.items(), key=lambda x: x[0])

            for combo in combinations(items, dimension_count):
                key = tuple(combo)

                if key not in buckets:
                    buckets[key] = []

                buckets[key].append(gid)

        for key, member_ids in buckets.items():
            unique_members = sorted(set(member_ids))

            if len(unique_members) < min_segment_size:
                continue

            candidates.append({
                "attributes": key,
                "member_ids": unique_members,
                "user_ids": unique_members,   # 🔥 ADD THIS LINE (DO NOT REMOVE member_ids)
                "size": len(unique_members),
                "dimension_count": dimension_count,
            })

    # -------------------------
    # Rank candidates
    # Prefer:
    # 1. Larger groups
    # 2. More specific groups
    # 3. Deterministic attribute order
    # -------------------------
    candidates = sorted(
        candidates,
        key=lambda s: (
            -s["size"],
            -s["dimension_count"],
            str(s["attributes"])
        )
    )

    # -------------------------
    # Greedy selection to maximize coverage
    # -------------------------
    selected = []
    covered = set()

    for candidate in candidates:
        candidate_members = set(candidate["member_ids"])
        MIN_NEW_USERS = 3   # or 10% of total
        MIN_NEW_RATIO = 0.4   # 40% of segment must be new

        new_coverage = candidate_members - covered

        if len(new_coverage) < MIN_NEW_USERS:
            continue

        if len(new_coverage) / len(candidate_members) < MIN_NEW_RATIO:
            continue

        selected.append(candidate)
        covered.update(candidate_members)

        if len(selected) >= max_segments:
            break

    outlier_ids = sorted(set(user_profiles.keys()) - covered)

    return selected, outlier_ids

def is_followup_prompt(q: str) -> bool:
    q_clean = q.strip().lower()

    # must be a question
    if "?" not in q_clean:
        return False

    # short = generic follow-up (not real survey question)
    if len(q_clean) > 80:
        return False

    # contains "more detail" intent
    followup_markers = [
        "elaborate",
        "more",
        "anything",
        "else",
        "share",
        "expand"
    ]

    has_marker = any(m in q_clean for m in followup_markers)

    # exclude real questions that happen to contain "more"
    exclusion_markers = [
        "how",
        "what",
        "which",
        "rate",
        "feel",
        "experience",
        "version",
        "device",
        "color",
        "size",
        "weight",
        "connection"
    ]

    has_exclusion = any(e in q_clean for e in exclusion_markers)

    return has_marker and not has_exclusion

def build_sections_from_rows(rows):
    """
    Build survey sections deterministically.

    Section = consecutive numeric/categorical questions until a qualitative question.
    """

    # -------------------------
    # Build question map
    # -------------------------
    question_map = {}
    question_order = {}

    for r in rows:
        pos = r["question_position"]
        q = r["question_text"]
        val = r["answer_text"]

        if pos not in question_map:
            question_map[pos] = {
                "question": q,
                "values": [],
                "responses": [],
            }
            question_order[pos] = pos

        question_map[pos]["values"].append(val)
        question_map[pos]["responses"].append({
            "response_group_id": str(r.get("response_group_id") or ""),
            "answer": val,
            "answer_numeric": r.get("answer_numeric"),
        })

    # 🔥 TRUE ORDER (by position)
    ordered_positions = sorted(question_map.keys())

    # -------------------------
    # Build sections
    # -------------------------
    sections = []
    current = {
        "quant_questions": [],
        "qual_question": None
    }

    for pos in ordered_positions:

        q = question_map[pos]["question"]
        values = question_map[pos]["values"]

        # -------------------------
        # 🔥 SKIP PROFILE QUESTIONS
        # -------------------------
        if is_profile_question(q):
            continue

        q_lower = q.lower()

        if "agree to be contacted" in q_lower:
            continue

        # Keep all non-profile survey questions.
        # Balanced or unanimous answer distributions are still valid evidence;
        # filtering them here can hide Usage/KPI sections from reports.

        # 🔥 STRUCTURAL QUAL OVERRIDE
        if is_followup_prompt(q):
            q_type = "qualitative"
        else:
            q_type = classify(values)

        # -------------------------
        # Numeric + Categorical
        # -------------------------
        if q_type in ["numeric", "categorical"]:

            current["quant_questions"].append({
                "question": q,
                "values": values,
                "responses": question_map[pos].get("responses") or [],
                "type": q_type
            })

        # -------------------------
        # Qualitative → boundary
        # -------------------------
        elif q_type == "qualitative":


            if current["quant_questions"]:
                for qq in current["quant_questions"]:
                    pass

                current["qual_question"] = {
                    "question": q,
                    "values": values,
                    "responses": question_map[pos].get("responses") or [],
                }

                sections.append(current)

                current = {
                    "quant_questions": [],
                    "qual_question": None
                }


        # -------------------------
        # Safety fallback
        # -------------------------
        else:
            current["quant_questions"].append({
                "question": q,
                "values": values,
                "responses": question_map[pos].get("responses") or [],
                "type": "unknown"
            })

    # -------------------------
    # trailing section
    # -------------------------
    if current["quant_questions"]:
        sections.append(current)

    return sections

def classify_question_type(answer_values):
    numeric_count = 0
    text_count = 0

    for v in answer_values:
        if v is None:
            continue

        v = str(v).strip()

        # numeric (1–5, etc.)
        if v.replace(".", "", 1).isdigit():
            numeric_count += 1
        else:
            text_count += 1

    if numeric_count > text_count:
        return "quant"
    else:
        return "qual"
    
# -------------------------
# Helper: classify profile questions
# -------------------------
def is_profile_question(q: str) -> bool:
    import re

    if not q:
        return False

    q = q.lower().strip()

    # -------------------------
    # Core profile signals (stable traits)
    # -------------------------
    keyword_signals = [
        "gender",
        "age",
        "country",
        "city",
        "region",
        "location",
        "occupation",
        "role",
        "industry",
        "os",
        "operating system"
    ]

    # -------------------------
    # Phrase patterns (intent-based)
    # -------------------------
    phrase_patterns = [
        r"\bwhere are you\b",
        r"\bwhere do you live\b",
        r"\bwhere are you from\b",
        r"\bwhat country\b",
        r"\bwhich country\b",
        r"\bwhat region\b",
        r"\blocation\b",
        r"\bhow often do you\b",
        r"\bwhat kind of\b",
        r"\bwhat platform do you use\b",
        r"\bwhich oss?\b",
        r"\bwhat oss?\b",
        r"\bwhich operating systems?\b",
        r"\bwhat operating systems?\b",
        r"\bwhat device did you connect\b",
        r"\bhave you ever used\b",
        r"\bcan you describe any scenario\b",
    ]

    # -------------------------
    # Keyword match (strict word boundary)
    # -------------------------
    if any(re.search(rf"\b{re.escape(k)}\b", q) for k in keyword_signals):
        return True

    # -------------------------
    # Phrase match (looser intent)
    # -------------------------
    if any(re.search(p, q) for p in phrase_patterns):
        return True

    return False


def generate_historical_section_swot_summary(*, section: dict, debug_callback=None) -> str | None:
    """
    Generate the Historical SWOT summary for one section.

    This is intentionally the same analysis method used by Historical reports:
    section questions provide context, and the qualitative follow-up responses
    are the source material for SWOT generation.

    debug_callback is optional and is used by Product Trial diagnostics only.
    Historical callers do not pass it, so Historical behavior stays unchanged.
    """

    from app.services.ai_service import call_ai

    def _debug(message: str, **fields) -> None:
        if callable(debug_callback):
            try:
                debug_callback(message, **fields)
            except Exception:
                pass

    qual = section.get("qual_question")

    if not qual:
        _debug(
            "historical_swot_skipped_no_qual",
            section_name=section.get("section_name"),
        )
        return None

    raw_values = qual.get("values", [])

    answers = [str(v).strip() for v in raw_values if v and str(v).strip()]

    if not answers:
        _debug(
            "historical_swot_skipped_no_answers",
            section_name=section.get("section_name"),
            qual_question=qual.get("question"),
            raw_value_count=len(raw_values or []),
        )
        return None

    answer_block = "\n".join(f"- {a}" for a in answers[:30])

    # 🔥 include section questions as context
    quant_questions = [q["question"] for q in section["quant_questions"]]

    context_block = "\n".join(f"- {q}" for q in quant_questions)

    prompt = f"""
        You are analyzing user feedback for a product survey section.

        SECTION QUESTIONS:
        {context_block}

        Return a SWOT analysis in JSON format:

        {{
        "strengths": ["..."],
        "weaknesses": ["..."],
        "opportunities": ["..."],
        "threats": ["..."]
        }}

        Definitions:
        - Strengths = what users consistently like
        - Weaknesses = what users consistently dislike
        - Opportunities = improvements or feature ideas
        - Threats = risks, frustrations that could lead to churn, or competitive disadvantages

        Rules:
        - Each item must be short (1 sentence max)
        - No markdown
        - No formatting symbols
        - No extra text outside JSON
        - Max 5 items per category

        IMPORTANT:
        Only consider feedback relevant to the SECTION QUESTIONS.

        User Responses:
        {answer_block}
        """

    _debug(
        "historical_swot_ai_call_start",
        section_name=section.get("section_name"),
        quant_question_count=len(quant_questions),
        answer_count=len(answers),
        prompt_length=len(prompt),
    )

    ai_result = call_ai(
        prompt=prompt,
        temperature=0.3,
        max_tokens=800
    )

    summary = (
        ai_result.get("content")
        or ai_result.get("response")
        or ""
    ).strip()

    _debug(
        "historical_swot_ai_call_result",
        section_name=section.get("section_name"),
        success=ai_result.get("success"),
        error=ai_result.get("error"),
        response_length=len(summary),
    )

    if not ai_result.get("success"):
        return None

    # 🔥 Robust extraction (handles both schemas)
    return summary or None


def classify(values):

    cleaned = [str(v).strip() for v in values if v]

    if not cleaned:
        return "qualitative"

    unique_vals = set(cleaned)

    # -------------------------
    # Numeric
    # -------------------------
    numeric_count = sum(
        1 for v in cleaned if v.replace(".", "", 1).isdigit()
    )

    if numeric_count >= len(cleaned) * 0.7:
        return "numeric"

    # -------------------------
    # Categorical (multi-choice)
    # -------------------------
    # repeated values, limited variety
    if len(unique_vals) <= 8 and len(cleaned) >= 5:
        return "categorical"

    # -------------------------
    # Qualitative (free text)
    # -------------------------
    return "qualitative"

def _generate_historical_section_names(*, dataset_id):
    from app.db.historical import get_historical_answers_by_dataset, upsert_section_name
    from app.services.ai_service import call_ai

    def _clean_ai_section_name(value: object) -> str:
        name = " ".join(str(value or "").strip().split())
        if not name:
            return ""

        name = name.strip("\"'` ")
        name = name.replace(".", "").replace(":", "").replace(";", "").strip()

        if not name:
            return ""

        words = name.split()
        if len(words) > 6:
            name = " ".join(words[:6]).strip()

        return name

    rows = get_historical_answers_by_dataset(dataset_id)
    rows = sorted(rows, key=lambda r: (r["question_position"], r["response_group_id"]))
    sections = build_sections_from_rows(rows)

    for idx, section in enumerate(sections, start=1):
        questions = [q["question"] for q in section["quant_questions"]]

        if not questions:
            qual = section.get("qual_question")
            if qual and qual.get("question"):
                questions = [qual["question"]]

        if not questions:
            continue

        question_block = "\n".join(f"- {q}" for q in questions)

        prompt = f"""
You are naming ONE survey section.

Given only these section questions, return a SHORT section name.

Rules:
- Return only the section name
- 2-4 words preferred
- 6 words maximum
- Title Case
- No punctuation
- No explanation
- Do not mention survey, section, users, or feedback unless that is the actual topic

Section questions:
{question_block}
"""

        ai_result = call_ai(
            prompt=prompt,
            temperature=0.1,
            max_tokens=500
        )

        name = ""
        if ai_result.get("success"):
            name = _clean_ai_section_name(
                ai_result.get("response")
                or ai_result.get("content")
                or ""
            )

        if not name:
            retry_prompt = f"""
Name this ONE survey section.

Return only a concise Title Case name, 2-4 words.

Questions:
{question_block}
"""
            retry_result = call_ai(
                prompt=retry_prompt,
                temperature=0,
                max_tokens=500
            )

            if retry_result.get("success"):
                name = _clean_ai_section_name(
                    retry_result.get("response")
                    or retry_result.get("content")
                    or ""
                )

        if not name:
            continue

        upsert_section_name(dataset_id, idx, name)


def _generate_historical_section_summaries(*, dataset_id):
    from app.db.historical import (
        get_historical_answers_by_dataset,
        upsert_section_summary,
    )
    from app.services.product_trial_report_service import (
        _generate_comment_buckets,
        _section_bucket_response_rows,
    )

    rows = get_historical_answers_by_dataset(dataset_id)
    rows = sorted(rows, key=lambda r: (r["question_position"], r["response_group_id"]))

    sections = build_sections_from_rows(rows)

    for idx, section in enumerate(sections, start=1):
        summary = generate_historical_section_swot_summary(section=section)

        if not summary:
            continue

        summary_payload = _historical_section_summary_payload(summary)
        if not summary_payload:
            upsert_section_summary(dataset_id, idx, summary)
            continue

        section_for_buckets = dict(section or {})
        section_for_buckets["section_name"] = summary_payload.get("section_name") or f"Section {idx}"
        section_for_buckets["_bucket_response_rows"] = _section_bucket_response_rows(section_for_buckets)

        comment_buckets = _generate_comment_buckets(section_for_buckets)
        if comment_buckets:
            summary_payload["comment_buckets"] = comment_buckets

        upsert_section_summary(
            dataset_id,
            idx,
            json.dumps(summary_payload, ensure_ascii=False),
        )


def _generate_historical_context_insights(*, context_id):
    from app.services.historical_insights import (
        generate_trial_insights,
        generate_ai_insights
    )

    generate_trial_insights(context_id)
    generate_ai_insights(context_id)


def handle_historical_generate_report_post(*, user_id, data):
    context_id, dataset_id = _validate_historical_context_dataset_target(
        user_id=user_id,
        data=data,
    )
    if not context_id or not dataset_id:
        return {"redirect": "/historical"}

    _generate_historical_section_names(dataset_id=dataset_id)
    _generate_historical_section_summaries(dataset_id=dataset_id)
    _generate_historical_context_insights(context_id=context_id)

    return {
        "redirect": f"/historical/context?context_id={context_id}"
    }