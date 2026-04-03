# handlers/user_selection.py

def render_user_selection_get(*, user_id, base_template, inject_nav, query_params):
    from pathlib import Path

    from app.services.selection_service import (
        create_or_get_selection_session,
        get_current_pool,
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
        target_users=45  # TEMP
    )

    target = session["TargetUsers"]
    session_id = session["SessionID"]
    status = session.get("Status", "in_progress")

    mode = "selection" if status == "selection" else "hard_gate_review"
    
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

        scored.append({
            "user_id": r["user_id"],
            "display_name": r.get("display_name"),

            "eligible": "Yes" if r.get("eligible", True) else "No",
            "reason": reason_text,

            "quality": r["quality_score"] if r.get("eligible", True) else "—",
            "profile": r["profile_score_scaled"] if r.get("eligible", True) else "—",
            "final": r["final_score"] if r.get("eligible", True) else "—",

            # 🔥 THIS WAS MISSING
            "motivation": r.get("motivation") or ""
        })

    top = scored

    # -------------------------
    # BUILD ROWS
    # -------------------------
    rows = ""
    for u in top:
        rows += f"""
        <tr>
            <td class="user-cell">
                <div class="user-name">{u.get("display_name") or u["user_id"]}</div>
            </td>

            <td class="eligible-cell {'eligible-yes' if u['eligible'] == 'Yes' else 'eligible-no'}">
                {u["eligible"]}
            </td>

            <td class="reason-cell">
                {u["reason"]}
            </td>
            <td class="score-cell">{u["quality"]}</td>
            <td class="score-cell">{u["profile"]}</td>
            <td class="score-cell final">{u["final"]}</td>
            <td>
                <div class="motivation-preview">
                    {(u.get("motivation") or "")[:60]}{"..." if len(u.get("motivation") or "") > 60 else ""}
                </div>
                <div class="motivation-full" style="display:none;">
                    {u.get("motivation") or ""}
                </div>
                <a href="#" onclick="toggleMotivation(this); return false;">View</a>
            </td>
        </tr>
        """

    # -------------------------
    # LOAD PAGE TEMPLATE
    # -------------------------
    page_template = Path(
        "app/templates/user_selection.html"
    ).read_text(encoding="utf-8")

    page = page_template
    page = page.replace("{{ session_id }}", str(session_id))
    page = page.replace("{{ initial_pool_size }}", str(len(candidates)))
    page = page.replace("{{ eligible_pool_size }}", str(eligible_pool_size))
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
        left_rail = """
        <div class="rail-section">
            <h3>Profile Controls</h3>
            <p>Profile criteria will appear here.</p>
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