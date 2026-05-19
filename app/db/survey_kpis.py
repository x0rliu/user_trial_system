# app/db/survey_kpis.py

from __future__ import annotations

import re
from decimal import Decimal

import mysql.connector

from app.config.config import DB_CONFIG


_EXCLUDED_PRODUCT_KPI_SURVEY_TYPE_IDS = {
    "UTSurveyType0001",  # Recruiting
    "UTSurveyType0027",  # Consolidated/internal results
    "UTSurveyType0028",  # Report issue
    "UTSurveyType1001",  # Survey 1 / OOBE / first impression
}


_QUALITY_REASON_KEYWORDS = (
    "quality issue",
    "major quality",
    "functional hurdle",
    "functionality issue",
    "not working",
    "doesn't work",
    "does not work",
    "didn't work",
    "did not work",
    "stopped working",
    "broken",
    "defect",
    "defective",
    "bug",
    "bugs",
    "crash",
    "crashes",
    "crashed",
    "disconnect",
    "disconnects",
    "disconnected",
    "connection issue",
    "pairing issue",
    "lag",
    "latency",
    "delay",
    "unusable",
    "critical usability",
    "firmware",
    "hardware issue",
    "software issue",
)


_YES_VALUES = {"yes", "y", "true", "1"}
_NO_VALUES = {"no", "n", "false", "0"}


def _normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _to_float(value: object) -> float | None:
    if value is None:
        return None

    if isinstance(value, Decimal):
        return float(value)

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_yes(value: object) -> bool:
    text = _normalize_text(value)
    return text in _YES_VALUES or text.startswith("yes ") or text.startswith("yes,")


def _is_no(value: object) -> bool:
    text = _normalize_text(value)
    return text in _NO_VALUES or text.startswith("no ") or text.startswith("no,")


def _has_quality_issue_reason(text_values: list[str]) -> bool:
    combined = _normalize_text(" ".join(v for v in text_values if v))
    if not combined:
        return False

    return any(keyword in combined for keyword in _QUALITY_REASON_KEYWORDS)


def _is_product_kpi_survey_type(survey_type_id: object) -> bool:
    return str(survey_type_id or "").strip() not in _EXCLUDED_PRODUCT_KPI_SURVEY_TYPE_IDS


def _is_star_rating_question(question_text: object) -> bool:
    q = _normalize_text(question_text)
    if not q:
        return False

    if "software" in q:
        return False

    if "star rating" in q:
        return True

    if "how would you rate this product" in q:
        return True

    if "how would you rate the product" in q:
        return True

    if re.search(r"\brate (this|the) product\b", q):
        return True

    return False


def _is_software_rating_question(question_text: object) -> bool:
    q = _normalize_text(question_text)
    if not q or "software" not in q:
        return False

    if "software rating" in q:
        return True

    if "software experience" in q and "rate" in q:
        return True

    if "rate the software" in q:
        return True

    if "rate your software" in q:
        return True

    return False


def _is_nps_question(question_text: object) -> bool:
    q = _normalize_text(question_text)
    if not q or "recommend" not in q:
        return False

    if "software" in q:
        return False

    has_product_target = "this product" in q or "the product" in q or "this device" in q or "the device" in q
    has_nps_audience = "colleague" in q or "friend" in q

    return has_product_target and has_nps_audience


def _is_hurdles_question(question_text: object) -> bool:
    q = _normalize_text(question_text)
    if not q:
        return False

    if "functional hurdles" in q:
        return True

    return (
        "features not working" in q
        and "critical usability" in q
        and "quality issues" in q
    )


def _is_ready_question(question_text: object) -> bool:
    q = _normalize_text(question_text)
    if not q:
        return False

    if "ready for sales" in q:
        return True

    if "ready for market release" in q:
        return True

    if "ready for a market release" in q:
        return True

    if "ready for market" in q:
        return True

    return False


def _is_qualitative_followup_question(question_text: object) -> bool:
    q = _normalize_text(question_text)
    if not q:
        return False

    return (
        "elaborate" in q
        or "tell us why" in q
        or "tell us more" in q
        or "share a little" in q
        or "comments" in q
    )


def _average_for_metric(rows: list[dict], question_matcher, *, min_score: float, max_score: float) -> tuple[float | None, int]:
    values: list[float] = []

    for row in rows:
        if not _is_product_kpi_survey_type(row.get("SurveyTypeID")):
            continue

        if not question_matcher(row.get("QuestionText")):
            continue

        score = _to_float(row.get("AnswerNumeric"))
        if score is None:
            continue

        if min_score <= score <= max_score:
            values.append(score)

    if not values:
        return None, 0

    return round(sum(values) / len(values), 2), len(values)


def _nps_for_rows(rows: list[dict]) -> dict:
    scores: list[float] = []

    for row in rows:
        if not _is_product_kpi_survey_type(row.get("SurveyTypeID")):
            continue

        if not _is_nps_question(row.get("QuestionText")):
            continue

        score = _to_float(row.get("AnswerNumeric"))
        if score is None:
            continue

        if 0 <= score <= 10:
            scores.append(score)

    if not scores:
        return {
            "nps": None,
            "nps_count": 0,
            "nps_promoters": 0,
            "nps_passives": 0,
            "nps_detractors": 0,
        }

    total = len(scores)
    promoters = len([s for s in scores if s >= 9])
    detractors = len([s for s in scores if s <= 6])
    passives = total - promoters - detractors

    pct_promoters = (promoters / total) * 100
    pct_detractors = (detractors / total) * 100

    return {
        "nps": round(pct_promoters - pct_detractors),
        "nps_count": total,
        "nps_promoters": promoters,
        "nps_passives": passives,
        "nps_detractors": detractors,
    }


def _ready_for_sales_for_rows(rows: list[dict]) -> dict:
    by_distribution: dict[int, list[dict]] = {}

    for row in rows:
        if not _is_product_kpi_survey_type(row.get("SurveyTypeID")):
            continue

        distribution_id = row.get("DistributionID")
        if distribution_id is None:
            continue

        by_distribution.setdefault(int(distribution_id), []).append(row)

    ready_count = 0
    total_count = 0
    blocked_count = 0
    invalid_no_reason_count = 0

    for answer_rows in by_distribution.values():
        answer_rows.sort(key=lambda r: int(r.get("AnswerID") or 0))

        hurdles_answer = None
        ready_answer = None
        ready_answer_index = None
        ready_answer_id = None

        for idx, row in enumerate(answer_rows):
            q_text = row.get("QuestionText")

            if hurdles_answer is None and _is_hurdles_question(q_text):
                hurdles_answer = row.get("AnswerValue")

            if ready_answer is None and _is_ready_question(q_text):
                ready_answer = row.get("AnswerValue")
                ready_answer_index = idx
                ready_answer_id = int(row.get("AnswerID") or 0)

        if hurdles_answer is None and ready_answer is None:
            continue

        total_count += 1

        if _is_no(hurdles_answer):
            ready_count += 1
            continue

        if _is_yes(ready_answer):
            ready_count += 1
            continue

        if _is_no(ready_answer):
            followup_text_values: list[str] = []

            for idx, row in enumerate(answer_rows):
                answer_value = str(row.get("AnswerValue") or "").strip()
                if not answer_value:
                    continue

                if _to_float(row.get("AnswerNumeric")) is not None:
                    continue

                is_after_ready = False
                if ready_answer_index is not None and idx > ready_answer_index:
                    is_after_ready = True
                elif ready_answer_id is not None and int(row.get("AnswerID") or 0) > ready_answer_id:
                    is_after_ready = True

                if is_after_ready or _is_qualitative_followup_question(row.get("QuestionText")):
                    followup_text_values.append(answer_value)

            if _has_quality_issue_reason(followup_text_values):
                blocked_count += 1
                continue

            invalid_no_reason_count += 1
            ready_count += 1
            continue

        # If the respondent hit the hurdles KPI but did not answer readiness,
        # count it as not-ready only when the hurdle answer itself is explicitly yes.
        if _is_yes(hurdles_answer):
            blocked_count += 1
            continue

        # If the available answer cannot be interpreted, remove it from the KPI denominator.
        total_count -= 1

    ready_for_sales = None
    if total_count > 0:
        ready_for_sales = round((ready_count / total_count) * 100, 1)

    return {
        "ready_for_sales": ready_for_sales,
        "ready_for_sales_count": total_count,
        "ready_for_sales_ready_count": ready_count,
        "ready_for_sales_blocked_count": blocked_count,
        "ready_for_sales_invalid_no_reason_count": invalid_no_reason_count,
    }


def get_round_product_kpis(round_id: int) -> dict:
    """
    Derive Product KPIs for a round from stored survey_answers rows.

    KPI rules:
    - Star Rating: average 1-5 product star/rating question.
    - Software Rating: average 1-5 software rating question, if present.
    - NPS: standard 0-10 recommendation score, % promoters minus % detractors.
    - Ready for Sales: respondent-level pass/fail metric using the current two-question model,
      with legacy one-question support when only a ready-for-sales/market-release answer exists.

    The helper is read-only. It never mutates state from a GET render path.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                AnswerID,
                SurveyID,
                DistributionID,
                user_id,
                SurveyTypeID,
                QuestionText,
                AnswerValue,
                AnswerNumeric
            FROM survey_answers
            WHERE RoundID = %s
            ORDER BY DistributionID ASC, AnswerID ASC
            """,
            (int(round_id),),
        )

        rows = cursor.fetchall()

    finally:
        conn.close()

    star_rating, star_rating_count = _average_for_metric(
        rows,
        _is_star_rating_question,
        min_score=1,
        max_score=5,
    )
    software_rating, software_rating_count = _average_for_metric(
        rows,
        _is_software_rating_question,
        min_score=1,
        max_score=5,
    )

    nps_payload = _nps_for_rows(rows)
    ready_payload = _ready_for_sales_for_rows(rows)

    return {
        "star_rating": star_rating,
        "star_rating_count": star_rating_count,
        "software_rating": software_rating,
        "software_rating_count": software_rating_count,
        **nps_payload,
        **ready_payload,
    }