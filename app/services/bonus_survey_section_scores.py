def _safe_to_float(val):
    """
    Convert value to float if possible.
    Returns None if not numeric.
    """
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def build_bonus_survey_section_scores(payload: dict) -> dict:
    """
    Build quantitative scores per section.

    Rules:
    - Only numeric answers are considered
    - Non-numeric answers are ignored
    - Returns:
        - section-level average
        - question-level averages
    """

    sections = payload.get("sections", {})

    results = []

    for section_key, entries in sections.items():

        # -------------------------
        # Group values by question
        # -------------------------
        question_map = {}

        for item in entries:
            q_hash = item.get("question_hash")
            q_text = (item.get("question_text") or "").strip()

            val = _safe_to_float(item.get("answer_text"))
            if val is None:
                continue

            if q_hash not in question_map:
                question_map[q_hash] = {
                    "question_text": q_text,
                    "values": []
                }

            question_map[q_hash]["values"].append(val)

        # -------------------------
        # Compute per-question scores
        # -------------------------
        question_scores = []

        for q_hash, data in question_map.items():
            question = data["question_text"]
            values = data["values"]
            avg = round(sum(values) / len(values), 2)

            question_scores.append({
                "question_text": question,
                "avg_score": avg,
                "response_count": len(values)
            })

        # -------------------------
        # Compute section score (unchanged behavior)
        # -------------------------
        all_values = [v for vals in question_map.values() for v in vals]

        if all_values:
            avg_score = round(sum(all_values) / len(all_values), 2)
            count = len(all_values)
        else:
            avg_score = None
            count = 0

        results.append({
            "section_key": section_key,
            "metrics": {
                "avg_score": avg_score,
                "response_count": count,
                "questions": question_scores   # ✅ NEW (non-breaking)
            }
        })

    return {
        "success": True,
        "sections": results
    }