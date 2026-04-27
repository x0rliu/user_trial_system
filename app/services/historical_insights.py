# app/services/historical_insights.py

import json

from app.db.historical import (
    get_historical_answers_by_context,
    insert_historical_insight_run,
    insert_historical_trial_insight
)


# -------------------------
# SERVICE: Generate Trial Insights
# -------------------------
def generate_trial_insights(context_id):
    """
    Generates deterministic (non-AI) insights for a trial.
    Snapshot-based. No GET usage. Fully persisted.
    """

    rows = get_historical_answers_by_context(context_id)

    print("\n====================")
    print("INSIGHTS DEBUG — INPUT")
    print("====================")
    print("Context ID:", context_id)
    print("Total rows:", len(rows))

    # sample rows
    for r in rows[:3]:
        print("ROW SAMPLE:", {
            "response_group_id": r.get("response_group_id"),
            "answer_text": r.get("answer_text"),
            "answer_numeric": r.get("answer_numeric")
        })

    if not rows:
        return

    # -------------------------
    # Step 1: Create insight run
    # -------------------------
    insight_run_id = insert_historical_insight_run(
        context_id=context_id,
        trigger_type="manual",
        generation_version="v1"
    )

    # -------------------------
    # Step 2: Grouping (still simple: overall only)
    # -------------------------
    sections = {
        "overall": rows
    }

    # -------------------------
    # Step 3: Generate Insights (deterministic)
    # -------------------------
    for section_name, section_rows in sections.items():

        # -------------------------
        # Sample size
        # -------------------------
        sample_size = len(set(r["response_group_id"] for r in section_rows))

        # -------------------------
        # Extract qualitative answers
        # -------------------------
        qualitative = [
            r["answer_text"].strip()
            for r in section_rows
            if r.get("answer_text") and not r.get("answer_numeric")
        ]

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for q in qualitative:
            if q not in seen:
                deduped.append(q)
                seen.add(q)

        qualitative = deduped

        print("\n--- QUALITATIVE ---")
        print("Total qualitative:", len(qualitative))

        for q in qualitative[:5]:
            print("Q:", q)

        # -------------------------
        # Basic signal extraction
        # -------------------------
        total_comments = len(qualitative)

        # Simple word frequency (very lightweight)
        word_counts = {}
        STOPWORDS = {
            "this", "that", "with", "have", "from", "they", "were", "been",
            "very", "really", "just", "also", "there", "their", "about",
            "would", "could", "should", "some", "what", "when", "where",
            "which", "while", "your", "them", "then", "than", "into",
            "like", "because", "these", "those", "being", "over",
            "make", "made", "much", "many", "well",
            "more", "less", "feel", "feels", "felt",
            "thing", "things", "stuff",
            "good", "nice", "great", "bad",
            "better", "worse", "need",
            "black", "white",  # optional depending on use case
            "product", "device", "keyboard","mice","mouse","headset",  # 🔥 important
            "dont", "don't", "cant", "can't", "wont", "won't"
        }

        phrase_counts = {}

        for text in qualitative:
            words = [
                w.strip(".,!?()[]{}\"'").lower()
                for w in text.split()
            ]

            # filter words
            words = [
                w.replace("'", "")
                for w in words
            ]

            words = [
                w for w in words
                if (
                    len(w) >= 4
                    and w not in STOPWORDS
                    and not w.isnumeric()
    )
]

            # build 2-word phrases
            for i in range(len(words) - 1):
                phrase = f"{words[i]} {words[i+1]}"
                phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

        # -------------------------
        # Rank phrases FIRST
        # -------------------------
        sorted_phrases = sorted(
            phrase_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Only keep meaningful ones
        top_phrases = [
            p for p, count in sorted_phrases
            if count >= 2
        ][:5]

        # Fallback if no phrases
        if not top_phrases:
            word_counts = {}

            for text in qualitative:
                for w in text.split():
                    w = w.strip(".,!?()[]{}\"'").lower().replace("'", "")
                    if len(w) >= 5 and w not in STOPWORDS:
                        word_counts[w] = word_counts.get(w, 0) + 1

            sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
            top_phrases = [w for w, _ in sorted_words[:5]]

        # Final themes
        top_themes = top_phrases
        
        # -------------------------
        # Quote selection
        # -------------------------
        quotes = qualitative[:5]

        # -------------------------
        # Insight Summary (structured)
        # -------------------------
        summary_parts = []

        summary_parts.append(f"{sample_size} responses analyzed")
        summary_parts.append(f"{total_comments} qualitative comments captured")

        if top_themes:
            summary_parts.append("Common themes: " + ", ".join(top_themes))

        insight_summary = ". ".join(summary_parts) + "."

        # -------------------------
        # Insight JSON payload
        # -------------------------
        insight_json = {
            "summary": insight_summary,
            "supporting_quotes": quotes,
            "sample_size": sample_size,
            "total_comments": total_comments,
            "top_themes": top_themes
        }

        # -------------------------
        # Persist
        # -------------------------
        insert_historical_trial_insight(
            insight_run_id=insight_run_id,
            context_id=context_id,
            section_name=section_name,
            insight_type="summary",
            insight_summary=insight_summary,
            insight_json=json.dumps(insight_json),
            source_sample_size=sample_size,
            filters_applied=None
        )

        # -------------------------
        # ADDITIONAL INSIGHTS (v2 layer)
        # -------------------------

        # Build phrase → quotes map (reuse qualitative)
        phrase_map = {}

        for text in qualitative:
            words = [
                w.strip(".,!?()[]{}\"'").lower().replace("'", "")
                for w in text.split()
            ]

            words = [
                w for w in words
                if len(w) >= 4 and w not in STOPWORDS
            ]

            for i in range(len(words) - 1):
                phrase = f"{words[i]} {words[i+1]}"

                if phrase not in phrase_map:
                    phrase_map[phrase] = {
                        "count": 0,
                        "quotes": []
                    }

                phrase_map[phrase]["count"] += 1

                if len(phrase_map[phrase]["quotes"]) < 3:
                    phrase_map[phrase]["quotes"].append(text)

        print("\n--- PHRASE MAP ---")
        print("Total phrases:", len(phrase_map))

        for k, v in list(phrase_map.items())[:10]:
            print(f"{k} -> {v['count']}")

        # Sort by signal strength
        ranked = sorted(
            phrase_map.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )

        # -------------------------
        # CLUSTERED PATTERN INSIGHTS (v3 - domain agnostic)
        # -------------------------

        # Step 1: Build clusters dynamically from phrase_map
        clusters = {}

        for phrase, data in phrase_map.items():
            words = phrase.split()

            # pick a root word (longest word heuristic)
            root = max(words, key=len)

            if root not in clusters:
                clusters[root] = {
                    "phrases": [],
                    "count": 0,
                    "quotes": []
                }

            clusters[root]["phrases"].append((phrase, data["count"]))
            clusters[root]["count"] += data["count"]

            # collect quotes (limit total per cluster)
            for q in data["quotes"]:
                if q not in clusters[root]["quotes"]:
                    clusters[root]["quotes"].append(q)
                if len(clusters[root]["quotes"]) >= 5:
                    break

        # Step 2: Rank clusters by signal strength
        ranked_clusters = sorted(
            clusters.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )

        print("\n--- CLUSTERS ---")
        for root, data in ranked_clusters[:10]:
            print(f"CLUSTER: {root}")
            print("  count:", data["count"])
            print("  phrases:", [p for p, _ in data["phrases"]])
            print("  sample quotes:", data["quotes"][:2])

        # Step 3: Generate insights from clusters
        for root, data in ranked_clusters[:3]:  # top 3 clusters only

            cluster_count = data["count"]
            phrases = [p for p, _ in data["phrases"]]
            quotes = data["quotes"][:3]

            if cluster_count < 3:
                continue

            # impact logic (reuse your thresholds)
            if cluster_count >= 8:
                impact = "high"
            elif cluster_count >= 4:
                impact = "medium"
            else:
                impact = "low"

            explanation = (
                f"User feedback frequently references related concepts such as "
                f"{', '.join(phrases[:3])}. "
                f"These repeated mentions ({cluster_count} total signals across {sample_size} participants) "
                f"indicate a consistent pattern in how users perceive this aspect of the product."
            )

            pattern_json = {
                "title": f"Recurring theme around '{root}'",
                "explanation": explanation,
                "quotes": quotes,
                "impact": impact,
                "signal_strength": cluster_count,
                "sample_size": sample_size,
                "phrases": phrases,
                "type": "pattern_cluster"
            }

            print("\n--- INSERTING INSIGHT ---")
            print("TYPE:", pattern_json.get("type"))
            print("TITLE:", pattern_json.get("title"))
            print("IMPACT:", pattern_json.get("impact"))

            insert_historical_trial_insight(
                insight_run_id=insight_run_id,
                context_id=context_id,
                section_name=section_name,
                insight_type="pattern",
                insight_summary=root,
                insight_json=json.dumps(pattern_json),
                source_sample_size=sample_size,
                filters_applied=None
            )

        # -------------------------
        # CONTRADICTION INSIGHT
        # -------------------------
        positives = ["good", "great", "nice", "love", "premium"]
        negatives = ["bad", "hate", "too", "not", "bulky", "heavy"]

        pos_hits = [q for q in qualitative if any(p in q.lower() for p in positives)]
        neg_hits = [q for q in qualitative if any(n in q.lower() for n in negatives)]

        if len(pos_hits) >= 2 and len(neg_hits) >= 2:

            contradiction_json = {
                "title": "Polarized user feedback",
                "explanation": (
                    "User feedback shows divergence in perception. Some users describe positive "
                    "experiences, while others report negative reactions to similar aspects. "
                    "This suggests inconsistent user experience or differing expectations."
                ),
                "quotes": pos_hits[:2] + neg_hits[:2],
                "impact": "high",
                "signal_strength": len(pos_hits) + len(neg_hits),
                "sample_size": sample_size,
                "type": "contradiction"
            }

            insert_historical_trial_insight(
                insight_run_id=insight_run_id,
                context_id=context_id,
                section_name=section_name,
                insight_type="contradiction",
                insight_summary="Polarized feedback detected",
                insight_json=json.dumps(contradiction_json),
                source_sample_size=sample_size,
                filters_applied=None
            )

AI_SYSTEM_PROMPT = """
You are a senior UX research analyst.

Your job is to analyze user feedback from a SINGLE product trial round.

STRICT RULES:
- Only use the data provided
- Do NOT generalize beyond this dataset
- Do NOT invent quotes
- Every insight MUST be supported by actual user comments

Your task is to generate high-quality product insights.

Do NOT include:
- markdown
- backticks
- explanations outside JSON

Return ONLY valid JSON array. Each item must follow this exact structure:

[
  {
    "type": "ai_summary",
    "summary": "3-5 sentences summarizing the most important findings across the dataset"
  },
  {
    "type": "ai_insight",
    "title": "Short, clear insight title",
    "explanation": "2-3 sentences explaining the insight clearly and concretely",
    "evidence": [
      "Direct quote from users",
      "Direct quote from users"
    ],
    "impact": "high | medium | low"
  }
]

QUALITY RULES:

1. Insights must be MEANINGFUL
   - Not just repeating keywords
   - Not just summarizing responses
   - Must interpret what the feedback actually means
   - Must explain WHY users feel this way

2. Evidence is REQUIRED
   - 2–3 quotes per insight
   - Quotes must come from the input
   - Quotes should clearly support the claim
   - Do NOT modify or paraphrase quotes

3. Avoid generic insights like:
   - "Users like the product"
   - "Feedback is mixed"

4. Look for:
   - recurring patterns
   - user frustrations
   - unmet expectations
   - surprising behavior
   - contradictions (IMPORTANT: explicitly highlight when users disagree)

5. Impact definition:
   - high → affects many users or core product experience
   - medium → noticeable but not critical
   - low → minor or edge-case

6. Never do the following:
    - Use a user's real name when quoting them
    - Only identify users as "User N" (User 1, User 2, etc.)
    - If a user is quoted multiple times, reuse the same User N
    - Do NOT include raw names from the dataset

7. General Rules
    - Maximum 5 insights
    - Each insight must be independent
    - DO NOT repeat the same idea in different wording
    - Each insight must represent a DISTINCT pattern
    - Keep quotes SHORT (under 200 chars)
    - Escape all quotes properly
    - Do NOT cut off JSON

8. SUMMARY RULES (NEW - IMPORTANT)
    - MUST be the FIRST item in the array
    - MUST NOT repeat individual insights verbatim
    - MUST synthesize (connect patterns together)
    - MUST include BOTH strengths and weaknesses
    - MUST read like an executive-level overview, not bullet points
    - MUST NOT include quotes
    - MUST NOT mention "users said" repeatedly

9. CROSS-SIGNAL THINKING (NEW)
    - Prefer insights that combine multiple signals
    - Example: connect usability complaints with perception of quality
    - Identify patterns that span multiple comments, not isolated statements

10. PRIORITIZATION (NEW)
    - Focus on the most important signals first
    - Do NOT include weak or low-signal insights if stronger ones exist

---

DATASET:

Total Responses: {sample_size}
Total Comments: {len(qualitative)}

INPUT DATA:
{qualitative[:200]}
"""

def generate_ai_insights(context_id):
    from app.services.ai_service import call_ai
    import json

    rows = get_historical_answers_by_context(context_id)

    if not rows:
        return

    # -------------------------
    # Build qualitative dataset
    # -------------------------
    qualitative = [
        r["answer_text"].strip()
        for r in rows
        if r.get("answer_text") and not r.get("answer_numeric")
    ]

    # Deduplicate
    seen = set()
    qualitative = [q for q in qualitative if not (q in seen or seen.add(q))]

    sample_size = len(set(r["response_group_id"] for r in rows))

    # Limit to prevent token explosion
    qualitative = qualitative[:120]

    # -------------------------
    # Build prompt
    # -------------------------
    user_prompt = f"""
Sample Size: {sample_size}

User Comments:
{chr(10).join(f"- {q}" for q in qualitative)}
"""

    # -------------------------
    # Call AI
    # -------------------------
    response = call_ai(
        prompt=user_prompt,
        system_prompt=AI_SYSTEM_PROMPT,
        temperature=0.3,
        max_tokens=5000
    )

    import json

    # -------------------------
    # Extract AI response safely
    # -------------------------
    raw = response.get("response") if isinstance(response, dict) else response

    if not raw:
        print("AI EMPTY RESPONSE:", response)
        return

    print("AI RAW RESPONSE (first 500 chars):", raw[:500])

    # -------------------------
    # Clean formatting
    # -------------------------
    raw = raw.strip()

    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()

    # Normalize line breaks
    raw = raw.replace("\n", " ").replace("\r", " ")

    # -------------------------
    # Parse JSON
    # -------------------------
    try:
        insights = json.loads(raw)
    except Exception as e:
        print("AI PARSE ERROR CLEANED:", raw[:1000])
        print("ERROR:", e)
        return


    from app.db.historical import delete_insights_by_context_and_type

    # -------------------------
    # Clear previous AI insights (prevent duplication)
    # -------------------------

    delete_insights_by_context_and_type(context_id, "ai_insight")
    # -------------------------
    # Create insight run
    # -------------------------

    insight_run_id = insert_historical_insight_run(
        context_id=context_id,
        trigger_type="manual_ai",
        generation_version="ai_v1"
    )

    # -------------------------
    # Persist insights
    # -------------------------
    seen_titles = set()

    for item in insights:

        insight_type = item.get("type")

        # -------------------------
        # SUMMARY (single)
        # -------------------------
        if insight_type == "ai_summary":

            summary_text = item.get("summary", "").strip()

            if not summary_text:
                continue

            insert_historical_trial_insight(
                insight_run_id=insight_run_id,
                context_id=context_id,
                section_name="overall",
                insight_type="ai_summary",
                insight_summary=summary_text,
                insight_json=json.dumps(item),
                source_sample_size=sample_size,
                filters_applied=None
            )

        # -------------------------
        # INSIGHTS
        # -------------------------
        elif insight_type == "ai_insight":

            title = (item.get("title") or "").strip().lower()

            if not title or title in seen_titles:
                continue

            seen_titles.add(title)

            insert_historical_trial_insight(
                insight_run_id=insight_run_id,
                context_id=context_id,
                section_name="overall",
                insight_type="ai_insight",
                insight_summary=item.get("title"),
                insight_json=json.dumps(item),
                source_sample_size=sample_size,
                filters_applied=None
            )