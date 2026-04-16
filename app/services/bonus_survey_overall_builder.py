# app/services/bonus_survey_overall_builder.py

from collections import defaultdict


def _is_numeric(val: str) -> bool:
    if not val:
        return False
    val = val.strip()
    return val.isdigit()


def build_overall_summary(payload: dict):
    """
    Build:
    - Overall score (from rating questions)
    - Lightweight summary signals (non-AI)
    """

    responses = payload.get("responses", [])

    if not responses:
        return {
            "success": False,
            "overall_score": None,
            "summary": "No responses available."
        }

    # -------------------------
    # Collect numeric scores
    # -------------------------
    scores = []

    # -------------------------
    # Collect simple signals
    # -------------------------
    support_channels = defaultdict(int)
    issue_frequency = defaultdict(int)

    for r in responses:
        for a in r.get("answers", []):
            q = (a.get("question_text") or "").lower()
            text = a.get("answer_text")

            if not text:
                continue

            text_clean = text.strip()

            # -------------------------
            # Numeric rating
            # -------------------------
            if _is_numeric(text_clean):
                val = int(text_clean)

                # basic sanity filter (1–5 scale)
                if 1 <= val <= 5:
                    scores.append(val)

            # -------------------------
            # Support channels
            # -------------------------
            if "go-to avenues of support" in q:
                support_channels[text_clean] += 1

            # -------------------------
            # Issue frequency
            # -------------------------
            if "how often do you typically run into an issue" in q:
                issue_frequency[text_clean] += 1

    # -------------------------
    # Compute overall score
    # -------------------------
    overall_score = None

    if scores:
        overall_score = round(sum(scores) / len(scores), 2)

    # -------------------------
    # Build summary text
    # -------------------------
    summary_parts = []

    if overall_score is not None:
        summary_parts.append(
            f"Users rated the experience highly, with an average score of {overall_score} out of 5."
        )

    if support_channels:
        top_channel = max(support_channels, key=support_channels.get)
        summary_parts.append(
            f"Most users rely on '{top_channel}' when seeking support."
        )

    if issue_frequency:
        top_freq = max(issue_frequency, key=issue_frequency.get)
        summary_parts.append(
            f"Issues are most commonly encountered '{top_freq}'."
        )

    summary = " ".join(summary_parts) if summary_parts else "No strong overall signals detected."

    return {
        "success": True,
        "overall_score": overall_score,
        "summary": summary
    }