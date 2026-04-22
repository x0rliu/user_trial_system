# app/services/bonus_survey_section_generator.py

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
            q_hash = a.get("question_hash")
            q_text = (a.get("question_text") or "").strip()

            if not q_hash or not q_text:
                continue

            if q_hash not in questions:
                questions[q_hash] = q_text

    question_list = list(questions.values())

    def _is_qual(q: str) -> bool:
        ql = q.lower()
        return any([
            "why" in ql,
            "elaborate" in ql,
            "explain" in ql,
            "reason" in ql,
        ])

    # Build paired structure
    paired_questions = []
    i = 0

    while i < len(question_list):
        current = question_list[i]

        if i + 1 < len(question_list) and _is_qual(question_list[i + 1]):
            paired_questions.append({
                "quant": current,
                "qual": question_list[i + 1]
            })
            i += 2
        else:
            paired_questions.append({
                "quant": current,
                "qual": None
            })
            i += 1

    # Add index to preserve order context
    indexed_questions = [
        {"index": i, "question": q}
        for i, q in enumerate(question_list)
    ]

    if not question_list:
        raise ValueError("No questions found in payload")

    # -------------------------
    # AI prompt (minimal, structural only)
    # -------------------------
    system_prompt = """
    You are organizing survey questions into structured sections.

    CRITICAL RULES:

    1. CLASSIFY QUESTIONS INTO TWO TYPES

    A. PROFILE QUESTIONS (NOT part of sections)
    - Demographics (gender, age, country, name)
    - Identity attributes
    - Product ownership / usage
    - Behavioral frequency (e.g. "how often do you encounter issues")

    These MUST be EXCLUDED from sections.
    They will be handled separately as user profile data.

    B. FEEDBACK QUESTIONS (ONLY these go into sections)
    - Opinions about the product, experience, usability, content, or support
    - Ratings, evaluations, and their follow-up explanations

    2. EXCLUDE NON-ANALYTICAL QUESTIONS
    - Ignore administrative or consent questions such as:
    - "Do you agree?"
    - consent to be contacted
    - opt-in / opt-out questions
    These must NOT appear anywhere in the output

    3. ORDER MATTERS (STRICT)
    - Questions are provided with an index
    - You MUST use index order to determine relationships

    4. QUALITATIVE ANCHOR RULE (STRICT)
    - If a question is vague (e.g. "Can you elaborate?", "Why?", "Explain your reasoning")
    - It MUST be grouped with the IMMEDIATELY PRECEDING question (index - 1)
    - DO NOT assign these to any other section

    5. SECTION STRUCTURE
    - Each section = one topic
    - Each section should contain:
    - 1–3 quantitative questions
    - followed by their qualitative follow-ups (if present)

    6. DO NOT SKIP FEEDBACK QUESTIONS
    - Every feedback question must be assigned to exactly one section

    7. PRIORITY RULE
    - The section containing overall rating MUST be:
    section_key = "overall"
    and MUST be first

    8. NAMING
    - snake_case only
    - short and specific

    9. OUTPUT FORMAT (STRICT JSON ONLY)

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
    Questions (paired):

    {json.dumps(paired_questions, ensure_ascii=False)}
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

    for sec in sections:
        if "section_key" not in sec or "questions" not in sec:
            raise ValueError("Invalid section object")

        if not isinstance(sec["section_key"], str) or not sec["section_key"].strip():
            raise ValueError(f"Invalid section_key: {sec.get('section_key')}")

        if not isinstance(sec["questions"], list):
            raise ValueError(f"Invalid questions list for section: {sec.get('section_key')}")

        # Allow duplicate question_text across sections
        # because identical wording (e.g. "Can you elaborate?")
        # can refer to different logical questions
        for q in sec["questions"]:
            if not isinstance(q, str) or not q.strip():
                raise ValueError(f"Invalid question value: {q}")

    # NOTE:
    # Some questions (demographics, usage, etc.) are intentionally excluded
    # from sections and handled as profile questions.
    # Therefore we do NOT enforce full coverage here.

    return {
        "sections": sections
    }