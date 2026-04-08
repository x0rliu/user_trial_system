# handlers/user_selection.py

def render_user_selection_get(*, user_id, base_template, inject_nav, query_params):
    from pathlib import Path

    from app.services.selection_service import (
        create_or_get_selection_session,
        get_current_pool,
        get_selection_results,
        get_current_participant_user_ids,
    )
    from app.services.selection_scoring_service import score_users

    # -------------------------
    # INPUT
    # -------------------------
    round_id = int(query_params.get("round_id", [0])[0])

    if not round_id:
        return {"redirect": "/trials"}

    # -------------------------
    # SESSION
    # -------------------------
    session = create_or_get_selection_session(
        round_id=round_id,
        user_id=user_id,
        target_users=None
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
    # PROFILE
    # -------------------------
    from app.services.selection_profile_service import get_effective_profile_criteria

    trial_profile = get_effective_profile_criteria(
        session_id=session_id,
        round_id=round_id
    )

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
    import html

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
                    value="{uid}"
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
                <div class="user-name">{u.get("display_name") or uid}</div>
                {badge_html}
            </td>

            <td class="eligible-cell {'eligible-yes' if u['eligible'] == 'Yes' else 'eligible-no'}">
                {u["eligible"]}
            </td>

            <td class="reason-cell {reason_class}">
                {reason_text}
            </td>
            <td class="score-cell" title="{html.escape(u.get('quality_tooltip') or '', quote=True)}">{u["quality"]}</td>
            <td class="score-cell" title="{html.escape(u.get('profile_tooltip') or '', quote=True)}">{u["profile"]}</td>
            <td class="score-cell final" title="{html.escape(u.get('final_tooltip') or '', quote=True)}">{u["final"]}</td>
            <td class="motivation-cell">
                <div class="motivation-row">
                    <div class="motivation-preview">
                        {u.get("motivation") or ""}
                    </div>

                    <div class="motivation-full" style="display:none;">
                        {u.get("motivation") or ""}
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
                <input type="hidden" name="session_id" value="{session_id}">
                <input type="hidden" name="round_id" value="{round_id}">

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
            <input type="hidden" name="session_id" value="{session_id}">
            <input type="hidden" name="round_id" value="{round_id}">
            <input type="hidden" name="removed_user_ids" value="{removed_hidden}">
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
    page = page.replace("{{ session_id }}", str(session_id))
    page = page.replace("{{ initial_pool_size }}", str(len(candidates)))
    page = page.replace("{{ eligible_pool_size }}", str(eligible_pool_size))
    page = page.replace("{{ target_users }}", str(target))
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
                Excluded: {hard_gate_counts["region"]}
            </div>

            <div style="margin-top:10px;">
                <strong>Concurrent</strong><br>
                Excluded: {hard_gate_counts["concurrent"]}
            </div>

            <div style="margin-top:10px;">
                <strong>Blacklist</strong><br>
                Excluded: {hard_gate_counts["blacklist"]}
            </div>

            <div style="margin-top:20px;">
                <a href="/trials/selection/confirm?session_id={session_id}&round_id={round_id}">
                    Confirm Hard Gate Review
                </a>
            </div>
        </div>
        """
    else:
        profile_html = ""

        if trial_profile:
            for category_id, config in sorted(trial_profile.items()):
                category_name = config.get("category_name") or f"Category {category_id}"

                include_items = sorted(config.get("include", {}).values())
                exclude_items = sorted(config.get("exclude", {}).values())

                boost_items = sorted(
                    config.get("boost", {}).values(),
                    key=lambda x: x["label"]
                )

                deprioritize_items = sorted(
                    config.get("deprioritize", {}).values(),
                    key=lambda x: x["label"]
                )

                profile_html += f"""
                <div class="profile-criteria-block" style="margin-top:14px;">
                    <div style="font-weight:600; margin-bottom:6px;">
                        {category_name}
                    </div>
                """

                if include_items:
                    include_html = "<br>".join(include_items)
                    profile_html += f"""
                    <div style="margin-bottom:8px;">
                        <strong>Include</strong><br>
                        {include_html}
                    </div>
                    """

                if exclude_items:
                    exclude_html = "<br>".join(exclude_items)
                    profile_html += f"""
                    <div style="margin-bottom:8px;">
                        <strong>Exclude</strong><br>
                        {exclude_html}
                    </div>
                    """

                if boost_items:
                    boost_html = "<br>".join(
                        [f"{item['label']} ({item['weight']})" for item in boost_items]
                    )
                    profile_html += f"""
                    <div style="margin-bottom:8px;">
                        <strong>Boost</strong><br>
                        {boost_html}
                    </div>
                    """

                if deprioritize_items:
                    deprioritize_html = "<br>".join(
                        [f"{item['label']} ({item['weight']})" for item in deprioritize_items]
                    )
                    profile_html += f"""
                    <div style="margin-bottom:8px;">
                        <strong>Deprioritize</strong><br>
                        {deprioritize_html}
                    </div>
                    """

                profile_html += "</div>"

        else:
            profile_html = "<p>No established profile criteria yet.</p>"

        left_rail = f"""
        <div class="rail-section">
            <h3>Profile Controls</h3>
            {profile_html}
        </div>
        """

    initial_pool = len(candidates)
    eligible_count = len([
        r for r in pre_filter_results if r.get("eligible", True)
    ])

    right_rail = f"""
    <div class="rail-section">
        <h3>Hard Gate Impact</h3>

        <div>
            <strong>Initial Pool:</strong> {initial_pool}<br>
            <strong>After Hard Gates:</strong> {eligible_pool_size}
        </div>

        <div style="margin-top:10px;">
            <strong>Breakdown:</strong><br>
            Region: -{hard_gate_counts["region"]}<br>
            Concurrent: -{hard_gate_counts["concurrent"]}<br>
            Blacklist: -{hard_gate_counts["blacklist"]}
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
        return {"redirect": "/trials"}

    from app.services.selection_service import update_selection_session

    update_selection_session(
        session_id=session_id,
        updates={
            "Status": "selection"
        }
    )

    return {
        "redirect": f"/trials/selection?round_id={round_id}"
    }


def handle_user_selection_post(*, user_id, data: dict):
    action = data.get("action")
    session_id_raw = data.get("session_id")
    round_id_raw = data.get("round_id")

    try:
        session_id = int(session_id_raw or 0)
    except ValueError:
        session_id = 0

    try:
        round_id = int(round_id_raw or 0)
    except ValueError:
        round_id = 0

    if not session_id or not round_id:
        return {"redirect": "/trials"}

    def _normalize_selected_ids(value):
        if value is None:
            return []
        if isinstance(value, list):
            return [v for v in value if v]
        return [value] if value else []

    if action == "select_top_users":
        from app.services.selection_service import select_top_users

        select_top_users(session_id=session_id)

        return {
            "redirect": f"/trials/selection?round_id={round_id}&mode=selection"
        }

    if action == "manual_selection":
        from app.services.selection_service import clear_selection_results

        clear_selection_results(session_id=session_id)

        return {
            "redirect": f"/trials/selection?round_id={round_id}&mode=manual"
        }

    if action == "save_manual_selection":
        from app.services.selection_service import replace_selected_users

        removed_user_ids = (data.get("removed_user_ids") or "").strip()

        selected_user_ids = _normalize_selected_ids(data.get("selected_user_ids"))
        replace_selected_users(
            session_id=session_id,
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
            session_id=session_id,
            user_ids=selected_user_ids,
        )

        finalize_selection(session_id=session_id)

        return {
            "redirect": f"/ut-lead/project?round_id={round_id}&selection_finalized=1"
        }

    return {"redirect": f"/trials/selection?round_id={round_id}"}