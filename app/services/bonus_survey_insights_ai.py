# app/services/bonus_survey_insights_ai.py

from app.services.bonus_survey_segment_builder import (
    build_segment_views,
    _build_user_segment_tags
)
from app.services.bonus_survey_signal_extractor import extract_signals_from_responses
from app.services.ai_service import call_ai

import json


def generate_segment_insights(payload: dict):
    """
    Generate insights per segment.
    """

    segments = build_segment_views(payload)

    results = []

    for seg in segments:
        segment_key = seg["segment_key"]

        # -------------------------
        # Collect responses (REBUILT FROM PAYLOAD)
        # -------------------------
        responses = [
            r for r in payload.get("responses", [])
            if segment_key in _build_user_segment_tags(r)
        ]

        grouped = []

        for r in responses:
            answers = [
                a["answer_text"]
                for a in r.get("answers", [])
                if a.get("answer_text")
            ]
            if answers:
                grouped.append(answers)

        if not grouped:
            continue

        grouped = grouped[:100]

        # -------------------------
        # Extract signals
        # -------------------------
        signal_result = extract_signals_from_responses(grouped)

        if not signal_result.get("success"):
            continue

        signals = signal_result.get("signals", [])

        # -------------------------
        # Fallback for weak data
        # -------------------------
        if not signals:
            raw_answers = []

            for r in responses:
                for a in r.get("answers", []):
                    question = (a.get("question_text") or "").lower()
                    text = a.get("answer_text")

                    # -------------------------
                    # FILTER NON-INSIGHT QUESTIONS
                    # -------------------------
                    if any(x in question for x in [
                        "name",
                        "gender",
                        "age",
                        "country",
                        "agree",
                        "select",
                        "what is your"
                    ]):
                        continue

                    if not text:
                        continue

                    text = text.strip()

                    if len(text) < 4:
                        continue

                    if text.isdigit():
                        continue

                    raw_answers.append(text)

            if not raw_answers:
                continue

            signals = raw_answers[:50]

        # -------------------------
        # Build AI prompt
        # -------------------------
        system_prompt = """
You are analyzing a specific user segment from a survey.

Rules:
- Only use provided signals
- Identify 3–5 key themes
- Focus on WHAT this segment uniquely experiences
- Avoid generic observations
- Be concise

Return JSON:

{
  "segment_summary": "string",
  "strengths": ["string"],
  "pain_points": ["string"]
}
"""

        user_prompt = f"""
Segment: {segment_key}

Signals:
{json.dumps(signals, ensure_ascii=False)}
"""

        ai_result = call_ai(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model="gpt-4o",
            temperature=0.2,
            max_tokens=1000,
        )

        if not ai_result.get("success"):
            continue

        raw = ai_result.get("response", "").strip()

        try:
            start = raw.find("{")
            end = raw.rfind("}")

            if start == -1 or end == -1:
                continue

            parsed = json.loads(raw[start:end+1])

            results.append({
                "segment": segment_key,
                "user_count": seg.get("user_count"),
                "insights": parsed
            })

        except Exception as e:
            print(f"[DEBUG] Failed parsing segment: {segment_key}")
            print("[DEBUG] Raw response:")
            print(raw)
            continue

    return {
        "success": True,
        "segments": results
    }