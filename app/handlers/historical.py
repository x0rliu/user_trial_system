# app/handlers/historical.py

from app.services.historical_ingestion import ingest_historical_csv


def handle_historical_upload_post(data):

    context_id = data.get("context_id")
    dataset_type = data.get("dataset_type")
    round_number = data.get("round_number")
    file_item = data.get("file")

    # normalize round_number
    try:
        round_number = int(round_number) if round_number else None
    except:
        round_number = None

    # 🔥 HARD CLEAN (critical for your parser)
    dataset_type = dataset_type.split("\r\n")[0]

    if not context_id or not dataset_type or not file_item or not file_item.get("filename"):
        return {"redirect": "/historical/upload?error=missing"}

    try:
        context_id = int(context_id)
    except:
        return {"redirect": "/historical/upload?error=invalid_context"}

    from app.db.historical import dataset_exists_for_context

    if dataset_exists_for_context(context_id, dataset_type):
        return {
            "redirect": f"/historical/upload?context_id={context_id}&error=duplicate_dataset"
        }

    from io import BytesIO

    ingest_historical_csv(
        context_id=context_id,
        dataset_type=dataset_type,
        file_obj=BytesIO(file_item["file"]),
        filename=file_item["filename"],
        round_number=round_number
    )

    # -------------------------
    # 🔥 Persist round to context
    # -------------------------
    if round_number is not None:
        from app.db.historical import update_context_round
        update_context_round(context_id, round_number)

    return {"redirect": f"/historical/context?context_id={context_id}"}

from app.db.historical import (
    get_context_with_product,
    get_datasets_by_context,
    get_historical_metrics_by_context
)
from app.utils.html_escape import escape_html as e
from app.db.historical import get_latest_insights_by_context


def render_historical_context_get(
    user_id,
    base_template,
    inject_nav,
    context_id,
    query_params
):

    # -------------------------
    # Fetch data (NO raw SQL here)
    # -------------------------
    context = get_context_with_product(context_id)
    datasets = get_datasets_by_context(context_id)
    metrics = get_historical_metrics_by_context(context_id)
    insights = get_latest_insights_by_context(context_id)

    if not context:
        return {"redirect": "/historical"}

    from app.db.historical import get_historical_answers_by_dataset

    # -------------------------
    # Build Profile Stats
    # -------------------------
    profile_stats = {}
    profile_segments = []
    profile_outliers = []
    sections = []
    latest_dataset_id = None

    if datasets:
        latest_dataset_id = datasets[-1].get("dataset_id")

    if latest_dataset_id:
        rows = get_historical_answers_by_dataset(latest_dataset_id)

        responses = {}

        for r in rows:
            gid = r["response_group_id"]
            q = r["question_text"]
            a = r["answer_text"]

            if gid not in responses:
                responses[gid] = {}

            responses[gid][q] = a

        gid_list = sorted(responses.keys())

        import re

        for gid in gid_list:
            for q, val in responses[gid].items():

                if not val:
                    continue

                if not is_profile_question(q):
                    continue

                if q not in profile_stats:
                    profile_stats[q] = {}

                raw_val = str(val).strip()

                # -------------------------
                # SAFE SPLIT LOGIC (no guessing)
                # -------------------------
                parts = [raw_val]

                if "," in raw_val:

                    candidates = [p.strip() for p in raw_val.split(",") if p.strip()]

                    def is_clean_token(token):
                        # Reject obvious fragments
                        if len(token) < 2:
                            return False

                        # Reject trailing fragments like "etc.)"
                        if token.lower().endswith("etc.)") or token.endswith(".)"):
                            return False

                        # If original value contains parentheses, assume it's a single label
                        if "(" in raw_val and ")" in raw_val:
                            return False

                        return True

                    clean_tokens = [t for t in candidates if is_clean_token(t)]

                    # Only split if ALL tokens are clean
                    if len(clean_tokens) == len(candidates):
                        parts = clean_tokens

                # -------------------------
                # Process parts
                # -------------------------
                for part in parts:

                    cleaned = part.strip()

                    # -------------------------
                    # Normalize numeric values
                    # -------------------------
                    numeric_match = re.match(r"^\d+(\.\d+)?%?$", cleaned)

                    if numeric_match:
                        number = cleaned.replace("%", "")

                        try:
                            number = float(number)

                            if number.is_integer():
                                key = f"{int(number)}%"
                            else:
                                key = f"{number:.1f}%"

                        except:
                            key = cleaned
                    else:
                        key = cleaned

                    if key not in profile_stats[q]:
                        profile_stats[q][key] = 0

                    profile_stats[q][key] += 1

        profile_segments, profile_outliers = build_profile_segments(
            responses,
            max_segments=5,
            min_segment_size=3
        )

        sections = build_sections_from_rows(rows)

    # -------------------------
    # NORMALIZE PROFILE STATS (FOR UI)
    # -------------------------
    normalized_segments = {}

    for question, counts in profile_stats.items():

        total = sum(counts.values()) if counts else 0

        rows_formatted = []

        for label, count in counts.items():
            percent = round((count / total) * 100, 1) if total > 0 else 0

            rows_formatted.append({
                "label": label,
                "count": count,
                "percent": percent
            })

        # sort descending by count
        rows_formatted.sort(key=lambda x: x["count"], reverse=True)

        normalized_segments[question] = rows_formatted

    # -------------------------
    # Format context
    # -------------------------
    internal = e(context.get("internal_name") or "")
    market = e(context.get("market_name") or "")
    product_name = f"{internal} ({market})" if market else internal

    round_number = context.get("round_number") or "-"
    lifecycle = e(context.get("lifecycle_stage") or "-")
    purpose = e(context.get("trial_purpose") or "-")
    invited = context.get("invited_user_count") or "-"

    # -------------------------
    # Navigation (Back + Raw)
    # -------------------------
    raw_link = ""
    if latest_dataset_id:
        raw_link = f"""
            | <a href="/historical/raw?context_id={context_id}&dataset_id={latest_dataset_id}">
                View Raw Data
            </a>
        """

    # -------------------------
    # Build HTML
    # -------------------------
    html = ""   # 🔥 REQUIRED INITIALIZATION

    # -------------------------
    # NAVIGATION (BACK LINK)
    # -------------------------
    html += """
    <div style="margin-bottom:12px;">
        <a href="/historical" style="
            font-size:13px;
            color:#2c7be5;
            text-decoration:none;
        ">
            ← Back to Historical
        </a>
    </div>
    """

    # -------------------------
    # TRIAL NAME (DB SOURCE OF TRUTH)
    # -------------------------
    internal = context.get("internal_name")
    market = context.get("market_name")

    if internal and market:
        trial_name = f"{internal} ({market})"
    elif internal:
        trial_name = internal
    elif market:
        trial_name = market
    else:
        trial_name = "Unnamed Trial"

    html += f"""
    <div style="
        margin-bottom:24px;
        padding-bottom:12px;
        border-bottom:1px solid #eee;
    ">

        <div style="
            font-size:32px;
            font-weight:700;
            letter-spacing:-0.5px;
            margin-bottom:4px;
        ">
            {e(trial_name)}
        </div>

    </div>
    """

    # -------------------------
    # EXECUTIVE SUMMARY
    # -------------------------
    summary_text = ""

    # Try to find AI-generated summary (future-proof)
    for insight in insights:
        if insight.get("insight_type") == "ai_summary":
            summary_text = insight.get("insight_summary")
            break

    if not summary_text:
        summary_text = "No executive summary generated yet."

    html += f"""
    <div class="card" style="margin-top:16px;">

        <h3 style="margin-bottom:8px;">
            Executive Summary
        </h3>

        <div style="
            font-size:14px;
            line-height:1.6;
            color:#333;
        ">
            {e(summary_text)}
        </div>

    </div>
    """

    # -------------------------
    # TRIAL ASSETS
    # -------------------------
    html += f"""
    <div class="card" style="margin-top:20px;">

        <div style="
            font-size:18px;
            font-weight:600;
            margin-bottom:16px;
        ">
            <H3>Trial Assets</H3>
        </div>

        <div style="
            display:grid;
            grid-template-columns: 1fr 1fr;
            gap:16px;
            margin-bottom:16px;
        ">

            <!-- OVERVIEW -->
            <div style="
                border:1px solid #e5e5e5;
                border-radius:6px;
                padding:14px;
                background:#fafafa;
            ">
                <div style="
                    font-size:15px;
                    font-weight:600;
                    margin-bottom:10px;
                ">
                    Overview
                </div>

                <div style="
                    font-size:14px;
                    color:#444;
                    line-height:1.8;
                ">
                    <div><strong>Round:</strong> {e(context.get("round_number") or "-")}</div>
                    <div><strong>Lifecycle:</strong> {e(context.get("lifecycle_stage") or "-")}</div>
                    <div><strong>Purpose:</strong> {e(context.get("trial_purpose") or "-")}</div>
                    <div><strong>Invited Users:</strong> {e(context.get("invited_user_count") or "-")}</div>
                </div>
            </div>

            <!-- METRICS -->
            <div style="
                border:1px solid #e5e5e5;
                border-radius:6px;
                padding:14px;
                background:#fafafa;
            ">
                <div style="
                    font-size:15px;
                    font-weight:600;
                    margin-bottom:10px;
                ">
                    Metrics
                </div>
    """

    if not metrics:
        html += """
                <div style="font-size:14px; color:#666;">
                    No metrics computed yet.
                </div>
        """
    else:
        html += f"""
                <div style="
                    display:grid;
                    grid-template-columns: 1fr auto;
                    row-gap:8px;
                    font-size:14px;
                    color:#444;
                ">

                    <div>Total Responses</div>
                    <div><strong>{metrics.get('total_responses')}</strong></div>

                    <div>Completion Rate</div>
                    <div><strong>{metrics.get('completion_rate') or '—'}</strong></div>

                    <div>Avg Response Length</div>
                    <div><strong>{metrics.get('avg_response_length')}</strong></div>

                    <div>Empty Response Rate</div>
                    <div><strong>{metrics.get('empty_response_rate')}</strong></div>

                </div>
        """

    html += """
            </div>

        </div>

        <!-- DATASET -->
        <div style="
            border:1px solid #e5e5e5;
            border-radius:6px;
            padding:14px;
            background:#fff;
        ">
            <div style="
                font-size:15px;
                font-weight:600;
                margin-bottom:10px;
            ">
                Dataset
            </div>
    """

    if not datasets:
        html += """
            <div style="font-size:13px; color:#666;">
                No datasets uploaded yet.
            </div>
        """
    else:
        for d in datasets:
            dtype = e(d.get("dataset_type") or "")
            fname = e(d.get("source_file_name") or "")

            html += f"""
            <div style="
                font-size:13px;
                color:#555;
                margin-bottom:4px;
            ">
                {dtype} — {fname}
            </div>
            """

    html += """
        </div>

    </div>
    """
    # -------------------------
    # PROFILE SUMMARY (GRID CARDS - PRESENTATION ONLY)
    # -------------------------
    if profile_stats:
        html += """
        <div class="card" style="margin-top:20px;">
            <h3>User Profile Summary</h3>

            <div style="
                display:grid;
                grid-template-columns: 1fr 1fr;
                gap:16px;
                margin-top:12px;
            ">
        """

        total_users = len(responses) if latest_dataset_id else 0

        for q, counts in profile_stats.items():

            # sort descending by count (no logic change, just ordering)
            # 🔥 Special handling for age ranges (semantic order)
            if "age" in q.lower():
                def age_key(label):
                    try:
                        return int(label.split("-")[0].strip())
                    except:
                        return 999  # fallback to end
                sorted_items = sorted(counts.items(), key=lambda x: age_key(x[0]))
            else:
                sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)

            html += f"""
                    <div style="
                        border:1px solid #e5e5e5;
                        border-radius:6px;
                        padding:14px;
                        background:#fff;
                    ">
                    <div style="
                        font-size:13px;
                        color:#888;
                        text-transform:uppercase;
                        margin-bottom:6px;
                    ">
                        {e(q)}
                    </div>
            """

            top_count = max(counts.values()) if counts else None

            for val, count in sorted_items:
                pct = (count / total_users) * 100 if total_users else 0

                is_top = count == top_count

                html += f"""
                    <div style="
                        display:grid;
                        grid-template-columns: 55% 20% 25%;
                        align-items:center;
                        font-size:13px;
                        margin-bottom:2px;
                        {'font-weight:500; color:#333;' if is_top else 'color:#666;'}
                    ">
                        <div>{e(val)}</div>

                        <div style="
                            text-align:right;
                            font-variant-numeric: tabular-nums;
                        ">
                            {count}
                        </div>

                        <div style="
                            text-align:right;
                            color:#999;
                            font-variant-numeric: tabular-nums;
                        ">
                            {pct:.1f}%
                        </div>
                    </div>
                """

            html += "</div>"

        html += "</div></div>"

    # -------------------------
    # SEGMENTS (CARD STYLE)
    # -------------------------
    if profile_segments:
        html += """
        <div class="card" style="margin-top:20px;">
            <h3>User Segments</h3>
            <p style="font-size:13px; color:#666;">
                Deterministic groupings based on shared profile attributes.
            </p>
        """
        html += """
            <div style="
                display:grid;
                grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
                gap:20px;
                align-items:start;
            ">
        """
        for idx, segment in enumerate(profile_segments, start=1):

            size = segment["size"]
            attributes = segment["attributes"]

            # -------------------------
            # 🔥 Compute Segment Strength
            # -------------------------
            segment_user_ids = segment.get("user_ids", [])
            matched_users = [gid for gid in segment_user_ids if gid in responses]

            question_answer_map = {}

            for gid in segment_user_ids:
                user_answers = responses.get(gid, {})

                for q, val in user_answers.items():

                    if not val:
                        continue

                    # ❌ Skip profile questions
                    segment_attribute_pairs = set(
                        (attr_q, str(attr_val).strip())
                        for attr_q, attr_val in attributes
                    )

                    if (q, str(val).strip()) in segment_attribute_pairs:
                        continue

                    # ❌ Skip long free-text
                    if len(str(val)) > 1000:
                        continue

                    if q not in question_answer_map:
                        question_answer_map[q] = {}

                    key = str(val).strip()

                    if key not in question_answer_map[q]:
                        question_answer_map[q][key] = 0

                    question_answer_map[q][key] += 1

            # -------------------------
            # 🔥 Compute dominance
            # -------------------------
            dominance_scores = []

            for q, counts in question_answer_map.items():

                total = sum(counts.values())
                if total == 0:
                    continue

                top = max(counts.values())
                dominance = top / total

                dominance_scores.append(dominance)

            # -------------------------
            # 🔥 Final strength
            # -------------------------
            if dominance_scores:
                segment_strength = sum(dominance_scores) / len(dominance_scores)
            else:
                segment_strength = None

            # -------------------------
            # 🔥 Label
            # -------------------------
            if segment_strength is None:
                strength_label = "N/A"
            elif segment_strength >= 0.75:
                strength_label = "Strong"
            elif segment_strength >= 0.55:
                strength_label = "Moderate"
            else:
                strength_label = "Weak"

            # -------------------------
            # SEGMENT CARD START
            # -------------------------
            html += f"""
            <div style="
                border:1px solid #e5e5e5;
                border-radius:8px;
                padding:16px;
                background:#fff;
            ">

                <div style="
                    display:flex;
                    justify-content:space-between;
                    align-items:flex-start;
                    margin-bottom:10px;
                ">
                    <div>
                        <div style="font-weight:600;">
                            Segment {idx}
                        </div>

                        <div style="font-size:11px; color:#aaa; margin-top:4px;">
                            users: {len(segment_user_ids)} | matched: {len(matched_users)}
                        </div>
                    </div>

                    <div style="
                        display:flex;
                        gap:12px;
                        align-items:center;
                        font-size:12px;
                        color:#666;
                    ">
                        <div>
                            Strength:
                            <strong>
                                {f"{segment_strength:.2f}" if segment_strength is not None else "—"}
                            </strong>
                            ({strength_label})
                        </div>

                        <div>
                            Users: {size}
                        </div>
                    </div>
                </div>
            """

            # 🔥 Normalize label (presentation only — no data mutation)
            def _normalize_label(q):
                import re

                if not q:
                    return ""

                label = q.strip()

                # Remove leading survey-style phrasing
                label = re.sub(r"(?i)^what is your\s+", "", label)
                label = re.sub(r"(?i)^which\s+", "", label)
                label = re.sub(r"(?i)^provide\s+", "", label)
                label = re.sub(r"(?i)^please\s+", "", label)
                label = re.sub(r"(?i)^refer to.*?:\s*", "", label)

                # Remove trailing punctuation
                label = re.sub(r"[?:.]$", "", label)

                # Collapse excessive whitespace
                label = re.sub(r"\s+", " ", label).strip()

                # Title case (safe normalization)
                if label:
                    label = label[0].upper() + label[1:]

                return label


            # 🔥 Render each attribute cleanly
            for q, val in attributes:

                label = _normalize_label(q)

                html += f"""
                <div style="
                    display:grid;
                    grid-template-columns: minmax(240px, 1.4fr) minmax(140px, 1fr);
                    column-gap:16px;
                    font-size:13px;
                    margin-bottom:8px;
                    align-items:start;
                ">
                    <div style="
                        color:#888;
                        line-height:1.4;
                    ">
                        {e(label)}
                    </div>

                    <div style="
                        font-weight:500;
                        color:#333;
                        line-height:1.4;
                    ">
                        {e(val)}
                    </div>
                </div>
                """
            # Close segment card
            html += "</div>"
        # -------------------------
        # OUTLIERS (CARD STYLE)
        # -------------------------
        if profile_outliers:
            html += f"""
            <div style="
                margin-top:16px;
                padding:10px;
                background:#fafafa;
                border:1px dashed #ddd;
                border-radius:6px;
                font-size:13px;
                color:#666;
            ">
                <strong>Outliers:</strong>
                {len(profile_outliers)} user(s) were not covered by the selected segments.
            </div>
            """
        html += "</div>"

    # -------------------------
    # SECTION RESULTS
    # -------------------------
    if sections:
        html += f"""
        <div style="
            display:flex;
            align-items:center;
            justify-content:space-between;
            margin-top:24px;
            margin-bottom:10px;
        ">

            <div style="display:flex; align-items:center; gap:12px;">
                <h3 style="margin:0;">
                    Section Results
                </h3>

                <div style="
                    font-size:12px;
                    color:#888;
                    display:flex;
                    gap:8px;
                    margin-left:8px;
                ">
                    <a href="#" onclick="expandAllSections(); return false;" style="color:#888;">
                        Expand all
                    </a>
                    <span>|</span>
                    <a href="#" onclick="collapseAllSections(); return false;" style="color:#888;">
                        Collapse all
                    </a>
                </div>
            </div>

            <div style="
                display:flex;
                gap:8px;
            ">

                <form method="POST" action="/historical/generate-section-names" style="margin:0;"
                    onsubmit="startAnalysisLoading()">
                    <input type="hidden" name="dataset_id" value="{latest_dataset_id}">
                    <input type="hidden" name="context_id" value="{context_id}">
                    <button type="submit" style="font-size:12px; padding:6px 10px;">
                        Generate Names
                    </button>
                </form>

                <form method="POST" action="/historical/generate-section-summaries" style="margin:0;"
                    onsubmit="startAnalysisLoading()">
                    <input type="hidden" name="dataset_id" value="{latest_dataset_id}">
                    <input type="hidden" name="context_id" value="{context_id}">
                    <button type="submit" style="font-size:12px; padding:6px 10px;">
                        Generate Summaries
                    </button>
                </form>

            </div>

        </div>
        """

        from app.db.historical import get_section_names

        section_names = {}
        if latest_dataset_id:
            section_names = get_section_names(latest_dataset_id)

        from app.db.historical import get_section_summaries

        section_summaries = {}
        if latest_dataset_id:
            section_summaries = get_section_summaries(latest_dataset_id)

        for idx, section in enumerate(sections, start=1):

            section_name = section_names.get(idx, f"Section {idx}")

            html += f"""
            <div class="rail-group historical-section-result collapsed" data-historical-section="{idx}" style="
                margin-top:20px;
                margin-bottom:20px;
                border:1px solid #e5e5e5;
                border-radius:8px;
                background:#fafafa;
            ">

                <div class="rail-toggle" style="
                    display:flex;
                    align-items:center;
                    padding:14px 16px;
                    border-bottom:1px solid #eee;
                    cursor:pointer;
                ">

                    <!-- LEFT: title -->
                    <div style="
                        font-size:15px;
                        font-weight:600;
                    ">
                        {e(section_name)}
                    </div>

                    <!-- RIGHT: actions -->
                    <div style="
                        display:flex;
                        align-items:center;
                        gap:12px;
                        margin-left:auto;
                    ">

                        <div style="
                            font-size:12px;
                            color:#888;
                        ">
                            <a href="/historical/edit-section-name?dataset_id={latest_dataset_id}&section_index={idx}&context_id={context_id}">
                                edit
                            </a>
                        </div>

                    </div>

                </div>

                <div class="rail-content" style="
                    padding:14px 16px;
                ">
            """

            # -------------------------
            # Quant Questions
            # -------------------------
            html += """
                <div style="
                    display:flex;
                    gap:12px;
                    flex-wrap:wrap;
                    margin-left:0px;
                    margin-bottom:10px;
                ">
            """

            for q in section["quant_questions"]:
                question = e(q["question"])
                values = q["values"]

                numeric_vals = []
                counts = {}

                for v in values:
                    if v is None:
                        continue

                    v_str = str(v).strip()

                    # numeric
                    if v_str.replace(".", "", 1).isdigit():
                        numeric_vals.append(float(v_str))
                    else:
                        counts[v_str] = counts.get(v_str, 0) + 1

                # -------------------------
                # NUMERIC CARD
                # -------------------------
                if numeric_vals:
                    avg = sum(numeric_vals) / len(numeric_vals)
                    bar_width = int((avg / 5) * 100)

                    html += f"""
                        <div style="
                            padding:10px 12px;
                            border:1px solid #e5e5e5;
                            border-radius:6px;
                            display:flex;
                            align-items:center;
                            justify-content:space-between;
                            gap:12px;
                            width:calc(50% - 6px);
                            box-sizing:border-box;
                        ">

                            <div style="
                                font-size:14px;
                                flex:1;
                            ">
                                {question}
                            </div>

                            <div style="
                                display:flex;
                                align-items:center;
                                gap:8px;
                                min-width:160px;
                                justify-content:flex-end;
                            ">

                                <div style="
                                    background:#eee;
                                    height:6px;
                                    width:100px;
                                    border-radius:4px;
                                    overflow:hidden;
                                ">
                                    <div style="
                                        width:{bar_width}%;
                                        background:#2c7be5;
                                        height:100%;
                                    "></div>
                                </div>

                                <div style="
                                    font-size:13px;
                                    color:#666;
                                    width:36px;
                                    text-align:right;
                                ">
                                    {avg:.2f}
                                </div>

                            </div>

                        </div>
                    """

                # -------------------------
                # MULTI-CHOICE CARD (aligned with grid)
                # -------------------------
                elif counts:

                    # -------------------------
                    # 🔥 Split multi-select into individual signals
                    # -------------------------
                    split_counts = {}

                    for opt, cnt in counts.items():
                        parts = [p.strip() for p in opt.split(",")]

                        for part in parts:
                            if not part:
                                continue

                            if part not in split_counts:
                                split_counts[part] = 0

                            split_counts[part] += cnt

                    # -------------------------
                    # Sort descending
                    # -------------------------
                    sorted_items = sorted(split_counts.items(), key=lambda x: x[1], reverse=True)

                    max_val = max(split_counts.values()) if split_counts else 1

                    # -------------------------
                    # Build UI (label + count + bar)
                    # -------------------------
                    options_html = ""

                    for opt, cnt in sorted_items:
                        bar_width = int((cnt / max_val) * 100)

                        options_html += f"""
                            <div style="margin-bottom:8px;">

                                <div style="
                                    display:flex;
                                    justify-content:space-between;
                                    font-size:13px;
                                    color:#444;
                                    margin-bottom:2px;
                                ">
                                    <div>{e(opt)}</div>
                                    <div style="
                                        font-variant-numeric: tabular-nums;
                                    ">
                                        {cnt}
                                    </div>
                                </div>

                                <div style="
                                    background:#eee;
                                    height:6px;
                                    border-radius:4px;
                                    overflow:hidden;
                                ">
                                    <div style="
                                        width:{bar_width}%;
                                        background:#2c7be5;
                                        height:100%;
                                    "></div>
                                </div>

                            </div>
                        """

                    html += f"""
                        <div style="
                            padding:10px 12px;
                            border:1px solid #e5e5e5;
                            border-radius:6px;
                            width:calc(50% - 6px);
                            box-sizing:border-box;
                        ">

                            <div style="
                                font-size:14px;
                                margin-bottom:8px;
                            ">
                                {question}
                            </div>

                            <div>
                                {options_html}
                            </div>

                        </div>
                    """
            # 🔥 CLOSE container ONCE (after loop)
            html += "</div>"

            # -------------------------
            # SWOT Summary (Card Layout)
            # -------------------------
            import json

            summary = section_summaries.get(idx)

            if summary:
                try:
                    parsed = json.loads(summary)
                except:
                    parsed = {}

                def build_items(items):
                    html_items = ""
                    for i, item in enumerate(items):
                        if i == 0:
                            # 🔥 primary insight
                            html_items += f"<li style='font-weight:500;'>{e(item)}</li>"
                        else:
                            html_items += f"<li style='color:#777;'>{e(item)}</li>"
                    return html_items

                strengths = parsed.get("strengths", [])
                weaknesses = parsed.get("weaknesses", [])
                opportunities = parsed.get("opportunities", [])
                threats = parsed.get("threats", [])

                html += """
                    <div style="
                        display:flex;
                        gap:12px;
                        flex-wrap:wrap;
                        margin-left:12px;
                        margin-top:10px;
                    ">
                """

                def swot_card(title, icon, items):
                    return f"""
                        <div style="
                            border:1px solid #e5e5e5;
                            border-radius:6px;
                            padding:10px 12px;
                            width:calc(50% - 6px);
                            box-sizing:border-box;
                        ">

                            <div style="
                                font-size:13px;
                                color:#888;
                                text-transform:uppercase;
                                margin-bottom:6px;
                            ">
                                {icon} {title}
                            </div>

                            <ul style="
                                margin:0;
                                padding-left:16px;
                                font-size:14px;
                            ">
                                {build_items(items)}
                            </ul>

                        </div>
                    """

                html += swot_card("Strengths", "💪", strengths)
                html += swot_card("Weaknesses", "⚠️", weaknesses)
                html += swot_card("Opportunities", "🚀", opportunities)
                html += swot_card("Threats", "🔥", threats)

                # Close SWOT container
                html += "</div>"
            
            # 🔥 ONLY CLOSE HERE
            html += "</div></div>"  # closes rail-content + rail-group

    # -------------------------
    # INSIGHTS
    # -------------------------

    html += f"""
    <div class="card" style="margin-top:20px;">

        <div style="
            display:flex;
            justify-content:space-between;
            align-items:center;
            margin-bottom:12px;
        ">
            <h3 style="margin:0;">Insights</h3>

            <form method="POST" action="/historical/generate-insights" style="margin:0;"
                onsubmit="startAnalysisLoading()">
                <input type="hidden" name="context_id" value="{context_id}">
                <button type="submit" style="
                    background:#2c7be5;
                    color:white;
                    border:none;
                    padding:6px 10px;
                    border-radius:4px;
                    cursor:pointer;
                    font-size:13px;
                ">
                    Generate Insights
                </button>
            </form>
        </div>
    """

    # -------------------------
    # EMPTY STATE
    # -------------------------
    if not insights:
        html += """
            <div style="color:#666; font-size:14px;">
                No insights generated yet.
            </div>
        """
    else:
        import json

        # -------------------------
        # GROUP BY SECTION (FIXED)
        # -------------------------
        grouped = {}

        for insight in insights:
            if insight.get("insight_type") != "ai_insight":
                continue

            section = insight.get("section_name") or "General"
            grouped.setdefault(section, []).append(insight)

        # -------------------------
        # RENDER
        # -------------------------
        for section_name, items in grouped.items():

            html += f"""
            <div style="
                margin-bottom:16px;
                padding:12px;
                border:1px solid #e5e5e5;
                border-radius:6px;
                background:#fafafa;
            ">
                <div style="
                    font-size:13px;
                    text-transform:uppercase;
                    color:#888;
                    margin-bottom:8px;
                ">
                    {e(section_name)}
                </div>
            """

            html += """
            <div style="
                display:grid;
                grid-template-columns: 1fr 1fr;
                gap:12px;
            ">
            """

            for insight in items:

                raw_json = insight.get("insight_json")
                summary = e(insight.get("insight_summary") or "")

                if raw_json:
                    try:
                        data = json.loads(raw_json)
                        insight_type = data.get("type")

                        # -------------------------
                        # AI INSIGHT (UPGRADED CARD)
                        # -------------------------
                        if insight_type == "ai_insight":

                            title = e(data.get("title", ""))
                            explanation = e(data.get("explanation", ""))
                            evidence = data.get("evidence", [])
                            impact = (data.get("impact") or "").lower()

                            # -------------------------
                            # IMPACT + SENTIMENT VISUAL MAPPING (2-AXIS)
                            # -------------------------
                            impact = (data.get("impact") or "").lower()
                            sentiment = (data.get("sentiment") or "neutral").lower()

                            # Default fallback
                            border_color = "#6c757d"
                            badge = "NEUTRAL"

                            # Mixed (special case)
                            if sentiment == "mixed":
                                border_color = "#7b61ff"  # purple
                                badge = f"{impact.upper()} • MIXED"

                            # Neutral
                            elif sentiment == "neutral":
                                border_color = "#999"
                                badge = f"{impact.upper()} • NEUTRAL"

                            # Positive axis
                            elif sentiment == "positive":

                                if impact == "high":
                                    border_color = "#2fbf71"  # strong green
                                elif impact == "medium":
                                    border_color = "#3b82f6"  # blue
                                else:
                                    border_color = "#60a5fa"  # light blue

                                badge = f"{impact.upper()} • POSITIVE"

                            # Negative axis
                            elif sentiment == "negative":

                                if impact == "high":
                                    border_color = "#e5533d"  # red
                                elif impact == "medium":
                                    border_color = "#f59e0b"  # amber
                                else:
                                    border_color = "#fbbf24"  # light amber

                                badge = f"{impact.upper()} • NEGATIVE"

                            html += f"""
                            <div style="
                                margin-bottom:16px;
                                padding:14px;
                                border:1px solid #e5e5e5;
                                border-left:4px solid {border_color};
                                border-radius:8px;
                                background:#fff;
                            ">

                                <div style="
                                    display:flex;
                                    justify-content:space-between;
                                    align-items:center;
                                    margin-bottom:6px;
                                ">
                                    <div style="
                                        font-weight:600;
                                        font-size:15px;
                                    ">
                                        🧠 {title}
                                    </div>

                                    <div style="
                                        font-size:11px;
                                        padding:2px 6px;
                                        border-radius:4px;
                                        background:{border_color}20;
                                        color:{border_color};
                                        font-weight:500;
                                    ">
                                        {badge}
                                    </div>
                                </div>

                                <div style="
                                    font-size:13px;
                                    color:#444;
                                    line-height:1.5;
                                    margin-bottom:8px;
                                ">
                                    {explanation}
                                </div>
                            """

                            if evidence:
                                html += """
                                <div style="
                                    font-size:12px;
                                    color:#888;
                                    margin-bottom:4px;
                                ">
                                    Evidence:
                                </div>
                                """

                                html += "<ul style='margin:4px 0 0 16px; padding:0;'>"
                                for q in evidence[:3]:
                                    clean_q = q.strip().strip('"').strip("'")

                                    html += f"""
                                    <li style="
                                        font-size:13px;
                                        color:#555;
                                        margin-bottom:4px;
                                    ">
                                        “{e(clean_q)}”
                                    </li>
                                    """
                                html += "</ul>"

                            html += "</div>"

                        # -------------------------
                        # PATTERN CLUSTER
                        # -------------------------
                        elif insight_type == "pattern_cluster":

                            title = e(data.get("title", ""))
                            explanation = e(data.get("explanation", ""))
                            quotes = data.get("quotes", [])
                            impact = data.get("impact", "")

                            html += f"""
                            <div style="
                                margin-bottom:12px;
                                padding:10px;
                                border-left:3px solid #2c7be5;
                                background:#fff;
                            ">
                                <div style="font-weight:600;">🔍 {title}</div>
                                <div style="color:#444; margin:6px 0;">{explanation}</div>
                            """

                            if impact:
                                html += f"""
                                <div style="font-size:12px; color:#666;">
                                    Impact: {e(impact)}
                                </div>
                                """

                            if quotes:
                                html += "<ul style='margin-top:6px;'>"
                                for q in quotes[:3]:
                                    html += f"<li style='color:#555;'>\"{e(q)}\"</li>"
                                html += "</ul>"

                            html += "</div>"

                        # -------------------------
                        # FALLBACK SUMMARY
                        # -------------------------
                        else:
                            html += f"""
                            <div style="margin-bottom:8px; font-size:14px;">
                                {summary}
                            </div>
                            """

                    except Exception as ex:
                        html += f"""
                        <div style="margin-bottom:8px; font-size:14px;">
                            {summary}
                        </div>
                        """

                else:
                    html += f"""
                    <div style="margin-bottom:8px; font-size:14px;">
                        {summary}
                    </div>
                    """
            html += "</div>"

    # -------------------------
    # CLOSE CARD
    # -------------------------
    html += """
    </div>
    """
    # -------------------------
    # Final render
    # -------------------------
    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}

from app.db.historical import get_all_historical_contexts
from app.db.connection import get_db_connection

def render_historical_upload_get(user_id, base_template, inject_nav, context_id, query_params):

    from app.db.historical import get_context_with_product, get_datasets_by_context

    context = get_context_with_product(context_id)
    error = query_params.get("error", [None])[0]

    datasets = get_datasets_by_context(context_id)

    if not context:
        return {"redirect": "/historical"}

    # -------------------------
    # Build HTML
    # -------------------------

    safe_context_id_raw = str(context_id)

    # -------------------------
    # Build trial name (reuse existing logic)
    # -------------------------
    internal = context.get("internal_name")
    market = context.get("market_name")

    if internal and market:
        trial_name = f"{internal} ({market})"
    elif internal:
        trial_name = internal
    elif market:
        trial_name = market
    else:
        trial_name = "Unnamed Trial"

    html = f"""
    <div class="results-section">
        <h2>Upload Data</h2>
        <div style="
            font-size:14px;
            color:#666;
            margin-top:4px;
            margin-bottom:16px;
        ">
            {e(trial_name)}
        </div>
    """

    # -------------------------
    # Error block (OUTSIDE f-string)
    # -------------------------
    if error == "duplicate_dataset":
        html += """
        <div class="alert alert-error">
            Dataset already exists for this context.
        </div>
        """

    # -------------------------
    # Continue HTML
    # -------------------------
    html += f"""
        <form method="POST" action="/historical/upload" enctype="multipart/form-data"
            onsubmit="startAnalysisLoading()">

            <input type="hidden" name="context_id" value="{safe_context_id_raw}">

            <label>Dataset Name:</label><br>
            <input type="text" name="dataset_type" placeholder="e.g. survey_1, validation_round2" required><br><br>

            <label>Round:</label><br>
            <input type="number" name="round_number" value="1"><br><br>

            <label>CSV File:</label><br>
            <input type="file" name="file" required><br><br>

            <button type="submit">Upload</button>

        </form>
    </div>
    """
    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def handle_historical_create_context_post(data):

    product_id = data.get("product_id", [""])[0]
    round_number = data.get("round_number", [""])[0]
    lifecycle_stage = data.get("lifecycle_stage", [""])[0]
    trial_purpose = data.get("trial_purpose", [""])[0]
    mix = data.get("internal_vs_external_mix", [""])[0]
    invited = data.get("invited_user_count", [""])[0]
    description = data.get("description", [""])[0]

# -------------------------
# Validate required fields
# -------------------------

    if not product_id:
        return {"error": "missing_product"}

    if not lifecycle_stage:
        return {"error": "missing_stage"}

    if not trial_purpose:
        return {"error": "missing_purpose"}

    if not mix:
        return {"error": "missing_scope"}

    try:
        product_id = int(product_id)
    except:
        return {"error": "invalid_product"}

    round_number = int(round_number) if round_number else None
    invited = int(invited) if invited else None

    from app.db.historical import create_historical_context

    context_id = create_historical_context(
        product_id,
        round_number,
        lifecycle_stage,
        trial_purpose,
        mix,
        invited,
        description
    )

    return {
        "redirect": f"/historical/upload?context_id={context_id}"
    }

from app.db.connection import get_db_connection

def render_historical_create_context_get(user_id, base_template, inject_nav):

    from app.db.historical import get_all_products_for_context_creation

    products = get_all_products_for_context_creation()

    product_options = ""

    for p in products:
        internal = e(p.get("internal_name") or "")
        market = e(p.get("market_name") or "")

        label = internal
        if market:
            label += f" ({market})"

        product_options += f"<option value='{p['product_id']}'>{label}</option>"

    html = f"""
    <div class="results-section">
        <h2>Create Legacy Trial Context</h2>

        <form method="POST" action="/historical/create-context" class="form-stack">

            <div class="form-group">
                <label>Product</label>
                <select name="product_id" class="form-input" required>
                    <option value="" disabled selected>Select your product</option>
                    {product_options}
                </select>
            </div>

            <div class="form-group">
                <label>Lifecycle Stage</label>
                <select name="lifecycle_stage" class="form-input" required>
                    <option value="" disabled selected>Select your stage</option>
                    <option value="Pre G1">Pre G1</option>
                    <option value="PB1">PB1</option>
                    <option value="PB2">PB2</option>
                    <option value="PBX">PBX</option>
                    <option value="GX">GX</option>
                </select>
            </div>

            <div class="form-group">
                <label>Trial Purpose</label>
                <select name="trial_purpose" class="form-input" required>
                    <option value="" disabled selected>Select your purpose</option>

                    <option value="Out of Box and First Impressions Survey">
                        Out of Box and First Impressions Survey
                    </option>

                    <option value="Usage Experience and KPIs Survey">
                        Usage Experience and KPIs Survey
                    </option>

                    <option value="Other">
                        Other
                    </option>

                </select>
            </div>

            <div class="form-group">
                <label>Internal vs External</label>
                <select name="internal_vs_external_mix" class="form-input" required>
                    <option value="" disabled selected>Set user scope</option>
                    <option value="Internal">Internal</option>
                    <option value="External">External</option>
                    <option value="Hybrid">Hybrid</option>
                </select>
            </div>

            <div class="form-group">
                <label>Invited User Count</label>
                <input type="number" name="invited_user_count" class="form-input" value="30">
            </div>

            <div class="form-group">
                <label>Description (Optional)</label>
                <textarea name="description" class="form-input" rows="4"></textarea>
            </div>

            <div style="margin-top: 16px;">
                <button type="submit" class="btn-primary">Create Context</button>
            </div>

            <div style="margin-top: 12px; font-size: 13px; color: #666;">
                After creating this context, you will upload survey data in the next step.
            </div>

        </form>
    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}

from app.db.historical import get_legacy_contexts

def render_historical_landing_get(user_id, base_template, inject_nav):

    contexts = get_legacy_contexts()

    html = """
    <div class="results-section">
        <h2>Legacy Trial History</h2>

        <div style="margin-bottom: 16px;">
            <a href="/historical/create-context" class="btn-secondary">
                + Create Legacy Context
            </a>
        </div>
    """

    if not contexts:
        html += "<p>No historical trials loaded yet.</p>"
    else:
        html += """
        <div class="table-scroll">
        <table class="data-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Internal</th>
                    <th>Market</th>
                    <th>Survey</th>
                    <th>Round</th>
                    <th>Lifecycle</th>
                    <th>Purpose</th>
                    <th>Report</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
        """

        for idx, c in enumerate(contexts, start=1):

            internal = e(c.get("internal_name") or "-")
            product = e(c.get("market_name") or "-")
            round_number = c.get("dataset_round")
            dataset_name = e(c.get("dataset_name") or "-")
            round_display = str(round_number) if round_number else "-"
            lifecycle = e(c.get("lifecycle_stage") or "-")
            purpose = e(c.get("trial_purpose") or "-")
            context_id = c.get("context_id")

            dataset_id = c.get("dataset_id")

            raw_link = ""
            if dataset_id:
                raw_link = f"""
                    | <a href="/historical/raw?context_id={context_id}&dataset_id={dataset_id}">
                        Raw
                    </a>
                """

            html += f"""
            <tr>
                <td>{idx}</td>
                <td>{internal}</td>
                <td>{product}</td>
                <td>{dataset_name}</td>
                <td>{round_display}</td>
                <td>{lifecycle}</td>
                <td>{purpose}</td>
                <td>
                    <a href="/historical/context?context_id={context_id}">
                        View Report
                    </a>
                    {raw_link}
                </td>
                <td>
                    <a href="/historical/upload?context_id={context_id}">
                        Upload
                    </a>
                </td>
            </tr>
            """
        html += """
            </tbody>
        </table>
        </div>
        """

    html += "</div>"

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}

def render_historical_raw_get(user_id, base_template, inject_nav, dataset_id, context_id):
    from app.db.historical import get_historical_answers_by_dataset

    # -------------------------
    # Fetch data
    # -------------------------
    rows = get_historical_answers_by_dataset(dataset_id)

    if not rows:
        html = "<div class='results-section'><p>No data found.</p></div>"
        full_html = base_template.replace("__BODY__", html)
        full_html = inject_nav(full_html, mode="internal")
        return {"html": full_html}

    # -------------------------
    # Pivot: build structure
    # -------------------------
    responses = {}
    profile_questions = []
    survey_questions = []

    for r in rows:
        gid = r["response_group_id"]
        q = r["question_text"]
        a = r["answer_text"]

        if gid not in responses:
            responses[gid] = {}

        q_lower = q.lower()

        # Remove PII columns entirely
        if any(token in q_lower for token in ["name", "email"]):
            continue

        # Split profile vs survey
        if is_profile_question(q):
            if q not in profile_questions:
                profile_questions.append(q)
        else:
            if q not in survey_questions:
                survey_questions.append(q)

        responses[gid][q] = a

    # Stable ordering
    gid_list = sorted(responses.keys())

    # -------------------------
    # Build HTML
    # -------------------------
    html = f"""
    <div class="results-section">

        <div style="margin-bottom: 16px;">
            <a href="/historical/context?context_id={context_id}" class="btn-secondary">
                ← Back to Context
            </a>
        </div>

        <h2>Reconstructed Survey (Raw Data)</h2>
    """

    # -------------------------
    # SURVEY TABLE
    # -------------------------
    if survey_questions:
        html += """
        <h3 style="margin-top:30px;">Survey Responses</h3>
        <div class="table-scroll">
        <table class="data-table">
            <thead>
                <tr>
                    <th>User</th>
        """

        for q in survey_questions:
            html += f"<th>{e(q)}</th>"

        html += "</tr></thead><tbody>"

        for idx, gid in enumerate(gid_list, start=1):
            html += f"<tr><td>User {idx}</td>"

            for q in survey_questions:
                val = responses[gid].get(q, "")
                html += f"<td>{e(val or '')}</td>"

            html += "</tr>"

        html += """
            </tbody>
        </table>
        </div>
        """

    html += "</div>"

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}

def build_profile_segments(responses, *, max_segments=5, min_segment_size=3):
    """
    Deterministic segmentation engine.

    Input:
    - responses: {response_group_id: {question_text: answer_text}}

    Output:
    - segments: list of segment dicts
    - outlier_ids: response_group_ids not covered by any selected segment
    """

    from itertools import combinations

    # -------------------------
    # Build normalized profile map
    # -------------------------
    user_profiles = {}

    for gid, answers in responses.items():
        profile = {}

        for q, val in answers.items():
            if not val:
                continue

            if not is_profile_question(q):
                continue

            clean_val = str(val).strip()
            if not clean_val:
                continue

            profile[q] = clean_val

        user_profiles[gid] = profile

    total_users = len(user_profiles)

    if total_users == 0:
        return [], []

    # -------------------------
    # Generate candidate segments
    # -------------------------
    candidates = []

    for dimension_count in [2]:
        buckets = {}

        for gid, profile in user_profiles.items():
            items = sorted(profile.items(), key=lambda x: x[0])

            for combo in combinations(items, dimension_count):
                key = tuple(combo)

                if key not in buckets:
                    buckets[key] = []

                buckets[key].append(gid)

        for key, member_ids in buckets.items():
            unique_members = sorted(set(member_ids))

            if len(unique_members) < min_segment_size:
                continue

            candidates.append({
                "attributes": key,
                "member_ids": unique_members,
                "user_ids": unique_members,   # 🔥 ADD THIS LINE (DO NOT REMOVE member_ids)
                "size": len(unique_members),
                "dimension_count": dimension_count,
            })

    # -------------------------
    # Rank candidates
    # Prefer:
    # 1. Larger groups
    # 2. More specific groups
    # 3. Deterministic attribute order
    # -------------------------
    candidates = sorted(
        candidates,
        key=lambda s: (
            -s["size"],
            -s["dimension_count"],
            str(s["attributes"])
        )
    )

    # -------------------------
    # Greedy selection to maximize coverage
    # -------------------------
    selected = []
    covered = set()

    for candidate in candidates:
        candidate_members = set(candidate["member_ids"])
        MIN_NEW_USERS = 3   # or 10% of total
        MIN_NEW_RATIO = 0.4   # 40% of segment must be new

        new_coverage = candidate_members - covered

        if len(new_coverage) < MIN_NEW_USERS:
            continue

        if len(new_coverage) / len(candidate_members) < MIN_NEW_RATIO:
            continue

        selected.append(candidate)
        covered.update(candidate_members)

        if len(selected) >= max_segments:
            break

    outlier_ids = sorted(set(user_profiles.keys()) - covered)

    return selected, outlier_ids

def is_followup_prompt(q: str) -> bool:
    q_clean = q.strip().lower()

    # must be a question
    if "?" not in q_clean:
        return False

    # short = generic follow-up (not real survey question)
    if len(q_clean) > 80:
        return False

    # contains "more detail" intent
    followup_markers = [
        "elaborate",
        "more",
        "anything",
        "else",
        "share",
        "expand"
    ]

    has_marker = any(m in q_clean for m in followup_markers)

    # exclude real questions that happen to contain "more"
    exclusion_markers = [
        "how",
        "what",
        "which",
        "rate",
        "feel",
        "experience",
        "version",
        "device",
        "color",
        "size",
        "weight",
        "connection"
    ]

    has_exclusion = any(e in q_clean for e in exclusion_markers)

    return has_marker and not has_exclusion

def build_sections_from_rows(rows):
    """
    Build survey sections deterministically.

    Section = consecutive numeric/categorical questions until a qualitative question.
    """

    # -------------------------
    # Build question map
    # -------------------------
    question_map = {}
    question_order = {}

    for r in rows:
        pos = r["question_position"]
        q = r["question_text"]
        val = r["answer_text"]

        if pos not in question_map:
            question_map[pos] = {
                "question": q,
                "values": []
            }
            question_order[pos] = pos

        question_map[pos]["values"].append(val)

    # 🔥 TRUE ORDER (by position)
    ordered_positions = sorted(question_map.keys())

    # -------------------------
    # Build sections
    # -------------------------
    sections = []
    current = {
        "quant_questions": [],
        "qual_question": None
    }

    for pos in ordered_positions:

        q = question_map[pos]["question"]
        values = question_map[pos]["values"]

        # -------------------------
        # 🔥 SKIP PROFILE QUESTIONS
        # -------------------------
        if is_profile_question(q):
            continue

        q_lower = q.lower()

        if "agree to be contacted" in q_lower:
            continue

        # -------------------------
        # 🔥 FILTER: remove non-discriminating questions
        # Rule: if all answer frequencies are identical → no signal
        # -------------------------
        from collections import Counter

        counts = Counter(values)

        if counts:
            unique_counts = set(counts.values())

            if len(unique_counts) == 1:
                # DEBUG (optional)
                print(f"IGNORED QUESTION (uniform distribution): {q}")
                continue

        # 🔥 STRUCTURAL QUAL OVERRIDE
        if is_followup_prompt(q):
            q_type = "qualitative"
        else:
            q_type = classify(values)

        # -------------------------
        # Numeric + Categorical
        # -------------------------
        if q_type in ["numeric", "categorical"]:

            current["quant_questions"].append({
                "question": q,
                "values": values,
                "type": q_type
            })

        # -------------------------
        # Qualitative → boundary
        # -------------------------
        elif q_type == "qualitative":


            if current["quant_questions"]:
                for qq in current["quant_questions"]:
                    pass

                current["qual_question"] = {
                    "question": q,
                    "values": values
                }

                sections.append(current)

                current = {
                    "quant_questions": [],
                    "qual_question": None
                }


        # -------------------------
        # Safety fallback
        # -------------------------
        else:
            current["quant_questions"].append({
                "question": q,
                "values": values,
                "type": "unknown"
            })

    # -------------------------
    # trailing section
    # -------------------------
    if current["quant_questions"]:
        sections.append(current)

    return sections

def classify_question_type(answer_values):
    numeric_count = 0
    text_count = 0

    for v in answer_values:
        if v is None:
            continue

        v = str(v).strip()

        # numeric (1–5, etc.)
        if v.replace(".", "", 1).isdigit():
            numeric_count += 1
        else:
            text_count += 1

    if numeric_count > text_count:
        return "quant"
    else:
        return "qual"
    
# -------------------------
# Helper: classify profile questions
# -------------------------
def is_profile_question(q: str) -> bool:
    import re

    if not q:
        return False

    q = q.lower().strip()

    # -------------------------
    # Core profile signals (stable traits)
    # -------------------------
    keyword_signals = [
        "gender",
        "age",
        "country",
        "city",
        "region",
        "location",
        "occupation",
        "role",
        "industry",
        "os",
        "operating system"
    ]

    # -------------------------
    # Phrase patterns (intent-based)
    # -------------------------
    phrase_patterns = [
        r"\bwhere are you\b",
        r"\bwhere do you live\b",
        r"\bwhere are you from\b",
        r"\bwhat country\b",
        r"\bwhich country\b",
        r"\bwhat region\b",
        r"\blocation\b",
        r"\bhow often do you\b",
        r"\bwhat kind of\b",
        r"\bwhat platform do you use\b",
        r"\bwhat device did you connect\b",
        r"\bhave you ever used\b",
        r"\bcan you describe any scenario\b",
    ]

    # -------------------------
    # Keyword match (strict word boundary)
    # -------------------------
    if any(re.search(rf"\b{re.escape(k)}\b", q) for k in keyword_signals):
        return True

    # -------------------------
    # Phrase match (looser intent)
    # -------------------------
    if any(re.search(p, q) for p in phrase_patterns):
        return True

    return False

def handle_update_section_name_post(data):

    dataset_id = data.get("dataset_id", [""])[0]
    section_index = data.get("section_index", [""])[0]
    section_name = data.get("section_name", [""])[0]

    if not dataset_id or not section_index or not section_name:
        return {"redirect": "/historical"}

    try:
        dataset_id = int(dataset_id)
        section_index = int(section_index)
    except:
        return {"redirect": "/historical"}

    from app.db.historical import upsert_section_name

    upsert_section_name(dataset_id, section_index, section_name)

    return {
        "redirect": f"/historical/context?context_id={data.get('context_id',[0])[0]}"
    }

def render_edit_section_name_get(user_id, base_template, inject_nav, query_params):

    dataset_id = query_params.get("dataset_id", [""])[0]
    section_index = query_params.get("section_index", [""])[0]
    context_id = query_params.get("context_id", [""])[0]

    html = f"""
    <div class="results-section">
        <h2>Edit Section Name</h2>

        <form method="POST" action="/historical/update-section-name">
            <input type="hidden" name="dataset_id" value="{e(dataset_id)}">
            <input type="hidden" name="section_index" value="{e(section_index)}">
            <input type="hidden" name="context_id" value="{e(context_id)}">

            <label>Section Name:</label><br>
            <input type="text" name="section_name" required><br><br>

            <button type="submit">Save</button>
        </form>
    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}

def handle_generate_section_names_post(data):

    # -------------------------
    # 🔥 FIX: correct POST parsing (no list indexing)
    # -------------------------
    dataset_id = data.get("dataset_id")
    context_id = data.get("context_id")

    if not context_id:
        return {"redirect": "/historical"}

    try:
        context_id = int(context_id)
    except:
        return {"redirect": "/historical"}

    if not dataset_id:
        return {"redirect": "/historical"}

    try:
        dataset_id = int(dataset_id)
    except:
        return {"redirect": "/historical"}

    from app.db.historical import get_historical_answers_by_dataset, upsert_section_name, get_section_names
    from app.services.ai_service import call_ai
    from app.handlers.historical import build_sections_from_rows

    # -------------------------
    # Build rows
    # -------------------------
    rows = get_historical_answers_by_dataset(dataset_id)

    # -------------------------
    # Build sections
    # -------------------------
    rows = sorted(rows, key=lambda r: (r["question_position"], r["response_group_id"]))
    sections = build_sections_from_rows(rows)

    # -------------------------
    # Existing names
    # -------------------------
    existing_names = get_section_names(dataset_id)

    # -------------------------
    # Generate names
    # -------------------------
    for idx, section in enumerate(sections, start=1):

        # -------------------------
        # Build question list
        # -------------------------
        questions = [q["question"] for q in section["quant_questions"]]

        # Fallback to qualitative anchor
        if not questions:
            qual = section.get("qual_question")

            if qual and qual.get("question"):
                questions = [qual["question"]]

        if not questions:
            continue

        # -------------------------
        # Build prompt
        # -------------------------
        question_block = "\n".join(f"- {q}" for q in questions)

        prompt = f"""
You are naming a survey section.

Given the following questions, return a SHORT section name (2-4 words max).

Rules:
- No punctuation
- No full sentences
- Title case
- Focus on theme

Questions:
{question_block}

Return only the section name.
"""

        ai_result = call_ai(
            prompt=prompt,
            model="gpt-4o-mini",
            temperature=0.2,
            max_tokens=20
        )

        if not ai_result.get("success"):
            continue

        name = ai_result.get("response", "").strip()

        if not name:
            continue

        # Normalize
        name = name.replace(".", "").strip()

        upsert_section_name(dataset_id, idx, name)

    return {
        "redirect": f"/historical/context?context_id={context_id}"
    }

def handle_generate_section_summaries_post(data):

    # -------------------------
    # 🔥 FIX: correct POST parsing (no list indexing)
    # -------------------------
    dataset_id = data.get("dataset_id")
    context_id = data.get("context_id")

    if not dataset_id or not context_id:
        return {"redirect": "/historical"}

    try:
        dataset_id = int(dataset_id)
        context_id = int(context_id)
    except:
        return {"redirect": "/historical"}

    from app.db.historical import (
        get_historical_answers_by_dataset,
        upsert_section_summary,
        get_section_summaries
    )
    from app.services.ai_service import call_ai
    from app.handlers.historical import build_sections_from_rows

    # -------------------------
    # Fetch rows
    # -------------------------
    rows = get_historical_answers_by_dataset(dataset_id)

    # -------------------------
    # Stable ordering
    # -------------------------
    rows = sorted(rows, key=lambda r: (r["question_position"], r["response_group_id"]))

    sections = build_sections_from_rows(rows)

    existing = get_section_summaries(dataset_id)

    # -------------------------
    # Generate summaries
    # -------------------------
    for idx, section in enumerate(sections, start=1):

        if idx in existing:
            continue

        qual = section.get("qual_question")

        if not qual:
            continue

        raw_values = qual.get("values", [])

        answers = [str(v).strip() for v in raw_values if v and str(v).strip()]

        if not answers:
            continue

        answer_block = "\n".join(f"- {a}" for a in answers[:30])

        # 🔥 include section questions as context
        quant_questions = [q["question"] for q in section["quant_questions"]]

        context_block = "\n".join(f"- {q}" for q in quant_questions)

        prompt = f"""
        You are analyzing user feedback for a product survey section.

        SECTION QUESTIONS:
        {context_block}

        Return a SWOT analysis in JSON format:

        {{
        "strengths": ["..."],
        "weaknesses": ["..."],
        "opportunities": ["..."],
        "threats": ["..."]
        }}

        Definitions:
        - Strengths = what users consistently like
        - Weaknesses = what users consistently dislike
        - Opportunities = improvements or feature ideas
        - Threats = risks, frustrations that could lead to churn, or competitive disadvantages

        Rules:
        - Each item must be short (1 sentence max)
        - No markdown
        - No formatting symbols
        - No extra text outside JSON
        - Max 5 items per category

        IMPORTANT:
        Only consider feedback relevant to the SECTION QUESTIONS.

        User Responses:
        {answer_block}
        """

        ai_result = call_ai(
            prompt=prompt,
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=800
        )

        if not ai_result.get("success"):
            continue

        # 🔥 Robust extraction (handles both schemas)
        summary = (
            ai_result.get("content")
            or ai_result.get("response")
            or ""
        ).strip()

        if not summary:
            continue

        upsert_section_summary(dataset_id, idx, summary)

    return {
        "redirect": f"/historical/context?context_id={context_id}"
    }

def classify(values):

    cleaned = [str(v).strip() for v in values if v]

    if not cleaned:
        return "qualitative"

    unique_vals = set(cleaned)

    # -------------------------
    # Numeric
    # -------------------------
    numeric_count = sum(
        1 for v in cleaned if v.replace(".", "", 1).isdigit()
    )

    if numeric_count >= len(cleaned) * 0.7:
        return "numeric"

    # -------------------------
    # Categorical (multi-choice)
    # -------------------------
    # repeated values, limited variety
    if len(unique_vals) <= 8 and len(cleaned) >= 5:
        return "categorical"

    # -------------------------
    # Qualitative (free text)
    # -------------------------
    return "qualitative"

def handle_generate_insights_post(data):
    # -------------------------
    # Normalize context_id
    # -------------------------
    raw_id = data.get("context_id")

    if isinstance(raw_id, list):
        context_id = raw_id[0]
    else:
        context_id = raw_id

    if not context_id:
        return {"redirect": "/historical"}

    try:
        context_id = int(context_id)
    except:
        return {"redirect": "/historical"}

    from app.services.historical_insights import (
        generate_trial_insights,
        generate_ai_insights
    )

    # -------------------------
    # Step 1: deterministic baseline
    # -------------------------
    generate_trial_insights(context_id)

    # -------------------------
    # Step 2: AI refinement
    # -------------------------
    generate_ai_insights(context_id)

    return {
        "redirect": f"/historical/context?context_id={context_id}"
    }