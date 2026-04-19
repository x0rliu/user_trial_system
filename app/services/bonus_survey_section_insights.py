# app/services/bonus_survey_section_insights.py

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.ai_service import call_ai


def generate_bonus_survey_section_insights(payload: dict):
    """
    Generate deep insights per section.

    Rules:
    - Use only section responses
    - Identify patterns, strengths, pain points
    - Avoid repeating summary layer
    """

    sections = payload.get("sections", {})

    def _process_section(section_key, entries):
        texts = []

        for item in entries:
            txt = item.get("answer_text")
            if not txt:
                continue

            txt = txt.strip()

            # filter noise
            if len(txt) < 4:
                continue
            if txt.isdigit():
                continue

            texts.append(txt)

        if not texts:
            return None

        texts = texts[:80]

        system_prompt = """
You are analyzing survey responses for a specific section.

Rules:
- Focus on patterns within this section only
- Identify meaningful themes
- Be specific to the data
- Avoid generic statements

Return JSON:

{
  "summary": "string",
  "strengths": ["string"],
  "pain_points": ["string"]
}
"""

        user_prompt = f"""
Section: {section_key}

Responses:
{json.dumps(texts, ensure_ascii=False)}
"""

        result = call_ai(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model="gpt-4o",
            temperature=0.2,
            max_tokens=800,
        )

        if not result.get("success"):
            return None

        raw = result.get("response", "").strip()

        try:
            start = raw.find("{")
            end = raw.rfind("}")

            if start == -1 or end == -1:
                return None

            parsed = json.loads(raw[start:end+1])

            return {
                "section_key": section_key,
                "insights": parsed
            }

        except Exception:
            return None

    # -------------------------
    # Parallel execution
    # -------------------------
    results = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(_process_section, key, entries)
            for key, entries in sections.items()
        ]

        for future in as_completed(futures):
            res = future.result()
            if res:
                results.append(res)

    return {
        "success": True,
        "sections": results
    }