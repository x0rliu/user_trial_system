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
	Generate structured AI analysis for a bonus survey.
	"""

	# -------------------------
	# 1. Build dataset
	# -------------------------
	payload = build_bonus_survey_analysis_payload(bonus_survey_id)
	summary = get_bonus_survey_summary(bonus_survey_id)

	responses = payload.get("responses", [])

	if not responses:
		return {
			"success": False,
			"analysis": None,
			"error": "No responses available for analysis",
		}

	# -------------------------
	# 2. Group answers per user
	# -------------------------
	grouped_responses = []

	for r in responses:
		user_answers = []

		answers_sorted = sorted(
			r.get("answers", []),
			key=lambda x: x.get("question_hash", "")
		)

		for a in answers_sorted:
			text = a.get("answer_text")
			if text:
				user_answers.append(text)

		if user_answers:
			grouped_responses.append(user_answers)

	# Safety cap
	grouped_responses = grouped_responses[:200]

	# -------------------------
	# 2.5 Extract signals
	# -------------------------
	signal_result = extract_signals_from_responses(grouped_responses)

	if not signal_result.get("success"):
		return {
			"success": False,
			"analysis": None,
			"error": signal_result.get("error"),
			"raw": signal_result.get("raw"),  # 👈 ADD THIS
		}

	signals = signal_result.get("signals", [])

	# -------------------------
	# 3. Build prompts
	# -------------------------
	system_prompt = """
You are an analyst for a user trial survey.

STRICT RULES:
- Only use the provided dataset
- Do not invent themes
- Do not generalize beyond evidence
- Themes must be DISTINCT and NON-OVERLAPPING
- Themes should represent ONE clear idea only
- Avoid combining unrelated concepts
- Merge only when concepts are truly identical
- Prefer clear, focused themes
- Input consists of atomic signals extracted from responses
- Count how many UNIQUE signals support each theme
- Only include SPECIFIC, actionable quotes
- EXCLUDE vague phrases (e.g., "very helpful", "no problem")
- Each signal must belong to ONLY ONE theme
- Do NOT assign the same signal to multiple themes
- Do NOT write explanations outside JSON

- You MUST minimize the number of themes
- Aim for 4–6 themes maximum
- Merge similar themes aggressively
- Prefer broader, well-defined themes over multiple narrow ones
- If two themes are closely related, combine them into a single theme

- If a quote contains non-English text:
  - Preserve the original text exactly
  - Do NOT translate proper nouns, names, or product terms
  - If translation is needed:
    - Translate ONLY the non-English portion
    - Append translation in parentheses immediately after that portion
    - Format: ORIGINAL TEXT (TRANSLATION)

Examples:

"简单可视化" → "简单可视化 (Simple and visualized)"

"搜索很醒目且准确迅速"
→ "搜索很醒目且准确迅速 (Search is prominent, accurate, and fast)"

Do NOT duplicate or re-translate English content.

Return JSON ONLY:

{
  "themes": [
    {
      "theme": "string",
      "mention_count": number,
      "sentiment": "positive|negative|mixed",
      "quotes": ["string", "string"]
    }
  ]
}
"""

	user_prompt = f"""
Survey: {payload.get('survey_title')}

Total Responses: {summary.get('responses')}
Total Questions: {summary.get('questions')}

Signals:
{json.dumps(signals, ensure_ascii=False)}
"""

	# -------------------------
	# 4. Call AI
	# -------------------------
	ai_result = call_ai(
		prompt=user_prompt,
		system_prompt=system_prompt,
		model="gpt-4o",
		temperature=0.2,
		max_tokens=2000,
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
			"raw": ai_result,
		}

	# -------------------------
	# 5. Extract + Parse JSON
	# -------------------------

	raw_clean = raw_text.strip()

	start = raw_clean.find("{")
	end = raw_clean.rfind("}")

	if start == -1 or end == -1:
		return {
			"success": False,
			"analysis": None,
			"error": "No JSON object found in AI response",
			"raw": raw_text,
		}

	raw_clean = raw_clean[start:end+1]

	try:
		parsed = json.loads(raw_clean)

		return {
			"success": True,
			"analysis": parsed,
			"error": None,
		}

	except Exception:
		return {
			"success": False,
			"analysis": None,
			"error": "Failed to parse AI JSON response",
			"raw": raw_text,
		}