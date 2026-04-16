# app/services/bonus_survey_signal_extractor.py

import json

from app.services.ai_service import call_ai


def extract_signals_from_responses(responses: list) -> dict:
	"""
	Extract atomic signals from grouped responses.
	"""

	if not responses:
		return {
			"success": False,
			"signals": [],
			"error": "No responses provided",
		}

	# Safety cap
	responses = responses[:200]

	system_prompt = """
You are a data extraction engine.

TASK:
- Extract ATOMIC signals from user responses

RULES:
- Each response may contain MULTIPLE ideas
- Split responses into SEPARATE signals when needed
- Each signal must represent ONE clear idea
- Keep signals SHORT and precise
- Preserve original wording as much as possible
- Do NOT summarize or generalize
- Do NOT merge ideas
- Output MUST be valid JSON (no markdown, no backticks)
- Ignore structured or demographic data such as:
  - names
  - gender
  - age ranges
  - product lists
  - numeric ratings
- Only extract signals that represent user EXPERIENCE, FEEDBACK, or OPINIONS

EXAMPLE:

Input:
"I love the images, but navigation is confusing"

Output:
{
	"signals": [
		"I love the images",
		"navigation is confusing"
	]
}
"""

	user_prompt = f"""
Responses:
{json.dumps(responses, ensure_ascii=False)}
"""

	result = call_ai(
		prompt=user_prompt,
		system_prompt=system_prompt,
		model="gpt-4o",
		temperature=0.1,
		max_tokens=2000
	)

	raw = result.get("response")

	if not raw:
		return {
			"success": False,
			"signals": [],
			"error": "Empty AI response",
			"raw": result,
		}

	# -------------------------
	# Truncation guard (NEW)
	# -------------------------
	if not raw.strip().endswith("}"):
		return {
			"success": False,
			"signals": [],
			"error": "Truncated AI response",
			"raw": raw,
		}

	# -------------------------
	# Clean markdown wrappers
	# -------------------------
	raw_clean = raw.strip()

	if raw_clean.startswith("```"):
		raw_clean = raw_clean.strip("`")
		if raw_clean.startswith("json"):
			raw_clean = raw_clean[4:].strip()

	# -------------------------
	# Parse JSON
	# -------------------------
	try:
		parsed = json.loads(raw_clean)
		signals = parsed.get("signals", [])

		signals = [
			s.strip()
			for s in signals
			if isinstance(s, str) and s.strip()
		]

		return {
			"success": True,
			"signals": signals,
			"error": None,
		}

	except Exception:
		return {
			"success": False,
			"signals": [],
			"error": "Failed to parse signals",
			"raw": raw,
		}