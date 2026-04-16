# app/services/bonus_survey_segment_builder.py

def _derive_age_band(birth_year: int | None) -> str | None:
    if not birth_year:
        return None

    from datetime import datetime
    current_year = datetime.utcnow().year
    age = current_year - birth_year

    if age < 25:
        return "18-24"
    if age < 35:
        return "25-34"
    if age < 45:
        return "35-44"
    if age < 55:
        return "45-54"
    return "55+"


def _build_user_segment_tags(response: dict) -> list[str]:
    """
    Convert a user into segment tags.
    Each tag is a simple, composable dimension.
    """

    tags = []

    demo = response.get("demographics", {})
    profiles = response.get("profiles", {})

    # -------------------------
    # Demographics
    # -------------------------
    gender = (demo.get("gender") or "").lower()
    if gender:
        tags.append(f"gender:{gender}")

    country = demo.get("country")
    if country:
        tags.append(f"country:{country}")

    age_band = _derive_age_band(demo.get("birth_year"))
    if age_band:
        tags.append(f"age:{age_band}")

    # -------------------------
    # Profiles (behavioral)
    # -------------------------
    for category, levels in profiles.items():
        for level in levels:
            tag = f"{category}:{level}"
            tags.append(tag)

    # -------------------------
    # Behavioral: Issue frequency
    # -------------------------
    for answer in response.get("answers", []):
        q = (answer.get("question_text") or "").lower()
        text = answer.get("answer_text")

        if not text:
            continue

        if "how often do you typically run into an issue" in q:
            text_clean = text.strip().lower()
            tags.append(f"issue_freq:{text_clean}")

    return tags


def build_segment_views(payload: dict):
    """
    Build segment-level aggregations from payload.

    Output:
    - segments keyed by tag
    - each segment contains users + answers
    """

    responses = payload.get("responses", [])

    segments = {}

    for response in responses:
        user_id = response["user_id"]
        tags = _build_user_segment_tags(response)

        for tag in tags:
            if tag not in segments:
                segments[tag] = {
                    "segment_key": tag,
                    "users": set(),
                    "responses": [],
                    "sections": {
                        "overall": [],
                        "site_nav": [],
                        "solutions": [],
                    }
                }

            segments[tag]["users"].add(user_id)
            segments[tag]["responses"].append(response)

            # -------------------------
            # Push answers into sections
            # -------------------------
            for answer in response.get("answers", []):
                section = None

                q = (answer.get("question_text") or "").lower()

                if "overall" in q:
                    section = "overall"
                elif (
                    "find your device" in q
                    or "navigation menus" in q
                    or "site map" in q
                ):
                    section = "site_nav"
                elif (
                    "solve your issue" in q
                    or "read and understand" in q
                    or "native language" in q
                ):
                    section = "solutions"

                if section and answer.get("answer_text"):
                    segments[tag]["sections"][section].append(answer["answer_text"])

    # -------------------------
    # Final cleanup
    # -------------------------
    result = []

    for seg in segments.values():
        result.append({
            "segment_key": seg["segment_key"],
            "user_count": len(seg["users"]),
            "response_count": len(seg["responses"]),
            "sections": seg["sections"],
        })

    return result