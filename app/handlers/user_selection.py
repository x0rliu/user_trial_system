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

    # -------------------------
    # POOL
    # -------------------------
    from app.services.selection_service import get_current_pool

    candidates = get_current_pool(session_id=session_id)

    context = {
        "eligible_pool_size": len(candidates),
        "target_users": target
    }

    # -------------------------
    # PROFILE (TEMP)
    # -------------------------
    trial_profile = {
        "type": "internal",
        "criteria": [
            {"field": "CountryCode", "values": ["US"]}
        ]
    }

    # -------------------------
    # SCORING
    # -------------------------
    scored_results = score_users(candidates, context, trial_profile)

    # -------------------------
    # MAP TO TABLE STRUCTURE
    # STEP 2: add eligibility + reason
    # TEMP DEFAULTS until hard-gate visibility is wired
    # -------------------------
    scored = []

    for r in scored_results:
        scored.append({
            "user_id": r["user_id"],
            "display_name": r.get("display_name"),

            "eligible": "Yes" if r.get("eligible", True) else "No",
            "reason": r.get("exclusion_reason") or "—",

            "quality": r["quality_score"] if r.get("eligible", True) else "—",
            "profile": r["profile_score_scaled"] if r.get("eligible", True) else "—",
            "final": r["final_score"] if r.get("eligible", True) else "—"
        })

    top = scored[:target]

    # -------------------------
    # BUILD ROWS
    # -------------------------
    rows = ""
    for u in top:
        rows += f"""
        <tr>
            <td>{u.get("display_name") or u["user_id"]}</td>
            <td>{u["eligible"]}</td>
            <td>{u["reason"]}</td>
            <td>{u["quality"]}</td>
            <td>{u["profile"]}</td>
            <td>{u["final"]}</td>
        </tr>
        """

    # -------------------------
    # LOAD PAGE TEMPLATE
    # -------------------------
    page_template = Path(
        "app/templates/user_selection.html"
    ).read_text(encoding="utf-8")

    # -------------------------
    # INJECT VALUES
    # -------------------------
    page = page_template
    page = page.replace("{{ session_id }}", str(session_id))
    page = page.replace("{{ pool_size }}", str(len(candidates)))
    page = page.replace("{{ rows }}", rows)

    # -------------------------
    # INJECT INTO BASE
    # -------------------------
    html = base_template.replace("__BODY_CLASS__", "ut-lead")
    html = html.replace("{{ body }}", page)

    html = inject_nav(html, user_id)

    return {
        "html": html
    }