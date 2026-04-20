# app/services/bonus_survey_analysis.py

import json

from app.services.bonus_survey_signal_extractor import extract_signals_from_responses
from app.services.bonus_survey_analysis_builder import (
    build_bonus_survey_analysis_payload,
)
from app.services.bonus_survey_summary import (
    get_bonus_survey_summary,
)
from app.services.ai_service import call_ai


def generate_bonus_survey_analysis(bonus_survey_id: int) -> dict:
    """
    Generate FULL structured AI report (summary + sections + segments).

    Enforces:
    - Structure is source of truth
    - Single-pass generation
    - Strict JSON output
    - Output sections must match saved structure exactly
    """

    import json
    from app.services.bonus_survey_analysis_builder import (
        build_bonus_survey_analysis_payload,
    )
    from app.services.ai_service import call_ai

    # -------------------------
    # 1. Build payload (WITH STRUCTURE)
    # -------------------------
    payload = build_bonus_survey_analysis_payload(bonus_survey_id)

    if not payload.get("responses"):
        return {
            "success": False,
            "analysis": None,
            "error": "No responses available for analysis",
        }

    # -------------------------
    # 2. Build expected section order from structure
    # -------------------------
    structure_rows = payload.get("structure", []) or []

    expected_sections = []
    seen_section_names = set()

    for row in structure_rows:
        if row.get("placement_type") != "section":
            continue

        section_name = (row.get("section_key") or "").strip()
        if not section_name:
            continue

        if section_name not in seen_section_names:
            seen_section_names.add(section_name)
            expected_sections.append(section_name)

    if not expected_sections:
        return {
            "success": False,
            "analysis": None,
            "error": "No structured sections found. Define section structure before generating insights.",
        }

    # -------------------------
    # 3. Build prompt (LOCKED STRUCTURE)
    # -------------------------
    system_prompt = """
You are analyzing structured survey data.

You MUST strictly follow the provided structure.

HARD RULES (NON-NEGOTIABLE):

1. SECTION STRUCTURE IS FIXED
   - You MUST use ONLY the sections provided
   - You MUST NOT create new sections
   - You MUST NOT merge sections
   - You MUST NOT rename sections

2. QUESTION MAPPING IS FIXED
   - Each question belongs ONLY to its assigned section
   - You MUST NOT move questions between sections

3. OUTPUT SHAPE IS FIXED
   - You MUST return ALL sections, even if empty
   - If no data exists, return null values or empty arrays

4. ORDERING IS FIXED
   - Sections MUST appear in the same order as provided
   - Questions MUST remain in original order

5. DATA TYPES (CRITICAL CLARIFICATION)

Each answer has:
- question_text
- answer_text

You MUST classify answer_text:

Quantitative:
- Pure numbers (e.g. 1, 2, 3, 4, 5)
- Numeric ratings
→ Use for averages and scores

Qualitative:
- Sentences, phrases, explanations
→ Use for insights and quotes

IMPORTANT:
- If answer_text cannot be parsed as a number → treat as qualitative
- NEVER discard qualitative answers
- ALWAYS extract insights from qualitative responses if present

6. NO HALLUCINATION
   - DO NOT infer missing structure
   - DO NOT generalize beyond provided data

7. OUTPUT FORMAT
   - Return VALID JSON ONLY
   - No markdown
   - No explanations
   - No extra text

Failure to follow these rules is considered incorrect.
"""

    user_prompt = f"""
STRUCTURE (AUTHORITATIVE — DO NOT MODIFY):

You MUST:
- Use these sections exactly
- Keep this order
- Keep question-to-section mapping unchanged

{json.dumps(payload.get("structure"), ensure_ascii=False)}

----------------------------------------

EXPECTED SECTION ORDER:

{json.dumps(expected_sections, ensure_ascii=False)}

----------------------------------------

SECTION DATA (PRE-GROUPED ANSWERS):

{json.dumps(payload.get("sections"), ensure_ascii=False)}

----------------------------------------

RESPONSES (FULL DATASET):

{json.dumps(
    payload.get("responses"),
    ensure_ascii=False,
    default=str
)}

----------------------------------------

TASK:

Generate a FULL report with:

1. summary
2. sections (STRICTLY follow provided structure)
3. segments

----------------------------------------

OUTPUT FORMAT (STRICT JSON):

{{
  "summary": {{
    "response_count": int,
    "key_patterns": [string]
  }},
  "sections": [
    {{
        "section_name": string,
        "average_score": float | null,
        "key_findings": [string],
        "qualitative_insights": [
        "Summarize recurring themes from text answers"
        ],
        "notable_quotes": [
        "Exact quotes from responses (only if meaningful text exists)"
        ]
    }}
  ],
  "segments": [
    {{
      "segment": string,
      "insights": [string]
    }}
  ]
}}

IMPORTANT:
- Every section in EXPECTED SECTION ORDER must appear exactly once
- Use the exact same section names
- Use the exact same order
- If no data → return empty arrays / null values
- Do NOT skip sections
- Every section MUST produce qualitative_insights if any text answers exist
- Do NOT leave qualitative_insights empty if text responses are present
- Do NOT output "-" or placeholders
- Always produce meaningful analysis from text responses

Return JSON ONLY.
"""

    # -------------------------
    # 4. Call AI (ONE PASS)
    # -------------------------
    ai_result = call_ai(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model="gpt-4o",
        temperature=0.2,
        max_tokens=3000,
    )

    if not ai_result.get("success"):
        return {
            "success": False,
            "analysis": None,
            "error": ai_result.get("error"),
        }

    raw_text = ai_result.get("response")

    if not raw_text:
        return {
            "success": False,
            "analysis": None,
            "error": "Empty AI response",
        }

    # -------------------------
    # 5. Extract JSON safely
    # -------------------------
    raw_clean = raw_text.strip()

    start = raw_clean.find("{")
    end = raw_clean.rfind("}")

    if start == -1 or end == -1:
        return {
            "success": False,
            "analysis": None,
            "error": "No JSON object found",
            "raw": raw_text,
        }

    raw_clean = raw_clean[start:end + 1]

    try:
        parsed = json.loads(raw_clean)
    except Exception:
        return {
            "success": False,
            "analysis": None,
            "error": "JSON parse failed",
            "raw": raw_text,
        }

    # -------------------------
    # 6. Validate top-level shape
    # -------------------------
    if not isinstance(parsed, dict):
        return {
            "success": False,
            "analysis": None,
            "error": "Invalid AI output: root must be an object",
            "raw": raw_text,
        }

    if "summary" not in parsed:
        return {
            "success": False,
            "analysis": None,
            "error": "Invalid AI output: missing summary",
            "raw": raw_text,
        }

    if "sections" not in parsed:
        return {
            "success": False,
            "analysis": None,
            "error": "Invalid AI output: missing sections",
            "raw": raw_text,
        }

    if "segments" not in parsed:
        return {
            "success": False,
            "analysis": None,
            "error": "Invalid AI output: missing segments",
            "raw": raw_text,
        }

    if not isinstance(parsed["sections"], list):
        return {
            "success": False,
            "analysis": None,
            "error": "Invalid AI output: sections must be a list",
            "raw": raw_text,
        }

    # -------------------------
    # 7. Validate section structure exactly
    # -------------------------
    actual_sections = []

    for idx, section in enumerate(parsed["sections"]):
        if not isinstance(section, dict):
            return {
                "success": False,
                "analysis": None,
                "error": f"Invalid AI output: section at index {idx} must be an object",
                "raw": raw_text,
            }

        name = (section.get("section_name") or "").strip()
        if not name:
            return {
                "success": False,
                "analysis": None,
                "error": f"Invalid AI output: section at index {idx} missing section_name",
                "raw": raw_text,
            }

        actual_sections.append(name)

    if len(actual_sections) != len(expected_sections):
        return {
            "success": False,
            "analysis": None,
            "error": (
                "Invalid AI output: section count mismatch. "
                f"Expected {len(expected_sections)}, got {len(actual_sections)}"
            ),
            "raw": raw_text,
        }

    if actual_sections != expected_sections:
        return {
            "success": False,
            "analysis": None,
            "error": (
                "Invalid AI output: section names/order mismatch. "
                f"Expected {expected_sections}, got {actual_sections}"
            ),
            "raw": raw_text,
        }

    return {
        "success": True,
        "analysis": parsed,
        "error": None,
    }