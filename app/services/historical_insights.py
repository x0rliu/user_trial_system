# app/services/historical_insights.py

import json

from app.db.historical import (
    get_historical_answers_by_context,
    insert_historical_insight_run,
    insert_historical_trial_insight
)


# -------------------------
# SERVICE: Generate Trial Insights
# -------------------------
def generate_trial_insights(context_id):
    """
    Generates AI insights for a trial.
    Snapshot-based. No GET usage. Fully persisted.
    """

    rows = get_historical_answers_by_context(context_id)

    if not rows:
        return

    # -------------------------
    # Step 1: Create insight run
    # -------------------------
    insight_run_id = insert_historical_insight_run(
        context_id=context_id,
        trigger_type="ingestion",
        generation_version="v1"
    )

    # -------------------------
    # Step 2: Basic section grouping (simple for now)
    # -------------------------
    # NOTE: This is intentionally simple and deterministic.
    # We are NOT doing AI section inference yet.

    sections = {
        "overall": []
    }

    for r in rows:
        sections["overall"].append(r)

    # -------------------------
    # Step 3: Generate Insights (non-AI placeholder for now)
    # -------------------------
    # IMPORTANT: We are NOT calling AI yet.
    # We first build a deterministic structure.

    for section_name, section_rows in sections.items():

        # Sample size
        sample_size = len(set(r["response_group_id"] for r in section_rows))

        # Extract qualitative answers
        qualitative = [
            r["answer_text"]
            for r in section_rows
            if r["answer_text"] and r["answer_numeric"] is None
        ]

        # Take first N quotes (simple deterministic selection)
        quotes = qualitative[:5]

        insight_summary = "Initial insight placeholder. AI generation not yet implemented."

        insight_json = {
            "summary": insight_summary,
            "supporting_quotes": quotes,
            "sample_size": sample_size
        }

        insert_historical_trial_insight(
            insight_run_id=insight_run_id,
            context_id=context_id,
            section_name=section_name,
            insight_type="summary",
            insight_summary=insight_summary,
            insight_json=json.dumps(insight_json),
            source_sample_size=sample_size,
            filters_applied=None
        )