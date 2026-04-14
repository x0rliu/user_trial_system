# handlers/user_selection.py

from pathlib import Path
from app.services.selection_service import (
    create_or_get_selection_session,
    get_current_pool,
    get_selection_results,
    get_current_participant_user_ids,
)
from app.services.selection_scoring_service import score_users
from app.db.external_scoring import get_external_scoring_config
from app.db.user_trial_lead import get_round_profile_criteria
from app.db.user_profiles import get_all_profiles
from app.utils.html_escape import escape_html as e

def render_user_selection_get(*, user_id, base_template, inject_nav, query_params):


    # -------------------------
    # INPUT
    # -------------------------
    round_id = int(query_params.get("round_id", [0])[0])

    from app.services.round_access import validate_round_access

    validated_round = validate_round_access(
        actor_user_id=user_id,
        round_id=round_id,
        required_role="ut_lead",
        allow_admin=True,
    )

    if not validated_round:
        return {"redirect": "/dashboard"}

    if not round_id:
        return {"redirect": "/dashboard"}

    external_scoring_config = get_external_scoring_config(round_id=round_id)
    criteria_rows = get_round_profile_criteria(round_id)

    # -------------------------
    # SESSION
    # -------------------------
    session = create_or_get_selection_session(
        validated_round=validated_round,
        user_id=user_id,
    )

    target = session["TargetUsers"]
    session_id = session["SessionID"]
    status = session.get("Status", "in_progress")

    requested_mode = (query_params.get("mode", [""])[0] or "").strip().lower()

    removed_user_ids_raw = (query_params.get("removed_user_ids", [""])[0] or "").strip()
    removed_user_ids = {
        uid.strip()
        for uid in removed_user_ids_raw.split(",")
        if uid.strip()
    }

    mode = "selection" if status in ("selection", "finalized") else "hard_gate_review"
    review_mode = requested_mode in ("selection", "manual", "edit")
    
    # -------------------------
    # POOL
    # -------------------------
    from app.services.selection_service import get_current_pool

    candidates = get_current_pool(session_id=session_id)

    # -------------------------
    # PROFILE (CANONICAL SOURCE)
    # -------------------------
    trial_profile = {}

    for row in criteria_rows:
        category = row["CategoryName"]
        operator = row["Operator"].lower()   # include / exclude
        value = row["LevelDescription"]
        profile_uid = row["ProfileUID"]

        if category not in trial_profile:
            trial_profile[category] = {
                "include": {},
                "exclude": {}
            }

        trial_profile[category][operator][profile_uid] = value

    # -------------------------
    # INITIAL CONTEXT
    # -------------------------
    context = {
        "eligible_pool_size": len(candidates),  # placeholder
        "target_users": target
    }

    # -------------------------
    # FIRST SCORING PASS
    # -------------------------
    scored_results = score_users(candidates, context, trial_profile)

    # -------------------------
    # STEP 2 — REAL ELIGIBLE POOL
    # -------------------------
    eligible_pool_size = len([
        u for u in scored_results if u.get("eligible")
    ])

    # -------------------------
    # UPDATE CONTEXT
    # -------------------------
    context["eligible_pool_size"] = eligible_pool_size

    # -------------------------
    # FINAL SCORING (WITH CORRECT CONTEXT)
    # -------------------------
    final_results = score_users(candidates, context, trial_profile)

    pre_filter_results = list(final_results)
    scored_results = pre_filter_results

    # -------------------------
    # MODE: FILTER DISPLAY
    # -------------------------
    if mode == "selection":
        scored_results = [
            r for r in pre_filter_results
            if r.get("eligible", True)
        ]

    # -------------------------
    # EXISTING PROVISIONAL SELECTION / CURRENT ROSTER
    # -------------------------
    selected_result_rows = get_selection_results(session_id=session_id)

    provisional_selected_user_ids = {
        row["UserID"]
        for row in selected_result_rows
        if row.get("ResultType") == "selected"
    }

    current_participant_user_ids = get_current_participant_user_ids(round_id=round_id)

    if requested_mode == "manual":
        selected_user_ids = set()

    elif requested_mode == "edit":
        # In edit mode, prefer a saved draft if one exists.
        # Otherwise start from the current participant roster.
        selected_user_ids = set(
            provisional_selected_user_ids or current_participant_user_ids
        )

    else:
        # Normal selection mode
        selected_user_ids = set(
            provisional_selected_user_ids or current_participant_user_ids
        )

    # -------------------------
    # HARD GATE SUMMARY (TEMP PARSE)
    # -------------------------
    hard_gate_counts = {
        "region": 0,
        "concurrent": 0,
        "blacklist": 0
    }

    for r in pre_filter_results:
        gates = r.get("hard_gate_results", {})

        if not gates.get("region", {}).get("passed", True):
            hard_gate_counts["region"] += 1

        if not gates.get("concurrent", {}).get("passed", True):
            hard_gate_counts["concurrent"] += 1

        if not gates.get("blacklist", {}).get("passed", True):
            hard_gate_counts["blacklist"] += 1

    # -------------------------
    # MAP TO TABLE STRUCTURE
    # STEP 2: add eligibility + reason
    # TEMP DEFAULTS until hard-gate visibility is wired
    # -------------------------

    from app.services.selection_scoring_service import PROFILE_WEIGHT

    def _build_profile_tooltip(profile_breakdown: dict) -> str:
        if not profile_breakdown:
            return "No profile breakdown available."

        def _label_map(value):
            if isinstance(value, dict):
                return value
            return {}

        lines = []
        category_count = max(len(profile_breakdown), 1)

        for category_id, item in sorted(profile_breakdown.items()):
            rules = item.get("rules", {}) or {}
            category_name = rules.get("category_name") or f"Category {category_id}"

            result = item.get("result", "—")
            user_values = set(item.get("user_values", []) or [])

            include_map = _label_map(rules.get("include"))
            exclude_map = _label_map(rules.get("exclude"))

            base_score = float(item.get("base_score", 0.0) or 0.0)
            final_category_score = float(item.get("final_category_score", 0.0) or 0.0)

            displayed_points = (final_category_score / category_count) * PROFILE_WEIGHT

            matched_label = None

            if result == "include_match":
                for uid in user_values:
                    if uid in include_map:
                        matched_label = include_map[uid]
                        break

                if matched_label:
                    result_text = f"{matched_label} match"
                else:
                    result_text = "Wanted match"

            elif result == "exclude_match":
                for uid in user_values:
                    if uid in exclude_map:
                        matched_label = exclude_map[uid]
                        break

                if matched_label:
                    result_text = f"{matched_label} non-match"
                else:
                    result_text = "Explicit unwanted match"

            elif result == "unknown":
                result_text = "No data"

            elif result == "explicit_no_match":
                result_text = "Explicit data, no wanted match"

            else:
                result_text = result

            point_word = "point" if abs(base_score - 1.0) < 0.0001 else "points"

            line = (
                f"{category_name}: {result_text}"
                f" | {base_score:.1f} {point_word}"
                f" | +{displayed_points:.1f} displayed"
            )

            lines.append(line)

        return "\n".join(lines)

    scored = []

    for r in scored_results:
        gates = r.get("hard_gate_results", {})

        gate_lines = []

        exclusion_reason = r.get("exclusion_reason") or ""

        # -------------------------
        # REGION
        # -------------------------
        region_gate = gates.get("region", {})
        if not region_gate.get("passed", True):
            # Extract country code (temporary parsing)
            country = ""
            if "(" in exclusion_reason and ")" in exclusion_reason:
                country = exclusion_reason.split("(")[-1].replace(")", "")

            if country:
                gate_lines.append(f"Region ({country})")
            else:
                gate_lines.append("Region")

        # -------------------------
        # CONCURRENT
        # -------------------------
        concurrent_gate = gates.get("concurrent", {})
        if not concurrent_gate.get("passed", True):
            gate_lines.append("Concurrent")

        # -------------------------
        # BLACKLIST
        # -------------------------
        blacklist_gate = gates.get("blacklist", {})
        if not blacklist_gate.get("passed", True):
            gate_lines.append("Blacklist")

        # -------------------------
        # FINAL FORMAT
        # -------------------------
        if gate_lines:
            reason_text = ", ".join(gate_lines)
        else:
            reason_text = "—"

        profile_breakdown = (
            r.get("breakdown", {}).get("profile", {})
            if r.get("eligible", True)
            else {}
        )

        scored.append({
            "user_id": r["user_id"],
            "display_name": r.get("display_name"),

            "eligible": "Yes" if r.get("eligible", True) else "No",
            "reason": reason_text,

            "quality": r["quality_score"] if r.get("eligible", True) else "—",
            "profile": r["profile_score_scaled"] if r.get("eligible", True) else "—",
            "profile_tooltip": _build_profile_tooltip(profile_breakdown),
            "final": r["final_score"] if r.get("eligible", True) else "—",

            "motivation": r.get("motivation") or ""
        })

    top = scored

    suggested_user_ids = set()

    # In edit mode, if there is no saved draft yet, auto-suggest replacements
    if requested_mode == "edit" and not provisional_selected_user_ids:
        kept_user_ids = set(current_participant_user_ids) - set(removed_user_ids)
        vacancy_count = max(target - len(kept_user_ids), 0)

        for u in top:
            if vacancy_count <= 0:
                break

            uid = u["user_id"]

            if u["eligible"] != "Yes":
                continue

            if uid in kept_user_ids:
                continue

            if uid in removed_user_ids:
                continue

            suggested_user_ids.add(uid)
            vacancy_count -= 1

        selected_user_ids = kept_user_ids | suggested_user_ids

    # -------------------------
    # BUILD ROWS
    # -------------------------
    rows = ""
    for u in top:
        uid = u["user_id"]
        reason_text = u["reason"] or "—"
        reason_class = "reason-empty" if reason_text == "—" else "reason-filled"

        is_removed = uid in removed_user_ids
        is_suggested = uid in suggested_user_ids
        is_selected = uid in selected_user_ids

        row_classes = []
        badges = []

        if is_removed:
            row_classes.append("selection-row-removed")
            badges.append('<span class="selection-badge removed">Removed</span>')

        elif is_suggested:
            row_classes.append("selection-row-suggested")
            badges.append('<span class="selection-badge suggested">Suggested</span>')

        elif requested_mode == "edit" and uid in current_participant_user_ids:
            badges.append('<span class="selection-badge current">Current</span>')

        checked_attr = "checked" if is_selected else ""
        disabled_attr = "disabled" if is_removed else ""

        select_cell = ""
        if review_mode:
            select_cell = f"""
            <td class="select-cell">
                <input
                    class="selection-checkbox"
                    type="checkbox"
                    name="selected_user_ids"
                    value="{e(uid)}"
                    {checked_attr}
                    {disabled_attr}
                >
            </td>
            """

        badge_html = ""
        if badges:
            badge_html = f'<div class="selection-badge-group">{" ".join(badges)}</div>'

        row_class_attr = f' class="{" ".join(row_classes)}"' if row_classes else ""

        rows += f"""
        <tr{row_class_attr}>
            {select_cell}
            <td class="user-cell">
                <div class="user-name">{e(u.get("display_name") or uid)}</div>
                {badge_html}
            </td>

            <td class="eligible-cell {'eligible-yes' if u['eligible'] == 'Yes' else 'eligible-no'}">
                {e(u["eligible"])}
            </td>

            <td class="reason-cell {reason_class}">
                {e(reason_text)}
            </td>
            <td class="score-cell" title="{e(u.get('quality_tooltip') or '')}">{e(u["quality"])}</td>
            <td class="score-cell" title="{e(u.get('profile_tooltip') or '')}">{e(u["profile"])}</td>
            <td class="score-cell final" title="{e(u.get('final_tooltip') or '')}">{e(u["final"])}</td>
            <td class="motivation-cell">
                <div class="motivation-row">
                    <div class="motivation-preview">
                        {e(u.get("motivation") or "")}
                    </div>

                    <div class="motivation-full" style="display:none;">
                        {e(u.get("motivation") or "")}
                    </div>

                    <a href="#"
                       class="motivation-toggle"
                       onclick="toggleMotivation(this); return false;">View</a>
                </div>
            </td>
        </tr>
        """

    # -------------------------
    # LOAD PAGE TEMPLATE
    # -------------------------
    page_template = Path(
        "app/templates/user_selection.html"
    ).read_text(encoding="utf-8")

    if mode == "selection":
        selection_actions = f"""
        <div class="selection-actions" style="margin: 16px 0 20px 0;">
            <form method="post" action="/trials/selection" style="display:flex; gap:10px; align-items:center;">
                <input type="hidden" name="session_id" value="{e(session_id)}">
                <input type="hidden" name="round_id" value="{e(round_id)}">

                <select name="action" required>
                    <option value="select_top_users">Select top users</option>
                    <option value="manual_selection">Manual selection</option>
                </select>

                <button type="submit">Execute</button>
            </form>
        </div>
        """
    else:
        selection_actions = ""

    if review_mode:
        selection_column_header = '<th class="col-select">Select</th>'
        removed_hidden = ",".join(sorted(removed_user_ids))

        review_form_open = f"""
        <form method="post" action="/trials/selection">
            <input type="hidden" name="session_id" value="{e(session_id)}">
            <input type="hidden" name="round_id" value="{e(round_id)}">
            <input type="hidden" name="removed_user_ids" value="{e(removed_hidden)}">
        """
        review_footer = """
        <div class="selection-review-actions" style="margin-top:20px; display:flex; gap:12px; align-items:center;">
            <button type="submit" name="action" value="save_manual_selection">
                Save Selection
            </button>

            <button type="submit" name="action" value="finalize_selection">
                Finalize Selection
            </button>
        </div>
        """
        review_form_close = "</form>"
    else:
        selection_column_header = ""
        review_form_open = ""
        review_footer = ""
        review_form_close = ""

    page = page_template
    page = page.replace("{{ session_id }}", e(session_id))
    page = page.replace("{{ initial_pool_size }}", str(len(candidates)))
    page = page.replace("{{ eligible_pool_size }}", str(eligible_pool_size))
    page = page.replace("{{ target_users }}", e(target))
    page = page.replace("{{ selected_count }}", str(len(selected_user_ids)))
    page = page.replace("{{ selection_actions }}", selection_actions)
    page = page.replace("{{ selection_column_header }}", selection_column_header)
    page = page.replace("{{ review_form_open }}", review_form_open)
    page = page.replace("{{ review_footer }}", review_footer)
    page = page.replace("{{ review_form_close }}", review_form_close)
    page = page.replace("{{ rows }}", rows)

    # -------------------------
    # LOAD 3-RAIL LAYOUT
    # -------------------------
    layout_template = Path(
        "app/templates/layouts/three_rail.html"
    ).read_text(encoding="utf-8")

    # -------------------------
    # TEMP LEFT / RIGHT RAIL
    # -------------------------
    if mode == "hard_gate_review":
        left_rail = f"""
        <div class="rail-section">
            <h3>Hard Gate Review</h3>

            <div>
                <strong>Region</strong><br>
                Excluded: {e(hard_gate_counts["region"])}
            </div>

            <div style="margin-top:10px;">
                <strong>Concurrent</strong><br>
                Excluded: {e(hard_gate_counts["concurrent"])}
            </div>

            <div style="margin-top:10px;">
                <strong>Blacklist</strong><br>
                Excluded: {e(hard_gate_counts["blacklist"])}
            </div>

            <div style="margin-top:20px;">
                <a href="/trials/selection/confirm?session_id={e(session_id)}&round_id={e(round_id)}">
                    Confirm Hard Gate Review
                </a>
            </div>
        </div>
        """
    else:
        profile_html = ""

        from app.db.user_profiles import get_all_profiles

        profiles = get_all_profiles()

        profile_option_html = ""

        for p in profiles:
            profile_option_html += f'''
            <option value="{e(p["ProfileUID"])}">
                {e(p["CategoryName"])} - {e(p["LevelDescription"])}
            </option>
            '''

        include_rows = []
        exclude_rows = []

        for row in criteria_rows:
            category_name = row["CategoryName"]
            level_description = row["LevelDescription"]
            profile_uid = row["ProfileUID"]
            operator = (row["Operator"] or "").upper()

            line_html = f"""
            <div style="margin-bottom:8px; display:flex; align-items:center; justify-content:space-between; gap:8px;">
                <span>&gt; {e(category_name)} - {e(level_description)}</span>
                <button type="submit"
                        name="remove_profile_uid"
                        value="{e(profile_uid)}"
                        style="padding:2px 8px;">
                    Remove
                </button>
            </div>
            """

            if operator == "INCLUDE":
                include_rows.append(line_html)
            elif operator == "EXCLUDE":
                exclude_rows.append(line_html)

        profile_html += """
        <div style="margin-bottom:14px;">
            <div style="font-weight:700; margin-bottom:8px;">Include</div>
        """

        if include_rows:
            profile_html += "".join(include_rows)
        else:
            profile_html += '<div class="muted small" style="margin-bottom:8px;">None</div>'

        profile_html += """
        </div>

        <div style="margin-bottom:14px;">
            <div style="font-weight:700; margin-bottom:8px;">Exclude</div>
        """

        if exclude_rows:
            profile_html += "".join(exclude_rows)
        else:
            profile_html += '<div class="muted small" style="margin-bottom:8px;">None</div>'

        profile_html += """
        </div>
        """

        profile_html += f"""
        <div style="margin-top:16px; padding-top:12px; border-top:1px solid #ddd;">
            <div style="font-weight:700; margin-bottom:8px;">Add</div>

            <div style="display:flex; flex-direction:column; gap:8px;">
                <select name="new_profile_uid">
                    <option value="">Select Profile</option>
                    {profile_option_html}
                </select>

                <select name="new_profile_operator">
                    <option value="INCLUDE">Include</option>
                    <option value="EXCLUDE">Exclude</option>
                </select>

                <button type="submit">
                    Save
                </button>
            </div>
        </div>
        """

        external_scoring_html = ""

        if external_scoring_config:

            external_scoring_html += """
            <div class="rail-section" style="margin-top:20px;">
                <h3>External Scoring</h3>
            """

            for q in external_scoring_config:

                external_scoring_html += f"""
                <div style="margin-bottom:14px;">

                    <div style="font-weight:600; margin-bottom:4px;">
                        {e(q["question_text"])}
                    </div>

                    <div class="muted small" style="margin-bottom:6px;">
                        Weight:
                        <input type="number" step="0.1"
                            name="weight_{e(q["question_config_id"])}"
                            value="{e(q["weight"])}"
                            style="width:60px;">
                    </div>
                """

                for a in q["answers"]:
                    external_scoring_html += f"""
                    <div class="muted small">
                        - {e(a["value"])}:
                        <input type="number" step="0.1"
                            name="score_{e(a["answer_config_id"])}"
                            value="{e(a["score"])}"
                            style="width:60px;">
                    </div>
                    """

                external_scoring_html += "</div>"

            external_scoring_html += "</div>"

        left_rail = f"""
        <form method="POST" action="/trials/selection">

            <input type="hidden" name="session_id" value="{e(session_id)}">
            <input type="hidden" name="round_id" value="{e(round_id)}">
            <input type="hidden" name="action" value="update_selection_model">

            <div class="rail-section">
                <h3>Profile Controls</h3>
                {profile_html}
            </div>

            {external_scoring_html}

            <div style="margin-top:15px;">
                <button type="submit">Apply Changes</button>
            </div>

        </form>
        """

    initial_pool = len(candidates)
    eligible_count = len([
        r for r in pre_filter_results if r.get("eligible", True)
    ])

    right_rail = f"""
    <div class="rail-section">
        <h3>Hard Gate Impact</h3>

        <div>
            <strong>Initial Pool:</strong> {e(initial_pool)}<br>
            <strong>After Hard Gates:</strong> {e(eligible_pool_size)}
        </div>

        <div style="margin-top:10px;">
            <strong>Breakdown:</strong><br>
            Region: -{e(hard_gate_counts["region"])}<br>
            Concurrent: -{e(hard_gate_counts["concurrent"])}<br>
            Blacklist: -{e(hard_gate_counts["blacklist"])}
        </div>
    </div>
    """

    # -------------------------
    # BUILD LAYOUT
    # -------------------------
    layout = layout_template
    layout = layout.replace("{{ LEFT_RAIL }}", left_rail)
    layout = layout.replace("{{ MAIN_CONTENT }}", page)
    layout = layout.replace("{{ RIGHT_RAIL }}", right_rail)

    # -------------------------
    # INJECT INTO BASE
    # -------------------------
    html = base_template.replace("__BODY_CLASS__", "ut-lead")
    html = html.replace("{{ body }}", layout)

    html = inject_nav(html, user_id)

    return {
        "html": html
    }

def handle_user_selection_confirm_get(*, user_id, query_params):
    session_id = int(query_params.get("session_id", [0])[0])
    round_id = int(query_params.get("round_id", [0])[0])

    if not session_id or not round_id:
        return {"redirect": "/dashboard"}

    from app.services.selection_auth import validate_selection_session_access

    selection_session = validate_selection_session_access(
        actor_user_id=user_id,
        session_id=session_id,
        round_id=round_id,
    )

    if not selection_session:
        return {"redirect": "/dashboard"}

    from app.services.selection_service import update_selection_session

    update_selection_session(
        validated_session=selection_session,
        updates={
            "Status": "selection"
        }
    )

    return {
        "redirect": f"/trials/selection?round_id={round_id}"
    }


def handle_user_selection_post(*, user_id, data: dict):
    action = data.get("action") or "update_selection_model"
    session_id_raw = data.get("session_id")
    round_id_raw = data.get("round_id")

    if isinstance(session_id_raw, list):
        session_id_raw = session_id_raw[0]

    if isinstance(round_id_raw, list):
        round_id_raw = round_id_raw[0]

    try:
        session_id = int(session_id_raw or 0)
    except ValueError:
        session_id = 0

    try:
        round_id = int(round_id_raw or 0)
    except ValueError:
        round_id = 0

    if not session_id or not round_id:
        return {"redirect": "/dashboard"}

    from app.services.selection_auth import validate_selection_session_access
    from app.services.round_object_binding import validate_round_object_binding

    selection_session = validate_selection_session_access(
        actor_user_id=user_id,
        session_id=session_id,
        round_id=round_id,
    )

    if not selection_session:
        return {"redirect": "/dashboard"}

    def _normalize_selected_ids(value):
        if value is None:
            return []
        if isinstance(value, list):
            return [v for v in value if v]
        return [value] if value else []

    if action == "update_selection_model":

        from app.db.user_trial_lead import (
            add_round_profile_criteria,
            remove_round_profile_criteria,
        )
        from app.db.external_scoring import update_answer_score, update_question_weight

        # -------------------------
        # REMOVE PROFILE
        # -------------------------
        remove_profile_uid = data.get("remove_profile_uid")

        if isinstance(remove_profile_uid, list):
            remove_profile_uid = remove_profile_uid[0]

        if remove_profile_uid:
            remove_round_profile_criteria(
                round_id=int(round_id),
                profile_uid=remove_profile_uid,
            )

        # -------------------------
        # ADD PROFILE
        # -------------------------
        new_profile_uid = data.get("new_profile_uid")
        new_operator = data.get("new_profile_operator")

        if isinstance(new_profile_uid, list):
            new_profile_uid = new_profile_uid[0]

        if isinstance(new_operator, list):
            new_operator = new_operator[0]

        if new_operator:
            new_operator = new_operator.upper()

        if new_profile_uid and new_operator:
            add_round_profile_criteria(
                round_id=int(round_id),
                profile_uid=new_profile_uid,
                operator=new_operator,
            )

        # -------------------------
        # EXTERNAL SCORING (existing logic)
        # -------------------------
        for key, value in data.items():

            if key.startswith("score_"):
                answer_id = key.replace("score_", "")
                try:
                    if not validate_round_object_binding(
                        round_id=round_id,
                        answer_id=int(answer_id),
                    ):
                        continue

                    update_answer_score(selection_session, int(answer_id), float(value))
                except:
                    pass

            if key.startswith("weight_"):
                question_id = key.replace("weight_", "")
                try:
                    if not validate_round_object_binding(
                        round_id=round_id,
                        question_id=int(question_id),
                    ):
                        continue

                    update_question_weight(selection_session, int(question_id), float(value))
                except:
                    pass

        return {
            "redirect": f"/trials/selection?round_id={round_id}"
        }


    if action == "select_top_users":
        from app.services.selection_service import select_top_users

        select_top_users(validated_session=selection_session)

        return {
            "redirect": f"/trials/selection?round_id={round_id}&mode=selection"
        }

    if action == "manual_selection":
        from app.services.selection_service import clear_selection_results

        clear_selection_results(validated_session=selection_session)

        return {
            "redirect": f"/trials/selection?round_id={round_id}&mode=manual"
        }

    if action == "save_manual_selection":
        from app.services.selection_service import replace_selected_users

        removed_user_ids = (data.get("removed_user_ids") or "").strip()

        selected_user_ids = _normalize_selected_ids(data.get("selected_user_ids"))
        replace_selected_users(
            validated_session=selection_session,
            user_ids=selected_user_ids,
        )

        removed_query = f"&removed_user_ids={removed_user_ids}" if removed_user_ids else ""
        redirect_mode = "edit" if removed_user_ids else "selection"

        return {
            "redirect": f"/trials/selection?round_id={round_id}&mode={redirect_mode}&saved=1{removed_query}"
        }

    if action == "finalize_selection":
        from app.services.selection_service import replace_selected_users, finalize_selection

        selected_user_ids = _normalize_selected_ids(data.get("selected_user_ids"))

        replace_selected_users(
            validated_session=selection_session,
            user_ids=selected_user_ids,
        )

        finalize_selection(validated_session=selection_session)

        return {
            "redirect": f"/ut-lead/project?round_id={round_id}&selection_finalized=1"
        }

    return {"redirect": f"/trials/selection?round_id={round_id}"}