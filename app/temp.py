from app.services.bonus_survey_analysis_builder import build_bonus_survey_analysis_payload
from app.services.bonus_survey_segment_builder import build_segment_views
from app.services.bonus_survey_insights_ai import generate_segment_insights
from app.services.bonus_survey_segment_comparator import compare_segments
from app.services.bonus_survey_overall_builder import build_overall_summary
from app.services.bonus_survey_report_builder import build_bonus_survey_report

BONUS_SURVEY_ID = 29  # ← change this


# -------------------------
# STEP 1: Build payload
# -------------------------
payload = build_bonus_survey_analysis_payload(BONUS_SURVEY_ID)

print("\n=== PAYLOAD CHECK ===")
print(f"Responses: {len(payload.get('responses', []))}")

# Show one sample
if payload["responses"]:
    print("\nSample Response:")
    print(payload["responses"][0])

# -------------------------
# STEP 0: Overall summary
# -------------------------
overall = build_overall_summary(payload)

print("\n=== OVERALL CHECK ===")

if not overall.get("success"):
    print("FAILED:", overall)
else:
    print("Score:", overall["overall_score"])
    print("Summary:", overall["summary"])
    

# -------------------------
# STEP 2: Build segments
# -------------------------
segments = build_segment_views(payload)

print("\n=== SEGMENTS CHECK ===")
print(f"Segments: {len(segments)}")

# Show top 5 segments
for seg in segments[:5]:
    print(seg["segment_key"], "| users:", seg["user_count"])


# -------------------------
# STEP 3: Generate insights
# -------------------------
result = generate_segment_insights(payload)

print("\n=== INSIGHTS CHECK ===")

if not result.get("success"):
    print("FAILED:", result)
else:
    segments = result.get("segments", [])
    print(f"Insight Segments: {len(segments)}")

    for seg in segments[:3]:
        print("\n---")
        print("Segment:", seg["segment"])
        print("Users:", seg["user_count"])
        print("Insights:", seg["insights"])

# -------------------------
# STEP 4: Compare segments
# -------------------------
print("\n=== COMPARISON CHECK ===")

comparison_result = compare_segments(payload)

if not comparison_result.get("success"):
    print("FAILED:", comparison_result)
else:
    comparisons = comparison_result.get("comparisons", [])
    print(f"Comparisons found: {len(comparisons)}")

    for c in comparisons[:5]:
        print("\n---")
        print("Signal:", c["signal"])
        print("Segment A:", c["segment_a"], "|", c["a_pct"])
        print("Segment B:", c["segment_b"], "|", c["b_pct"])
        print("Diff:", c["difference"])

# -------------------------
# STEP 5: FULL REPORT
# -------------------------
print("\n=== FULL REPORT ===")

report_result = build_bonus_survey_report(payload)

if not report_result.get("success"):
    print("FAILED:", report_result)
else:
    report = report_result["report"]

    print("\n--- OVERALL ---")
    print("Score:", report["overall"].get("overall_score"))
    print("Summary:", report["overall"].get("summary"))

    print("\n--- SEGMENTS ---")
    for seg in report["segments"]:
        print("\nSegment:", seg["segment"])
        print("Users:", seg["user_count"])
        print("Summary:", seg["insights"].get("segment_summary"))

    print("\n--- COMPARISONS ---")
    if not report["comparisons"]:
        print("No meaningful differences detected.")
    else:
        for c in report["comparisons"]:
            print("\nSignal:", c["signal"])
            print("A:", c["segment_a"], c["a_pct"])
            print("B:", c["segment_b"], c["b_pct"])