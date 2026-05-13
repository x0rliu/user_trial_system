# app/services/historical_metrics.py

from collections import defaultdict
from statistics import median

from app.db.historical import (
    get_historical_answers_by_context,
    upsert_historical_trial_metrics
)


# -------------------------
# SERVICE: Compute Trial Metrics
# -------------------------
def compute_trial_metrics(context_id):
    """
    Computes deterministic metrics for a given trial (context_id).
    Fully recomputable. No AI. No guessing.
    """

    rows = get_historical_answers_by_context(context_id)

    if not rows:
        return

    # -------------------------
    # Group by response_group_id
    # -------------------------
    responses = defaultdict(list)

    for r in rows:
        responses[r["response_group_id"]].append(r)

    total_responses = len(responses)

    # -------------------------
    # Build dataset → users map
    # -------------------------
    dataset_users = {}
    required_dataset_types = set()

    for r in rows:
        dataset_type = (r.get("dataset_type") or "").strip()
        response_group_id = r["response_group_id"]

        if not dataset_type:
            continue

        if dataset_type not in dataset_users:
            dataset_users[dataset_type] = set()

        dataset_users[dataset_type].add(response_group_id)

        try:
            is_required = int(r.get("is_required_for_completion") or 0)
        except (TypeError, ValueError):
            is_required = 0

        if is_required == 1:
            required_dataset_types.add(dataset_type)

    dataset_response_counts = {
        dataset_type: len(users)
        for dataset_type, users in dataset_users.items()
    }

    survey_1_responses = None
    survey_2_responses = None

    for dataset_type, response_count in dataset_response_counts.items():
        normalized_dataset_type = dataset_type.lower()

        if "survey 1" in normalized_dataset_type or "survey_1" in normalized_dataset_type:
            survey_1_responses = max(survey_1_responses or 0, response_count)

        if "survey 2" in normalized_dataset_type or "survey_2" in normalized_dataset_type:
            survey_2_responses = max(survey_2_responses or 0, response_count)

    # -------------------------
    # Completion / Drop-off
    # -------------------------
    required_sets = [
        dataset_users.get(dataset_type, set())
        for dataset_type in sorted(required_dataset_types)
    ]

    completed = set()

    if required_sets and all(required_sets):
        completed = set.intersection(*required_sets)

    completion_rate = None
    drop_off_rate = None

    if total_responses > 0 and required_sets:
        completion_rate = (len(completed) / total_responses) * 100
        drop_off_rate = 100 - completion_rate

    # -------------------------
    # Timing
    # -------------------------
    timestamps = [
        r["response_submitted_at"]
        for r in rows
        if r["response_submitted_at"] is not None
    ]

    first_response_at = min(timestamps) if timestamps else None
    last_response_at = max(timestamps) if timestamps else None

    response_window_days = None
    if first_response_at and last_response_at:
        response_window_days = (last_response_at - first_response_at).days

    # -------------------------
    # Response Length
    # -------------------------
    lengths = []
    empty_count = 0
    total_answers = 0

    for r in rows:
        answer = r["answer_text"]

        if answer is None or str(answer).strip() == "":
            empty_count += 1
            continue

        total_answers += 1
        lengths.append(len(str(answer).split()))

    avg_response_length = None
    median_response_length = None

    if lengths:
        avg_response_length = sum(lengths) / len(lengths)
        median_response_length = median(lengths)

    empty_response_rate = None
    if total_answers + empty_count > 0:
        empty_response_rate = (empty_count / (total_answers + empty_count)) * 100

    # -------------------------
    # Question Composition
    # -------------------------
    question_types = {}

    for r in rows:
        q_hash = r["question_hash"]

        if not q_hash:
            continue

        if q_hash not in question_types:
            question_types[q_hash] = {
                "has_numeric": False,
                "has_answer": False,
            }

        if r["answer_numeric"] is not None:
            question_types[q_hash]["has_numeric"] = True

        answer = r["answer_text"]
        if answer is not None and str(answer).strip() != "":
            question_types[q_hash]["has_answer"] = True

    quant_count = 0
    qual_count = 0

    for q_info in question_types.values():
        if q_info["has_numeric"]:
            quant_count += 1
        else:
            qual_count += 1

    # -------------------------
    # Build metrics dict
    # -------------------------
    metrics = {
        "total_responses": total_responses,
        "survey_1_responses": survey_1_responses,
        "survey_2_responses": survey_2_responses,
        "completion_rate": completion_rate,
        "drop_off_rate": drop_off_rate,
        "first_response_at": first_response_at,
        "last_response_at": last_response_at,
        "response_window_days": response_window_days,
        "trial_start_date": None,
        "trial_end_date": None,
        "avg_response_length": avg_response_length,
        "median_response_length": median_response_length,
        "empty_response_rate": empty_response_rate,
        "quant_question_count": quant_count,
        "qual_question_count": qual_count,
        "generation_version": "v3"
    }

    # -------------------------
    # Persist
    # -------------------------
    upsert_historical_trial_metrics(context_id, metrics)