# app/handlers/historical.py

from app.services.historical_ingestion import ingest_historical_csv
from app.utils.html_escape import escape_html as e
from app.db.historical import get_latest_insights_by_context
from app.utils.csrf import generate_csrf_token
from app.utils.upload_security import require_csv_upload
from urllib.parse import urlencode
from app.services.upload_controls import render_csv_dropzone


def _historical_nav_item(label, href, active=False, disabled=False):
    active_class = " is-active" if active else ""

    if disabled:
        return f"""
            <span class="historical-subnav-item is-disabled">
                {e(label)}
            </span>
        """

    return f"""
        <a class="historical-subnav-item{active_class}" href="{e(href)}">
            {e(label)}
        </a>
    """


def _render_historical_subnav(active_key=None, context_id=None, dataset_id=None, product_id=None):
    safe_context_id = None
    safe_dataset_id = None
    safe_product_id = None

    try:
        safe_context_id = int(context_id) if context_id else None
    except (TypeError, ValueError):
        safe_context_id = None

    try:
        safe_dataset_id = int(dataset_id) if dataset_id else None
    except (TypeError, ValueError):
        safe_dataset_id = None

    try:
        safe_product_id = int(product_id) if product_id else None
    except (TypeError, ValueError):
        safe_product_id = None

    items = [
        _historical_nav_item(
            "Legacy Projects",
            "/historical",
            active=(active_key == "projects"),
        ),
        _historical_nav_item(
            "Create Context",
            "/historical/create-context",
            active=(active_key == "create"),
        ),
        _historical_nav_item(
            "Product Taxonomy",
            "/historical/product-taxonomy",
            active=(active_key == "taxonomy"),
        ),
    ]

    if safe_product_id:
        items.append(
            _historical_nav_item(
                "Product Lifecycle",
                f"/historical/product?product_id={safe_product_id}",
                active=(active_key == "product"),
            )
        )

    if safe_context_id:
        items.extend([
            _historical_nav_item(
                "Current Report",
                f"/historical/context?context_id={safe_context_id}",
                active=(active_key == "context"),
            ),
            _historical_nav_item(
                "Upload Data",
                f"/historical/upload?context_id={safe_context_id}",
                active=(active_key == "upload"),
            ),
            _historical_nav_item(
                "Pattern Comparison",
                f"/historical/comparison?context_id={safe_context_id}",
                active=(active_key == "comparison"),
            ),
        ])

        if safe_dataset_id:
            items.append(
                _historical_nav_item(
                    "Raw Data",
                    f"/historical/raw?context_id={safe_context_id}&dataset_id={safe_dataset_id}",
                    active=(active_key == "raw"),
                )
            )

    return f"""
    <div class="historical-subnav" aria-label="Historical workflow navigation">
        {''.join(items)}
    </div>
    """


def _can_access_historical_context(*, user_id, context_id) -> bool:
    if not user_id or not context_id:
        return False

    from app.db.user_roles import get_effective_permission_level

    if get_effective_permission_level(user_id) < 70:
        return False

    from app.db.historical import get_context_with_product

    return get_context_with_product(context_id) is not None


def _dataset_belongs_to_context(*, dataset_id, context_id) -> bool:
    if not dataset_id or not context_id:
        return False

    from app.db.historical import get_context_id_for_dataset

    dataset_context_id = get_context_id_for_dataset(dataset_id)
    if dataset_context_id is None:
        return False

    return int(dataset_context_id) == int(context_id)


def _historical_upload_redirect(*, context_id=None, error=None) -> dict:
    params = {}

    if context_id:
        params["context_id"] = context_id

    if error:
        params["error"] = error

    query = urlencode(params)

    if query:
        return {"redirect": f"/historical/upload?{query}"}

    return {"redirect": "/historical/upload"}


def handle_historical_upload_post(*, user_id, data):

    raw_context_id = data.get("context_id")
    dataset_type = data.get("dataset_type")
    round_number = data.get("round_number")
    file_item = data.get("file")

    # normalize round_number
    try:
        round_number = int(round_number) if round_number else None
    except Exception:
        round_number = None

    # HARD CLEAN: keep only the first posted dataset_type line.
    dataset_type = str(dataset_type or "").split("\r\n")[0].strip()

    try:
        context_id = int(raw_context_id) if raw_context_id else None
    except Exception:
        return _historical_upload_redirect(error="invalid_context")

    if not context_id:
        return _historical_upload_redirect(error="missing")

    if not dataset_type:
        return _historical_upload_redirect(
            context_id=context_id,
            error="missing",
        )

    if not file_item or not file_item.get("filename"):
        return _historical_upload_redirect(
            context_id=context_id,
            error="missing",
        )

    file_bytes = file_item.get("file")

    if not file_bytes:
        return _historical_upload_redirect(
            context_id=context_id,
            error="missing",
        )

    if not _can_access_historical_context(
        user_id=user_id,
        context_id=context_id,
    ):
        return {"redirect": "/historical"}

    try:
        safe_filename = require_csv_upload(
            filename=file_item.get("filename"),
            file_bytes=file_bytes,
        )
    except ValueError:
        return _historical_upload_redirect(
            context_id=context_id,
            error="invalid_file",
        )

    from app.db.historical import dataset_exists_for_context

    if dataset_exists_for_context(context_id, dataset_type):
        return _historical_upload_redirect(
            context_id=context_id,
            error="duplicate_dataset",
        )

    from io import BytesIO

    try:
        ingest_historical_csv(
            context_id=context_id,
            dataset_type=dataset_type,
            file_obj=BytesIO(file_bytes),
            filename=safe_filename,
            round_number=round_number,
        )
    except Exception:
        return _historical_upload_redirect(
            context_id=context_id,
            error="ingest_failed",
        )

    # -------------------------
    # Persist round to context
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


def render_historical_context_get(
    user_id,
    base_template,
    inject_nav,
    context_id,
    query_params
):

    if not _can_access_historical_context(
        user_id=user_id,
        context_id=context_id,
    ):
        return {"redirect": "/historical"}

    # -------------------------
    # Fetch data (NO raw SQL here)
    # -------------------------
    context = get_context_with_product(context_id)
    datasets = get_datasets_by_context(context_id)
    metrics = get_historical_metrics_by_context(context_id)
    insights = get_latest_insights_by_context(context_id)

    if not context:
        return {"redirect": "/historical"}

    action_csrf_token = generate_csrf_token(user_id)

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
    # Build HTML
    # -------------------------
    html = ""   # 🔥 REQUIRED INITIALIZATION

    html += _render_historical_subnav(
        active_key="context",
        context_id=context_id,
        dataset_id=latest_dataset_id,
    )

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
                    <input type="hidden" name="csrf_token" value="{e(action_csrf_token)}">
                    <input type="hidden" name="dataset_id" value="{latest_dataset_id}">
                    <input type="hidden" name="context_id" value="{context_id}">
                    <button type="submit" style="font-size:12px; padding:6px 10px;">
                        Generate Names
                    </button>
                </form>

                <form method="POST" action="/historical/generate-section-summaries" style="margin:0;"
                    onsubmit="startAnalysisLoading()">
                    <input type="hidden" name="csrf_token" value="{e(action_csrf_token)}">
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
                <input type="hidden" name="csrf_token" value="{e(action_csrf_token)}">
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

                    except Exception:
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
    csrf_token = generate_csrf_token(user_id)

    if not _can_access_historical_context(
        user_id=user_id,
        context_id=context_id,
    ):
        return {"redirect": "/historical"}

    datasets = get_datasets_by_context(context_id)
    latest_dataset_id = datasets[-1].get("dataset_id") if datasets else None

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
    <div class="results-section historical-page">
        {_render_historical_subnav(
            active_key="upload",
            context_id=context_id,
            dataset_id=latest_dataset_id,
        )}

        <h2>Upload Data</h2>
        <div class="historical-page-description">
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

            <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
            <input type="hidden" name="context_id" value="{safe_context_id_raw}">

            <label>Dataset Name:</label><br>
            <input type="text" name="dataset_type" placeholder="e.g. survey_1, validation_round2" required><br><br>

            <label>Round:</label><br>
            <input type="number" name="round_number" value="1"><br><br>

            {render_csv_dropzone(
                input_name="file",
                input_id="historical_csv_file",
                label="Drop historical CSV here or click to choose",
            )}

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

    csrf_token = generate_csrf_token(user_id)

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
    <div class="results-section historical-page">
        {_render_historical_subnav(active_key="create")}

        <h2>Create Legacy Project Context</h2>

        <form method="POST" action="/historical/create-context" class="form-stack historical-form">
            <input type="hidden" name="csrf_token" value="{csrf_token}">

            <div class="form-group">
                <label>Product</label>
                <select name="product_id" class="form-input" required>
                    <option value="" disabled selected>Select your product</option>
                    {product_options}
                </select>
                <div class="historical-form-note">
                    Contexts with the same product and round are grouped together on the Legacy Projects page.
                </div>
            </div>

            <div class="form-group">
                <label>Round</label>
                <input type="number" name="round_number" class="form-input" value="1" min="1">
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
                <button type="submit" class="btn-primary">Create Project Context</button>
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

from app.db.historical import get_legacy_project_groups

def render_historical_landing_get(user_id, base_template, inject_nav):

    project_groups = get_legacy_project_groups()

    html = f"""
    <div class="results-section historical-page">
        {_render_historical_subnav(active_key="projects")}

        <div class="historical-page-header">
            <div>
                <h2>Legacy Projects</h2>
                <p class="historical-page-description">
                    Contexts with the same product and round are grouped together as one legacy project.
                    Expand a project to review the individual survey contexts, reports, raw data, and upload actions.
                </p>
            </div>
        </div>
    """

    if not project_groups:
        html += "<p>No historical projects loaded yet.</p>"
    else:
        html += """
        <div class="historical-project-list" role="table" aria-label="Legacy projects">
            <div class="historical-project-list-header" role="row">
                <div>#</div>
                <div>Project</div>
                <div>Product</div>
                <div class="is-centered">Round</div>
                <div>Surveys</div>
                <div class="is-centered">Lifecycle</div>
                <div class="is-action-cell">Project Actions</div>
            </div>
        """

        for idx, group in enumerate(project_groups, start=1):

            product_id = group.get("product_id")
            product_href = f"/historical/product?product_id={int(product_id)}" if product_id else "/historical"
            internal = e(group.get("internal_name") or "-")
            market = e(group.get("market_name") or "-")
            product_type = e(group.get("product_type_display") or "-")
            business_group = e(group.get("business_group") or "-")
            round_number = group.get("round_number")
            round_display = e(str(round_number)) if round_number is not None else "<span class='historical-warning-chip'>Needs round</span>"
            context_count = int(group.get("context_count") or 0)
            dataset_count = int(group.get("dataset_count") or 0)
            latest_context_id = group.get("latest_context_id")
            contexts = group.get("contexts") or []

            survey_label = "survey" if context_count == 1 else "surveys"
            dataset_label = "dataset" if dataset_count == 1 else "datasets"
            survey_summary = f"{context_count} {survey_label} ({dataset_count} {dataset_label})"

            lifecycle_values = []
            for context in contexts:
                lifecycle = context.get("lifecycle_stage")
                if lifecycle and lifecycle not in lifecycle_values:
                    lifecycle_values.append(lifecycle)

            lifecycle_display = e(", ".join(lifecycle_values) if lifecycle_values else "-")

            survey_rows = ""
            for survey_idx, context in enumerate(contexts, start=1):
                context_id = context.get("context_id")
                dataset_id = context.get("dataset_id")
                dataset_name = context.get("dataset_name") or "Untitled survey"
                purpose = context.get("trial_purpose") or "-"
                lifecycle = context.get("lifecycle_stage") or "-"

                if dataset_id:
                    data_status = "<span class='historical-status-chip is-ready'>Data uploaded</span>"
                    raw_action = f"""
                        <a class="historical-action-pill is-secondary" href="/historical/raw?context_id={context_id}&dataset_id={dataset_id}">
                            Raw Data
                        </a>
                    """
                else:
                    data_status = "<span class='historical-status-chip is-muted'>No data yet</span>"
                    raw_action = "<span class='historical-action-pill is-disabled'>Raw Data</span>"

                survey_rows += f"""
                    <tr>
                        <td>{survey_idx}</td>
                        <td>
                            <div class="historical-project-title">{e(dataset_name)}</div>
                            <div class="historical-muted">{e(purpose)}</div>
                        </td>
                        <td>{e(lifecycle)}</td>
                        <td>{data_status}</td>
                        <td>
                            <div class="historical-action-row">
                                <a class="historical-action-pill" href="/historical/context?context_id={context_id}">
                                    Survey Report
                                </a>
                                {raw_action}
                                <a class="historical-action-pill is-secondary" href="/historical/upload?context_id={context_id}">
                                    Upload Data
                                </a>
                            </div>
                        </td>
                    </tr>
                """

            html += f"""
            <details class="historical-project-card">
                <summary class="historical-project-summary-row">
                    <span class="historical-project-caret" aria-hidden="true">▸</span>
                    <span class="historical-project-index">{idx}</span>
                    <span class="historical-project-cell historical-project-inline-cell">
                        <a class="historical-inline-link historical-project-title" href="{e(product_href)}" onclick="event.stopPropagation();">{internal}</a><span class="historical-inline-muted">({market})</span>
                    </span>
                    <span class="historical-project-cell historical-project-inline-cell">
                        <span class="historical-inline-text">{business_group} / {product_type}</span>
                    </span>
                    <span class="historical-project-cell is-centered">{round_display}</span>
                    <span class="historical-project-cell historical-project-inline-cell">
                        <span class="historical-inline-text historical-count-inline">{e(survey_summary)}</span>
                    </span>
                    <span class="historical-project-cell is-centered"><span class="historical-lifecycle-pill">{lifecycle_display}</span></span>
                    <span class="historical-project-actions is-action-cell">
                        <a class="historical-action-pill" href="/historical/context?context_id={latest_context_id}" onclick="event.stopPropagation();">
                            Latest Report
                        </a>
                        <a class="historical-action-pill is-secondary" href="/historical/create-context" onclick="event.stopPropagation();">
                            Add Survey
                        </a>
                    </span>
                </summary>

                <div class="historical-project-detail">
                    <div class="historical-project-detail-heading">
                        Surveys in this project round
                    </div>
                    <div class="table-scroll">
                        <table class="data-table historical-survey-detail-table">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Survey</th>
                                    <th>Lifecycle</th>
                                    <th>Dataset</th>
                                    <th>Survey Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {survey_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </details>
            """

        html += """
        </div>
        """

    html += "</div>"

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def handle_historical_product_publish_post(user_id, data):
    raw_product_id = data.get("product_id", [None])
    if isinstance(raw_product_id, list):
        raw_product_id = raw_product_id[0] if raw_product_id else None

    raw_action = data.get("action", [None])
    if isinstance(raw_action, list):
        raw_action = raw_action[0] if raw_action else None

    try:
        product_id = int(raw_product_id)
    except (TypeError, ValueError):
        return {"redirect": "/historical?error=invalid_product"}

    action = str(raw_action or "").strip().lower()

    if action == "publish":
        from app.db.historical import publish_historical_product_lifecycle

        success = publish_historical_product_lifecycle(product_id, user_id)
    elif action == "withdraw":
        from app.db.historical import withdraw_historical_product_lifecycle

        success = withdraw_historical_product_lifecycle(product_id, user_id)
    else:
        return {"redirect": f"/historical/product?product_id={product_id}&error=invalid_action"}

    if not success:
        return {"redirect": "/historical?error=invalid_product"}

    return {"redirect": f"/historical/product?product_id={product_id}"}


def handle_historical_product_access_post(user_id, data):
    raw_product_id = data.get("product_id", [None])
    if isinstance(raw_product_id, list):
        raw_product_id = raw_product_id[0] if raw_product_id else None

    raw_action = data.get("action", [None])
    if isinstance(raw_action, list):
        raw_action = raw_action[0] if raw_action else None

    try:
        product_id = int(raw_product_id)
    except (TypeError, ValueError):
        return {"redirect": "/historical?error=invalid_product"}

    action = str(raw_action or "").strip().lower()

    if action == "grant":
        raw_email = data.get("target_email", [""])
        if isinstance(raw_email, list):
            raw_email = raw_email[0] if raw_email else ""

        raw_role = data.get("access_role", ["manual"])
        if isinstance(raw_role, list):
            raw_role = raw_role[0] if raw_role else "manual"

        from app.db.historical import grant_historical_product_publication_access_by_email

        result = grant_historical_product_publication_access_by_email(
            product_id=product_id,
            target_email=raw_email,
            granted_by_user_id=user_id,
            access_role=raw_role,
        )

        return {"redirect": f"/historical/product?product_id={product_id}&access={result}"}

    if action == "revoke":
        raw_target_user_id = data.get("target_user_id", [None])
        if isinstance(raw_target_user_id, list):
            raw_target_user_id = raw_target_user_id[0] if raw_target_user_id else None

        target_user_id = str(raw_target_user_id or "").strip()
        if not target_user_id:
            return {"redirect": f"/historical/product?product_id={product_id}&access=missing_user"}

        from app.db.historical import revoke_historical_product_publication_access

        success = revoke_historical_product_publication_access(
            product_id=product_id,
            target_user_id=target_user_id,
            revoked_by_user_id=user_id,
        )

        result = "revoked" if success else "revoke_not_found"
        return {"redirect": f"/historical/product?product_id={product_id}&access={result}"}

    return {"redirect": f"/historical/product?product_id={product_id}&access=invalid_action"}


def render_historical_product_lifecycle_get(
    user_id,
    base_template,
    inject_nav,
    product_id,
    query_params=None,
    can_manage_publication=True,
):
    from app.db.historical import (
        get_historical_product_publication,
        get_historical_product_publication_access,
        get_legacy_product_lifecycle,
    )

    lifecycle = get_legacy_product_lifecycle(product_id)
    if not lifecycle:
        return {"redirect": "/historical"}

    product = lifecycle.get("product") or {}
    rounds = lifecycle.get("rounds") or []

    internal = e(product.get("internal_name") or "-")
    market = e(product.get("market_name") or "-")
    product_type = e(product.get("product_type_display") or "-")
    business_group = e(product.get("business_group") or "-")

    round_count = len(rounds)
    survey_count = sum(int(round_group.get("context_count") or 0) for round_group in rounds)
    dataset_count = sum(int(round_group.get("dataset_count") or 0) for round_group in rounds)
    round_label = "round" if round_count == 1 else "rounds"
    survey_label = "survey" if survey_count == 1 else "surveys"
    dataset_label = "dataset" if dataset_count == 1 else "datasets"

    publication = get_historical_product_publication(product_id)
    publication_status = (publication or {}).get("status")
    is_published = publication_status == "published"
    access_grants = get_historical_product_publication_access(product_id) if can_manage_publication else []
    access_message_key = ""
    if query_params:
        raw_access_message = query_params.get("access", [""])
        access_message_key = raw_access_message[0] if isinstance(raw_access_message, list) and raw_access_message else ""

    access_messages = {
        "granted": "Access granted.",
        "revoked": "Access revoked.",
        "user_not_found": "No registered user was found for that email.",
        "missing_email": "Enter a registered email before granting access.",
        "publication_not_found": "Publish the product lifecycle before granting Product Team access.",
        "missing_user": "No user was selected for access removal.",
        "revoke_not_found": "That active access grant was not found.",
        "invalid_action": "That access action is not supported.",
    }
    access_message_html = ""
    if access_message_key in access_messages:
        access_message_class = "is-success" if access_message_key in ("granted", "revoked") else "is-warning"
        access_message_html = f"""
            <div class="historical-access-message {access_message_class}">
                {e(access_messages[access_message_key])}
            </div>
        """

    if can_manage_publication:
        publish_csrf_token = generate_csrf_token(user_id)
        access_csrf_token = generate_csrf_token(user_id)

        if is_published:
            published_at = publication.get("published_at") or ""
            publication_status_html = f"""
                <div class="historical-publication-status is-published">
                    Published to Reporting & Insights
                </div>
                <div class="historical-muted">Published {e(str(published_at)) if published_at else ""}. Product Team visibility is limited to explicit report access.</div>
            """
            publication_action_html = f"""
                <form method="POST" action="/historical/product/publish" class="historical-publish-form">
                    <input type="hidden" name="csrf_token" value="{e(publish_csrf_token)}">
                    <input type="hidden" name="product_id" value="{e(str(product_id))}">
                    <input type="hidden" name="action" value="withdraw">
                    <button type="submit" class="historical-action-pill is-secondary">Withdraw</button>
                </form>
            """
        else:
            publication_status_html = """
                <div class="historical-publication-status is-draft">
                    Not published yet
                </div>
                <div class="historical-muted">Publishing will make this product lifecycle visible in Reporting & Insights. Product Team menu visibility requires explicit report access.</div>
            """
            publication_action_html = f"""
                <form method="POST" action="/historical/product/publish" class="historical-publish-form">
                    <input type="hidden" name="csrf_token" value="{e(publish_csrf_token)}">
                    <input type="hidden" name="product_id" value="{e(str(product_id))}">
                    <input type="hidden" name="action" value="publish">
                    <button type="submit" class="historical-action-pill">Publish Product Lifecycle</button>
                </form>
            """
    else:
        published_at = (publication or {}).get("published_at") or ""
        publication_status_html = f"""
            <div class="historical-publication-status is-published">
                Published report
            </div>
            <div class="historical-muted">Published {e(str(published_at)) if published_at else ""}</div>
        """
        publication_action_html = ""

    access_management_html = ""
    if can_manage_publication:
        if not is_published:
            access_management_html = f"""
            <section class="historical-access-card">
                <div>
                    <h3>Product Team report access</h3>
                    <p>Publish this product lifecycle before granting Product Team report access.</p>
                </div>
                {access_message_html}
            </section>
            """
        else:
            grant_rows_html = ""
            for grant in access_grants:
                target_user_id = grant.get("user_id") or ""
                first_name = grant.get("FirstName") or ""
                last_name = grant.get("LastName") or ""
                email = grant.get("Email") or ""
                access_role = grant.get("access_role") or "manual"
                display_name = " ".join(part for part in [first_name, last_name] if part).strip() or email

                grant_rows_html += f"""
                <tr>
                    <td>
                        <div class="historical-project-title">{e(display_name)}</div>
                        <div class="historical-muted">{e(email)}</div>
                    </td>
                    <td><span class="historical-lifecycle-pill">{e(access_role)}</span></td>
                    <td>
                        <form method="POST" action="/historical/product/access" class="historical-inline-form">
                            <input type="hidden" name="csrf_token" value="{e(access_csrf_token)}">
                            <input type="hidden" name="product_id" value="{e(str(product_id))}">
                            <input type="hidden" name="action" value="revoke">
                            <input type="hidden" name="target_user_id" value="{e(str(target_user_id))}">
                            <button type="submit" class="historical-action-pill is-secondary">Remove</button>
                        </form>
                    </td>
                </tr>
                """

            if not grant_rows_html:
                grant_rows_html = """
                <tr>
                    <td colspan="3">
                        <div class="historical-muted">No Product Team users have explicit access yet.</div>
                    </td>
                </tr>
                """

            access_management_html = f"""
            <section class="historical-access-card">
                <div class="historical-access-card-header">
                    <div>
                        <h3>Product Team report access</h3>
                        <p>Grant access to Product Team users who should see this report under their Reports & Summaries menu.</p>
                    </div>
                </div>

                {access_message_html}

                <form method="POST" action="/historical/product/access" class="historical-access-form">
                    <input type="hidden" name="csrf_token" value="{e(access_csrf_token)}">
                    <input type="hidden" name="product_id" value="{e(str(product_id))}">
                    <input type="hidden" name="action" value="grant">

                    <div class="historical-access-field">
                        <label>Registered user email</label>
                        <input type="email" name="target_email" class="form-input" placeholder="name@logitech.com" required>
                    </div>

                    <div class="historical-access-field">
                        <label>Access role</label>
                        <select name="access_role" class="form-input">
                            <option value="requestor">Requestor</option>
                            <option value="stakeholder">Stakeholder</option>
                            <option value="manual" selected>Manual viewer</option>
                        </select>
                    </div>

                    <button type="submit" class="historical-action-pill historical-access-submit">Grant Access</button>
                </form>

                <div class="table-scroll">
                    <table class="data-table historical-access-table">
                        <thead>
                            <tr>
                                <th>User</th>
                                <th>Role</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {grant_rows_html}
                        </tbody>
                    </table>
                </div>
            </section>
            """

    nav_html = _render_historical_subnav(
        active_key="product",
        product_id=product_id,
    ) if can_manage_publication else ""

    html = f"""
    <div class="results-section historical-page">
        {nav_html}

        <div class="historical-product-hero">
            <div>
                <div class="historical-kicker">Product lifecycle</div>
                <h2>{internal} <span class="historical-heading-muted">({market})</span></h2>
                <p class="historical-page-description">
                    Review this product across historical rounds so earlier findings are treated as iteration history,
                    not as equal-weight final product conclusions.
                </p>
            </div>
            <div class="historical-product-meta-card">
                <div><strong>{business_group}</strong> / {product_type}</div>
                <div>{round_count} {round_label}</div>
                <div>{survey_count} {survey_label} · {dataset_count} {dataset_label}</div>
                <div class="historical-product-publication-block">
                    {publication_status_html}
                    {publication_action_html}
                </div>
            </div>
        </div>

        <div class="historical-lifecycle-note">
            Product-level publishing is intentionally separate from round-level reports. The final product conclusion should
            preserve the sequence: what each round found, what changed afterward, and which findings remain current.
        </div>

        {access_management_html}
    """

    if not rounds:
        html += "<p>No historical rounds have been loaded for this product yet.</p>"
    else:
        html += "<div class='historical-product-round-list'>"

        for round_idx, round_group in enumerate(rounds, start=1):
            round_number = round_group.get("round_number")
            round_display = e(str(round_number)) if round_number is not None else "<span class='historical-warning-chip'>Needs round</span>"
            context_count = int(round_group.get("context_count") or 0)
            dataset_count = int(round_group.get("dataset_count") or 0)
            latest_context_id = round_group.get("latest_context_id")
            lifecycle_values = round_group.get("lifecycle_values") or []
            lifecycle_display = e(", ".join(lifecycle_values) if lifecycle_values else "-")

            survey_label = "survey" if context_count == 1 else "surveys"
            dataset_label = "dataset" if dataset_count == 1 else "datasets"
            round_summary = f"{context_count} {survey_label} ({dataset_count} {dataset_label})"

            survey_rows = ""
            for survey_idx, context in enumerate(round_group.get("contexts") or [], start=1):
                context_id = context.get("context_id")
                dataset_id = context.get("dataset_id")
                dataset_name = context.get("dataset_name") or "Untitled survey"
                purpose = context.get("trial_purpose") or "-"
                lifecycle_stage = context.get("lifecycle_stage") or "-"

                if dataset_id:
                    data_status = "<span class='historical-status-chip is-ready'>Data uploaded</span>"
                    raw_action = f"""
                        <a class="historical-action-pill is-secondary" href="/historical/raw?context_id={context_id}&dataset_id={dataset_id}">
                            Raw Data
                        </a>
                    """
                else:
                    data_status = "<span class='historical-status-chip is-muted'>No data yet</span>"
                    raw_action = "<span class='historical-action-pill is-disabled'>Raw Data</span>"

                survey_rows += f"""
                    <tr>
                        <td>{survey_idx}</td>
                        <td>
                            <div class="historical-project-title">{e(dataset_name)}</div>
                            <div class="historical-muted">{e(purpose)}</div>
                        </td>
                        <td><span class="historical-lifecycle-pill">{e(lifecycle_stage)}</span></td>
                        <td>{data_status}</td>
                        <td>
                            <div class="historical-action-row">
                                {f'<a class="historical-action-pill" href="/historical/context?context_id={context_id}">Survey Report</a>' if can_manage_publication else '<span class="historical-action-pill is-disabled">Managed by UT</span>'}
                                {raw_action if can_manage_publication else ""}
                                {f'<a class="historical-action-pill is-secondary" href="/historical/upload?context_id={context_id}">Upload Data</a>' if can_manage_publication else ""}
                            </div>
                        </td>
                    </tr>
                """

            html += f"""
            <details class="historical-project-card historical-product-round-card" {'open' if round_idx == len(rounds) else ''}>
                <summary class="historical-product-round-summary">
                    <span class="historical-project-caret" aria-hidden="true">▸</span>
                    <span class="historical-round-title">Round {round_display}</span>
                    <span class="historical-inline-text">{e(round_summary)}</span>
                    <span class="historical-project-cell is-centered"><span class="historical-lifecycle-pill">{lifecycle_display}</span></span>
                    <span class="historical-project-actions is-action-cell">
                        {f'<a class="historical-action-pill" href="/historical/context?context_id={latest_context_id}" onclick="event.stopPropagation();">Latest Round Report</a>' if can_manage_publication else ''}
                    </span>
                </summary>

                <div class="historical-project-detail">
                    <div class="historical-project-detail-heading">
                        Survey contexts in this round
                    </div>
                    <div class="table-scroll">
                        <table class="data-table historical-survey-detail-table">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Survey</th>
                                    <th>Lifecycle</th>
                                    <th>Dataset</th>
                                    <th>Survey Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {survey_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </details>
            """

        html += "</div>"

    html += "</div>"

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def render_historical_product_taxonomy_get(
    user_id,
    base_template,
    inject_nav,
):
    from app.services.product_taxonomy_service import (
        build_product_taxonomy_audit,
        build_product_taxonomy_summary,
    )

    audit = build_product_taxonomy_audit()
    summary = build_product_taxonomy_summary()

    products_total = audit.get("products_total") or 0
    products_ready = audit.get("products_ready") or 0
    readiness_rate = audit.get("readiness_rate")

    readiness_display = "—"
    if readiness_rate is not None:
        readiness_display = f"{readiness_rate}%"

    product_types = audit.get("product_types") or []
    business_groups = audit.get("business_groups") or []
    missing_type = audit.get("products_missing_type") or []
    missing_business_group = audit.get("products_missing_business_group") or []
    limitations = audit.get("limitations") or []

    def _display(value, fallback="—"):
        if value is None:
            return fallback

        value = str(value).strip()
        return value if value else fallback

    def _product_name(product):
        internal_name = _display(product.get("internal_name"), "")
        market_name = _display(product.get("market_name"), "")

        if internal_name and market_name:
            return f"{internal_name} ({market_name})"

        if internal_name:
            return internal_name

        if market_name:
            return market_name

        return f"Product {product.get('product_id') or '—'}"

    html = f"""
    <div class="results-section historical-page">
        {_render_historical_subnav(active_key="taxonomy")}

        <h2 style="margin-bottom:6px;">
            Product Taxonomy Audit
        </h2>

        <p class="muted" style="margin-top:0;">
            Read-only audit of DB-backed product classification fields used by historical comparison.
            Product type and business group are never inferred from names.
        </p>

        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Comparison Readiness</h3>

            <div class="info-grid">
                <div class="info-row"><strong>Total Products:</strong> {e(products_total)}</div>
                <div class="info-row"><strong>Comparison Ready:</strong> {e(products_ready)}</div>
                <div class="info-row"><strong>Readiness Rate:</strong> {e(readiness_display)}</div>
                <div class="info-row"><strong>Product Types:</strong> {e(summary.get("product_type_count") or 0)}</div>
                <div class="info-row"><strong>Business Groups:</strong> {e(summary.get("business_group_count") or 0)}</div>
                <div class="info-row"><strong>Missing Product Type:</strong> {e(summary.get("missing_type_count") or 0)}</div>
                <div class="info-row"><strong>Missing Business Group:</strong> {e(summary.get("missing_business_group_count") or 0)}</div>
            </div>
        </div>
    """

    if limitations:
        html += """
        <div class="card" style="margin-top:16px; border-left:4px solid #f59e0b;">
            <h3 style="margin-top:0;">Limitations</h3>
            <ul style="margin-bottom:0;">
        """

        for limitation in limitations:
            html += f"<li>{e(limitation)}</li>"

        html += """
            </ul>
        </div>
        """

    html += """
        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Product Types</h3>
    """

    if not product_types:
        html += """
            <p class="muted" style="margin-bottom:0;">
                No product types found.
            </p>
        """
    else:
        html += """
            <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Product Type Key</th>
                        <th>Display</th>
                        <th>Products</th>
                        <th>Business Groups</th>
                    </tr>
                </thead>
                <tbody>
        """

        for row in product_types:
            html += f"""
                    <tr>
                        <td>{e(_display(row.get("product_type_key")))}</td>
                        <td>{e(_display(row.get("product_type_display")))}</td>
                        <td>{e(row.get("product_count") or 0)}</td>
                        <td>{e(", ".join(row.get("business_groups") or []))}</td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
            </div>
        """

    html += """
        </div>

        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Business Groups</h3>
    """

    if not business_groups:
        html += """
            <p class="muted" style="margin-bottom:0;">
                No business groups found.
            </p>
        """
    else:
        html += """
            <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Business Group</th>
                        <th>Products</th>
                        <th>Product Types</th>
                    </tr>
                </thead>
                <tbody>
        """

        for row in business_groups:
            html += f"""
                    <tr>
                        <td>{e(_display(row.get("business_group")))}</td>
                        <td>{e(row.get("product_count") or 0)}</td>
                        <td>{e(", ".join(row.get("product_types") or []))}</td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
            </div>
        """

    html += """
        </div>

        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Products Missing Product Type</h3>
    """

    if not missing_type:
        html += """
            <p class="muted" style="margin-bottom:0;">
                No products are missing product_type_key.
            </p>
        """
    else:
        html += """
            <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Product</th>
                        <th>Business Group</th>
                    </tr>
                </thead>
                <tbody>
        """

        for product in missing_type:
            html += f"""
                    <tr>
                        <td>{e(_product_name(product))}</td>
                        <td>{e(_display(product.get("business_group")))}</td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
            </div>
        """

    html += """
        </div>

        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Products Missing Business Group</h3>
    """

    if not missing_business_group:
        html += """
            <p class="muted" style="margin-bottom:0;">
                No products are missing business_group.
            </p>
        """
    else:
        html += """
            <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Product</th>
                        <th>Product Type</th>
                    </tr>
                </thead>
                <tbody>
        """

        for product in missing_business_group:
            product_type = product.get("product_type_display") or product.get("product_type_key")
            html += f"""
                    <tr>
                        <td>{e(_product_name(product))}</td>
                        <td>{e(_display(product_type))}</td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
            </div>
        """

    html += """
        </div>

    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def render_historical_comparison_get(
    user_id,
    base_template,
    inject_nav,
    context_id,
    query_params
):
    try:
        context_id = int(context_id)
    except (TypeError, ValueError):
        return {"redirect": "/historical"}

    if not _can_access_historical_context(
        user_id=user_id,
        context_id=context_id,
    ):
        return {"redirect": "/historical"}

    from app.services.historical_comparison_service import (
        build_historical_pattern_comparison,
    )

    comparison = build_historical_pattern_comparison(context_id)

    target = comparison.get("target_context") or {}
    comparison_basis = comparison.get("comparison_basis") or {}
    metric_comparison = comparison.get("metric_comparison") or {}
    target_metrics = metric_comparison.get("target") or {}
    baseline_metrics = metric_comparison.get("baseline") or {}
    deltas = metric_comparison.get("deltas") or {}
    matched_contexts = comparison.get("matched_contexts") or []
    match_summary = comparison.get("match_summary") or {}
    target_readiness = comparison.get("target_readiness") or {}
    comparison_scope = comparison.get("comparison_scope") or {}
    repeated_patterns = comparison.get("repeated_patterns") or []
    limitations = comparison.get("limitations") or []
    data_quality = comparison.get("data_quality") or {}

    def _display(value, fallback="—"):
        if value is None:
            return fallback

        value = str(value).strip()
        return value if value else fallback

    def _metric_value(value):
        if value is None:
            return "—"

        try:
            numeric_value = float(value)
            if numeric_value.is_integer():
                return str(int(numeric_value))
            return f"{numeric_value:.2f}"
        except (TypeError, ValueError):
            return str(value)

    target_name = _display(target.get("product_name"), "Unknown product")
    target_product_type = _display(target.get("product_type_display") or target.get("product_type_key"))
    target_business_group = _display(target.get("business_group"))
    target_lifecycle = _display(target.get("lifecycle_stage"))
    target_purpose = _display(target.get("trial_purpose"))

    target_taxonomy_ready = "Yes" if target_readiness.get("is_taxonomy_ready") else "No"
    target_missing_fields = ", ".join(target_readiness.get("missing_fields") or []) or "—"

    comparison_mode = _display(comparison_scope.get("mode"))
    recommendation_status = "Yes" if comparison_scope.get("generates_recommendations") else "No"

    tier = _display(comparison_basis.get("tier"))
    tier_reason = _display(comparison_basis.get("reason"), "No comparison basis available.")
    match_count = comparison_basis.get("match_count") or 0

    target_metric_count = data_quality.get("target_metric_count") or 0
    baseline_metric_count = data_quality.get("baseline_metric_count") or 0
    repeated_pattern_count = data_quality.get("repeated_pattern_count") or 0
    limitation_count = data_quality.get("limitation_count") or len(limitations)
    coverage_note = _display(
        data_quality.get("coverage_note"),
        "Comparison data is available.",
    )

    strong_match_count = match_summary.get("strong") or 0
    medium_match_count = match_summary.get("medium") or 0
    weak_match_count = match_summary.get("weak") or 0
    broad_match_count = match_summary.get("broad") or 0

    top_match_reasons = match_summary.get("top_reasons") or []
    top_match_reason_text = "—"

    if top_match_reasons:
        top_match_reason_text = ", ".join([
            f"{item.get('reason')} ({item.get('count')})"
            for item in top_match_reasons[:4]
            if item.get("reason")
        ]) or "—"

    html = f"""
    <div class="results-section historical-page">
        {_render_historical_subnav(
            active_key="comparison",
            context_id=context_id,
        )}

        <h2 style="margin-bottom:6px;">
            Historical Pattern Comparison
        </h2>

        <p class="muted" style="margin-top:0;">
            Read-only comparison using explicit DB-backed product taxonomy, historical metrics,
            and saved historical insight rows. This page does not generate recommendations.
        </p>

        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Target Trial</h3>

            <div class="info-grid">
                <div class="info-row"><strong>Product:</strong> {e(target_name)}</div>
                <div class="info-row"><strong>Product Type:</strong> {e(target_product_type)}</div>
                <div class="info-row"><strong>Business Group:</strong> {e(target_business_group)}</div>
                <div class="info-row"><strong>Lifecycle:</strong> {e(target_lifecycle)}</div>
                <div class="info-row"><strong>Purpose:</strong> {e(target_purpose)}</div>
                <div class="info-row"><strong>Taxonomy Ready:</strong> {e(target_taxonomy_ready)}</div>
                <div class="info-row"><strong>Missing Taxonomy Fields:</strong> {e(target_missing_fields)}</div>
                <div class="info-row"><strong>Mode:</strong> {e(comparison_mode)}</div>
                <div class="info-row"><strong>Generates Recommendations:</strong> {e(recommendation_status)}</div>
            </div>
        </div>

        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Comparison Basis</h3>

            <div class="info-grid">
                <div class="info-row"><strong>Tier:</strong> {e(tier)}</div>
                <div class="info-row"><strong>Matched Contexts:</strong> {e(match_count)}</div>
                <div class="info-row"><strong>Strong Matches:</strong> {e(strong_match_count)}</div>
                <div class="info-row"><strong>Medium Matches:</strong> {e(medium_match_count)}</div>
                <div class="info-row"><strong>Weak Matches:</strong> {e(weak_match_count)}</div>
                <div class="info-row"><strong>Broad Baseline:</strong> {e(broad_match_count)}</div>
            </div>

            <p class="muted" style="margin-bottom:8px;">
                {e(tier_reason)}
            </p>

            <p class="muted" style="margin-bottom:0;">
                <strong>Top match reasons:</strong> {e(top_match_reason_text)}
            </p>
        </div>

        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Data Coverage</h3>

            <div class="info-grid">
                <div class="info-row"><strong>Target Metrics Available:</strong> {e(target_metric_count)}</div>
                <div class="info-row"><strong>Baseline Metrics Available:</strong> {e(baseline_metric_count)}</div>
                <div class="info-row"><strong>Repeated Patterns Found:</strong> {e(repeated_pattern_count)}</div>
                <div class="info-row"><strong>Limitations Listed:</strong> {e(limitation_count)}</div>
            </div>

            <p class="muted" style="margin-bottom:0;">
                {e(coverage_note)}
            </p>
        </div>
    """

    if limitations:
        html += """
        <div class="card" style="margin-top:16px; border-left:4px solid #f59e0b;">
            <h3 style="margin-top:0;">Limitations</h3>
            <ul style="margin-bottom:0;">
        """

        for limitation in limitations:
            html += f"<li>{e(limitation)}</li>"

        html += """
            </ul>
        </div>
        """

    html += """
        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Matched Historical Contexts</h3>
    """

    if not matched_contexts:
        html += """
            <p class="muted" style="margin-bottom:0;">
                No comparable historical contexts were found.
            </p>
        """
    else:
        html += """
            <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Product</th>
                        <th>Type</th>
                        <th>BG</th>
                        <th>Lifecycle</th>
                        <th>Purpose</th>
                        <th>Strength</th>
                        <th>Reasons</th>
                        <th>Datasets</th>
                    </tr>
                </thead>
                <tbody>
        """

        for item in matched_contexts:
            reasons = ", ".join(item.get("match_reasons") or [])
            html += f"""
                    <tr>
                        <td>
                            <a href="/historical/context?context_id={item.get('context_id')}">
                                {e(_display(item.get("product_name")))}
                            </a>
                        </td>
                        <td>{e(_display(item.get("product_type_display") or item.get("product_type_key")))}</td>
                        <td>{e(_display(item.get("business_group")))}</td>
                        <td>{e(_display(item.get("lifecycle_stage")))}</td>
                        <td>{e(_display(item.get("trial_purpose")))}</td>
                        <td>{e(_display(item.get("match_strength")))}</td>
                        <td>{e(reasons)}</td>
                        <td>{e(item.get("dataset_count") or 0)}</td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
            </div>
        """

    html += """
        </div>
    """

    metric_rows = [
        ("Total Responses", "total_responses"),
        ("Survey 1 Responses", "survey_1_responses"),
        ("Survey 2 Responses", "survey_2_responses"),
        ("Completion Rate", "completion_rate"),
        ("Drop-off Rate", "drop_off_rate"),
        ("Avg Response Length", "avg_response_length"),
        ("Median Response Length", "median_response_length"),
        ("Empty Response Rate", "empty_response_rate"),
        ("Quant Question Count", "quant_question_count"),
        ("Qual Question Count", "qual_question_count"),
    ]

    html += """
        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Metric Comparison</h3>
            <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Target</th>
                        <th>Historical Baseline</th>
                        <th>Delta</th>
                    </tr>
                </thead>
                <tbody>
    """

    for label, key in metric_rows:
        html += f"""
                    <tr>
                        <td>{e(label)}</td>
                        <td>{e(_metric_value(target_metrics.get(key)))}</td>
                        <td>{e(_metric_value(baseline_metrics.get(key)))}</td>
                        <td>{e(_metric_value(deltas.get(key)))}</td>
                    </tr>
        """

    html += """
                </tbody>
            </table>
            </div>
        </div>
    """

    html += """
        <div class="card" style="margin-top:16px;">
            <h3 style="margin-top:0;">Repeated Historical Patterns</h3>
    """

    if not repeated_patterns:
        html += """
            <p class="muted" style="margin-bottom:0;">
                No repeated saved insight patterns were found across matched contexts.
            </p>
        """
    else:
        html += """
            <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Pattern</th>
                        <th>Contexts</th>
                        <th>Confidence</th>
                        <th>Insight Types</th>
                    </tr>
                </thead>
                <tbody>
        """

        for pattern in repeated_patterns:
            insight_types = ", ".join(pattern.get("insight_types") or [])
            html += f"""
                    <tr>
                        <td>{e(_display(pattern.get("pattern")))}</td>
                        <td>{e(pattern.get("source_context_count") or 0)}</td>
                        <td>{e(_display(pattern.get("confidence")))}</td>
                        <td>{e(insight_types)}</td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
            </div>
        """

    html += """
        </div>

    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def render_historical_raw_get(user_id, base_template, inject_nav, dataset_id, context_id):
    from app.db.historical import get_historical_answers_by_dataset

    try:
        context_id = int(context_id)
        dataset_id = int(dataset_id)
    except (TypeError, ValueError):
        return {"redirect": "/historical"}

    if not _can_access_historical_context(
        user_id=user_id,
        context_id=context_id,
    ):
        return {"redirect": "/historical"}

    if not _dataset_belongs_to_context(
        dataset_id=dataset_id,
        context_id=context_id,
    ):
        return {"redirect": "/historical"}

    # -------------------------
    # Fetch data
    # -------------------------
    rows = get_historical_answers_by_dataset(dataset_id)

    if not rows:
        html = f"""
        <div class="results-section historical-page">
            {_render_historical_subnav(
                active_key="raw",
                context_id=context_id,
                dataset_id=dataset_id,
            )}

            <p>No data found.</p>
        </div>
        """
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
    <div class="results-section historical-page">
        {_render_historical_subnav(
            active_key="raw",
            context_id=context_id,
            dataset_id=dataset_id,
        )}

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

def handle_generate_section_names_post(*, user_id, data):

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

    if not _can_access_historical_context(
        user_id=user_id,
        context_id=context_id,
    ):
        return {"redirect": "/historical"}

    if not _dataset_belongs_to_context(
        dataset_id=dataset_id,
        context_id=context_id,
    ):
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

def handle_generate_section_summaries_post(*, user_id, data):

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

    if not _can_access_historical_context(
        user_id=user_id,
        context_id=context_id,
    ):
        return {"redirect": "/historical"}

    if not _dataset_belongs_to_context(
        dataset_id=dataset_id,
        context_id=context_id,
    ):
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

def handle_generate_insights_post(*, user_id, data):
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

    if not _can_access_historical_context(
        user_id=user_id,
        context_id=context_id,
    ):
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