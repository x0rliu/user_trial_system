# app/services/bonus_survey_analysis.py

import json
import hashlib
from app.services.bonus_survey_signal_extractor import extract_signals_from_responses
from app.services.bonus_survey_analysis_builder import (
    build_bonus_survey_analysis_payload,
)
from app.services.bonus_survey_summary import (
    get_bonus_survey_summary,
)
from app.services.ai_service import call_ai


def _humanize_section_key(section_key: str) -> str:
    parts = [
        part
        for part in (section_key or "").replace("-", "_").split("_")
        if part
    ]

    if not parts:
        return "Untitled Section"

    return " ".join(part.capitalize() for part in parts)


def build_bonus_report_structure_contract(*, bonus_survey_id: int) -> dict:
    """
    Build the current report structure contract from DB state.

    Source of truth:
    - bonus_survey_question_structure controls question placement.
    - bonus_survey_sections controls section display names/order.

    This performs reads only. It does not mutate DB state.
    """

    from app.db.bonus_survey_question_structure import (
        get_bonus_survey_structure_rows,
    )
    from app.db.bonus_survey_sections import get_bonus_survey_sections

    structure_rows = get_bonus_survey_structure_rows(
        bonus_survey_id=bonus_survey_id,
    )

    section_rows = get_bonus_survey_sections(
        bonus_survey_id=bonus_survey_id,
    )

    section_keys_in_structure = []
    seen_section_keys = set()

    for row in structure_rows:
        if row.get("placement_type") != "section":
            continue

        section_key = (row.get("section_key") or "").strip()
        if not section_key:
            continue

        if section_key in seen_section_keys:
            continue

        seen_section_keys.add(section_key)
        section_keys_in_structure.append(section_key)

    structure_key_set = set(section_keys_in_structure)

    section_metadata_by_key = {}
    ordered_metadata_keys = []

    for row in section_rows:
        section_key = (row.get("section_key") or "").strip()
        if not section_key:
            continue

        if section_key not in structure_key_set:
            continue

        display_name = (row.get("display_name") or "").strip()
        if not display_name:
            display_name = _humanize_section_key(section_key)

        section_order = row.get("section_order")
        if section_order is None:
            section_order = len(ordered_metadata_keys) + 1

        section_metadata_by_key[section_key] = {
            "section_key": section_key,
            "display_name": display_name,
            "section_order": int(section_order or 0),
        }

        ordered_metadata_keys.append(section_key)

    ordered_section_keys = []

    # Prefer saved bonus_survey_sections ordering when available.
    for section_key in ordered_metadata_keys:
        if section_key not in ordered_section_keys:
            ordered_section_keys.append(section_key)

    # Preserve structure order for any section missing from bonus_survey_sections.
    for section_key in section_keys_in_structure:
        if section_key not in ordered_section_keys:
            ordered_section_keys.append(section_key)

    expected_sections = []

    for index, section_key in enumerate(ordered_section_keys, start=1):
        metadata = section_metadata_by_key.get(section_key) or {}
        display_name = (
            metadata.get("display_name")
            or _humanize_section_key(section_key)
        )
        section_order = metadata.get("section_order") or index

        expected_sections.append({
            "section_key": section_key,
            "section_name": display_name,
            "display_name": display_name,
            "section_order": int(section_order),
        })

    structure_snapshot = []

    for row in structure_rows:
        structure_snapshot.append({
            "question_hash": row.get("question_hash"),
            "question_order": row.get("question_order"),
            "placement_type": row.get("placement_type"),
            "section_key": row.get("section_key"),
        })

    structure_fingerprint_source = {
        "sections": expected_sections,
        "structure": structure_snapshot,
    }

    structure_fingerprint = hashlib.sha256(
        json.dumps(
            structure_fingerprint_source,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()

    return {
        "version": "bonus_report_v2",
        "sections": expected_sections,
        "structure_snapshot": structure_snapshot,
        "structure_fingerprint": structure_fingerprint,
    }


def generate_bonus_survey_analysis(bonus_survey_id: int) -> dict:
    """
    Generate FULL structured AI report (summary + sections + segments).

    Enforces:
    - Structure is source of truth
    - Section metadata is source of truth for display names/order
    - Single-pass generation
    - Strict JSON output
    - Output sections must match saved structure exactly
    """

    import json
    from app.services.bonus_survey_analysis_builder import (
        build_bonus_survey_analysis_payload,
    )
    from app.services.ai_service import call_ai
    from app.db.bonus_survey_sections import get_bonus_survey_sections

    def _humanize_section_key(section_key: str) -> str:
        parts = [
            part
            for part in (section_key or "").replace("-", "_").split("_")
            if part
        ]

        if not parts:
            return "Untitled Section"

        return " ".join(part.capitalize() for part in parts)

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
    # 2. Build expected section contract
    # -------------------------
    structure_rows = payload.get("structure", []) or []
    section_rows = get_bonus_survey_sections(
        bonus_survey_id=bonus_survey_id,
    )

    section_keys_in_structure = []
    seen_section_keys = set()

    for row in structure_rows:
        if row.get("placement_type") != "section":
            continue

        section_key = (row.get("section_key") or "").strip()
        if not section_key:
            continue

        if section_key in seen_section_keys:
            continue

        seen_section_keys.add(section_key)
        section_keys_in_structure.append(section_key)

    if not section_keys_in_structure:
        return {
            "success": False,
            "analysis": None,
            "error": "No structured sections found. Define section structure before generating insights.",
        }

    structure_key_set = set(section_keys_in_structure)

    section_metadata_by_key = {}
    ordered_metadata_keys = []

    for row in section_rows:
        section_key = (row.get("section_key") or "").strip()
        if not section_key:
            continue

        if section_key not in structure_key_set:
            continue

        display_name = (row.get("display_name") or "").strip()
        if not display_name:
            display_name = _humanize_section_key(section_key)

        section_order = row.get("section_order")
        if section_order is None:
            section_order = len(ordered_metadata_keys) + 1

        section_metadata_by_key[section_key] = {
            "section_key": section_key,
            "display_name": display_name,
            "section_order": int(section_order or 0),
        }

        ordered_metadata_keys.append(section_key)

    ordered_section_keys = []

    # Prefer saved bonus_survey_sections ordering when available.
    for section_key in ordered_metadata_keys:
        if section_key not in ordered_section_keys:
            ordered_section_keys.append(section_key)

    # Preserve structure order for any section missing from bonus_survey_sections.
    for section_key in section_keys_in_structure:
        if section_key not in ordered_section_keys:
            ordered_section_keys.append(section_key)

    expected_sections = []

    for index, section_key in enumerate(ordered_section_keys, start=1):
        metadata = section_metadata_by_key.get(section_key) or {}
        display_name = (
            metadata.get("display_name")
            or _humanize_section_key(section_key)
        )
        section_order = metadata.get("section_order") or index

        expected_sections.append({
            "section_key": section_key,
            "section_name": display_name,
            "display_name": display_name,
            "section_order": int(section_order),
        })

    expected_section_keys = [
        section["section_key"]
        for section in expected_sections
    ]

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
   - You MUST NOT rename section_key
   - section_name and display_name MUST use the provided display name

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

EXPECTED SECTIONS (AUTHORITATIVE):

Each output section MUST include:
- section_key exactly as provided
- section_name exactly as provided
- display_name exactly as provided
- section_order exactly as provided

{json.dumps(expected_sections, ensure_ascii=False)}

----------------------------------------

EXPECTED SECTION KEY ORDER:

{json.dumps(expected_section_keys, ensure_ascii=False)}

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
        "section_key": string,
        "section_name": string,
        "display_name": string,
        "section_order": int,
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
- Every section in EXPECTED SECTIONS must appear exactly once
- Use the exact same section_key values
- Use the exact same section_name/display_name values
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
    # 7. Validate and normalize section contract exactly
    # -------------------------
    actual_section_keys = []

    for idx, section in enumerate(parsed["sections"]):
        if not isinstance(section, dict):
            return {
                "success": False,
                "analysis": None,
                "error": f"Invalid AI output: section at index {idx} must be an object",
                "raw": raw_text,
            }

        expected_section = (
            expected_sections[idx]
            if idx < len(expected_sections)
            else None
        )

        if expected_section is None:
            return {
                "success": False,
                "analysis": None,
                "error": f"Invalid AI output: unexpected section at index {idx}",
                "raw": raw_text,
            }

        section_key = (section.get("section_key") or "").strip()

        # Backward-compatible tolerance for models that put the stable key in
        # section_name despite the prompt. The saved output is normalized below.
        if not section_key:
            section_key = (section.get("section_name") or "").strip()

        if not section_key:
            return {
                "success": False,
                "analysis": None,
                "error": f"Invalid AI output: section at index {idx} missing section_key",
                "raw": raw_text,
            }

        if section_key != expected_section["section_key"]:
            return {
                "success": False,
                "analysis": None,
                "error": (
                    "Invalid AI output: section key/order mismatch. "
                    f"Expected {expected_section['section_key']} at index {idx}, got {section_key}"
                ),
                "raw": raw_text,
            }

        section["section_key"] = expected_section["section_key"]
        section["section_name"] = expected_section["section_name"]
        section["display_name"] = expected_section["display_name"]
        section["section_order"] = expected_section["section_order"]

        actual_section_keys.append(section_key)

    if len(actual_section_keys) != len(expected_section_keys):
        return {
            "success": False,
            "analysis": None,
            "error": (
                "Invalid AI output: section count mismatch. "
                f"Expected {len(expected_section_keys)}, got {len(actual_section_keys)}"
            ),
            "raw": raw_text,
        }

    if actual_section_keys != expected_section_keys:
        return {
            "success": False,
            "analysis": None,
            "error": (
                "Invalid AI output: section keys/order mismatch. "
                f"Expected {expected_section_keys}, got {actual_section_keys}"
            ),
            "raw": raw_text,
        }

    # --------------------------------------------------
    # Normalize authoritative counts before persistence
    # --------------------------------------------------
    # The AI may return an incorrect response_count.
    # The DB/payload response count is authoritative.
    parsed["summary"]["response_count"] = payload.get("response_count", 0)

    parsed["section_contract"] = build_bonus_report_structure_contract(
        bonus_survey_id=bonus_survey_id,
    )

    return {
        "success": True,
        "analysis": parsed,
        "error": None,
    }