from app.services.bonus_survey_analysis_builder import build_bonus_survey_analysis_payload


def main():
    payload = build_bonus_survey_analysis_payload(29)

    print("Survey:", payload["survey_title"])
    print("Responses:", payload["response_count"])

    for r in payload["responses"][:2]:
        print("\nUSER:", r["user_id"])
        for a in r["answers"][:2]:
            print("-", a["question_text"], "→", a["answer_text"])

    # -------------------------
    # SANITY CHECKS
    # -------------------------
    print("\n--- SANITY CHECKS ---")

    # 1. Ensure all users have same question count
    question_counts = set(len(r["answers"]) for r in payload["responses"])
    print("Unique question counts across users:", question_counts)

    # 2. Check for empty answers
    empty_answers = 0
    for r in payload["responses"]:
        for a in r["answers"]:
            if not a["answer_text"]:
                empty_answers += 1

    print("Empty answers:", empty_answers)


if __name__ == "__main__":
    main()