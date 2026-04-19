# app/services/bonus_section_summaries.py

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.ai_service import call_ai


def generate_bonus_survey_section_summaries(payload: dict):
    """
    Generate concise summaries per section.

    Rules:
    - Use only section responses
    - No deep analysis
    - 1–2 sentence summary per section
    """

    sections = payload.get("sections", {})

    def _process_section(section_key, entries):
        texts = []

        for item in entries:
            txt = item.get("answer_text")
            if txt:
                txt = txt.strip()

                # filter low-signal noise
                if len(txt) < 4:
                    continue
                if txt.isdigit():
                    continue

                texts.append(txt)

        if not texts:
            return None

        texts = texts[:50]  # limit

        system_prompt = """
You are summarizing survey responses for a single section.

Rules:
- Be concise (1–2 sentences)
- Describe overall sentiment or pattern
- Do NOT analyze deeply
- Do NOT generalize beyond data
- No bullet points

Return JSON:

{
  "summary": "string"
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
            max_tokens=300,
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
                "summary": parsed.get("summary")
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