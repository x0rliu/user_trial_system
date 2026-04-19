import json
from collections import OrderedDict

from app.services.ai_service import call_ai


def generate_bonus_survey_sections(payload: dict) -> dict:
    """
    Generate section structure using AI.

    Input:
    payload["responses"] → answers → question_text

    Output:
    {
        "sections": [
            {
                "section_key": "setup",
                "questions": [...]
            }
        ]
    }
    """

    # -------------------------
    # Extract unique questions
    # -------------------------
    questions = OrderedDict()

    for r in payload.get("responses", []):
        for a in r.get("answers", []):
            q = (a.get("question_text") or "").strip()
            if q:
                questions[q] = True

    question_list = list(questions.keys())

    if not question_list:
        raise ValueError("No questions found in payload")

    # -------------------------
    # AI prompt (minimal, structural only)
    # -------------------------
    system_prompt = """
You are organizing survey questions into sections.

Rules:
- Do NOT analyze deeply
- Group by intent only
- Section names should be short (snake_case)
- Each question must belong to exactly one section
- Return JSON only

Format:

{
  "sections": [
    {
      "section_key": "string",
      "questions": ["string"]
    }
  ]
}
"""

    user_prompt = f"""
Questions:
{json.dumps(question_list, ensure_ascii=False)}
"""

    # -------------------------
    # AI call
    # -------------------------
    result = call_ai(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model="gpt-4o",
        temperature=0.0,
        max_tokens=800,
    )

    if not result.get("success"):
        raise RuntimeError("AI section generation failed")

    raw = result.get("response", "").strip()

    # -------------------------
    # Parse JSON safely
    # -------------------------
    try:
        start = raw.find("{")
        end = raw.rfind("}")

        if start == -1 or end == -1:
            raise ValueError("Invalid JSON from AI")

        parsed = json.loads(raw[start:end+1])

    except Exception as e:
        raise RuntimeError(f"Failed parsing section JSON: {e}")

    # -------------------------
    # Validate structure
    # -------------------------
    sections = parsed.get("sections")

    if not isinstance(sections, list):
        raise ValueError("Invalid sections format")

    seen_questions = set()

    for sec in sections:
        if "section_key" not in sec or "questions" not in sec:
            raise ValueError("Invalid section object")

        for q in sec["questions"]:
            if q in seen_questions:
                raise ValueError(f"Duplicate question assignment: {q}")
            seen_questions.add(q)

    # ensure full coverage
    missing = set(question_list) - seen_questions
    if missing:
        raise ValueError(f"Unassigned questions: {missing}")

    return parsed